#!/usr/bin/env python3
"""
Calibrate mask rectangles from a *rendered* no-mask preview.

The body text is rendered with the real font by the real renderer, so the red
target words give exact pixel boxes. We convert those to inches, add a small
safety margin, and hand the boxes to build_deck.py --masks.

usage:
    python calibrate_masks.py --spec deck.json --pages /tmp/preview --out masks.json

--pages must contain p1.png .. pN.png, 1920x1080 (96 dpi), rendered from the
NO_MASKS build of the same spec.
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image

DPI = 96.0
IMG_ZONE_X = 1265      # body-image column starts around x=1280px
IMG_ZONE_Y = 330       # ... and y=331px


def clusters_for_page(path, expected):
    im = np.array(Image.open(path).convert("RGB")).astype(int)
    red = (im[:, :, 0] > 200) & (im[:, :, 1] < 70) & (im[:, :, 2] < 70)
    # ignore red pixels inside the picture column (logos / photos)
    red[IMG_ZONE_Y:, IMG_ZONE_X:] = False

    ys, xs = np.where(red)
    if len(ys) == 0:
        return []
    # group into text lines
    rows = sorted(set(ys.tolist()))
    line_groups, cur = [], []
    for y in rows:
        if cur and y - cur[-1] > 6:
            line_groups.append(cur)
            cur = []
        cur.append(y)
    if cur:
        line_groups.append(cur)

    boxes = []
    for g in line_groups:
        m = (ys >= g[0]) & (ys <= g[-1])
        x = xs[m]
        xu = sorted(set(x.tolist()))
        x_groups, c = [], []
        for v in xu:
            if c and v - c[-1] > 25:
                x_groups.append((c[0], c[-1]))
                c = []
            c.append(v)
        if c:
            x_groups.append((c[0], c[-1]))
        for a, b in x_groups:
            if b - a < 8:
                continue
            sub = red[g[0]:g[-1] + 1, a:b + 1]
            yy = np.where(sub.any(axis=1))[0]
            if len(yy) == 0:
                continue
            boxes.append((a, g[0] + yy.min(), b, g[0] + yy.max()))
    boxes.sort(key=lambda t: (round(t[1] / 40), t[0]))
    if len(boxes) != expected:
        print("  ! page %s: expected %d words, found %d: %s"
              % (os.path.basename(path), expected, len(boxes), boxes), file=sys.stderr)
        raise SystemExit(2)
    return boxes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--pages", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.spec, encoding="utf-8") as f:
        spec = json.load(f)

    result = {"pages": []}
    for i, page in enumerate(spec["pages"]):
        img = os.path.join(args.pages, "p%d.png" % (i + 2))  # p1 = cover
        boxes = clusters_for_page(img, len(page.get("targets", [])))
        boxes_in = []
        for (x0, y0, x1, y1) in boxes:
            boxes_in.append({
                "x": round(x0 / DPI - 0.04, 3),
                "y": round(y0 / DPI - 0.06, 3),
                "w": round((x1 - x0) / DPI + 0.08, 3),
                "h": round((y1 - y0) / DPI + 0.12, 3),
            })
        result["pages"].append(boxes_in)
        print("page %d: %d masks" % (i + 1, len(boxes_in)))

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print("saved", args.out)


if __name__ == "__main__":
    main()
