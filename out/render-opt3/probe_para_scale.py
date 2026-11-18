"""纯段落文档 vs 结构密集文档：整篇路径与分块路径的耗时随规模怎么变。

用来坐实上一轮报告 §7.3 的说法——「纯段落文档几乎没有二次成本，分块反而多花拼接
开销（12 轮 1.22× 已接近临界）」，并给自适应分组找判据。

三份文档（同一份 BodyStyle、同一 content_width=676）：
- ``para``：每轮只有两段纯文本，没有任何结构性插入（无表格、无 frame、无 h2 横线）；
- ``mixed``：与 `probe_heavy` 同构（h2 + 横线 frame + 引用表 + 代码表 + 表格）；
- ``struct``：只有结构块，段落极少（压力方向相反）。

每份文档在若干规模下分别量：整篇路径（``_CHUNK_BLOCKS = 10**9``）、分组 50、
分组 25。每组取 3 次最小值，输出 JSON。
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

from PySide6.QtGui import QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle, render_markdown  # noqa: E402

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


DOCS = {"para": para_md, "mixed": mixed_md, "struct": struct_md}


def timed(md_text, style, group):
    saved = mdoc._CHUNK_BLOCKS
    mdoc._CHUNK_BLOCKS = group
    best = float("inf")
    doc = None
    for _ in range(3):
        start = time.perf_counter()
        doc = render_markdown(QTextDocument(), md_text, style, 676.0, None)
        best = min(best, (time.perf_counter() - start) * 1000.0)
    mdoc._CHUNK_BLOCKS = saved
    return round(best, 1), doc


def main():
    QApplication.instance() or QApplication([])
    style = BodyStyle()
    out = {}
    for name, build in DOCS.items():
        for turns in (12, 30, 120, 400):
            text = build(turns)
            blocks = mdoc.parse_markdown(text)
            structural = sum(
                1 for b in blocks
                if b.get("type") in ("table", "code", "quote", "hr")
                or (b.get("type") == "heading" and int(b.get("level") or 1) == 2)
            )
            row = {"blocks": len(blocks), "structural": structural,
                   "density": round(structural / max(1, len(blocks)), 3)}
            for label, group in (("whole", 10 ** 9), ("g50", 50), ("g25", 25)):
                took, doc = timed(text, style, group)
                row[label] = took
                row[label + "_blocks"] = doc.blockCount()
            row["speedup_g50"] = round(row["whole"] / row["g50"], 2)
            row["speedup_g25"] = round(row["whole"] / row["g25"], 2)
            out["%s_t%d" % (name, turns)] = row
            print("%-14s blocks=%-6d struct=%-5d whole=%-9.1f g50=%-9.1f g25=%-9.1f g50×%.2f"
                  % ("%s_t%d" % (name, turns), row["blocks"], structural,
                     row["whole"], row["g50"], row["g25"], row["speedup_g50"]),
                  flush=True)
    print("PARA " + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
