"""400 轮规模下，表格改动前/后的整篇渲染耗时（各 5 次取最小）。

「改动前」= 用 ``probe_old_table.py`` 从 git 取出 ``HEAD`` 版 `_table`/`_table_row`/
`_apply_cell_borders`，进程内替换；源码不动。
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

from PySide6.QtGui import QTextCursor, QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle  # noqa: E402
import probe_old_table  # noqa: E402
from probe_table_fast import make_md  # noqa: E402


def render(blocks, style, width):
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    renderer = mdoc._Renderer(doc, style, width, None)
    renderer.render_blocks(blocks, QTextCursor(doc))
    mdoc._collapse_edge_margins(doc)
    return doc


def main():
    app = QApplication.instance() or QApplication([])
    style = BodyStyle()
    blocks = mdoc.parse_markdown(make_md(400))

    new_table = mdoc._Renderer._table
    new_row = mdoc._Renderer._table_row
    probe_old_table.apply(mdoc, "HEAD")
    old_table = mdoc._Renderer._table
    old_row = mdoc._Renderer._table_row
    old_borders = mdoc._Renderer._apply_cell_borders

    def use_old():
        mdoc._Renderer._table = old_table
        mdoc._Renderer._table_row = old_row
        mdoc._Renderer._apply_cell_borders = old_borders

    def use_new():
        mdoc._Renderer._table = new_table
        mdoc._Renderer._table_row = new_row
        if hasattr(mdoc._Renderer, "_apply_cell_borders"):
            del mdoc._Renderer._apply_cell_borders

    results = {}
    for name, setter in (("old", use_old), ("new", use_new)):
        setter()
        best = None
        for _ in range(5):
            start = time.perf_counter()
            render(blocks, style, 676.0)
            dt = (time.perf_counter() - start) * 1000.0
            best = dt if best is None else min(best, dt)
        results[name] = round(best, 1)
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
