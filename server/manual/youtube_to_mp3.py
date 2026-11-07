#!/usr/bin/env python3
"""Download YouTube videos as '[Artist] Title.mp3' with ID3 metadata.

- Accept one or more URLs; each download succeeds or fails independently.
- yt-dlp and FFmpeg download and convert the best available audio.
- id3v2 writes the title, artist, and album tags.
- Mutagen writes the YouTube URL to the real ID3 COMM (comment) frame.
- Album detection checks YouTube metadata, the video description, then MusicBrainz.
- Artwork is fetched only for an identified album: Cover Art Archive first,
  then Apple Music as a fallback. Never embed YouTube thumbnails.
  If album is missing, artwork is always omitted.

Install: sudo apt install yt-dlp ffmpeg id3v2
         python3 -m pip install mutagen
"""

import argparse
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

try:
    from mutagen.id3 import APIC, COMM, ID3, ID3NoHeaderError
except ImportError:
    print("Error: Install Mutagen: python3 -m pip install mutagen", file=sys.stderr)
    sys.exit(1)


USER_AGENT = "youtube-to-mp3/1.5 (personal music metadata lookup)"
_last_musicbrainz_call = 0.0
MAX_ART_BYTES = 8 * 1024 * 1024
IGNORED_ALBUMS = {"youtube", "youtube music", "unknown", "unknown album", "n/a"}


