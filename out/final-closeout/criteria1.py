"""Criterion 1: chat / long-mid / long-bottom must differ pairwise (md5 + real pixel AE).

Usage: .venv/bin/python out/final-closeout/criteria1.py <qml-dir>
"""
from __future__ import annotations

import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "parity"))
from pngread import read_png  # noqa: E402

PAGES = ("chat", "long-mid", "long-bottom")


def main(argv: list[str]) -> int:
    qml_dir = argv[1]
    shots = {}
    for page in PAGES:
        path = os.path.join(qml_dir, f"{page}.png")
        width, height, pixels = read_png(path)
        digest = hashlib.md5(open(path, "rb").read()).hexdigest()
        shots[page] = (width, height, pixels, digest)
    for i, a in enumerate(PAGES):
        for b in PAGES[i + 1:]:
            wa, ha, pa, da = shots[a]
            wb, hb, pb, db = shots[b]
            total = 0
            worst = 0
            for x, y in zip(pa, pb):
                d = max(abs(x[0] - y[0]), abs(x[1] - y[1]), abs(x[2] - y[2]))
                if d:
                    total += 1
                    worst = max(worst, d)
            print(f"HARD_DIFFERENT {a} vs {b} md5={da}/{db} same_md5={da == db} AE={total} max={worst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
