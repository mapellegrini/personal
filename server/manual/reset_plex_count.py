#!/usr/bin/env python3
"""Reset Plex playback history and the authenticated user's watched state.

Plex can remain running. This script changes history via Plex's HTTP API,
not by editing Plex's SQLite database. Requires: pip install plexapi

Authentication: PLEX_TOKEN or ~/.config/plex/token (mode 0600).

Title examples:
    reset_plex_count.py 'Alien' 'Jaws'
    reset_plex_count.py 'Alien' --show-history

Path examples (match paths AS STORED IN PLEX, not the local shell's paths):
    reset_plex_count.py --delete-history-by-path '/a/b/c/d.mp3'
    reset_plex_count.py --delete-history-by-path '/a/b/c/'
    reset_plex_count.py --delete-history-by-path 'c/d.mp3' --dry-run

Paths ending in '/' match a folder and all descendants; other paths match
file paths by complete path or component-aligned suffix. Multiple criteria
are combined (union). File-path matching scans movie, episode and track
metadata in Plex libraries. A Plex item with multiple file versions shares
one ratingKey, so its watch state/history is changed for the entire item.
"""

import argparse
from collections import Counter
from dataclasses import dataclass, field
import os
from pathlib import Path
import posixpath
import re
import sys
from urllib.parse import urlsplit


@dataclass(frozen=True)
class PathPattern:
    original: str
    value: str
    directory: bool


@dataclass
class Target:
    section: str
    item: object
    paths: set[str] = field(default_factory=set)
    reasons: set[str] = field(default_factory=set)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description=("Delete playback history and reset watched state for Plex media "
                     "selected by movie title and/or stored file path. Plex stays running."),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            '  %(prog)s "Alien" "Jaws"\n'
            '  %(prog)s --delete-history-by-path "/a/b/c/d.mp3"\n'
            '  %(prog)s --delete-history-by-path "/a/b/c/" --dry-run\n'
            '  %(prog)s --delete-history-by-path "c/d.mp3" --show-history\n'
            "\nA trailing '/' selects a directory and its descendants.\n"
            "Without it, a path must match a file (full path or path suffix).\n"
            "Path queries are case-sensitive and compared to paths stored by Plex.\n"
            "History deletion applies to all accessible accounts by default;\n"
            "watched-state reset applies to the authenticated account only."
        ),
    )
    parser.add_argument("titles", nargs="*", metavar="TITLE",
                        help="Exact Plex MOVIE title(s); combine with path selection if desired")
    parser.add_argument("--delete-history-by-path", action="append", dest="paths",
                        metavar="PATH", default=[],
                        help="Select media by path or directory; may be provided more than once")
    parser.add_argument("--show-history", action="store_true",
                        help="Read-only: show playback history for matching media, then exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be changed; make no changes")
    parser.add_argument("--year", type=int,
                        help="Restrict movie-title matches to YEAR (doesn't restrict path matches)")
    parser.add_argument("--account-id", type=int,
                        help="Limit history listing/deletion to this Plex account ID")
    parser.add_argument("--url", default="http://127.0.0.1:32400",
                        help="Plex URL (default: http://127.0.0.1:32400)")
    parser.add_argument("--token-file", type=Path,
                        default=Path("~/.config/plex/token").expanduser(),
                        help="Read the authentication token from this file")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip confirmation before making irreversible changes")
    args = parser.parse_args(argv)
    if not args.titles and not args.paths:
        parser.error("provide at least one TITLE or --delete-history-by-path PATH")
    if args.year is not None and not args.titles:
        parser.error("--year requires a TITLE")
    if args.account_id is not None and args.account_id < 0:
        parser.error("--account-id must be non-negative")
    args.titles = list(dict.fromkeys(args.titles))
    args.paths = list(dict.fromkeys(args.paths))
    try:
        args.patterns = [compile_path_pattern(p) for p in args.paths]
    except ValueError as exc:
        parser.error(str(exc))
    return args


def compile_path_pattern(value):
    raw = value.replace("\\", "/").strip()
    if not raw or raw in ("/", ".", "..", "./", "../"):
        raise ValueError(f"Path query is empty or too broad: {value!r}")
    is_directory = raw.endswith("/")
    clean = posixpath.normpath(raw)
    if clean in ("/", ".", "..") or clean.startswith("../"):
        raise ValueError(f"Path query is too broad or escapes a directory: {value!r}")
    return PathPattern(original=value, value=clean, directory=is_directory)


