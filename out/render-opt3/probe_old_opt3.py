"""把 render-opt3 改动前的实现装回进程内（源码不动），供 A/B 的 BEFORE 口径使用。

三处都取 ``git show HEAD:app/src/markdown/document.py`` 的原样实现：

- ``_chunk_plan``：只按「块数 > 50」决定，恒定分 50；
- ``font`` / ``line_height`` / ``css_color``：每次重新构造，不查表；
- ``_table_row``：逐格 ``QTextTableCellFormat(cell.format())`` 新建并逐项写入。

``install()`` 返回撤销函数；``snapshot()/restore()`` 给需要反复切换的探针用。
"""
from __future__ import annotations

from PySide6.QtGui import QFont, QFontMetricsF, QGuiApplication, QTextBlockFormat
from PySide6.QtGui import QTextCharFormat, QTextFrameFormat, QTextTableCellFormat

from markdown import document as mdoc


def old_font(self, px, bold=False, mono=False, italic=False):
    font = QFont()
    font.setFamilies(list(self.style.mono if mono else self.style.sans))
    font.setPixelSize(max(1, int(round(px))))
    font.setBold(bold)
    font.setItalic(italic)
    return font


def old_line_height(self, px, factor):
    if QGuiApplication.instance() is None:
        return factor * 100.0
    spacing = QFontMetricsF(old_font(self, px)).lineSpacing()
    if spacing <= 0:
        return factor * 100.0
    return (px * factor) / spacing * 100.0


def old_table_row(self, table, row_index, cells, align, *, header_row):
    border = self.color(self.palette.border)
    solid = QTextFrameFormat.BorderStyle_Solid
    for column, cell_nodes in enumerate(cells):
        cell = table.cellAt(row_index, column)
        cell_fmt = QTextTableCellFormat(cell.format())
        cell_fmt.setLeftPadding(10.0 * self.style.scale)
        cell_fmt.setRightPadding(10.0 * self.style.scale)
        cell_fmt.setTopPadding(6.0 * self.style.scale)
        cell_fmt.setBottomPadding(6.0 * self.style.scale)
        if header_row:
            cell_fmt.setBackground(self.color(self.palette.bg_panel))
        elif row_index % 2 == 0:
            cell_fmt.setBackground(self.color(self.palette.bg_hover))
        cell_fmt.setBorder(0.0)
        for setter in (cell_fmt.setLeftBorder, cell_fmt.setRightBorder,
                       cell_fmt.setTopBorder, cell_fmt.setBottomBorder):
            setter(1.0)
        for setter in (cell_fmt.setLeftBorderBrush, cell_fmt.setRightBorderBrush,
                       cell_fmt.setTopBorderBrush, cell_fmt.setBottomBorderBrush):
            setter(border)
        for setter in (cell_fmt.setLeftBorderStyle, cell_fmt.setRightBorderStyle,
                       cell_fmt.setTopBorderStyle, cell_fmt.setBottomBorderStyle):
            setter(solid)
        cell.setFormat(cell_fmt)
        cell_cursor = cell.firstCursorPosition()
        block_fmt = QTextBlockFormat()
        block_fmt.setAlignment(mdoc._alignment(align[column] if column < len(align) else "left"))
        block_fmt.setLineHeight(
            self.line_height(13.0 * self.style.scale, self.style.line_height),
            QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        cell_cursor.setBlockFormat(block_fmt)
        char_fmt = QTextCharFormat()
        char_fmt.setFont(self.font(13.0 * self.style.scale, bold=header_row))
        char_fmt.setForeground(self.color(self.palette.fg))
        self._inline(cell_cursor, cell_nodes or [], char_fmt)


def old_plan(blocks):
    return 50 if len(blocks) > 50 else 0


def snapshot():
    return {
        "plan": mdoc._chunk_plan,
        "font": mdoc._Renderer.font,
        "line_height": mdoc._Renderer.line_height,
        "color": mdoc._Renderer.color,
        "table_row": mdoc._Renderer._table_row,
        "css_color": mdoc.css_color,
    }


def restore(snap):
    mdoc._chunk_plan = snap["plan"]
    mdoc._Renderer.font = snap["font"]
    mdoc._Renderer.line_height = snap["line_height"]
    mdoc._Renderer.color = snap["color"]
    mdoc._Renderer._table_row = snap["table_row"]
    mdoc.css_color = snap["css_color"]


def install_before():
    """装上改动前的全部实现；返回撤销函数。"""
    snap = snapshot()
    raw = mdoc.css_color.__wrapped__
    mdoc._chunk_plan = old_plan
    mdoc._Renderer.font = old_font
    mdoc._Renderer.line_height = old_line_height
    mdoc._Renderer.color = lambda self, value: raw(value)
    mdoc._Renderer._table_row = old_table_row
    mdoc.css_color = raw
    return lambda: restore(snap)
