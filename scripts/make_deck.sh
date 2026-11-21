#!/usr/bin/env bash
# Full pipeline: build no-mask preview -> render -> calibrate mask boxes ->
# build final deck with exact, render-derived masks.
#
# usage: PYTHON=<python with python-pptx/Pillow/numpy> scripts/make_deck.sh deck.json out.pptx
set -euo pipefail
spec="$(cd "$(dirname "$1")" && pwd)/$(basename "$1")"
out="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
here="$(cd "$(dirname "$0")" && pwd)"
py="${PYTHON:-python3}"

"$py" -c "import pptx, PIL, numpy" 2>/dev/null || {
  echo "PYTHON=$py lacks python-pptx/Pillow/numpy; set PYTHON=<DSH runtime python>" >&2
  exit 1
}

tmp="$(mktemp -d)"
cleanup() { rm -rf "$tmp"; }
trap cleanup EXIT

echo "[1/3] building no-mask preview"
NO_MASKS=1 "$py" "$here/build_deck.py" --spec "$spec" --out "$tmp/nomask.pptx"

echo "[2/3] rendering every page"
cp "$tmp/nomask.pptx" "$tmp/preview-$(date +%s%N).pptx"
preview="$tmp/preview-$(date +%s%N).pptx"
cp "$tmp/nomask.pptx" "$preview"
mkdir -p "$tmp/pages"
pages=$(unzip -l "$tmp/nomask.pptx" | grep -o 'ppt/slides/slide[0-9]*\.xml' | wc -l | tr -d ' ')
for i in $(seq 1 "$pages"); do
  officecli view "$preview" screenshot --page "$i" --out "$tmp/pages/p$i.png" >/dev/null 2>&1
done

echo "[3/3] calibrating masks and building final deck"
"$py" "$here/calibrate_masks.py" --spec "$spec" --pages "$tmp/pages" --out "$tmp/masks.json"
"$py" "$here/build_deck.py" --spec "$spec" --out "$out" --masks "$tmp/masks.json"
echo "done: $out"
