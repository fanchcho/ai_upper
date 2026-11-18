"""分组大小 × 文档结构 × 规模：只量渲染器（不含 Markdown 解析）。

自适应分组的判据必须来自「结构块数量」而不是总块数：二次成本只由结构性插入
（表格 / 代码表 / 引用表 / h2 横线 frame）产生，纯段落文档的整篇路径是线性的。
这里把三份不同密度的文档在同一进程里跑多个分组，输出可直接拟合的耗时。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextCursor, QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle, parse_markdown  # noqa: E402

CODE = """```python
def build_report(rows):
    out = []
    for row in rows:
        out.append({"name": row.name, "total": sum(row.values)})
    return sorted(out, key=lambda r: r["total"], reverse=True)
```"""

TABLE = """| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `README.md` | 文档 | 项目用途与运行方式 |
| `src/` | 目录 | 源代码 |"""


def para_md(turns):
    return "\n\n".join(
        "第 %d 轮提问：请把结果整理成要点。\n\n第 %d 轮回复：先读 README，再看依赖。" % (t, t)
        for t in range(turns)
    )


def mixed_md(turns):
    return "\n\n".join(
        "## 用户\n\n第 %d 轮：请整理结果。\n\n> 引用\n\n## 助手\n\n第 %d 轮回复。\n\n%s\n\n%s"
        % (t, t, CODE, TABLE)
        for t in range(turns)
    )


def struct_md(turns):
    return "\n\n".join("%s\n\n%s\n\n> 引用 %d" % (TABLE, CODE, t) for t in range(turns))


def para_table_md(turns):
    """每 8 段才一张表：低密度但非零。"""
    parts = []
    for t in range(turns):
        parts.append("第 %d 轮回复：先读 README，再看依赖。" % t)
        if t % 8 == 7:
            parts.append(TABLE)
    return "\n\n".join(parts)


DOCS = {"para": para_md, "sparse": para_table_md, "mixed": mixed_md, "struct": struct_md}
GROUPS = (10, 16, 24, 32, 50, 75, 100, 200)


def structural_count(blocks):
    """会走结构性插入的顶层块数（含引用内部嵌套）。"""
    total = 0
    for block in blocks:
        kind = block.get("type")
        if kind in ("table", "code", "quote", "hr"):
            total += 1
            if kind == "quote":
                total += structural_count(block.get("children") or [])
        elif kind == "heading" and int(block.get("level") or 1) == 2:
            total += 1
    return total


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
    doc = None
    for _ in range(repeats):
        start = time.perf_counter()
        doc = fn()
        best = min(best, (time.perf_counter() - start) * 1000.0)
    return round(best, 1), doc


def main():
    QApplication.instance() or QApplication([])
    style = BodyStyle()
    out = {}
    for name, build in DOCS.items():
        for turns in (12, 30, 120, 400):
            blocks = parse_markdown(build(turns))
            key = "%s_t%d" % (name, turns)
            row = {"blocks": len(blocks), "structural": structural_count(blocks)}
            row["whole"], whole = best_of(lambda b=blocks: render_whole(b, style))
            out[key] = row
            print("%-12s N=%-5d S=%-5d whole=%-9.1f"
                  % (key, row["blocks"], row["structural"], row["whole"]), end="", flush=True)
            for group in GROUPS:
                took, doc = best_of(lambda b=blocks, g=group: render_chunked(b, style, g))
                row["g%d" % group] = took
                row["g%d_blocks" % group] = doc.blockCount()
                print("  g%-3d=%-9.1f" % (group, took), end="", flush=True)
            row["whole_blocks"] = whole.blockCount()
            print(flush=True)
            out[key] = row
    print("SWEEP " + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