def text_field(info, *names):
    for name in names:
        value = info.get(name)
        if isinstance(value, list):
            value = ", ".join(str(x).strip() for x in value if str(x).strip())
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def safe_name(value):
    """Remove shell-unfriendly punctuation; preserve readable spaces and dashes."""
    value = re.sub(r"['’‘`´!¡]", "", value)
    value = re.sub(r"[^\w\s.\-]", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip(" ._-")
    return value or "Unknown"


def norm(value):
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def similarity(left, right):
    return SequenceMatcher(None, norm(left), norm(right)).ratio() if left and right else 0.0


def lookup_title(title, artist):
    """Remove official-video decoration and duplicate artist prefix."""
    title = re.sub(
        r"\s*(\[[^]]*(?:official|lyric|music video|audio)[^]]*\]|"
        r"\([^)]*(?:official|lyric|music video)[^)]*\))\s*$",
        "", title, flags=re.I,
    ).strip()
    parts = re.split(r"\s+[-–—]\s+", title, maxsplit=1)
    if len(parts) == 2 and similarity(parts[0], artist) >= 0.93:
        return parts[1].strip()
    return title


def clean_album(value):
    value = str(value or "").strip().strip('"“”\'‘’ ')
    return "" if value.casefold() in IGNORED_ALBUMS else value


def album_in_description(description):
    """Recognize clear album attributions; avoid guessing from arbitrary prose."""
    if not description:
        return ""
    patterns = (
        # e.g., from the album 'Under Rug Swept'
        r"\b(?:from|taken from|off)\s+(?:the\s+)?(?:new\s+)?album\s+[\"“'‘]([^\"”'’\r\n]{2,120})[\"”'’]",
        # e.g., from the album Under Rug Swept (one line)
        r"\b(?:from|taken from|off)\s+(?:the\s+)?(?:new\s+)?album\s+([^\r\n.!;|]{2,100})",
        # e.g., Album: Under Rug Swept
        r"(?im)^\s*album\s*[:：-]\s*(.+?)\s*$",
    )
    for pattern in patterns:
        match = re.search(pattern, description, flags=re.I | re.M)
        if match:
            album = clean_album(match.group(1))
            album = re.sub(r"\s*\((?:20|19)\d\d\)\s*$", "", album).strip()
            if album and len(album) <= 120:
                return album
    return ""


def get_info(url):
    result = subprocess.run(
        ["yt-dlp", "--no-playlist", "--skip-download", "--dump-single-json", url],
        text=True, capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "yt-dlp metadata extraction failed")
    info = json.loads(result.stdout)
    if info.get("_type") == "playlist":
        raise RuntimeError("Expected a single video URL, not a playlist")
    return info


def select_metadata(info, original_url):
    raw_title = text_field(info, "track", "title", "fulltitle") or "Untitled"
    artist = text_field(info, "artist", "artists", "creator", "creators")
    channel = text_field(info, "channel", "uploader", "uploader_id")
    if not artist and channel:
        artist = re.sub(r"\s+-\s+Topic$", "", channel, flags=re.I)
    if not artist:
        match = re.match(r"^(.+?)\s+[-–—]\s+(.+)$", raw_title)
        if match and not info.get("track"):
            artist = match.group(1).strip()
    artist = artist or "Unknown Artist"
    title = lookup_title(raw_title, artist)
    album = clean_album(text_field(info, "album"))
    if not album:
        album = album_in_description(text_field(info, "description"))
    # Do not use uploader/channel, playlist, or 'YouTube' as an album.
    source_url = text_field(info, "webpage_url", "original_url") or original_url
    return title, artist, album, source_url


def get_bytes(url, timeout=8, maximum=MAX_ART_BYTES, accept=None):
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError("Image or API response too large")
    return data


def musicbrainz_json(path, params=None):
    """Respect MusicBrainz's one-request-per-second rate limit."""
    global _last_musicbrainz_call
    remaining = 1.1 - (time.monotonic() - _last_musicbrainz_call)
    if remaining > 0:
        time.sleep(remaining)
    url = "https://musicbrainz.org/ws/2/" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    # Stamp immediately before the request, including failed requests.
    _last_musicbrainz_call = time.monotonic()
    return json.loads(get_bytes(url, timeout=10, maximum=1_000_000,
                                accept="application/json"))


def artist_credit_name(recording):
    credit = recording.get("artist-credit", [])
    parts = [part.get("name") or part.get("artist", {}).get("name", "")
             for part in credit if isinstance(part, dict)]
    return " ".join(part for part in parts if part)


def musicbrainz_releases(artist, title):
    """Get album release candidates for a confidently matched recording."""
    if artist == "Unknown Artist":
        return []

    def lucene_quote(value):
        return re.sub(r'([+!(){}\[\]^"~*?:\\/|&-])', r'\\\1', value)

    query = f'recording:"{lucene_quote(title)}" AND artist:"{lucene_quote(artist)}"'
    payload = musicbrainz_json("recording/", {"query": query, "fmt": "json", "limit": 25})
    candidates = []
    for rec in payload.get("recordings", []):
        if (int(rec.get("score") or 0) < 75
                or similarity(title, rec.get("title", "")) < 0.89
                or similarity(artist, artist_credit_name(rec)) < 0.89):
            continue
        for release in rec.get("releases", []):
            release_id = release.get("id", "")
            try:
                uuid.UUID(release_id)
            except (TypeError, AttributeError, ValueError):
                continue
            group = release.get("release-group") or {}
            primary = group.get("primary-type", "")
            secondary = group.get("secondary-types") or []
            if primary != "Album" or any(item in secondary for item in (
                    "Compilation", "Live", "Remix", "DJ-mix")):
                continue
            name = clean_album(release.get("title"))
            if not name or similarity(name, title) > 0.98:
                # A release named after the song may be a single masquerading as an album.
                continue
            rank = int(rec.get("score") or 0)
            if release.get("status") == "Official":
                rank += 10
            if release.get("country") in ("US", "GB", "XW"):
                rank += 2
            first_date = group.get("first-release-date", "")
            candidates.append({
                "album": name, "release_id": release_id,
                "group_id": group.get("id"), "score": rank,
                "date": first_date,
            })
    # Group by album title, so many reissues don't overwhelm one competing album.
    by_album = {}
    for candidate in candidates:
        key = norm(candidate["album"])
        current = by_album.get(key)
        if current is None or candidate["score"] > current["score"]:
            by_album[key] = candidate
    # Earlier first release is a slight preference, useful for original albums.
    return sorted(by_album.values(), key=lambda x: (-x["score"], x["date"] or "9999"))


def select_mb_album(candidates):
    """Only infer an album if there's a clear highest-ranked album candidate."""
    if not candidates:
        return ""
    best = candidates[0]
    if len(candidates) > 1 and candidates[1]["score"] == best["score"]:
        # A tie between distinct albums is ambiguous; don't guess.
        return ""
    return best["album"]


def valid_image(data):
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return None


def musicbrainz_album_groups(artist, album):
    """Search for the known *album*, independently of recording search results."""
    if not artist or not album or artist == "Unknown Artist":
        return []

    def quote(value):
        return re.sub(r'([+!(){}\[\]^"~*?:\\/|&-])', r'\\\1', value)

    query = f'releasegroup:"{quote(album)}" AND artist:"{quote(artist)}"'
    payload = musicbrainz_json("release-group/", {
        "query": query, "fmt": "json", "limit": 25,
    })
    matches = []
    for group in payload.get("release-groups", []):
        gid = group.get("id")
        try:
            uuid.UUID(str(gid))
        except (TypeError, ValueError):
            continue
        if (similarity(album, group.get("title", "")) < 0.95
                or similarity(artist, artist_credit_name(group)) < 0.90):
            continue
        if group.get("primary-type") not in ("Album", "EP"):
            continue
        secondary = group.get("secondary-types") or []
        if any(t in secondary for t in ("Compilation", "Live", "Remix")):
            continue
        matches.append({"group_id": gid, "score": int(group.get("score") or 0)})
    return sorted(matches, key=lambda m: -m["score"])


def release_ids_in_group(group_id):
    """Fallback when a release group lacks a selected representative front cover."""
    payload = musicbrainz_json(f"release-group/{group_id}", {
        "inc": "releases", "fmt": "json",
    })
    releases = payload.get("releases", [])
    # Prefer releases MusicBrainz says have front artwork, then official editions.
    releases.sort(key=lambda r: (
        not r.get("cover-art-archive", {}).get("front", False),
        r.get("status") != "Official",
    ))
    return [r["id"] for r in releases if r.get("id")]


def apple_album_art(artist, album, debug=False):
    """Use Apple Music as a fallback, only for an exact artist/album match."""
    url = "https://itunes.apple.com/search?" + urllib.parse.urlencode({
        "term": f"{artist} {album}", "media": "music", "entity": "album", "limit": 30,
    })
    try:
        data = json.loads(get_bytes(url, timeout=10, maximum=1_000_000,
                                    accept="application/json"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
            OSError, ValueError, json.JSONDecodeError) as exc:
        if debug:
            print(f"Artwork: Apple Music lookup failed: {exc}", file=sys.stderr)
        return None
    for item in data.get("results", []):
        if (similarity(item.get("artistName", ""), artist) < 0.92
                or similarity(item.get("collectionName", ""), album) < 0.95):
            continue
        art_url = item.get("artworkUrl100", "")
        if not art_url.startswith("https://"):
            continue
        # Apple's URLs support requesting a larger derivative image.
        large_art_url = re.sub(r"\d+x\d+", "600x600", art_url, count=1)
        for candidate_url in dict.fromkeys((large_art_url, art_url)):
            try:
                image_data = get_bytes(candidate_url, timeout=12)
                mime = valid_image(image_data)
                if mime:
                    return image_data, mime, "Apple Music"
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                    OSError, ValueError) as exc:
                if debug:
                    print(f"Artwork: Apple Music image failed: {exc}", file=sys.stderr)
    return None


def search_album_art(artist, album, candidates, debug=False):
    """Retrieve an actual album cover, never a video's thumbnail.

    A recording lookup may return a different edition or no releases at all.
    Search album release groups *directly*, then their individual releases.
    Apple Music is an independent fallback if Cover Art Archive isn't reachable.
    """
    if not album:
        return None

    groups = []
    try:
        groups = musicbrainz_album_groups(artist, album)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
            OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        if debug:
            print(f"Artwork: MusicBrainz album search failed: {exc}", file=sys.stderr)

    group_ids = []
    release_ids = []
    for group in groups:
        group_ids.append(group["group_id"])
    # Older recording-based candidates remain useful as fallback identifiers.
    for candidate in candidates:
        if norm(candidate.get("album", "")) != norm(album):
            continue
        if candidate.get("group_id"):
            group_ids.append(candidate["group_id"])
        if candidate.get("release_id"):
            release_ids.append(candidate["release_id"])

    seen = set()
    for gid in dict.fromkeys(group_ids):
        if gid in seen:
            continue
        seen.add(gid)
        for suffix in ("front-500", "front-250"):
            url = f"https://coverartarchive.org/release-group/{gid}/{suffix}"
            try:
                data = get_bytes(url, timeout=12)
                mime = valid_image(data)
                if mime:
                    return data, mime, "Cover Art Archive"
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                    OSError, ValueError) as exc:
                if debug:
                    print(f"Artwork: {url}: {exc}", file=sys.stderr)

    # If group has no front art, try individual releases, including editions
    # NOT present in the song-search results.
    if groups:
        try:
            release_ids.extend(release_ids_in_group(groups[0]["group_id"]))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            if debug:
                print(f"Artwork: release lookup failed: {exc}", file=sys.stderr)

    for rid in list(dict.fromkeys(release_ids))[:8]:
        for suffix in ("front-500", "front-250"):
            url = f"https://coverartarchive.org/release/{rid}/{suffix}"
            try:
                data = get_bytes(url, timeout=12)
                mime = valid_image(data)
                if mime:
                    return data, mime, "Cover Art Archive"
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError,
                    OSError, ValueError) as exc:
                if debug:
                    print(f"Artwork: {url}: {exc}", file=sys.stderr)

    return apple_album_art(artist, album, debug=debug)


