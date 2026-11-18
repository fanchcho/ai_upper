"""表格改动 × 分块分组的交叉保真矩阵（含 RICH 图片资源文档）。

对每个（轮数, 分组）组合，让「改动前渲染器」与「改动后渲染器」都走分块路径渲染
同一份 Markdown，逐块比文本/块格式/字符片、逐格比单元格格式、比表格形状、
文档尺寸与 ``toHtml()``。旧渲染器从 ``git show <rev>:app/src/markdown/document.py``
加载，它自己的 ``_CHUNK_BLOCKS`` 也设成同一分组。

用法：``python probe_table_matrix.py [before_rev=HEAD]``
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

from markdown import document as mdoc  # noqa: E402
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


def rows_of(doc):
    out, block = [], doc.begin()
    while block.isValid():
        out.append(block_sig(block))
        block = block.next()
    return out


def cells_of(doc):
    found, stack = [], [doc.rootFrame()]
    while stack:
        frame = stack.pop()
        if isinstance(frame, QTextTable):
            for r in range(frame.rows()):
                for c in range(frame.columns()):
                    cf = QTextTableCellFormat(frame.cellAt(r, c).format())
                    found.append((
                        r, c, cf.leftBorder(), cf.rightBorder(), cf.topBorder(), cf.bottomBorder(),
                        cf.leftBorderStyle(), cf.bottomBorderStyle(),
                        cf.leftBorderBrush().color().name() if cf.leftBorderBrush().style() else None,
                        round(cf.leftPadding(), 3), round(cf.topPadding(), 3),
                        cf.background().style(),
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
    result = {"before_rev": before_rev, "cells": {}}
    for turns in (12, 60, 120):
        md = make_md(turns)
        for size in (5, 25, 50, 100):
            mdoc._CHUNK_BLOCKS = size
            old._CHUNK_BLOCKS = size
            before = old.render_markdown(QTextDocument(), md, style, content_width=676.0,
                                         image_resolver=resolver)
            after = render_markdown(QTextDocument(), md, style, content_width=676.0,
                                    image_resolver=resolver)
            for doc in (before, after):
                doc.setTextWidth(696.0)
                doc.documentLayout()
            rb, ra = rows_of(before), rows_of(after)
            diffs = [i for i, (x, y) in enumerate(zip(rb, ra)) if x != y]
            cb, ca = cells_of(before), cells_of(after)
            result["cells"]["t%d_g%d" % (turns, size)] = {
                "blocks": [before.blockCount(), after.blockCount()],
                "chars": [before.characterCount(), after.characterCount()],
                "n_diffs": len(diffs),
                "tables_eq": tables(before) == tables(after),
                "n_tables": len(tables(before)),
                "cells_eq": cb == ca,
                "n_cells": [len(cb), len(ca)],
                "height_eq": before.size().height() == after.size().height(),
                "height": [round(before.size().height(), 3), round(after.size().height(), 3)],
                "html_eq": before.toHtml() == after.toHtml(),
                "images_kept": [len(_images(before)), len(_images(after))],
            }
    mdoc._CHUNK_BLOCKS = 50
    print(json.dumps(result, ensure_ascii=False, indent=1))


def _images(doc):
    from markdown.document import CODE_LANGUAGE_PROPERTY  # noqa: F401
    names = []
    block = doc.begin()
    while block.isValid():
        for spec in block.textFormats():
            fmt = spec.format
            if fmt.isImageFormat():
                names.append(fmt.toImageFormat().name())
        block = block.next()
    return names


if __name__ == "__main__":
    main()
