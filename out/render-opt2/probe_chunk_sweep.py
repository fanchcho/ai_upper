"""表格改成一次插满行之后，分块大小是否还该是 50。

同一份 400 轮正文，扫分组 10/25/50/100/200，各取 3 次最小值。分块太大时结构性
插入的二次成本回来，太小则拼接与游标开销占比上升，最优点可能随表格路径变便宜而右移。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path("/home/agent/shared_workspace/ai_upper")
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(ROOT / "out" / "render-chunking"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage, QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle, render_markdown  # noqa: E402
from probe_fidelity_chunked import make_md  # noqa: E402


def main():
    app = QApplication.instance() or QApplication([])
    style = BodyStyle()
    image = QImage(12, 8, QImage.Format.Format_RGB32)
    image.fill(0xFF3366CC)
    resolver = lambda src: image if src.startswith("my://") else None  # noqa: E731
    md = make_md(400)
    saved = mdoc._CHUNK_BLOCKS
    out = {}
    for size in (10, 25, 50, 100, 200):
        mdoc._CHUNK_BLOCKS = size
        best = None
        for _ in range(3):
            start = time.perf_counter()
            doc = render_markdown(QTextDocument(), md, style, content_width=676.0,
                                  image_resolver=resolver)
            dt = (time.perf_counter() - start) * 1000.0
            best = dt if best is None else min(best, dt)
        out[str(size)] = round(best, 1)
    mdoc._CHUNK_BLOCKS = saved
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