def write_comment_and_art(mp3_path, source_url, cover=None):
    try:
        tags = ID3(str(mp3_path))
    except ID3NoHeaderError:
        tags = ID3()
    tags.delall("COMM")
    tags.delall("APIC")  # No album or no verified art means NO embedded image.
    for key, frame in list(tags.items()):
        if key.startswith("TXXX:") and getattr(frame, "desc", "").lower() == "comment":
            del tags[key]
    tags.add(COMM(encoding=1, lang="eng", desc="", text=[source_url]))
    if cover:
        image_data, mime = cover[:2]
        tags.add(APIC(encoding=1, mime=mime, type=3, desc="Cover", data=image_data))
    tags.save(str(mp3_path), v2_version=3)


def verify_tags(mp3_path, source_url, album, expects_art):
    tags = ID3(str(mp3_path))
    comments = [str(value) for frame in tags.getall("COMM") for value in frame.text]
    if source_url not in comments:
        raise RuntimeError(f"COMM verification failed, found {comments!r}")
    album_frames = tags.getall("TALB")
    album_value = str(album_frames[0].text[0]) if album_frames else ""
    if album_value != album:
        raise RuntimeError(f"Album verification failed: expected {album!r}, got {album_value!r}")
    if bool(tags.getall("APIC")) != expects_art:
        raise RuntimeError("Unexpected embedded art" if not expects_art
                           else "Album art missing")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format_tags=comment",
         "-of", "json", str(mp3_path)], check=True, capture_output=True, text=True,
    )
    metadata = json.loads(result.stdout).get("format", {}).get("tags", {})
    comment = next((v for key, v in metadata.items() if key.lower() == "comment"), None)
    if comment != source_url:
        raise RuntimeError(f"FFprobe COMM mismatch: {comment!r}")


