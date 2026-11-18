"""render-opt3 前后对比：改动前（HEAD 实现）vs 改动后（当前源码）。

改动前口径包含三样（全部在本进程内替换，源码与其它进程不受影响，见
``probe_old_opt3.py``）：

- **分块计划**：只按「块数 > 50」决定、恒用 50；新版按结构密度选 16 / 50 / 整篇；
- **热路径缓存**：颜色解析、字体构造、行高换算每次都重新构造；
- **表格逐格格式**：每格新建 ``QTextTableCellFormat(cell.format())`` 并逐项写入。

同一进程内交替 A/B，每档取 3 次最小值；长会话（400 轮）与短会话（12 / 30 轮）
分开报，不做奇偶混合。
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
from probe_group_sweep import mixed_md, para_md, struct_md  # noqa: E402
from probe_old_opt3 import install_before  # noqa: E402


def run(md_text, style, mode):
    """mode = "before"（旧口径全部）或 "after"（当前源码）。"""
    undo = install_before() if mode == "before" else (lambda: None)
    try:
        start = time.perf_counter()
        doc = render_markdown(QTextDocument(), md_text, style, 676.0, None)
        took = (time.perf_counter() - start) * 1000.0
    finally:
        undo()
    return took, doc


def main():
    QApplication.instance() or QApplication([])
    style = BodyStyle()

    cases = {
        "mixed_t12": mixed_md(12),
        "mixed_t30": mixed_md(30),
        "mixed_t120": mixed_md(120),
        "mixed_t400": mixed_md(400),
        "para_t400": para_md(400),
        "struct_t400": struct_md(400),
    }
    out = {}
    for name, md in cases.items():
        blocks = parse_markdown(md)
        planned = mdoc._chunk_plan(blocks)
        best = {"before": float("inf"), "after": float("inf")}
        docs = {}
        for _ in range(3):
            for mode in ("before", "after"):   # 交替，避免顺序偏差
                took, doc = run(md, style, mode)
                best[mode] = min(best[mode], took)
                docs[mode] = doc
        for doc in docs.values():
            doc.setTextWidth(696.0)
            doc.documentLayout()
        out[name] = {
            "blocks": len(blocks),
            "planned_group": planned,
            "before_ms": round(best["before"], 1),
            "after_ms": round(best["after"], 1),
            "speedup": round(best["before"] / best["after"], 2),
            "html_eq": docs["before"].toHtml() == docs["after"].toHtml(),
            "blocks_eq": docs["before"].blockCount() == docs["after"].blockCount(),
            "height_eq": docs["before"].size().height() == docs["after"].size().height(),
        }
        print("%-12s blocks=%-5d plan=%-4s before=%-9.1f after=%-9.1f ×%.2f  html_eq=%s"
              % (name, len(blocks), planned, out[name]["before_ms"],
                 out[name]["after_ms"], out[name]["speedup"], out[name]["html_eq"]),
              flush=True)
    print("AB " + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
