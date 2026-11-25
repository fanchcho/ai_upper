"""Measure the markdown table's horizontal borders in a 1280x820 page shot.

Pure stdlib (scripts/parity/pngread.py) because the container has no PIL.

Usage: .venv/bin/python out/final-closeout/measure_table.py <png> [png ...]
"""
from __future__ import annotations

import os
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "parity"))
from pngread import read_png  # noqa: E402


def main(argv: list[str]) -> int:
    for path in argv[1:]:
        width, height, pixels = read_png(path)
        print(f"== {path} {width}x{height}")
        rows = []
        for y in range(55, 320):
            counter = Counter()
            for x in range(470, 810):
                r, g, b = pixels[y * width + x][:3]
                if max(r, g, b) < 250 and abs(r - g) <= 6 and abs(g - b) <= 6:
                    counter[(r, g, b)] += 1
            if not counter:
                continue
            color, count = counter.most_common(1)[0]
            if count > 200:
                rows.append((y, color, count))
        print("border_rows", rows)
        if rows:
            ys = [y for y, _, _ in rows]
            runs = []
            for y in ys:
                if runs and runs[-1][1] == y - 1:
                    runs[-1][1] = y
                else:
                    runs.append([y, y])
            print("runs", runs)
            print("advances", [b[0] - a[0] for a, b in zip(runs, runs[1:])])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