def download_one(url, args):
    """Download and tag one URL; let main handle failures for each URL."""
    info = get_info(url)
    title, artist, album, source_url = select_metadata(info, url)
    lookup_candidates = []
    # MusicBrainz lookup is needed to fill a missing album, or to locate
    # cover art for one we already know from YouTube.
    if artist != "Unknown Artist" and (
            not album or (not args.no_art and not args.no_cover_search)):
        try:
            lookup_candidates = musicbrainz_releases(artist, title)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError,
                KeyError, json.JSONDecodeError) as exc:
            print(f"Note: MusicBrainz lookup unavailable: {exc}", file=sys.stderr)
        if not album:
            album = select_mb_album(lookup_candidates)

    cover = None
    if album and not args.no_art and not args.no_cover_search:
        cover = search_album_art(artist, album, lookup_candidates, debug=args.debug_art)
    cover_source = cover[2] if cover else "none"

    args.output_dir.mkdir(parents=True, exist_ok=True)
    dest = args.output_dir / f"[{safe_name(artist)}] {safe_name(title)}.mp3"
    if dest.exists() and not args.overwrite:
        raise RuntimeError(f"File exists: {dest} (use --overwrite)")

    print(f"Title:   {title}")
    print(f"Artist:  {artist}")
    print(f"Album:   {album or '(not set)'}")
    print(f"Comment: {source_url}")
    print(f"Artwork: {cover_source}")
    print(f"Output:  {dest}", flush=True)

    template = str(dest.with_suffix("")).replace("%", "%%") + ".%(ext)s"
    cmd = [
        "yt-dlp", "--no-playlist", "-f", "bestaudio/best",
        "--extract-audio", "--audio-format", "mp3", "--audio-quality", "0",
        "--no-embed-thumbnail", "--output", template,
    ]
    if args.overwrite:
        cmd.append("--force-overwrites")
    cmd.append(url)
    subprocess.run(cmd, check=True)
    if not dest.is_file():
        raise RuntimeError(f"yt-dlp finished but no MP3 found: {dest}")

    tag_cmd = ["id3v2", "--song", title, "--artist", artist]
    if album:
        tag_cmd += ["--album", album]
    year = text_field(info, "release_year")
    if re.fullmatch(r"\d{4}", year):
        tag_cmd += ["--year", year]
    track = info.get("track_number")
    if track is not None and str(track).isdigit():
        tag_cmd += ["--track", str(track)]
    tag_cmd.append(str(dest))
    subprocess.run(tag_cmd, check=True)

    write_comment_and_art(dest, source_url, cover)
    verify_tags(dest, source_url, album, expects_art=bool(cover))

    print(f"\nSaved and tagged: {dest}")
    subprocess.run(["id3v2", "-l", str(dest)], check=True)
    return dest


