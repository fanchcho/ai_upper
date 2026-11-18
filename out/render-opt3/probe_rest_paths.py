"""剩余路径（代码块 / hairline / 段落与 inline）还有没有可省的重复工作。

两步：

1. 用 ``cProfile`` 在当前源码上跑 400 轮正文，按 tottime 看 Python 侧还剩什么；
2. 把候选微优化各自做成一档（进程内替换，源码不动），与当前实现交替 A/B，
   同时校验 ``toHtml()`` / 块数 / 高度。**只有既快又逐字节一致才允许进源码。**

候选与它对应的 profile 证据：

- ``measure_cache``：``_measure`` 每次新建 ``QFontMetricsF`` → 按 (字体族, 像素) 缓存；
- ``code_metrics``：代码块逐行 ``_measure`` → 每块只建一次 metrics；
- ``no_replace``：``_inline`` 对每个文本片都 ``str.replace`` → 不含换行才跳过。

表格逐格格式复用单独由 ``probe_cell_levels.py`` / ``probe_cell_reuse.py`` 定价，这里
不再重复测（它已经进源码，再当候选只会测到补丁自身的开销）。
"""
from __future__ import annotations

import cProfile
import io
import json
import os
import pstats
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFontMetricsF, QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle, parse_markdown, render_markdown  # noqa: E402
from probe_group_sweep import mixed_md  # noqa: E402

GROUP = 32


def render_once(md_text, style):
    saved = mdoc._chunk_plan
    mdoc._chunk_plan = lambda blocks: GROUP
    try:
        start = time.perf_counter()
        doc = render_markdown(QTextDocument(), md_text, style, 676.0, None)
        return (time.perf_counter() - start) * 1000.0, doc
    finally:
        mdoc._chunk_plan = saved


def profile(md_text, style):
    printer = io.StringIO()
    profiler = cProfile.Profile()
    profiler.enable()
    render_once(md_text, style)
    profiler.disable()
    pstats.Stats(profiler, stream=printer).sort_stats("tottime").print_stats(20)
    return printer.getvalue()


# ── 候选实现（每个函数只装补丁，返回撤销函数） ──────────────────────────────
def patch_measure_cache():
    cache = {}
    real = mdoc._measure

    def measure(font, text):
        if mdoc.QGuiApplication.instance() is None:
            return real(font, text)
        key = (tuple(font.families()), font.pixelSize())
        metrics = cache.get(key)
        if metrics is None:
            metrics = cache[key] = QFontMetricsF(font)
        return metrics.horizontalAdvance(text)

    mdoc._measure = measure

    def undo():
        mdoc._measure = real
    return undo


def patch_code_metrics():
    real = mdoc._Renderer._code

    def code(self, cursor, block):
        if mdoc.QGuiApplication.instance() is None:
            return real(self, cursor, block)
        text = str(block.get("text") or "")
        lines = set(text.split(mdoc.NEWLINE) if text else [""])
        metrics = QFontMetricsF(self.font(12.5 * self.style.scale, mono=True))
        advances = {line: metrics.horizontalAdvance(line) for line in lines}
        saved = mdoc._measure
        mdoc._measure = lambda font, line, _a=advances: _a[line]
        try:
            return real(self, cursor, block)
        finally:
            mdoc._measure = saved

    mdoc._Renderer._code = code

    def undo():
        mdoc._Renderer._code = real
    return undo


def patch_no_replace():
    real = mdoc._Renderer._inline

    def inline(self, cursor, nodes, base):
        real_insert = cursor.insertText

        def insert_text(text, *args, **kwargs):
            if isinstance(text, str) and mdoc.NEWLINE in text:
                text = text.replace(mdoc.NEWLINE, mdoc.LINE_SEPARATOR)
            return real_insert(text, *args, **kwargs)

        cursor.insertText = insert_text
        try:
            return real(self, cursor, nodes, base)
        finally:
            cursor.insertText = real_insert

    mdoc._Renderer._inline = inline

    def undo():
        mdoc._Renderer._inline = real
    return undo


VARIANTS = (
    ("measure_cache", patch_measure_cache),
    ("code_metrics", patch_code_metrics),
    ("no_replace", patch_no_replace),
)


def alternated(md_text, style, patches, rounds=3):
    """基准与各变体在同一轮里交替跑，避免「先跑完基准再跑变体」的顺序漂移。

    早先的写法把基准量一次、再逐个量变体，同一变体两次测得的结果能差 5%，
    那点漂移足以把噪声读成收益。这里每轮把基准和所有变体各跑一次，轮间取最小。
    """
    base_best = float("inf")
    variant_best = {name: float("inf") for name, _ in patches}
    docs = {"base": None}
    docs.update({name: None for name, _ in patches})
    for round_index in range(rounds):
        entries = [("base", None)] + list(patches)
        if round_index % 2:
            entries = list(reversed(entries))
        for name, patch in entries:
            undo = patch() if patch is not None else None
            try:
                took, doc = render_once(md_text, style)
            finally:
                if undo is not None:
                    undo()
            if name == "base":
                base_best = min(base_best, took)
            else:
                variant_best[name] = min(variant_best[name], took)
            docs[name] = doc
    return base_best, variant_best, docs


def main():
    QApplication.instance() or QApplication([])
    style = BodyStyle()
    md_text = mixed_md(400)
    blocks = parse_markdown(md_text)

    print("PROFILE_BEGIN", flush=True)
    print(profile(md_text, style), flush=True)
    print("PROFILE_END", flush=True)

    base_ms, variant_ms, docs = alternated(md_text, style, VARIANTS)
    for doc in docs.values():
        doc.setTextWidth(696.0)
        doc.documentLayout()
    base_doc = docs["base"]
    base_html, base_height = base_doc.toHtml(), base_doc.size().height()

    out = {"blocks": len(blocks), "group": GROUP, "base_ms": round(base_ms, 1),
           "variants": {}}
    for name, _ in VARIANTS:
        var_doc = docs[name]
        var_ms = variant_ms[name]
        out["variants"][name] = {
            "ms": round(var_ms, 1),
            "base_ms": round(base_ms, 1),
            "delta_ms": round(base_ms - var_ms, 1),
            "html_eq": var_doc.toHtml() == base_html,
            "blocks_eq": var_doc.blockCount() == base_doc.blockCount(),
            "height_eq": var_doc.size().height() == base_height,
        }
        row = out["variants"][name]
        print("%-14s base=%-8.1f variant=%-8.1f delta=%-7.1f html_eq=%s height_eq=%s"
              % (name, row["base_ms"], row["ms"], row["delta_ms"],
                 row["html_eq"], row["height_eq"]), flush=True)
    print("RESTPATHS " + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
