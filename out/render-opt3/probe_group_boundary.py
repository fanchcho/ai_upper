"""密度 0.31 与 0.44 之间的分组交界：g24 / g32 / g50 谁更快。

``probe_plan_check`` 显示这之间没有实测点，而两档在 0.31（g50 快 1.0%）与 0.44
（g32 快 1.5%）各占一头；交界若拍脑袋放在 0.40，可能把 0.36 的文档推给较慢的档。
这里补一个密度 ≈0.365 的点（每 3 段一堆结构块）把交界钉住。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle, parse_markdown, render_markdown  # noqa: E402
from probe_group_calib import density_md  # noqa: E402

GROUPS = (16, 24, 32, 50)
CASES = {
    "d36": lambda n: density_md(n, 3, 3, 3),   # 每 3 段 表 + 代码 + 引用
    "d40": lambda n: density_md(n, 2, 2, 0),   # 每 2 段 表 + 代码
}


def render(md_text, style, group):
    saved = mdoc._chunk_plan
    mdoc._chunk_plan = lambda blocks: group
    try:
        best = float("inf")
        for _ in range(4):
            start = time.perf_counter()
            render_markdown(QTextDocument(), md_text, style, 676.0, None)
            best = min(best, (time.perf_counter() - start) * 1000.0)
        return best
    finally:
        mdoc._chunk_plan = saved


def main():
    QApplication.instance() or QApplication([])
    style = BodyStyle()
    out = {}
    for name, build in CASES.items():
        for turns in (400, 1200, 2400):
            md = build(turns)
            blocks = parse_markdown(md)
            density = mdoc._structural_load(blocks) / len(blocks)
            times = {group: render(md, style, group) for group in GROUPS}
            best = min(GROUPS, key=lambda g: times[g])
            key = "%s_t%d" % (name, turns)
            out[key] = {"blocks": len(blocks), "density": round(density, 3),
                        "ms": {g: round(times[g], 1) for g in GROUPS},
                        "best_group": best}
            print("%-10s N=%-5d d=%.3f %s best=g%-3d  g32/g50=%+.1f%% g24/g50=%+.1f%%" % (
                key, len(blocks), density,
                " ".join("g%-3d=%-8.1f" % (g, times[g]) for g in GROUPS), best,
                (times[32] - times[50]) / times[50] * 100,
                (times[24] - times[50]) / times[50] * 100), flush=True)
    print("BOUNDARY " + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
