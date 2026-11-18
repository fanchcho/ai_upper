"""真实渲染路径的保真比对：分块路径（render_markdown 实走）vs 整篇路径。

整篇基准 = 把 `_CHUNK_BLOCKS` 临时提到极大，迫使走原路径；两者都在同一进程、
同一 style/宽度下渲染。逐块比较：文本、块格式（边距/行高/对齐/缩进/制表位/属性）、
每个字符片的字体/字号/字重/斜体/前景色/背景色/图片名；另比表格形状与文档总尺寸。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path("/home/agent/shared_workspace/ai_upper")
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import (  # noqa: E402
    QImage,
    QTextCursor,
    QTextDocument,
    QTextTable,
)
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle, render_markdown  # noqa: E402

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


def _fmt_tuple(fmt):
    return (
        round(fmt.topMargin(), 4), round(fmt.bottomMargin(), 4),
        round(fmt.leftMargin(), 4), round(fmt.rightMargin(), 4),
        round(fmt.textIndent(), 4), round(fmt.lineHeight(), 4), fmt.lineHeightType(),
        fmt.alignment(), fmt.indent(), tuple(round(tp.position, 4) for tp in fmt.tabPositions()),
        tuple(sorted((p, str(fmt.property(p))) for p in fmt.properties()
                     if p >= 0x100000)),
    )


def block_sig(block):
    rows = []
    for spec in block.textFormats():
        f = spec.format
        img = f.toImageFormat().name() if f.isImageFormat() else None
        rows.append((spec.start, spec.length, img,
                     f.font().family(), f.font().pixelSize(), int(f.font().weight()),
                     f.font().italic(),
                     f.foreground().color().name() if f.foreground().style() else None,
                     f.background().color().name() if f.background().style() else None))
    return (block.text(), _fmt_tuple(block.blockFormat()), tuple(rows))


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


def strip_user_state(html):
    out = []
    for line in html.splitlines():
        if "user-state" in line:
            continue
        out.append(line)
    return "\n".join(out)


def main():
    app = QApplication.instance() or QApplication([])
    style = BodyStyle()
    image = QImage(12, 8, QImage.Format.Format_RGB32)
    image.fill(0xFF3366CC)
    resolver = lambda src: image if src.startswith("my://") else None  # noqa: E731

    result = {}
    for turns in (5, 12, 30, 60, 120):
        md = make_md(turns)
        saved = mdoc._CHUNK_BLOCKS
        mdoc._CHUNK_BLOCKS = 10 ** 9
        whole = render_markdown(QTextDocument(), md, style, content_width=676.0,
                                image_resolver=resolver)
        mdoc._CHUNK_BLOCKS = saved
        chunked = render_markdown(QTextDocument(), md, style, content_width=676.0,
                                  image_resolver=resolver)
        for doc in (whole, chunked):
            doc.setTextWidth(696.0)
            doc.documentLayout()

        dw, dc = describe(whole), describe(chunked)
        diffs = [i for i, (a, b) in enumerate(zip(dw, dc)) if a != b]
        key = "turns_%d" % turns
        result[key] = {
            "blocks": [whole.blockCount(), chunked.blockCount()],
            "chars": [whole.characterCount(), chunked.characterCount()],
            "text_eq": whole.toPlainText() == chunked.toPlainText(),
            "n_diffs": len(diffs),
            "diff_indexes": diffs[:6],
            "tables_eq": tables(whole) == tables(chunked),
            "n_tables": len(tables(whole)),
            "size": [round(whole.size().width(), 4), round(whole.size().height(), 4),
                     round(chunked.size().width(), 4), round(chunked.size().height(), 4)],
            "height_eq": whole.size().height() == chunked.size().height(),
            "margin": [whole.documentMargin(), chunked.documentMargin()],
            "html_eq_after_strip": strip_user_state(whole.toHtml()) == strip_user_state(chunked.toHtml()),
            "html_len": [len(whole.toHtml()), len(chunked.toHtml())],
        }
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
