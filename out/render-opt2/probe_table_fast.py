"""表格路径候选实现的「改动前 / 一次插满行 / 边框只写表格级 / 落地版」四方对照。

基线固定为 git 里的改动前实现（``probe_old_table.apply`` 换成 ``HEAD`` 版
``_table``/``_table_row``/``_apply_cell_borders``），再在同一份 Markdown、同一
``BodyStyle``、同一宽度下渲染四个版本，逐块比格式、逐格比单元格格式、比
``toHtml()``。用途有两个：

1. 证明「边框只写整表、指望单元格继承」是**不等价**的（§3.3），不能为省时间采用；
2. 证明落地版（一次插满行 + 边框并入同一次 setFormat）与改动前**逐字节等价**。

用法：``python probe_table_fast.py``
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path("/home/agent/shared_workspace/ai_upper")
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextCursor, QTextDocument, QTextTable  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle  # noqa: E402
import probe_old_table  # noqa: E402

TABLE = """
| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `README.md` | 文档 | 项目用途与运行方式 |
| `src/` | 目录 | 源代码 |
| `package.json` | 配置 | 依赖清单 |
| a | b | c |
| d | e | f |
"""

CODE = """```python
def f(rows):
    return sorted(rows, key=lambda r: r["total"], reverse=True)
```
"""


def turn_md(t):
    return "## 用户\n\n第 %d 轮\n\n%s\n\n## 助手\n\n第 %d 轮答复\n\n%s" % (t, TABLE, t, CODE)


def make_md(turns):
    return "\n\n".join(turn_md(t) for t in range(turns))


def ms(fn):
    start = time.perf_counter()
    value = fn()
    return (time.perf_counter() - start) * 1000.0, value


def signature(doc):
    """逐块签名：文本 + 块格式 + 每个字符片的字体/字重/颜色/图片名。"""
    out, block = [], doc.begin()
    while block.isValid():
        fmt = block.blockFormat()
        runs = []
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            char_fmt = fragment.charFormat()
            runs.append((
                fragment.position(), fragment.length(),
                char_fmt.fontFamilies(), char_fmt.fontWeight(), char_fmt.foreground().color().name(),
                char_fmt.background().color().name(),
                char_fmt.toImageFormat().name() if char_fmt.isImageFormat() else None,
            ))
            iterator += 1
        out.append((
            block.text(),
            (round(fmt.leftMargin(), 3), round(fmt.rightMargin(), 3),
             round(fmt.topMargin(), 3), round(fmt.bottomMargin(), 3),
             round(fmt.lineHeight(), 3), int(fmt.lineHeightType()),
             int(fmt.alignment()), int(fmt.indent()), int(fmt.headingLevel()),
             tuple(sorted((p, str(fmt.property(p))) for p in fmt.properties() if p >= 0x100000))),
            tuple(runs),
        ))
        block = block.next()
    return out


def cells(doc):
    """逐格快照：行列位置 + 四边边框宽度/样式/画刷 + 四向内边距 + 底色。"""
    found, stack = [], [doc.rootFrame()]
    while stack:
        frame = stack.pop()
        if isinstance(frame, QTextTable):
            for row in range(frame.rows()):
                for column in range(frame.columns()):
                    cf = mdoc.QTextTableCellFormat(frame.cellAt(row, column).format())
                    found.append((
                        row, column,
                        cf.leftBorder(), cf.rightBorder(), cf.topBorder(), cf.bottomBorder(),
                        cf.leftBorderStyle(), cf.rightBorderStyle(),
                        cf.topBorderStyle(), cf.bottomBorderStyle(),
                        cf.leftBorderBrush().color().name(),
                        cf.topBorderBrush().color().name(),
                        round(cf.leftPadding(), 3), round(cf.rightPadding(), 3),
                        round(cf.topPadding(), 3), round(cf.bottomPadding(), 3),
                        cf.background().color().name() if cf.background().style() else None,
                    ))
        iterator = frame.begin()
        while not iterator.atEnd():
            child = iterator.currentFrame()
            if child is not None:
                stack.append(child)
            iterator += 1
    return found


def render_with(renderer_cls, md, style, width):
    doc = QTextDocument()
    doc.clear()
    doc.setDocumentMargin(0)
    renderer = renderer_cls(doc, style, width, None)
    renderer.render_blocks(mdoc.parse_markdown(md), QTextCursor(doc))
    mdoc._collapse_edge_margins(doc)
    return doc


def main():
    app = QApplication.instance() or QApplication([])
    style = BodyStyle()

    # 先取出落地版实现（当前源码），再把 ``_Renderer`` 换回 HEAD。
    current_table = mdoc._Renderer._table
    current_row = mdoc._Renderer._table_row
    probe_old_table.apply(mdoc, "HEAD")
    old_cls = mdoc._Renderer
    old_table = old_cls._table
    old_row = old_cls._table_row
    old_borders = old_cls._apply_cell_borders

    class OnceInsert(old_cls):
        """A：一次插满行，边框仍走第二遍整表遍历（即改动前的边框写法）。"""

        def _table(self, cursor, block):
            header = block.get("header") or []
            if not header:
                return
            self._insert_full_table(cursor, block)
            table = self._inserted_table
            old_borders.__get__(self)(table)
            self._after_frame(cursor, table.lastPosition() + 1)

    class TableLevelBorderOnly(old_cls):
        """B：一次插满行，边框只写在整表格式上，单元格不写（看是否继承）。"""

        def _table(self, cursor, block):
            header = block.get("header") or []
            if not header:
                return
            self._insert_full_table(cursor, block)
            self._after_frame(cursor, self._inserted_table.lastPosition() + 1)

    def _insert_full_table(self, cursor, block):
        header = block.get("header") or []
        rows = block.get("rows") or []
        align = list(block.get("align") or ["left"] * len(header))
        if self._has_content:
            cursor.insertBlock()
        table_fmt = mdoc.QTextTableFormat()
        table_fmt.setBorder(1.0)
        table_fmt.setBorderBrush(mdoc.QtGui.QBrush(self.color(self.palette.border)))
        table_fmt.setCellSpacing(0.0)
        table_fmt.setCellPadding(0.0)
        table_fmt.setBorderCollapse(True)
        table_fmt.setMargin(12.0)
        table_fmt.setAlignment(mdoc.ALIGN_LEFT)
        table = cursor.insertTable(1 + len(rows), len(header), table_fmt)
        self._table_row(table, 0, header, align, header_row=True)
        for row_index, row in enumerate(rows, start=1):
            self._table_row(table, row_index, row, align, header_row=False)
        self._inserted_table = table

    class Landed(old_cls):
        """落地版：一次插满行 + 边框并入 ``_table_row`` 的同一次 setFormat。"""

    for cls in (OnceInsert, TableLevelBorderOnly):
        cls._insert_full_table = _insert_full_table
    # 旧 ``_table_row`` 不写边框，正是 B 组需要的前提。
    Landed._table = current_table
    Landed._table_row = current_row

    out = {}
    for turns in (12, 60):
        md = make_md(turns)
        base_ms, base = ms(lambda: render_with(old_cls, md, style, 676.0))
        once_ms, once = ms(lambda: render_with(OnceInsert, md, style, 676.0))
        inh_ms, inh = ms(lambda: render_with(TableLevelBorderOnly, md, style, 676.0))
        landed_ms, landed = ms(lambda: render_with(Landed, md, style, 676.0))

        sb = signature(base)
        s_once, s_inh, s_landed = signature(once), signature(inh), signature(landed)
        cb, c_once, c_inh, c_landed = cells(base), cells(once), cells(inh), cells(landed)

        def diffs(s):
            return [i for i, (a, b) in enumerate(zip(sb, s)) if a != b]

        out["t%d" % turns] = {
            "ms": {"before": round(base_ms, 1), "once_insert": round(once_ms, 1),
                   "table_level_border_only": round(inh_ms, 1), "landed": round(landed_ms, 1)},
            "blocks": [base.blockCount(), once.blockCount(), inh.blockCount(), landed.blockCount()],
            "chars": [base.characterCount(), once.characterCount(),
                      inh.characterCount(), landed.characterCount()],
            "sig_diffs_once": len(diffs(s_once)),
            "sig_diffs_table_level": len(diffs(s_inh)),
            "sig_diffs_landed": len(diffs(s_landed)),
            "cells_eq_once": cb == c_once,
            "cells_eq_table_level": cb == c_inh,
            "cells_eq_landed": cb == c_landed,
            "html_eq_once": base.toHtml() == once.toHtml(),
            "html_eq_table_level": base.toHtml() == inh.toHtml(),
            "html_eq_landed": base.toHtml() == landed.toHtml(),
            "n_cells": [len(cb), len(c_once), len(c_inh), len(c_landed)],
        }
        if diffs(s_inh):
            out["t%d" % turns]["table_level_sample"] = (
                "first cell with borders in baseline:", cb[:1], "table-level variant:", c_inh[:1])
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