def main():
    parser = argparse.ArgumentParser(
        description="Download one or more YouTube videos as '[Artist] Title.mp3' with ID3 tags."
    )
    parser.add_argument("urls", nargs="+", metavar="URL",
                        help="One or more YouTube video URLs (not playlists)")
    parser.add_argument("-d", "--output-dir", type=Path, default=Path("."))
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing MP3s")
    parser.add_argument("--no-cover-search", action="store_true",
                        help="Skip online album artwork lookup (no YouTube thumbnail fallback)")
    parser.add_argument("--no-art", action="store_true", help="Never embed album art")
    parser.add_argument("--debug-art", action="store_true",
                        help="Print artwork lookup errors and failed download URLs")
    args = parser.parse_args()

    missing = [name for name in ("yt-dlp", "ffmpeg", "ffprobe", "id3v2")
               if not shutil.which(name)]
    if missing:
        parser.error("Missing commands on PATH: " + ", ".join(missing))

    failures = []
    for number, url in enumerate(args.urls, start=1):
        if len(args.urls) > 1:
            print(f"\n=== Video {number}/{len(args.urls)}: {url} ===", flush=True)
        try:
            download_one(url, args)
        except (OSError, subprocess.CalledProcessError, ValueError, RuntimeError) as exc:
            print(f"Error processing {url}: {exc}", file=sys.stderr, flush=True)
            failures.append(url)

    if len(args.urls) > 1:
        print(f"\nCompleted: {len(args.urls) - len(failures)} succeeded, "
              f"{len(failures)} failed (of {len(args.urls)} URLs).")
        if failures:
            print("Failed URLs:", file=sys.stderr)
            for url in failures:
                print(f"  {url}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
