"""高密度区间的分组细化：16 / 24 / 32 / 50 在 0.3~0.8 密度上谁更省。

``probe_plan_check.py`` 发现 0.31~0.44 这一档用 16 会比 24/32/50 慢 1.5~4.5%。
本探针专测这一段，用 3 种密度 × 3 种规模，每档取 3 次最小值，给出无争议的结论。
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

GROUPS = (12, 16, 24, 32, 50)
CASES = {
    "d31": lambda n: density_md(n, 4, 4, 4),      # 每 4 段 表 + 代码 + 引用
    "d44": lambda n: density_md(n, 2, 2, 2, 2),   # 每 2 段 表 + 代码 + 引用 + h2
    "d52": lambda n: density_md(n, 1, 2, 2, 2),   # 每段一张表，其余同 d44
    "d73": lambda n: density_md(n, 1, 1, 1),      # 每段 表 + 代码 + 引用
}


def render(md_text, style, group):
    saved = mdoc._chunk_plan
    mdoc._chunk_plan = lambda blocks: group
    try:
        best = float("inf")
        for _ in range(3):
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
            out[key] = {
                "blocks": len(blocks),
                "density": round(density, 3),
                "ms": {g: round(times[g], 1) for g in GROUPS},
                "best_group": best,
                "spread_pct": round((max(times.values()) - times[best]) / times[best] * 100, 1),
            }
            print("%-10s N=%-5d d=%.2f %s best=g%-3d spread=%.1f%%" % (
                key, len(blocks), density,
                " ".join("g%-3d=%-8.1f" % (g, times[g]) for g in GROUPS),
                best, out[key]["spread_pct"]), flush=True)
    print("DENSE " + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
