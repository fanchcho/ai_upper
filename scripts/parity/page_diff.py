#!/usr/bin/env python3
"""逐页量化：原版截图 vs QML 截图，给出可复现的差异数值 + 差异图。

判定口径（写进 REPORT.md 的就是这三项）：
  diff_px   通道最大差 > --threshold（默认 16）的像素数；
  ratio     diff_px / (W*H)，百分比保留 4 位；
  bbox      这些像素的包围盒 x0,y0-x1,y1（无差异时为 "-"）。
另外给出：
  max_ch    全图最大单通道差（0..255）；
  levels    差异像素按通道最大差分级的直方图（1,2-4,5-8,9-16,17-32,>32）。

为什么不用 numpy/Pillow：本项目 .venv 里没有这两个包，且装了会污染运行环境。
这里用 ImageMagick 解码成裸 RGB（`convert x.png -depth 8 rgb:-`）后纯 Python
逐像素比较——零额外依赖，CI 与本地结果一致。

用法:
  scripts/parity/page_diff.py <原版.png> <QML.png> <输出 diff.png> [--threshold N] [--json]
"""
from __future__ import annotations

import json
import subprocess
import sys

LEVELS = ("1", "2-4", "5-8", "9-16", "17-32", ">32")


def _run(cmd):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise SystemExit(
            "命令失败: %s\n%s" % (" ".join(cmd), proc.stderr.decode("utf-8", "replace")[:2000])
        )
    return proc.stdout


def load(path):
    """返回 (width, height, rgb_bytes)。用 ImageMagick 解码，保证与原图逐字节一致。"""
    size = _run(["identify", "-format", "%w %h", path]).decode().strip()
    width, height = (int(v) for v in size.split())
    raw = _run(["convert", path, "-depth", "8", "rgb:-"])
    expected = width * height * 3
    if len(raw) != expected:
        raise SystemExit("解码长度异常: %s 期望 %d 实得 %d" % (path, expected, len(raw)))
    return width, height, raw


def main(argv):
    if len(argv) < 4:
        print(__doc__, file=sys.stderr)
        return 2
    a_path, b_path, out_path = argv[1], argv[2], argv[3]
    threshold = 16
    if "--threshold" in argv:
        threshold = int(argv[argv.index("--threshold") + 1])

    wa, ha, a = load(a_path)
    wb, hb, b = load(b_path)
    if (wa, ha) != (wb, hb):
        raise SystemExit(
            "尺寸不同，无法判定：%s=%dx%d %s=%dx%d" % (a_path, wa, ha, b_path, wb, hb)
        )
    width, height = wa, ha
    total = width * height

    diff_px = 0
    max_ch = 0
    x0 = y0 = 1 << 30
    x1 = y1 = -1
    buckets = dict.fromkeys(LEVELS, 0)
    canvas = bytearray(total * 3)  # 差异图：原图压暗 25%，差异像素纯红

    idx = 0
    for y in range(height):
        row_off = y * width
        for x in range(width):
            r0 = a[idx]
            g0 = a[idx + 1]
            b0 = a[idx + 2]
            dr = r0 - b[idx]
            dg = g0 - b[idx + 1]
            db = b0 - b[idx + 2]
            if dr < 0:
                dr = -dr
            if dg < 0:
                dg = -dg
            if db < 0:
                db = -db
            d = dr if dr >= dg else dg
            if d >= db:
                pass
            else:
                d = db
            if d > max_ch:
                max_ch = d
            if d > 0:
                if d == 1:
                    buckets["1"] += 1
                elif d <= 4:
                    buckets["2-4"] += 1
                elif d <= 8:
                    buckets["5-8"] += 1
                elif d <= 16:
                    buckets["9-16"] += 1
                elif d <= 32:
                    buckets["17-32"] += 1
                else:
                    buckets[">32"] += 1
            if d > threshold:
                diff_px += 1
                px = row_off + x
                if x < x0:
                    x0 = x
                if x > x1:
                    x1 = x
                if y < y0:
                    y0 = y
                if y > y1:
                    y1 = y
                canvas[idx] = 255
                canvas[idx + 1] = 0
                canvas[idx + 2] = 0
            else:
                canvas[idx] = (r0 * 25) // 100
                canvas[idx + 1] = (g0 * 25) // 100
                canvas[idx + 2] = (b0 * 25) // 100
            idx += 3

    ratio = diff_px * 100.0 / total
    bbox = "-" if diff_px == 0 else "%d,%d-%d,%d" % (x0, y0, x1, y1)

    subprocess.run(
        [
            "convert", "-size", "%dx%d" % (width, height), "-depth", "8", "rgb:-",
            "png:" + out_path,
        ],
        input=bytes(canvas),
        check=True,
    )

    result = {
        "original": a_path,
        "qml": b_path,
        "size": "%dx%d" % (width, height),
        "threshold": threshold,
        "diff_px": diff_px,
        "diff_ratio_pct": round(ratio, 4),
        "bbox": bbox,
        "max_channel_delta": max_ch,
        "levels": buckets,
        "diff_png": out_path,
    }
    if "--json" in argv:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(
            "%dx%d threshold>%d: diff_px=%d ratio=%.4f%% bbox=%s maxD=%d levels=%s"
            % (width, height, threshold, diff_px, ratio, bbox, max_ch, buckets)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
