#!/usr/bin/env python3

import argparse
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path


DEFAULT_DB = (
    "/var/lib/plexmediaserver/Library/Application Support/"
    "Plex Media Server/Plug-in Support/Databases/"
    "com.plexapp.plugins.library.db"
)

DEFAULT_ROOT = "/mnt/data2/tv"


def normalize_title(value: str) -> str:
    """
    Normalize titles so harmless naming differences do not look suspicious.

    Examples:
        The_Wire              -> the wire
        Marvels_Daredevil     -> marvels daredevil
        The.Office            -> the office
        Shōgun                -> shogun
    """

    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))

    value = value.replace("_", " ")
    value = value.replace(".", " ")
    value = value.replace("-", " ")

    # Remove a trailing year in parentheses or bare form.
    value = re.sub(r"\s*\((?:19|20)\d{2}\)\s*$", "", value)
    value = re.sub(r"\s+(?:19|20)\d{2}\s*$", "", value)

    # Strip punctuation.
    value = re.sub(r"[^a-zA-Z0-9 ]+", "", value)

    # Normalize whitespace/case.
    value = re.sub(r"\s+", " ", value).strip().lower()

    return value


def extract_year(value: str):
    """
    Extract an apparent 4-digit year from a directory name.

    Examples:
        The_Shield_(2002) -> 2002
        Doctor_Who_2005   -> 2005
        The_Wire          -> None
    """

    years = re.findall(r"(?:19|20)\d{2}", value)

    if not years:
        return None

    return int(years[-1])


def similarity(a: str, b: str) -> float:
    """
    Simple token similarity.

    This intentionally avoids external Python dependencies.
    """

    a_tokens = set(normalize_title(a).split())
    b_tokens = set(normalize_title(b).split())

    if not a_tokens or not b_tokens:
        return 0.0

    intersection = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)

    return intersection / union


def get_top_level_folder(file_path: str, root: Path):
    try:
        relative = Path(file_path).relative_to(root)
    except ValueError:
        return None

    if len(relative.parts) < 2:
        return None

    return relative.parts[0]


def open_database(path: Path):
    if not path.exists():
        print(f"ERROR: Plex database not found:\n  {path}", file=sys.stderr)
        sys.exit(2)

    uri = f"file:{path}?mode=ro"

    try:
        return sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        print(f"ERROR: Could not open Plex database read-only: {exc}",
              file=sys.stderr)
        sys.exit(2)


def load_mappings(conn, root: Path):
    """
    Returns tuples:
        filesystem_folder
        plex_show_id
        plex_show_title
        plex_show_year
        file_path
    """

    root_string = str(root).rstrip("/") + "/%"

    query = """
        SELECT
            show.id,
            show.title,
            show.year,
            mp.file
        FROM media_parts AS mp
        JOIN media_items AS mi
            ON mp.media_item_id = mi.id
        JOIN metadata_items AS episode
            ON mi.metadata_item_id = episode.id
        JOIN metadata_items AS season
            ON episode.parent_id = season.id
        JOIN metadata_items AS show
            ON season.parent_id = show.id
        WHERE mp.file LIKE ?
        ORDER BY mp.file
    """

    rows = []

    for show_id, title, year, file_path in conn.execute(query, (root_string,)):
        folder = get_top_level_folder(file_path, root)

        if folder is None:
            continue

        rows.append(
            (
                folder,
                show_id,
                title or "",
                year,
                file_path,
            )
        )

    return rows


