"""分种类的二次成本系数：表格 / 代码 / 引用 / h2 横线各值多少。

自适应判据要回答「这篇文档值不值得分块」，而结构性插入的单价与种类有关：
``insertTable``（引用、代码块、表格都走它）和 ``insertFrame``（h2 横线、分隔线）
不是同一个写入路径。这里把每种结构单独稀释进同样规模的段落里，量整篇 vs 分组 32，
扣掉纯段落的分块固定开销后，反推每「结构块 × 文档规模」的成本系数。

系数 = (整篇 - 分块 + 分块固定开销) / (S * (N - G) / 2)，单位 ms。
只读源码、不改行为。
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

QUOTE = "> 引用里带 **粗体** 与 `代码`"

HR = "---"

H2 = "## 小节"


def doc_with(kind: str, turns: int, every: int):
    """每 ``every`` 段插一个结构块；其余是纯段落。"""
    parts = []
    for t in range(turns):
        parts.append("第 %d 段正文：先读 README，再看依赖。" % t)
        if every and t % every == every - 1:
            parts.append({"table": TABLE, "code": CODE, "quote": QUOTE,
                          "hr": HR, "h2": H2}[kind])
    return "\n\n".join(parts)


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


CASES = (
    ("para", 600, 0),
    ("table", 600, 4),
    ("code", 600, 4),
    ("quote", 600, 4),
    ("hr", 600, 4),
    ("h2", 600, 4),
)
GROUP = 32


def main():
    QApplication.instance() or QApplication([])
    style = BodyStyle()
    rows = {}
    for name, turns, every in CASES:
        blocks = parse_markdown(doc_with(name, turns, every))
        s, n = structural_count(blocks), len(blocks)
        whole = best_of(lambda b=blocks: render_whole(b, style))
        chunked = best_of(lambda b=blocks: render_chunked(b, style, GROUP))
        rows[name] = {"N": n, "S": s, "whole": whole, "g32": chunked,
                      "gain": round(whole - chunked, 1)}
        print("%-6s N=%-5d S=%-5d whole=%-9.1f g32=%-9.1f gain=%-8.1f"
              % (name, n, s, whole, chunked, whole - chunked), flush=True)

    # 纯段落那一行的「负增益」就是分块固定开销（拼接 + 每块新文档 + 光标）。
    overhead = -rows["para"]["gain"]
    rows["para"]["overhead_per_chunk_ms"] = round(
        overhead / max(1, rows["para"]["N"] // GROUP), 3)
    for name in ("table", "code", "quote", "hr", "h2"):
        row = rows[name]
        s, n = row["S"], row["N"]
        denom = s * (n - GROUP) / 2.0
        row["coefficient_ms"] = round((row["gain"] + overhead) / denom, 6) if denom else None
        row["weight_vs_table"] = None
    base = rows["table"].get("coefficient_ms") or 1.0
    for name in ("table", "code", "quote", "hr", "h2"):
        row = rows[name]
        if row.get("coefficient_ms"):
            row["weight_vs_table"] = round(row["coefficient_ms"] / base, 2)
    print("KIND " + json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    main()
