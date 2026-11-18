"""缓存候选的微基准：颜色解析 / 字体构造 / 行高换算。

只量「同一个值重复算」的成本，不改源码。三项都是无状态纯函数（输入定，输出定），
所以缓存不改变产物；但它们各自值多少，决定值不值得改。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QFontMetricsF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle  # noqa: E402


def best_of(fn, repeats=5):
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        best = min(best, (time.perf_counter() - start) * 1000.0)
    return best


def main():
    app = QApplication.instance() or QApplication([])
    style = BodyStyle()
    palette = style.palette
    values = [getattr(palette, name) for name in
              ("fg", "fg_muted", "fg_subtle", "bg_panel", "bg_hover", "border",
               "border_strong", "code_bg", "code_head_bg", "code_border", "bg_inset", "accent")]

    n = 19600
    t_css = best_of(lambda: [mdoc.css_color(values[i % len(values)]) for i in range(n)]) / n * 1000
    cache = {v: mdoc.css_color(v) for v in values}
    t_dict = best_of(lambda: [cache[values[i % len(values)]] for i in range(n)]) / n * 1000

    def make_font(call_index):
        font = QFont()
        font.setFamilies(list(style.sans))
        font.setPixelSize(max(1, int(round(14.0))))
        font.setBold(False)
        font.setItalic(False)
        return font

    t_font = best_of(lambda: [make_font(i) for i in range(8000)]) / 8000 * 1000
    frozen = QFont()
    frozen.setFamilies(list(style.sans))
    frozen.setPixelSize(14)
    t_copy = best_of(lambda: [QFont(frozen) for i in range(8000)]) / 8000 * 1000

    t_metrics = best_of(lambda: [QFontMetricsF(frozen).lineSpacing() for _ in range(9600)]) / 9600 * 1000
    spacing = QFontMetricsF(frozen).lineSpacing()

    print(json.dumps({
        "css_color_us": round(t_css, 3),
        "dict_lookup_us": round(t_dict, 4),
        "font_build_us": round(t_font, 3),
        "font_copy_us": round(t_copy, 3),
        "font_metrics_us": round(t_metrics, 3),
        "line_spacing": round(spacing, 3),
        "per_400_turn_doc_ms": {
            "css_color_19600": round(t_css * 19600 / 1000, 1),
            "font_20400": round(t_font * 20400 / 1000, 1),
            "metrics_12400": round(t_metrics * 12400 / 1000, 1),
        },
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
