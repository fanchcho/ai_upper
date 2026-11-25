"""表格网格 overlay：QQuickTextEdit 不画单元格边框，且表格级 1px 会落在半像素上。

这里锁住 overlay 的两条行为：
1. 每张 Markdown 表格都挂一个 ``tableGrid``，行列线取单元格块几何；
2. 底边只画一行实色像素（旧渲染是 y217/y218 两行），且不与文字/单元格底色错位。
"""
from __future__ import annotations

import os

import pytest

from test_qml_context_menu import _build_window, _find_item, _pump


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication

    yield QGuiApplication.instance() or QGuiApplication([])


TABLE_MD = """前一段。

| 文件 | 类型 |
| --- | --- |
| `README.md` | 文档 |
| `src/` | 目录 |

后一段。
"""


def test_table_grid_paints_single_pixel_borders(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QPointF

    window, bridge, store, home, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        window.setProperty("page", "chat")
        view = _find_item(window.contentItem(), "bodyView")
        bridge._body.set_markdown(TABLE_MD)
        bridge._body.attach(view.property("textDocument"))
        _pump(qapp, .4)
        grids = bridge._body._grids
        assert len(grids) == 1, "one Markdown table must yield one grid overlay"
        grid = grids[0]
        assert grid.objectName() == "tableGrid"
        assert grid.property("height") >= 70
        advances = [round(b - a, 3) for a, b in zip(grid._row_lines, grid._row_lines[1:])]
        assert advances and len(set(advances)) == 1, advances
        origin = view.mapToScene(QPointF(grid.x(), grid.y()))
        shot = window.grabWindow()
        left = int(origin.x()) + 2
        right = int(origin.x() + grid.width()) - 2
        bottom_y = int(origin.y() + grid.height() - 1)
        border = "#e6e6ea"
        bottom = sum(1 for x in range(left, right) if shot.pixelColor(x, bottom_y).name() == border)
        above = sum(1 for x in range(left, right) if shot.pixelColor(x, bottom_y - 1).name() == border)
        assert bottom >= (right - left) * 0.9, (bottom, right - left)
        assert above < (right - left) * 0.1, "bottom border must be a single pixel row"
        print(f"TABLE_GRID rows={len(grid._row_lines)} row_advance={advances[0]} "
              f"bottom_row={bottom_y} border_px={bottom} above_px={above}")
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()
