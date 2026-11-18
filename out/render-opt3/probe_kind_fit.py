"""结构性插入的二次系数：按种类，用两个规模直接拟合。

上一版只在一个规模上比整篇 vs 分块，差值只有几毫秒、被噪声淹没。这里改成
直接量整篇路径在两个规模下的耗时：同一「每 4 段一个结构块」的稀释方式下，
纯段落基线随 N 线性增长，结构块那部分是 ``b * S * N``。两档规模各解一次 b，
两档一致才说明模型成立；不一致就说明还有别的项，判据不能只用它。
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


def doc_with(kind, turns, every=4):
    parts = []
    for t in range(turns):
        parts.append("第 %d 段正文：先读 README，再看依赖。" % t)
        if kind != "para" and every and t % every == every - 1:
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


SCALES = (1200, 2400)
KINDS = ("para", "table", "code", "quote", "hr", "h2")
GROUP = 16


def main():
    QApplication.instance() or QApplication([])
    style = BodyStyle()
    data = {}
    for kind in KINDS:
        for turns in SCALES:
            blocks = parse_markdown(doc_with(kind, turns))
            s, n = structural_count(blocks), len(blocks)
            key = "%s_t%d" % (kind, turns)
            whole = best_of(lambda b=blocks: render_whole(b, style))
            chunked = best_of(lambda b=blocks: render_chunked(b, style, GROUP))
            data[key] = {"N": n, "S": s, "whole": whole, "g16": chunked,
                         "gain": round(whole - chunked, 1)}
            print("%-10s N=%-5d S=%-5d whole=%-9.1f g16=%-9.1f gain=%-8.1f"
                  % (key, n, s, whole, chunked, whole - chunked), flush=True)

    # 每个规模上：结构成本 = 整篇(该类) - 整篇(纯段落同规模)，b = 成本 / (S*N)
    fit = {}
    for turns in SCALES:
        base = data["para_t%d" % turns]["whole"]
        for kind in KINDS[1:]:
            row = data["%s_t%d" % (kind, turns)]
            cost = row["whole"] - base
            s, n = row["S"], row["N"]
            fit.setdefault(kind, {})[turns] = {
                "structural_ms": round(cost, 1),
                "b_ms_per_block2": round(cost / (s * n), 7) if s * n else None,
            }
        para = data["para_t%d" % turns]
        fit.setdefault("para", {})[turns] = {
            "per_block_ms": round(para["whole"] / para["N"], 5),
            "chunk_overhead_ms": round(para["g16"] - para["whole"], 1),
            "chunks": para["N"] // GROUP,
        }
    print("FIT " + json.dumps(fit, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
