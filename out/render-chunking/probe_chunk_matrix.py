"""分块路径的二维矩阵：轮数 × 分组大小。逐块签名差异 / 块数 / 字符数 / 表格 / 尺寸 / 耗时。"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path("/home/agent/shared_workspace/ai_upper")
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, "/tmp")
from probe_fidelity_chunked import (  # noqa: E402
    QApplication, QImage, QTextDocument, BodyStyle, mdoc, render_markdown,
    describe, tables, make_md,
)


def ms(fn):
    start = time.perf_counter()
    value = fn()
    return (time.perf_counter() - start) * 1000.0, value


def main():
    app = QApplication.instance() or QApplication([])
    style = BodyStyle()
    image = QImage(12, 8, QImage.Format.Format_RGB32)
    image.fill(0xFF3366CC)
    resolver = lambda src: image if src.startswith("my://") else None  # noqa: E731

    result = {}
    saved = mdoc._CHUNK_BLOCKS
    for turns in (12, 30, 120, 400):
        md = make_md(turns)
        mdoc._CHUNK_BLOCKS = 10 ** 9
        whole_ms, whole = ms(lambda m=md: render_markdown(QTextDocument(), m, style, 676.0, resolver))
        mdoc._CHUNK_BLOCKS = saved
        reference = describe(whole)
        reference_tables = tables(whole)
        for group in (5, 25, 50, 100):
            mdoc._CHUNK_BLOCKS = group
            took, doc = ms(lambda m=md: render_markdown(QTextDocument(), m, style, 676.0, resolver))
            sig = describe(doc)
            diffs = [i for i, (a, b) in enumerate(zip(reference, sig)) if a != b]
            for d in (whole, doc):
                d.setTextWidth(696.0)
                d.documentLayout()
            key = "t%d_g%d" % (turns, group)
            result[key] = {
                "whole_ms": round(whole_ms, 1), "chunked_ms": round(took, 1),
                "speedup": round(whole_ms / took, 2) if took else None,
                "blocks": [whole.blockCount(), doc.blockCount()],
                "chars": [whole.characterCount(), doc.characterCount()],
                "text_eq": whole.toPlainText() == doc.toPlainText(),
                "n_diffs": len(diffs), "first_diffs": diffs[:3],
                "tables_eq": reference_tables == tables(doc),
                "height_eq": whole.size().height() == doc.size().height(),
                "html_eq": whole.toHtml() == doc.toHtml(),
            }
            mdoc._CHUNK_BLOCKS = saved
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
