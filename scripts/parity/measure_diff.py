#!/usr/bin/env python3
"""逐页量化两版截图的差异，输出可直接抄进台账的表。

`compare.sh` 给的是「差异像素总数 / 3% 容差下还剩几个 / 最大单通道差」。本脚本把
「差异像素总数」拆开说清楚：多少像素只差 1 级、多少差 ≥2 级、它们落在关闭按钮 ✕
的框里还是页面内容上、页面内容上最差差几级。用户要求「不许把 1 像素说成完全零差异」，
所以这里逐级给出灰度级分布，而不是只给一个总数。

用法: scripts/parity/measure_diff.py <原版截图目录> <移植版截图目录> [--md]

依赖: imagemagick（convert）。
"""
from __future__ import annotations

import subprocess
import sys

PAGES = [
    "01-first-run",
    "02-settings-general",
    "03-settings-models",
    "04-settings-extensions",
    "05-settings-about",
    "06-after-settings",
    "07-chat",
]

# 关闭按钮 ✕ 所在的框：原版 Linux 的 titleBarOverlay 是右上角 96x40，
# ✕ 字形实测落在 10x10+1259+15。这里放宽到 1200..1280 x 0..40，只用来把
# 「按钮字形抗锯齿」与「页面内容」分开统计。
CLOSE_BOX = (1200, 0, 1280, 40)


def load_rgb(path: str) -> tuple[bytes, int, int]:
    size = subprocess.run(
        ["identify", "-format", "%w %h", path], capture_output=True, text=True, check=True
    ).stdout.split()
    width, height = int(size[0]), int(size[1])
    raw = subprocess.run(
        ["convert", path, "-depth", "8", "rgb:-"], capture_output=True, check=True
    ).stdout
    if len(raw) != width * height * 3:
        raise SystemExit(f"{path}: 解出的字节数与 {width}x{height} 不符")
    return raw, width, height


def measure(orig: str, port: str) -> dict[str, object]:
    a, width, height = load_rgb(orig)
    b, width_b, height_b = load_rgb(port)
    if (width, height) != (width_b, height_b):
        raise SystemExit(f"尺寸不同，无法判定：{orig}={width}x{height} {port}={width_b}x{height_b}")

    x0, y0, x1, y1 = CLOSE_BOX
    total = 0
    levels: dict[int, int] = {}
    close_px = 0
    close_levels: dict[int, int] = {}
    rest_px = 0
    rest_levels: dict[int, int] = {}
    rest_max = 0
    rest_bbox: list[int] | None = None  # [minx, miny, maxx, maxy] of ≥2-level diffs

    for y in range(height):
        for x in range(width):
            i = (y * width + x) * 3
            d = max(abs(a[i] - b[i]), abs(a[i + 1] - b[i + 1]), abs(a[i + 2] - b[i + 2]))
            if not d:
                continue
            total += 1
            levels[d] = levels.get(d, 0) + 1
            if x0 <= x < x1 and y0 <= y < y1:
                close_px += 1
                close_levels[d] = close_levels.get(d, 0) + 1
                continue
            rest_px += 1
            rest_levels[d] = rest_levels.get(d, 0) + 1
            rest_max = max(rest_max, d)
            if d >= 2:
                if rest_bbox is None:
                    rest_bbox = [x, y, x, y]
                else:
                    rest_bbox = [
                        min(rest_bbox[0], x),
                        min(rest_bbox[1], y),
                        max(rest_bbox[2], x),
                        max(rest_bbox[3], y),
                    ]

    def fmt(d: dict[int, int]) -> str:
        return " ".join(f"{k}:{d[k]}" for k in sorted(d))

    return {
        "page": orig.rsplit("/", 1)[-1][:-4],
        "size": f"{width}x{height}",
        "total": total,
        "levels": fmt(levels),
        "close_px": close_px,
        "close_levels": fmt(close_levels),
        "rest_px": rest_px,
        "rest_levels_1": rest_levels.get(1, 0),
        "rest_levels": fmt(rest_levels),
        "rest_ge2": rest_px - rest_levels.get(1, 0),
        "rest_max": rest_max,
        "rest_bbox": "-" if rest_bbox is None else "{},{}-{},{}".format(*rest_bbox),
    }


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    orig_dir, port_dir = argv[1], argv[2]
    rows = []
    for page in PAGES:
        rows.append(measure(f"{orig_dir}/{page}.png", f"{port_dir}/{page}.png"))

    print(
        f"{'PAGE':24} {'total':>7} {'✕块':>5} {'正文':>7} {'正文=1':>7} "
        f"{'正文>=2':>7} {'正文max':>7}  {'正文>=2 的包围盒':>18}"
    )
    for r in rows:
        print(
            f"{r['page']:24} {r['total']:7d} {r['close_px']:5d} {r['rest_px']:7d} "
            f"{r['rest_levels_1']:7d} {r['rest_ge2']:7d} {r['rest_max']:7d}  {r['rest_bbox']:>18}"
        )
    print()
    print("各级灰度像素数（通道最大差；✕块 / 正文分开列）：")
    for r in rows:
        print(f"  {r['page']:24} ✕块: {r['close_levels']}")
        print(f"  {'':24} 正文: {r['rest_levels']}")

    if "--md" in argv:
        print()
        print("| 页面 | 差异像素总数 | ✕ 字形内 | 正文内 | 正文内 >1 级 | 正文最大差 | 正文 >1 级包围盒 |")
        print("|---|---|---|---|---|---|---|")
        for r in rows:
            print(
                f"| {r['page']} | {r['total']} | {r['close_px']} | {r['rest_px']} | "
                f"{r['rest_ge2']} | {r['rest_max']} | {r['rest_bbox']} |"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