def print_issue(severity, kind, folder, details):
    print(f"[{severity:<6}] {kind}")
    print(f"         Folder: {folder}")

    for line in details:
        print(f"         {line}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Read-only audit of Plex TV filesystem-to-metadata mappings."
    )

    parser.add_argument(
        "--root",
        default=DEFAULT_ROOT,
        help=f"TV library filesystem root (default: {DEFAULT_ROOT})",
    )

    parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help="Path to Plex SQLite library database",
    )

    parser.add_argument(
        "--title-threshold",
        type=float,
        default=0.40,
        help=(
            "Minimum token similarity before a folder/title pair is flagged "
            "(default: 0.40)"
        ),
    )

    parser.add_argument(
        "--show-ok",
        action="store_true",
        help="Also display mappings that appear correct",
    )

    args = parser.parse_args()

    root = Path(args.root).resolve()
    db = Path(args.db)

    conn = open_database(db)

    try:
        mappings = load_mappings(conn, root)
    except sqlite3.Error as exc:
        print(f"ERROR while querying Plex database: {exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()

    if not mappings:
        print(f"No Plex media found beneath {root}")
        return 1

    by_folder = defaultdict(dict)
    by_show = defaultdict(set)

    for folder, show_id, title, year, file_path in mappings:
        by_folder[folder][show_id] = (title, year)
        by_show[(show_id, title, year)].add(folder)

    issues = 0
    print()
    print("Plex TV Library Audit")
    print("=====================")
    print(f"Root: {root}")
    print(f"Top-level folders represented in Plex: {len(by_folder)}")
    print()

    #
    # 1. One directory mapped to more than one Plex show.
    #
    for folder in sorted(by_folder):
        shows = by_folder[folder]

        if len(shows) > 1:
            issues += 1

            details = ["Mapped to multiple Plex shows:"]

            for show_id, (title, year) in sorted(
                shows.items(),
                key=lambda item: (item[1][0], item[1][1] or 0),
            ):
                details.append(
                    f"  Plex ID {show_id}: {title}"
                    + (f" ({year})" if year else "")
                )

            print_issue(
                "HIGH",
                "MULTIPLE PLEX SHOWS FOR ONE DIRECTORY",
                folder,
                details,
            )

    #
    # 2 & 3. Title and year comparisons.
    #
    for folder in sorted(by_folder):
        shows = by_folder[folder]

        # Don't make fuzzy-title judgments if the folder already has the
        # more serious multi-show problem.
        if len(shows) != 1:
            continue

        show_id, (title, plex_year) = next(iter(shows.items()))

        normalized_folder = normalize_title(folder)
        normalized_title = normalize_title(title)

        score = similarity(folder, title)

        folder_year = extract_year(folder)

        if normalized_folder != normalized_title and score < args.title_threshold:
            issues += 1

            print_issue(
                "MEDIUM",
                "POSSIBLE TITLE MISMATCH",
                folder,
                [
                    f"Plex: {title}"
                    + (f" ({plex_year})" if plex_year else ""),
                    f"Normalized folder: {normalized_folder}",
                    f"Normalized Plex:   {normalized_title}",
                    f"Similarity: {score:.2f}",
                ],
            )

        if (
            folder_year is not None
            and plex_year is not None
            and folder_year != plex_year
        ):
            issues += 1

            print_issue(
                "MEDIUM",
                "YEAR MISMATCH",
                folder,
                [
                    f"Directory year: {folder_year}",
                    f"Plex match: {title} ({plex_year})",
                ],
            )

        if args.show_ok:
            if (
                not (
                    normalized_folder != normalized_title
                    and score < args.title_threshold
                )
                and not (
                    folder_year is not None
                    and plex_year is not None
                    and folder_year != plex_year
                )
            ):
                print_issue(
                    "OK",
                    "MAPPING LOOKS REASONABLE",
                    folder,
                    [
                        f"Plex: {title}"
                        + (f" ({plex_year})" if plex_year else "")
                    ],
                )

    #
    # 4. One Plex show sourced from multiple top-level directories.
    #
    for (show_id, title, year), folders in sorted(
        by_show.items(),
        key=lambda item: item[0][1],
    ):
        if len(folders) <= 1:
            continue

        issues += 1

        print_issue(
            "MEDIUM",
            "PLEX SHOW USES MULTIPLE DIRECTORIES",
            ", ".join(sorted(folders)),
            [
                f"Plex ID {show_id}: {title}"
                + (f" ({year})" if year else "")
            ],
        )

    print("Summary")
    print("-------")

    if issues:
        print(f"{issues} potential issue(s) found.")
        print("No changes were made.")
        return 1

    print("No suspicious mappings found.")
    print("No changes were made.")
    return 0


if __name__ == "__main__":
    sys.exit(main())#!/usr/bin/env python3

import argparse
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path


DEFAULT_DB = (
    "/var/lib/plexmediaserver/Library/Application Support/"
    "Plex Media Server/Plug-in Support/Databases/"
    "com.plexapp.plugins.library.db"
)

DEFAULT_ROOT = "/mnt/data2/tv"


def normalize_title(value: str) -> str:
    """
    Normalize titles so harmless naming differences do not look suspicious.

    Examples:
        The_Wire              -> the wire
        Marvels_Daredevil     -> marvels daredevil
        The.Office            -> the office
        Shōgun                -> shogun
    """

    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))

    value = value.replace("_", " ")
    value = value.replace(".", " ")
    value = value.replace("-", " ")

    # Remove a trailing year in parentheses or bare form.