def path_matches(filename, pattern):
    """Component-safe match against a file's Plex-stored path.

    '/a/b/c/' matches '/a/b/c/d.mp3' and '/mnt/a/b/c/d.mp3', but
    does not match '/a/b/c-other/d.mp3'. 'd.mp3' matches file basenames,
    while 'c/d.mp3' matches a component-aligned relative file-path suffix.
    """
    if not filename:
        return False
    filename = posixpath.normpath(str(filename).replace("\\", "/"))
    fragment = pattern.value.strip("/")
    if pattern.directory:
        return f"/{fragment}/" in f"/{filename.lstrip('/')}"
    return filename == pattern.value or filename.endswith("/" + fragment)


def read_token(path):
    token = os.environ.get("PLEX_TOKEN", "").strip()
    if token:
        return token
    path = path.expanduser()
    if not path.is_file():
        raise ValueError(f"Set PLEX_TOKEN or create the Plex token file: {path}")
    if path.stat().st_mode & 0o077:
        raise ValueError(f"Token file must be private: chmod 600 '{path}'")
    token = path.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError(f"Token file is empty: {path}")
    return token


def item_name(item):
    kind = getattr(item, "type", "media")
    label = getattr(item, "title", "<untitled>")
    if kind == "movie":
        label += f" ({getattr(item, 'year', None) or '-'})"
    elif kind == "episode":
        show = getattr(item, "grandparentTitle", "")
        if show:
            label = f"{show}: {label}"
    elif kind == "track":
        artist = getattr(item, "grandparentTitle", "")
        album = getattr(item, "parentTitle", "")
        context = " / ".join(v for v in (artist, album) if v)
        if context:
            label = f"{context} / {label}"
    return f"{kind}: {label} [ID {item.ratingKey}]"


def discover_targets(plex, titles, patterns, year):
    targets = {}
    missing = []
    sections = plex.library.sections()

    # Existing behavior: match movie titles exactly (all movie libraries).
    if titles:
        movie_sections = [s for s in sections if s.type == "movie"]
        for title in titles:
            found = False
            for section in movie_sections:
                for item in section.search(title=title):
                    if (item.title != title or
                            (year is not None and item.year != year)):
                        continue
                    found = True
                    key = str(item.ratingKey)
                    target = targets.setdefault(key, Target(section.title, item))
                    target.reasons.add(f"title {title!r}")
            if not found:
                missing.append(f"title {title!r}")

    # Path mode: a Plex title is NOT necessarily the filename. Scan actual
    # media part paths, including music tracks and individual TV episodes.
    if patterns:
        supported_types = {"movie": "movie", "show": "episode", "artist": "track"}
        matched_patterns = set()
        for section in sections:
            libtype = supported_types.get(section.type)
            if libtype is None:
                continue
            print(f"Scanning library {section.title!r} ({libtype} files)...", flush=True)
            for item in section.all(libtype=libtype):
                # locations is populated from Part.file, i.e., the Plex server's
                # media path, even when this script runs on another computer.
                paths = [p for p in item.locations if p]
                for filename in paths:
                    for pattern in patterns:
                        if not path_matches(filename, pattern):
                            continue
                        matched_patterns.add(pattern.original)
                        key = str(item.ratingKey)
                        target = targets.setdefault(key, Target(section.title, item))
                        target.paths.add(filename)
                        target.reasons.add(f"path {pattern.original!r}")
        for pattern in patterns:
            if pattern.original not in matched_patterns:
                missing.append(f"path {pattern.original!r}")

    return list(targets.values()), missing


def history_for(plex, item, account_id):
    params = {"ratingKey": item.ratingKey}
    if account_id is not None:
        params["accountID"] = account_id
    history = list(plex.history(**params))
    for record in history:
        if str(record.ratingKey) != str(item.ratingKey):
            raise RuntimeError(f"Plex returned history for the wrong media ID: {item.ratingKey}")
        if account_id is not None and str(record.accountID) != str(account_id):
            raise RuntimeError("Plex returned history for an unexpected account")
    return history


def check_history_ids(histories):
    seen = set()
    for records in histories.values():
        for record in records:
            key = getattr(record, "historyKey", None)
            if not isinstance(key, str) or not re.fullmatch(
                r"/status/sessions/history/\d+", key
            ):
                raise RuntimeError(f"Invalid Plex history ID: {key!r}")
            if key in seen:
                raise RuntimeError(f"Duplicate Plex history ID: {key!r}")
            seen.add(key)


def reset_watched_state(item):
    item.reload()
    current_plays = getattr(item, "viewCount", None)
    current_offset = getattr(item, "viewOffset", None)
    last_viewed = getattr(item, "lastViewedAt", None)
    if current_plays in (0, None) and current_offset in (0, None) and last_viewed is None:
        print("  Watched state already clear")
        return False
    item.markUnplayed()
    item.reload()
    if (getattr(item, "viewCount", None) not in (0, None) or
            getattr(item, "viewOffset", None) not in (0, None) or
            getattr(item, "lastViewedAt", None) is not None):
        raise RuntimeError("Plex did not confirm that watched state was reset")
    print("  Watched state reset")
    return True


