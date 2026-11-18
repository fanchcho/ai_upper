"""`_apply_cell_borders` 拆解：读格式 / 写格式各占多少，能否用预置格式替代读-改-写。"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path("/home/agent/shared_workspace/ai_upper")
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import (QTextCursor, QTextDocument, QTextFrameFormat,  # noqa: E402
                           QTextTable, QTextTableCellFormat)
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle  # noqa: E402

TABLE = """
| a | b | c |
| --- | --- | --- |
| 1 | 2 | 3 |
| 4 | 5 | 6 |
| 7 | 8 | 9 |
| 10 | 11 | 12 |
| 13 | 14 | 15 |
| 16 | 17 | 18 |
| 19 | 20 | 21 |
| 22 | 23 | 24 |
"""


def make_md(turns):
    return "\n\n".join("## 用户\n\n第 %d 轮\n\n%s" % (t, TABLE) for t in range(turns))


def tables(doc):
    out, stack = [], [doc.rootFrame()]
    while stack:
        frame = stack.pop()
        if isinstance(frame, QTextTable):
            out.append(frame)
        it = frame.begin()
        while not it.atEnd():
            child = it.currentFrame()
            if child is not None:
                stack.append(child)
            it += 1
    return out


def render(md, style, cls=None):
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    renderer = (cls or mdoc._Renderer)(doc, style, 676.0, None)
    renderer.render_blocks(mdoc.parse_markdown(md), QTextCursor(doc))
    mdoc._collapse_edge_margins(doc)
    return doc


class Precomputed(mdoc._Renderer):
    """按「表头 / 偶数行 / 奇数行」三种格式预置，写的时候不再读 cell.format()。"""

    def _table(self, cursor, block):
        header = block.get("header") or []
        rows = block.get("rows") or []
        if not header:
            return
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
        # 预置三种单元格格式：表头、偶数行（斑马底）、奇数行。
        # 以奇数行（无底色）那格做模板，其余属性与 _table_row 写出来的保持一致。
        base = QTextTableCellFormat(table.cellAt(1, 0).format())
        border = self.color(self.palette.border)
        solid = QTextFrameFormat.BorderStyle_Solid

        def finish(fmt):
            fmt.setBorder(0.0)
            for setter in (fmt.setLeftBorder, fmt.setRightBorder,
                           fmt.setTopBorder, fmt.setBottomBorder):
                setter(1.0)
            for setter in (fmt.setLeftBorderBrush, fmt.setRightBorderBrush,
                           fmt.setTopBorderBrush, fmt.setBottomBorderBrush):
                setter(border)
            for setter in (fmt.setLeftBorderStyle, fmt.setRightBorderStyle,
                           fmt.setTopBorderStyle, fmt.setBottomBorderStyle):
                setter(solid)
            return fmt

        head_fmt = finish(QTextTableCellFormat(base))
        head_fmt.setBackground(self.color(self.palette.bg_panel))
        even_fmt = finish(QTextTableCellFormat(base))
        even_fmt.setBackground(self.color(self.palette.bg_hover))
        odd_fmt = finish(QTextTableCellFormat(base))
        for r in range(table.rows()):
            fmt = head_fmt if r == 0 else (even_fmt if r % 2 == 0 else odd_fmt)
            for c in range(table.columns()):
                table.cellAt(r, c).setFormat(fmt)
        self._after_frame(cursor, table.lastPosition() + 1)


def cell_snapshot(doc):
    snap = []
    for table in tables(doc):
        for r in range(table.rows()):
            for c in range(table.columns()):
                cf = QTextTableCellFormat(table.cellAt(r, c).format())
                snap.append((r, c, cf.leftBorder(), cf.rightBorder(), cf.topBorder(), cf.bottomBorder(),
                             cf.leftBorderStyle(), cf.leftBorderBrush().color().name()
                             if cf.leftBorderBrush().style() else None,
                             round(cf.leftPadding(), 3), round(cf.topPadding(), 3),
                             cf.background().color().name() if cf.background().style() else None))
    return snap


def main():
    app = QApplication.instance() or QApplication([])
    style = BodyStyle()
    md = make_md(60)
    base_doc = render(md, style)
    pre_doc = render(md, style, Precomputed)
    sb, sp = cell_snapshot(base_doc), cell_snapshot(pre_doc)
    diffs = [(a, b) for a, b in zip(sb, sp) if a != b]

    # 拆时：先把边框打回无边框，测「只读」和「只写」。
    table = tables(base_doc)[0]
    n = table.rows() * table.columns()

    def read_all():
        for r in range(table.rows()):
            for c in range(table.columns()):
                QTextTableCellFormat(table.cellAt(r, c).format())
        return None

    border = style and mdoc._Renderer(base_doc, style, 676.0, None).color(style and mdoc.BodyStyle().palette.border)
    solid = QTextFrameFormat.BorderStyle_Solid

    def write_all():
        for r in range(table.rows()):
            for c in range(table.columns()):
                cell = table.cellAt(r, c)
                fmt = QTextTableCellFormat(cell.format())
                fmt.setBorder(0.0)
                for s in (fmt.setLeftBorder, fmt.setRightBorder, fmt.setTopBorder, fmt.setBottomBorder):
                    s(1.0)
                for s in (fmt.setLeftBorderBrush, fmt.setRightBorderBrush,
                          fmt.setTopBorderBrush, fmt.setBottomBorderBrush):
                    s(border)
                for s in (fmt.setLeftBorderStyle, fmt.setRightBorderStyle,
                          fmt.setTopBorderStyle, fmt.setBottomBorderStyle):
                    s(solid)
                cell.setFormat(fmt)
        return None

    def timeit(fn, reps=3):
        best = None
        for _ in range(reps):
            start = time.perf_counter()
            fn()
            dt = (time.perf_counter() - start) * 1000.0
            best = dt if best is None else min(best, dt)
        return round(best, 2)

    print(json.dumps({
        "cells": n,
        "read_only_ms": timeit(read_all),
        "read_write_ms": timeit(write_all),
        "cells_equal": not diffs,
        "n_diffs": len(diffs),
        "diff_sample": diffs[:3],
        "html_equal": base_doc.toHtml() == pre_doc.toHtml(),
        "blocks": [base_doc.blockCount(), pre_doc.blockCount()],
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
