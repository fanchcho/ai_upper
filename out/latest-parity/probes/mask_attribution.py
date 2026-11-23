#!/usr/bin/env python3
"""A5/F3 遮罩归因：拆分弹窗外/弹窗内差异，核对 QML vs deva 取样 RGB。

只读脚本：不修改任何 QML 或 deva 文件。分母固定 1280*820=1,049,600。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "parity"))
from pngread import read_png  # noqa: E402

W, H = 1280, 820
DENOM = W * H
PAGES = [
    ("delete-confirm", (430, 317, 850, 503)),
    ("settings-general", (280, 130, 1000, 690)),
    ("settings-models", (280, 130, 1000, 690)),
    ("settings-extensions", (280, 130, 1000, 690)),
    ("settings-about", (280, 130, 1000, 690)),
]
SAMPLES = {
    "delete-confirm": [(60, 120), (300, 700), (1100, 100), (1200, 100), (600, 450)],
    "settings-general": [(60, 120), (60, 700), (300, 700), (900, 700), (1200, 700), (500, 600)],
}
PREFIX = "out/latest-parity"


def load(page: str):
    w, h, q = read_png(f"{PREFIX}/qml/{page}.png")
    w2, h2, d = read_png(f"{PREFIX}/deva/{page}-deva.png")
    if (w, h) != (W, H) or (w2, h2) != (W, H):
        raise SystemExit(f"{page}: unexpected size {(w, h)} / {(w2, h2)}")
    return q, d


def main() -> int:
    print(f"canvas={W}x{H} denominator={DENOM}")
    print("page                     total_diff  pct_page  diff_d1_2  pct_of_diff  outside_diff  outside_d1_2  inside_diff  inside_gt8")
    rows = {}
    for page, (x0, y0, x1, y1) in PAGES:
        q, d = load(page)
        total = d12 = outside = outside12 = inside = inside_gt8 = 0
        for y in range(H):
            base = y * W
            for x in range(W):
                qr = q[base + x]
                dr = d[base + x]
                md = max(abs(qr[i] - dr[i]) for i in range(3))
                if not md:
                    continue
                total += 1
                if md <= 2:
                    d12 += 1
                if x0 <= x < x1 and y0 <= y < y1:
                    inside += 1
                    if md > 8:
                        inside_gt8 += 1
                else:
                    outside += 1
                    if md <= 2:
                        outside12 += 1
        rows[page] = (total, d12, outside, outside12, inside, inside_gt8)
        print(f"{page:24s} {total:10d} {total / DENOM * 100:8.2f}% {d12:10d} {d12 / total * 100:10.2f}% {outside:13d} {outside12:13d} {inside:11d} {inside_gt8:9d}")

    print("\nsample points (x,y): qml_rgb deva_rgb delta")
    for page, pts in SAMPLES.items():
        q, d = load(page)
        print(f"-- {page}")
        for x, y in pts:
            qr = q[y * W + x]
            dr = d[y * W + x]
            delta = tuple(qr[i] - dr[i] for i in range(3))
            print(f"  ({x:4d},{y:3d}) qml={qr} deva={dr} delta={delta}")

    settings = ["settings-general", "settings-models", "settings-extensions", "settings-about"]
    outs = {p: rows[p][2] for p in settings}
    outs12 = {p: rows[p][3] for p in settings}
    print("\nsettings shared-background check:")
    for p in settings:
        print(f"  {p}: outside_diff={outs[p]} outside_d1_2={outs12[p]}")
    print(f"  identical_outside_diff={len(set(outs.values())) == 1} identical_outside_d1_2={len(set(outs12.values())) == 1}")

    print("\nattribution:")
    for page, _ in PAGES:
        total, d12, outside, outside12, inside, inside_gt8 = rows[page]
        print(
            f"  {page}: outside_share={outside / total * 100:.2f}% "
            f"diff_d1_2_share={d12 / total * 100:.2f}% "
            f"inside_share={inside / total * 100:.2f}% "
            f"inside_gt8={inside_gt8}"
        )
    print("  conclusion=mask-compositing-primary" if all(
        rows[p][2] / rows[p][0] > 0.90 for p in [name for name, _ in PAGES]
    ) else "  conclusion=structural-review-required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
