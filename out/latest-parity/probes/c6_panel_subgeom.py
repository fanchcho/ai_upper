"""D1 子几何：面板外框 / 分组标题 / 模型行 / 勾选位的相对墨迹范围。

用法: .venv/bin/python -I out/latest-parity/probes/c6_panel_subgeom.py
相对坐标以面板外框左上角为原点（deva 847,688；QML 847,688 —— B 轮 +2 后两侧面板外框同 x，宽度都是 248）。

不列「before」：HEAD 的旧代码是 (700,542) 的 thinking 面板，这组坐标上本来就没有面板。
"""
import sys

sys.path.insert(0, '/home/agent/shared_workspace/ai_upper/scripts/parity')
from pngread import read_png  # noqa: E402

BORDER = (230, 230, 234)
ROOT = '/home/agent/shared_workspace/ai_upper/out/latest-parity'


def analyse(path, left, top, thr=235):
    w, h, px = read_png(path)

    def ink(x0, x1, y0, y1):
        pts = [(x - left, y - top)
               for y in range(top + y0, top + y1 + 1)
               for x in range(left + x0, left + x1 + 1)
               if px[y * w + x] != BORDER and sum(px[y * w + x]) / 3 < thr]
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), max(xs), min(ys), max(ys), len(pts))

    return {
        "groupHead": ink(8, 120, 6, 30),
        "modelRow": ink(8, 200, 34, 57),
        "check": ink(205, 244, 34, 57),
    }


CASES = [
    ("deva", ROOT + '/deva/model-picker-deva.png', 847),
    ("after(current)", ROOT + '/qml/model-picker.png', 847),
]

for tag, path, left in CASES:
    r = analyse(path, left, 688)
    print("== %-30s" % tag,
          "  ".join("%s rel x%d..%d y%d..%d px=%d" % ((k,) + v)
                    for k, v in r.items() if v))
