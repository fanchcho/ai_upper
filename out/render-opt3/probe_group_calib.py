"""自适应分组的标定：结构密度 × 规模，整篇 vs 若干分组的耗时。

密度定义 ``S / N``（S = 会走结构性插入的顶层块数，N = 顶层块总数）。目标：
1. 找出「整篇仍更快」的区域（纯段落、稀疏结构）；
2. 在该走分块的一侧，找出适合 12 / 16 / 24 / 32 / 50 的密度区间。
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

from PySide6.QtGui import QTextCursor, QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle, parse_markdown  # noqa: E402
from probe_group_sweep import structural_count  # noqa: E402

TABLE = """| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `README.md` | 文档 | 项目用途与运行方式 |
| `src/` | 目录 | 源代码 |"""

CODE = """```python
def build_report(rows):
    return sorted(rows, key=lambda r: r["total"], reverse=True)
```"""


def density_md(turns, table_every, code_every, quote_every=0, h2_every=0):
    """按固定间隔稀释结构块，得到可控的 S/N。"""
    parts = []
    for t in range(turns):
        parts.append("第 %d 轮回复：先读 README，再看依赖。" % t)
        if table_every and t % table_every == table_every - 1:
            parts.append(TABLE)
        if code_every and t % code_every == code_every - 1:
            parts.append(CODE)
        if quote_every and t % quote_every == quote_every - 1:
            parts.append("> 引用 %d" % t)
        if h2_every and t % h2_every == h2_every - 1:
            parts.append("## 小节 %d" % t)
    return "\n\n".join(parts)


CASES = {
    "d06": lambda n: density_md(n, 16, 0),            # 每 16 段一张表
    "d20": lambda n: density_md(n, 8, 8),             # 每 8 段 表 + 代码
    "d43": lambda n: density_md(n, 4, 4, 4),          # 每 4 段 表 + 代码 + 引用
    "d67": lambda n: density_md(n, 2, 2, 2, 2),       # 每 2 段 表 + 代码 + 引用 + h2
}
TURNS = (30, 120, 400, 1200)
GROUPS = (12, 16, 24, 32, 50)


def render_whole(blocks, style):
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    mdoc._Renderer(doc, style, 676.0, None).render_blocks(blocks, QTextCursor(doc))
    mdoc._collapse_edge_margins(doc)
    return doc


def render_chunked(blocks, style, group):
    saved = mdoc._CHUNK_BLOCKS
    mdoc._CHUNK_BLOCKS = group
    try:
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        mdoc._render_chunked(doc, blocks, style, 676.0, None)
        mdoc._collapse_edge_margins(doc)
        return doc
    finally:
        mdoc._CHUNK_BLOCKS = saved


def best_of(fn, repeats=3):
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        best = min(best, (time.perf_counter() - start) * 1000.0)
    return round(best, 1)


def main():
    QApplication.instance() or QApplication([])
    style = BodyStyle()
    out = {}
    for name, build in CASES.items():
        for turns in TURNS:
            blocks = parse_markdown(build(turns))
            s, n = structural_count(blocks), len(blocks)
            row = {"N": n, "S": s, "density": round(s / max(1, n), 3), "SxN": s * n}
            row["whole"] = best_of(lambda b=blocks: render_whole(b, style))
            for group in GROUPS:
                row["g%d" % group] = best_of(lambda b=blocks, g=group: render_chunked(b, style, g))
            best_group = min(GROUPS, key=lambda g: row["g%d" % g])
            row["best_group"] = best_group
            row["best_chunked"] = row["g%d" % best_group]
            out["%s_t%d" % (name, turns)] = row
            print("%-10s N=%-6d S=%-5d S*N=%-9d whole=%-9.1f %s  best=g%-3d" % (
                "%s_t%d" % (name, turns), n, s, s * n, row["whole"],
                "  ".join("g%-3d=%-8.1f" % (g, row["g%d" % g]) for g in GROUPS), best_group),
                flush=True)
    print("CALIB " + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
