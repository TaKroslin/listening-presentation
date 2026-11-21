#!/usr/bin/env bash
# Render every slide of a PPTX to PNG, bypassing officecli's path-based cache.
# usage: scripts/render.sh deck.pptx [outdir]
set -euo pipefail
src="$1"
outdir="${2:-/tmp/listening-preview}"
mkdir -p "$outdir"
tmpdir="$(mktemp -d)"
tmp="$tmpdir/$(basename "$src" .pptx)-$(date +%s%N).pptx"
cp "$src" "$tmp"
pages=$(unzip -l "$src" | grep -o 'ppt/slides/slide[0-9]*\.xml' | wc -l | tr -d ' ')
for i in $(seq 1 "$pages"); do
  officecli view "$tmp" screenshot --page "$i" --out "$outdir/p$i.png" >/dev/null 2>&1
done
echo "$outdir ($pages pages)"
