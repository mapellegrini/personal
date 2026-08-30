#!/bin/bash

set -e

file="$1"

if [[ -z "$file" ]]; then
    echo "Usage: $0 <video-file>"
    exit 1
fi

if [[ ! -f "$file" ]]; then
    echo "Error: '$file' does not exist or is not a regular file."
    exit 1
fi

dir=$(dirname "$file")
base=$(basename "$file")
ext="${base##*.}"

tmp=$(mktemp --tmpdir="$dir" ".rotateccw.XXXXXX.$ext")

cleanup() {
    rm -f -- "$tmp"
}
trap cleanup EXIT

ffmpeg -i "$file" -vf "transpose=2" -c:a copy "$tmp"

mv -- "$tmp" "$file"
chmod 644 -- "$file"

trap - EXIT
