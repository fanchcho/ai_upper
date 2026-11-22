"""18 页逐页对照：md5 / 字节 / 像素差异百分比（原版基线 vs QML 移植版）。

用法: python3 -I scripts/parity/page_diff18.py <deva目录> <qml目录> [--md]

输出每页：两侧 md5、字节、差异像素数、差异像素占 1280x820 的百分比、最大单通道差。
PNG 由 `pngread.py` 用标准库解码——环境里没有 ImageMagick，重拍对照也必须能跑。
"""
from __future__ import annotations

import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pngread import read_png  # noqa: E402

PAGES = [
    "chat", "empty", "first-run", "search-open", "search-results", "search-none",
    "ctx-menu", "delete-confirm", "model-picker", "hover-thread", "focus-composer",
    "long-mid", "long-bottom", "settings-general", "settings-models",
    "settings-extensions", "settings-about", "dark-chat",
]


def load(path: str):
    width, height, pixels = read_png(path)
    with open(path, "rb") as handle:
        digest = hashlib.md5(handle.read()).hexdigest()
    return pixels, width, height, digest, os.path.getsize(path)


def diff(a, b, width: int, height: int) -> tuple[int, int]:
    total = 0
    worst = 0
    for x, y in zip(a, b):
        d = max(abs(x[0] - y[0]), abs(x[1] - y[1]), abs(x[2] - y[2]))
        if d:
            total += 1
            if d > worst:
                worst = d
    return total, worst


def main(argv: list[str]) -> int:
    deva_dir, qml_dir = argv[1], argv[2]
    rows = []
    for page in PAGES:
        dpath = f"{deva_dir}/{page}-deva.png"
        qpath = f"{qml_dir}/{page}.png"
        if not (os.path.isfile(dpath) and os.path.isfile(qpath)):
            rows.append((page, None))
            continue
        a, w, h, dmd5, dsize = load(dpath)
        b, w2, h2, qmd5, qsize = load(qpath)
        if (w, h) != (w2, h2):
            raise SystemExit(f"{page}: 尺寸不同 {w}x{h} vs {w2}x{h2}")
        total, worst = diff(a, b, w, h)
        rows.append((page, {
            "dmd5": dmd5, "qmd5": qmd5, "dsize": dsize, "qsize": qsize,
            "px": total, "pct": total * 100.0 / (w * h), "worst": worst,
            "same": dmd5 == qmd5,
        }))
    md = "--md" in argv
    if md:
        print("| 页 | 原版 md5 | QML md5 | 原版字节 | QML 字节 | 差异像素 | 差异占比 | 最大差 |")
        print("|---|---|---|---:|---:|---:|---:|---:|")
        for page, r in rows:
            if r is None:
                print(f"| {page} | 缺图 | 缺图 | - | - | - | - | - |")
                continue
            same = "（完全一致）" if r["same"] else ""
            print(f"| {page} | `{r['dmd5'][:10]}…`{same} | `{r['qmd5'][:10]}…` | "
                  f"{r['dsize']} | {r['qsize']} | {r['px']} | {r['pct']:.2f}% | {r['worst']} |")
    else:
        for page, r in rows:
            if r is None:
                print(f"{page:22} MISSING")
                continue
            print(f"{page:22} {r['dmd5']} {r['qmd5']} {r['dsize']:7d} {r['qsize']:7d} "
                  f"{r['px']:7d} {r['pct']:6.2f}% max={r['worst']:3d} same={r['same']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
