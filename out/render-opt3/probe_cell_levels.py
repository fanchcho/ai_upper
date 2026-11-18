"""表格逐格格式复用到底省多少：HEAD 口径 → 当前源码，逐层拆开。

背景：早先的 ``probe_cell_levels.py`` 把「当前源码」当作 base；源码本身加上了三张
缓存之后，base 已经是最快的一档，再叠加补丁反而更慢（测出来是负数）。这里把口径
钉死：

- ``head``：``probe_old_opt3.old_table_row``（逐格新建 ``QTextTableCellFormat`` 并
  逐项写入，与 HEAD 相同），但字体/颜色/行高仍走当前源码的缓存——只隔离「表格逐格
  格式」这一项；
- ``no_char`` / ``no_block``：当前源码，但把字符格式 / 块格式那张小缓存拆掉（逐格
  重建），用来给两张小缓存各自定价；
- ``source``：当前源码原样。

每档交替 5 轮取最小，并核对 ``toHtml()`` 与文档高度。
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

from PySide6.QtGui import QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle, parse_markdown, render_markdown  # noqa: E402
from probe_group_sweep import mixed_md  # noqa: E402
from probe_old_opt3 import old_table_row  # noqa: E402

ROUNDS = 5
GROUPS = (16, 32)
LEVELS = ("head", "no_char", "no_block", "source")

REAL_ROW = mdoc._Renderer._table_row


class _NoCacheDict(dict):
    """写进去就丢：让 ``get`` 恒为 None，模拟「没有缓存」。"""

    def __setitem__(self, key, value):
        pass


def rebuild_char_row(self, table, row_index, cells, align, *, header_row):
    """当前源码，但字符格式逐格重建（不查 ``_cell_char_formats``）。"""
    saved = self._cell_char_formats
    self._cell_char_formats = _NoCacheDict()
    try:
        return REAL_ROW(self, table, row_index, cells, align, header_row=header_row)
    finally:
        self._cell_char_formats = saved


def rebuild_block_row(self, table, row_index, cells, align, *, header_row):
    """当前源码，但块格式逐格重建（不查 ``_cell_block_formats``）。"""
    saved = self._cell_block_formats
    self._cell_block_formats = _NoCacheDict()
    try:
        return REAL_ROW(self, table, row_index, cells, align, header_row=header_row)
    finally:
        self._cell_block_formats = saved


def install(level):
    if level == "head":
        mdoc._Renderer._table_row = old_table_row
    elif level == "no_char":
        mdoc._Renderer._table_row = rebuild_char_row
    elif level == "no_block":
        mdoc._Renderer._table_row = rebuild_block_row
    else:
        mdoc._Renderer._table_row = REAL_ROW
    return lambda: setattr(mdoc._Renderer, "_table_row", REAL_ROW)


def render(md_text, style, group):
    saved = mdoc._chunk_plan
    mdoc._chunk_plan = lambda blocks: group
    try:
        start = time.perf_counter()
        doc = render_markdown(QTextDocument(), md_text, style, 676.0, None)
        return (time.perf_counter() - start) * 1000.0, doc
    finally:
        mdoc._chunk_plan = saved


def layout(doc):
    doc.setTextWidth(696.0)
    doc.documentLayout()
    return doc


def main():
    QApplication.instance() or QApplication([])
    style = BodyStyle()
    md_text = mixed_md(400)
    blocks = parse_markdown(md_text)
    out = {"blocks": len(blocks), "runs": {}}
    for group in GROUPS:
        best = {level: float("inf") for level in LEVELS}
        docs = {}
        for _ in range(ROUNDS):
            for level in LEVELS:                      # 交替，避免顺序偏差
                undo = install(level)
                try:
                    took, doc = render(md_text, style, group)
                finally:
                    undo()
                best[level] = min(best[level], took)
                docs[level] = doc
        for doc in docs.values():
            layout(doc)
        base_html = docs["source"].toHtml()
        base_height = docs["source"].size().height()
        row = {}
        for level in LEVELS:
            row[level] = {
                "ms": round(best[level], 1),
                "delta_vs_source_ms": round(best[level] - best["source"], 1),
                "html_eq": docs[level].toHtml() == base_html,
                "height_eq": docs[level].size().height() == base_height,
            }
        out["runs"][str(group)] = row
        print("group=%-3d %s" % (group, "  ".join(
            "%s=%.1f(%+.1f)" % (lvl, row[lvl]["ms"], row[lvl]["delta_vs_source_ms"])
            for lvl in LEVELS)), flush=True)
    out["all_html_eq"] = all(cell["html_eq"] and cell["height_eq"]
                             for row in out["runs"].values() for cell in row.values())
    print("CELLLEVELS " + json.dumps(out, ensure_ascii=False))
    return 0 if out["all_html_eq"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
