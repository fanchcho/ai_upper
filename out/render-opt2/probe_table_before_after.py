"""表格路径改动的「改动前 vs 改动后」逐块保真比对。

改动前的渲染器从 git 取出（``git show <rev>:app/src/markdown/document.py``）落成
临时文件，按独立模块导入；两版在同一进程、同一 style/宽度/图片解析器下渲染同一份
Markdown，逐块比文本、块格式、每个字符片、表格形状与单元格格式、文档尺寸、toHtml()。
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path("/home/agent/shared_workspace/ai_upper")
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(ROOT / "out" / "render-chunking"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage, QTextDocument, QTextTable, QTextTableCellFormat  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown.document import BodyStyle, render_markdown  # noqa: E402
from probe_fidelity_chunked import RICH, block_sig, make_md, tables  # noqa: E402


def load_old(rev: str):
    src = subprocess.run(
        ["git", "-C", str(ROOT), "show", "%s:app/src/markdown/document.py" % rev],
        capture_output=True, text=True, check=True,
    ).stdout
    path = Path(tempfile.mkdtemp(prefix="old-doc-")) / "document_old.py"
    path.write_text(src)
    spec = importlib.util.spec_from_file_location("document_old", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["document_old"] = module
    spec.loader.exec_module(module)
    return module


def cell_snapshot(doc):
    found, stack = [], [doc.rootFrame()]
    while stack:
        frame = stack.pop()
        if isinstance(frame, QTextTable):
            for r in range(frame.rows()):
                for c in range(frame.columns()):
                    cf = QTextTableCellFormat(frame.cellAt(r, c).format())
                    found.append((
                        r, c,
                        cf.leftBorder(), cf.rightBorder(), cf.topBorder(), cf.bottomBorder(),
                        cf.leftBorderStyle(), cf.rightBorderStyle(), cf.topBorderStyle(),
                        cf.bottomBorderStyle(),
                        cf.leftBorderBrush().color().name() if cf.leftBorderBrush().style() else None,
                        cf.topBorderBrush().color().name() if cf.topBorderBrush().style() else None,
                        round(cf.leftPadding(), 3), round(cf.rightPadding(), 3),
                        round(cf.topPadding(), 3), round(cf.bottomPadding(), 3),
                        cf.background().color().name() if cf.background().style() else None,
                    ))
        it = frame.begin()
        while not it.atEnd():
            child = it.currentFrame()
            if child is not None:
                stack.append(child)
            it += 1
    return found


def main():
    app = QApplication.instance() or QApplication([])
    style = BodyStyle()
    image = QImage(12, 8, QImage.Format.Format_RGB32)
    image.fill(0xFF3366CC)
    resolver = lambda src: image if src.startswith("my://") else None  # noqa: E731

    before_rev = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    old = load_old(before_rev)
    result = {"before_rev": before_rev}
    for turns in (5, 12, 30, 60, 120, 400):
        md = make_md(turns)
        before = old.render_markdown(QTextDocument(), md, style, content_width=676.0,
                                     image_resolver=resolver)
        after = render_markdown(QTextDocument(), md, style, content_width=676.0,
                                image_resolver=resolver)
        for doc in (before, after):
            doc.setTextWidth(696.0)
            doc.documentLayout()
        db, da = [(block_sig(b)) for b in _blocks(before)], [(block_sig(b)) for b in _blocks(after)]
        diffs = [i for i, (x, y) in enumerate(zip(db, da)) if x != y]
        cb, ca = cell_snapshot(before), cell_snapshot(after)
        result["turns_%d" % turns] = {
            "blocks": [before.blockCount(), after.blockCount()],
            "chars": [before.characterCount(), after.characterCount()],
            "text_eq": before.toPlainText() == after.toPlainText(),
            "n_diffs": len(diffs),
            "diff_indexes": diffs[:6],
            "tables_eq": tables(before) == tables(after),
            "n_tables": len(tables(before)),
            "n_cells": [len(cb), len(ca)],
            "cells_eq": cb == ca,
            "size": [round(before.size().width(), 4), round(before.size().height(), 4),
                     round(after.size().width(), 4), round(after.size().height(), 4)],
            "height_eq": before.size().height() == after.size().height(),
            "html_eq": before.toHtml().replace("user-state", "") == after.toHtml().replace("user-state", ""),
            "html_len": [len(before.toHtml()), len(after.toHtml())],
        }
        if cb != ca:
            for i, (x, y) in enumerate(zip(cb, ca)):
                if x != y:
                    result["turns_%d" % turns]["cell_diff_sample"] = {"i": i, "before": x, "after": y}
                    break
        if diffs:
            i = diffs[0]
            result["turns_%d" % turns]["block_diff_sample"] = {"i": i, "before": db[i], "after": da[i]}
    print(json.dumps(result, ensure_ascii=False, indent=1))


def _blocks(doc):
    block = doc.begin()
    while block.isValid():
        yield block
        block = block.next()


if __name__ == "__main__":
    main()
