"""渲染器热路径计数与计时：颜色解析 / 字体构造 / 行高换算 / 行内片段。

目的：在动手前判定「剩余路径」（代码块、hairline、段落与 inline）里哪些是
可省的重复工作，哪些是 Qt 必须付出的成本。只计数不改行为，不写源码。
"""
from __future__ import annotations

import collections
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFontMetricsF, QTextCursor, QTextDocument  # noqa: E402
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
| `src/` | 目录 | 源代码 |
| `package.json` | 配置 | 依赖清单 |"""


def mixed_md(turns):
    return "\n\n".join(
        "## 用户\n\n第 %d 轮：请整理结果。\n\n> 引用里有 **粗体** 与 `代码`\n\n"
        "## 助手\n\n第 %d 轮回复。\n\n- 一级\n  - 二级\n\n%s\n\n%s" % (t, t, CODE, TABLE)
        for t in range(turns)
    )


def main():
    app = QApplication.instance() or QApplication([])
    style = BodyStyle()
    blocks = parse_markdown(mixed_md(400))

    counts = collections.Counter()
    times = collections.Counter()

    real_css = mdoc.css_color
    def css(value):
        start = time.perf_counter()
        out = real_css(value)
        times["css_color"] += (time.perf_counter() - start) * 1000.0
        counts["css_color"] += 1
        return out
    mdoc.css_color = css

    real_metrics = mdoc.QFontMetricsF
    class Metrics(real_metrics):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            counts["QFontMetricsF"] += 1
    mdoc.QFontMetricsF = Metrics

    renderer_font = mdoc._Renderer.font
    def font(self, *args, **kwargs):
        start = time.perf_counter()
        out = renderer_font(self, *args, **kwargs)
        times["font"] += (time.perf_counter() - start) * 1000.0
        counts["font"] += 1
        return out
    mdoc._Renderer.font = font

    line_height = mdoc._Renderer.line_height
    def lh(self, px, factor):
        start = time.perf_counter()
        out = line_height(self, px, factor)
        times["line_height"] += (time.perf_counter() - start) * 1000.0
        counts["line_height"] += 1
        return out
    mdoc._Renderer.line_height = lh

    for name in ("_heading", "_paragraph", "_list", "_quote", "_table", "_code", "_rule",
                 "_inline", "_hairline", "_code_head", "_cell_edges"):
        real = getattr(mdoc._Renderer, name)
        def wrapper(self, *args, _real=real, _name=name, **kwargs):
            start = time.perf_counter()
            out = _real(self, *args, **kwargs)
            times["kind:" + _name] += (time.perf_counter() - start) * 1000.0
            counts["kind:" + _name] += 1
            return out
        setattr(mdoc._Renderer, name, wrapper)

    best = None
    for _ in range(3):
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        start = time.perf_counter()
        mdoc._Renderer(doc, style, 676.0, None).render_blocks(blocks, QTextCursor(doc))
        mdoc._collapse_edge_margins(doc)
        took = (time.perf_counter() - start) * 1000.0
        best = took if best is None else min(best, took)
        for key in list(times):
            times[key] = 0.0

    counts_by_pass = {k: v // 3 for k, v in counts.items()}
    print(json.dumps({
        "blocks": len(blocks),
        "render_ms_min": round(best, 1),
        "counts_per_pass": counts_by_pass,
        "calls": {k: counts_by_pass.get(k, 0) for k in
                  ("css_color", "QFontMetricsF", "font", "line_height")},
    }, ensure_ascii=False, indent=1))

    # 单独再跑一趟，只累计时间（避免 min 那趟把累计清零后只剩最后一次）
    times.clear()
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    start = time.perf_counter()
    mdoc._Renderer(doc, style, 676.0, None).render_blocks(blocks, QTextCursor(doc))
    mdoc._collapse_edge_margins(doc)
    total = (time.perf_counter() - start) * 1000.0
    print(json.dumps({
        "total_ms": round(total, 1),
        "times_ms": {k: round(v, 1) for k, v in sorted(times.items())},
        "sum_instrumented": round(sum(v for k, v in times.items() if not k.startswith("kind:")), 1),
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