def main(argv=None):
    args = parse_args(argv)
    endpoint = urlsplit(args.url)
    if endpoint.scheme not in ("http", "https") or not endpoint.hostname:
        raise ValueError("--url must be a valid HTTP(S) URL")
    if endpoint.scheme == "http" and endpoint.hostname not in (
        "localhost", "127.0.0.1", "::1"
    ):
        raise ValueError("Use HTTPS for remote connections to protect your Plex token")

    try:
        from plexapi.server import PlexServer
    except ImportError:
        raise ValueError("Install PlexAPI first: python3 -m pip install plexapi") from None

    plex = PlexServer(args.url.rstrip("/"), read_token(args.token_file), timeout=15)
    print(f"Connected to: {plex.friendlyName}")
    targets, missing = discover_targets(plex, args.titles, args.patterns, args.year)
    for unmatched in missing:
        print(f"Not found: {unmatched}")
    if not targets:
        print("Nothing matched; no changes made.")
        return 1

    print(f"\nFound {len(targets)} distinct Plex media item(s):")
    for target in targets:
        item = target.item
        print(f"  {item_name(item)} | Library: {target.section} | "
              f"Plays: {getattr(item, 'viewCount', None) or 0} | "
              f"Resume: {getattr(item, 'viewOffset', None) or 0} ms")
        for matched_file in sorted(target.paths):
            print(f"    File: {matched_file}")
        if target.paths and len(item.locations) > len(target.paths):
            print("    NOTE: This Plex item has additional file versions; "
                  "reset/deletion affects the entire item.")

    # Pre-read history for EVERY target before changes so selection and counts
    # can be reviewed together. No history or watched state is modified yet.
    try:
        accounts = {str(account.id): account.name for account in plex.systemAccounts()}
    except Exception:
        accounts = {}
    histories = {}
    print("\nServer playback history:")
    for target in targets:
        item = target.item
        records = history_for(plex, item, args.account_id)
        histories[str(item.ratingKey)] = records
        print(f"  {item_name(item)}: {len(records)} event(s)")
        for account_id, count in sorted(Counter(str(r.accountID) for r in records).items()):
            print(f"    Account {account_id} ({accounts.get(account_id, 'unknown')}): {count}")
    check_history_ids(histories)
    print(f"Total: {sum(len(h) for h in histories.values())} event(s)")

    if args.show_history:
        print("Read-only (--show-history): no changes made.")
        return int(bool(missing))
    if args.dry_run:
        print("Dry run: no changes made.")
        return int(bool(missing))
    if missing:
        print("Aborted: at least one requested title/path didn't match. "
              "No changes made.", file=sys.stderr)
        return 1

    print("\nWARNING: This permanently deletes the listed playback-history events "
          "and resets watched state for the authenticated account.")
    print("History is removed across all accessible Plex accounts"
          if args.account_id is None
          else f"Only history from account {args.account_id} will be deleted")
    print("This does not clear Plex cloud-synced history or other users' watched states.")
    if not args.yes and input("Proceed? [y/N] ").strip().lower() != "y":
        print("Canceled; no changes made.")
        return 0

    resets = deletions = skipped = errors = 0
    for target in targets:
        item = target.item
        print(f"\nProcessing {item_name(item)}")
        try:
            # Best-effort active-session guard, rechecked for each item.
            if str(item.ratingKey) in {str(s.ratingKey) for s in plex.sessions()}:
                print("  SKIPPED: Currently playing")
                skipped += 1
                continue
            for record in histories[str(item.ratingKey)]:
                try:
                    record.delete()
                    deletions += 1
                except Exception as exc:
                    print(f"  ERROR deleting history {record.historyKey}: {exc}",
                          file=sys.stderr)
                    errors += 1
            remaining = history_for(plex, item, args.account_id)
            print(f"  Remaining history events: {len(remaining)}")
            if remaining:
                errors += 1
                print("  ERROR: History is not fully cleared", file=sys.stderr)
            if reset_watched_state(item):
                resets += 1
        except Exception as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            errors += 1

    print(f"\nFinished: {resets} watched-state resets, {deletions} history deletions, "
          f"{skipped} skipped, {errors} errors.")
    return int(bool(errors or skipped or missing))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyboardInterrupt) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"ERROR: Plex request failed: {exc}", file=sys.stderr)
        sys.exit(1)
