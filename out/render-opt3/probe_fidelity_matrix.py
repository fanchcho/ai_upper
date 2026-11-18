"""保真矩阵（render-opt3）：轮数 × 分组，含 RICH 图片文档，逐块 + toHtml 比对。

与 render-chunking 的旧探针的区别：
- 分组由 ``_chunk_plan`` 的真实判据决定，逐档扫描 5/16/25/50/100 与「计划值」；
- 每一格都断言「整篇 vs 分块」逐块签名、表格形状、文档高度、``toHtml()`` 全等；
- 轮数覆盖 5/12/30/60/120/400，既有一组内的小文档也有跨多组的大文档。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage, QTextDocument, QTextTable  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle, parse_markdown, render_markdown  # noqa: E402

CODE = """```python
def build_report(rows):
    out = []
    for row in rows:
        out.append({"name": row.name, "total": sum(row.values)})
    return sorted(out, key=lambda r: r["total"], reverse=True)
```
"""

TABLE = """
| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `README.md` | 文档 | 项目用途与运行方式 |
| `src/` | 目录 | 源代码 |
| `package.json` | 配置 | 依赖清单 |
"""

RICH = """### 小结

> 引用里有 **粗体** 与 `代码`
>
> > 嵌套引用第二层

- 一级
  - 二级
1. 有序一
2. 有序二

- [x] 完成
- [ ] 未完成

![图](my://pic)

| 键 | 值 |
| --- | --- |
| a | 1 |
"""


def turn_md(t):
    return ("## 用户\n\n第 %d 轮：请整理结果。\n\n%s\n\n## 助手\n\n第 %d 轮回复。\n\n%s\n\n%s"
            % (t, RICH, t, CODE, TABLE))


def make_md(turns):
    return "\n\n".join(turn_md(t) for t in range(turns))


def make_dense_md(turns):
    """每轮两张表 + 代码 + 引用：密度 > 0.40，专门驱动「高密度分组」（现在是 32）。"""
    return "\n\n".join(
        "第 %d 轮：请整理结果。\n\n%s\n\n%s\n\n> 引用 **粗**\n>\n> > 嵌套"
        % (t, TABLE, TABLE) for t in range(turns))


def fmt_tuple(fmt):
    return (
        round(fmt.topMargin(), 4), round(fmt.bottomMargin(), 4),
        round(fmt.leftMargin(), 4), round(fmt.rightMargin(), 4),
        round(fmt.textIndent(), 4), round(fmt.lineHeight(), 4), fmt.lineHeightType(),
        fmt.alignment(), fmt.indent(),
        tuple(round(tp.position, 4) for tp in fmt.tabPositions()),
        tuple(sorted((p, str(fmt.property(p))) for p in fmt.properties() if p >= 0x100000)),
    )


def block_sig(block):
    rows = []
    for spec in block.textFormats():
        f = spec.format
        rows.append((spec.start, spec.length,
                     f.toImageFormat().name() if f.isImageFormat() else None,
                     f.font().family(), f.font().pixelSize(), int(f.font().weight()),
                     f.font().italic(),
                     f.foreground().color().name() if f.foreground().style() else None,
                     f.background().color().name() if f.background().style() else None))
    return block.text(), fmt_tuple(block.blockFormat()), tuple(rows)


def describe(doc):
    out, block = [], doc.begin()
    while block.isValid():
        out.append(block_sig(block))
        block = block.next()
    return out


def tables(doc):
    found, stack = [], [doc.rootFrame()]
    while stack:
        frame = stack.pop()
        if isinstance(frame, QTextTable):
            found.append((frame.rows(), frame.columns(),
                          round(frame.format().width().rawValue(), 3),
                          round(frame.format().margin(), 3),
                          frame.format().border(), frame.format().cellSpacing()))
        it = frame.begin()
        while not it.atEnd():
            child = it.currentFrame()
            if child is not None:
                stack.append(child)
            it += 1
    return found


def render(md, style, resolver, group=None):
    saved_plan = mdoc._chunk_plan
    saved_blocks = mdoc._CHUNK_BLOCKS
    if group == "whole":
        mdoc._chunk_plan = lambda blocks: 0
    elif group is not None:
        mdoc._chunk_plan = lambda blocks: group
    try:
        doc = render_markdown(QTextDocument(), md, style, content_width=676.0,
                              image_resolver=resolver)
    finally:
        mdoc._chunk_plan = saved_plan
        mdoc._CHUNK_BLOCKS = saved_blocks
    doc.setTextWidth(696.0)
    doc.documentLayout()
    return doc


def main():
    app = QApplication.instance() or QApplication([])
    style = BodyStyle()
    image = QImage(12, 8, QImage.Format.Format_RGB32)
    image.fill(0xFF3366CC)
    resolver = lambda src: image if src.startswith("my://") else None  # noqa: E731

    matrix = {}
    failures = []
    for doc_name, build in (("rich", make_md), ("dense", make_dense_md)):
        for turns in (5, 12, 30, 60, 120, 400):
            md = build(turns)
            blocks = parse_markdown(md)
            planned = mdoc._chunk_plan(blocks)
            base = render(md, style, resolver, "whole")
            row = {"blocks": len(blocks), "planned_group": planned}
            for group in ("whole", 5, 16, 25, 50, 100, "planned"):
                if group == "planned" and planned <= 0:
                    row["planned"] = "whole-path"
                    continue
                effective = planned if group == "planned" else group
                doc = base if group == "whole" else render(md, style, resolver, effective)
                sig_eq = describe(base) == describe(doc)
                html_eq = base.toHtml() == doc.toHtml()
                row[str(group)] = {
                    "blocks": doc.blockCount(),
                    "sig_eq": sig_eq,
                    "tables_eq": tables(base) == tables(doc),
                    "height_eq": base.size().height() == doc.size().height(),
                    "html_eq": html_eq,
                }
                if not (sig_eq and html_eq and row[str(group)]["tables_eq"]
                        and row[str(group)]["height_eq"]):
                    failures.append("%s turns=%d group=%s" % (doc_name, turns, group))
            matrix["%s_turns_%d" % (doc_name, turns)] = row
            print("%-5s turns=%-4d blocks=%-5d density=%.2f planned=%s" % (
                doc_name, turns, len(blocks),
                mdoc._structural_load(blocks) / len(blocks), planned), flush=True)

    print("FIDELITY " + json.dumps({"matrix": matrix, "failures": failures},
                                   ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
