"""热路径缓存的可行性验证：只改进程内的方法，量收益、验保真。

三个候选都是「输入定 → 输出定」的纯查表：
- ``_Renderer.color`` 走 ``css_color``（regex + QColor 解析），同一份主题下只有
  十几个不同取值，400 轮文档却调用 19600 次；
- ``_Renderer.font`` 每次都新建 QFont 并 setFamilies/setPixelSize/setBold/setItalic，
  400 轮 20400 次，键只有「字体族 + 像素 + 粗 + 等宽 + 斜」几个组合；
- ``_Renderer.line_height`` 每次都新建字体再取 ``QFontMetricsF.lineSpacing()``，
  9600 次，键只有「字号 + 倍率」。

这里在进程内替换成带缓存版本，与源码原版在同一份文档上比：耗时 + 逐块签名 +
``toHtml()``。只有收益明确且保真为 0 才值得改源码。
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

from PySide6.QtGui import QColor, QGuiApplication, QTextCursor, QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle, parse_markdown  # noqa: E402
from probe_group_sweep import mixed_md  # noqa: E402


def best_of(fn, repeats=3):
    best = float("inf")
    doc = None
    for _ in range(repeats):
        start = time.perf_counter()
        doc = fn()
        best = min(best, (time.perf_counter() - start) * 1000.0)
    return round(best, 1), doc


def describe(doc):
    out, block = [], doc.begin()
    while block.isValid():
        fmt = block.blockFormat()
        runs = tuple(
            (spec.start, spec.length,
             spec.format.toImageFormat().name() if spec.format.isImageFormat() else None,
             spec.format.font().family(), spec.format.font().pixelSize(),
             int(spec.format.font().weight()), spec.format.font().italic(),
             spec.format.foreground().color().name() if spec.format.foreground().style() else None,
             spec.format.background().color().name() if spec.format.background().style() else None)
            for spec in block.textFormats()
        )
        out.append((block.text(),
                    (round(fmt.topMargin(), 4), round(fmt.bottomMargin(), 4),
                     round(fmt.leftMargin(), 4), round(fmt.rightMargin(), 4),
                     round(fmt.textIndent(), 4), round(fmt.lineHeight(), 4),
                     fmt.lineHeightType(), fmt.alignment()),
                    runs))
        block = block.next()
    return out


def render_whole(blocks, style):
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    mdoc._Renderer(doc, style, 676.0, None).render_blocks(blocks, QTextCursor(doc))
    mdoc._collapse_edge_margins(doc)
    return doc


def render_chunked(blocks, style, group):
    saved = mdoc._CHUNK_BLOCKS
    mdoc._CHUNK_BLOCKS = group
    try:
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        mdoc._render_chunked(doc, blocks, style, 676.0, None)
        mdoc._collapse_edge_margins(doc)
        return doc
    finally:
        mdoc._CHUNK_BLOCKS = saved


def install_caches():
    """给 ``_Renderer`` 装上三张缓存表，返回计数器。"""
    counts = {"color": 0, "color_hit": 0, "font": 0, "font_hit": 0, "lh": 0, "lh_hit": 0}
    real_color = mdoc._Renderer.color
    real_font = mdoc._Renderer.font
    real_lh = mdoc._Renderer.line_height
    css_cache = {}
    font_cache = {}
    lh_cache = {}

    def color(self, value):
        counts["color"] += 1
        key = value or ""
        got = css_cache.get(key)
        if got is None:
            got = real_color(self, value)
            css_cache[key] = got
        else:
            counts["color_hit"] += 1
        return got

    def font(self, px, bold=False, mono=False, italic=False):
        counts["font"] += 1
        key = (tuple(self.style.mono if mono else self.style.sans),
               max(1, int(round(px))), bool(bold), bool(italic))
        got = font_cache.get(key)
        if got is None:
            got = real_font(self, px, bold, mono, italic)
            font_cache[key] = got
        else:
            counts["font_hit"] += 1
        return got

    def line_height(self, px, factor):
        counts["lh"] += 1
        key = (px, factor, tuple(self.style.sans),
               QGuiApplication.instance() is not None)
        got = lh_cache.get(key)
        if got is None:
            got = real_lh(self, px, factor)
            lh_cache[key] = got
        else:
            counts["lh_hit"] += 1
        return got

    mdoc._Renderer.color = color
    mdoc._Renderer.font = font
    mdoc._Renderer.line_height = line_height
    return counts


def main():
    app = QApplication.instance() or QApplication([])
    style = BodyStyle()
    blocks = parse_markdown(mixed_md(400))

    plain_whole, whole_doc = best_of(lambda: render_whole(blocks, style))
    plain_g16, g16_doc = best_of(lambda: render_chunked(blocks, style, 16))

    counts = install_caches()
    try:
        fast_whole, fwhole_doc = best_of(lambda: render_whole(blocks, style))
        fast_g16, fg16_doc = best_of(lambda: render_chunked(blocks, style, 16))
    finally:
        del mdoc._Renderer.color
        del mdoc._Renderer.font
        del mdoc._Renderer.line_height

    for doc in (whole_doc, g16_doc, fwhole_doc, fg16_doc):
        doc.setTextWidth(696.0)
        doc.documentLayout()

    print(json.dumps({
        "blocks": len(blocks),
        "whole_ms": [plain_whole, fast_whole],
        "g16_ms": [plain_g16, fast_g16],
        "speedup": {
            "whole": round(plain_whole / fast_whole, 3),
            "g16": round(plain_g16 / fast_g16, 3),
        },
        "fidelity": {
            "whole_sig_eq": describe(whole_doc) == describe(fwhole_doc),
            "whole_html_eq": whole_doc.toHtml() == fwhole_doc.toHtml(),
            "g16_sig_eq": describe(g16_doc) == describe(fg16_doc),
            "g16_html_eq": g16_doc.toHtml() == fg16_doc.toHtml(),
        },
        "cache_calls": counts,
        "color_copy_us": None,
    }, ensure_ascii=False, indent=1))

    # 缓存返回的是同一个 QColor 实例：量一下「每次拷贝一份再返回」的代价，
    # 决定是直接复用还是复制（调用方都是 setForeground/setBackground 这类拷贝语义）。
    frozen = QColor("#aabbcc")
    n = 19600
    start = time.perf_counter()
    for _ in range(n):
        QColor(frozen)
    copy_us = (time.perf_counter() - start) * 1000.0 / n * 1000
    print(json.dumps({"qcolor_copy_us": round(copy_us, 4)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
