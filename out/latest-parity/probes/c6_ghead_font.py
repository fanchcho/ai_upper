"""D1 分组标题字号：11.5px 在 Qt 侧无法表达，实测落在 11px 或 12px 两端。

用法: .venv/bin/python -I out/latest-parity/probes/c6_ghead_font.py [额外 png ...]
默认只量 deva 与当前落地图。额外传参时按「文件名:面板左边界」的格式量第 4 项之后的图，
用来复现这一轮 A/B：例如 /tmp/g-8.75.png:776。

输出 (minx, maxx, miny, maxy, 墨迹像素)，坐标为面板内相对坐标。
"""
import sys

sys.path.insert(0, '/home/agent/shared_workspace/ai_upper/scripts/parity')
from pngread import read_png  # noqa: E402

ROOT = '/home/agent/shared_workspace/ai_upper/out/latest-parity'
BORDER = (230, 230, 234)


def measure(path, left, top=688, thr=235):
    """分组标题文字带（面板内 x8..120、y6..30）的墨迹包围盒。"""
    w, h, px = read_png(path)
    pts = [(x - left, y - top)
           for y in range(top + 6, top + 31)
           for x in range(left + 8, left + 121)
           if px[y * w + x] != BORDER and sum(px[y * w + x]) / 3 < thr]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), max(xs), min(ys), max(ys), len(pts))


cases = [("deva", ROOT + '/deva/model-picker-deva.png', 847),
         ("qml after(current)", ROOT + '/qml/model-picker.png', 776)]
for spec in sys.argv[1:]:
    path, _, left = spec.rpartition(':')
    cases.append((path.split('/')[-1], path, int(left)))

for tag, path, left in cases:
    print("%-28s %s" % (tag, measure(path, left)))
