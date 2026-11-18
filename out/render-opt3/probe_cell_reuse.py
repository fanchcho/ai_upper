"""表格逐格格式复用的保真矩阵：HEAD 口径 vs 当前源码，覆盖多种正文与分组。

``probe_cell_levels.py`` 给出收益；这里负责「改了也没走样」：3 种正文
（mixed / struct / para）× 4 个轮数 × 4 个分组，逐格比对 ``toHtml()``、块数、
文档高度。BEFORE 用 ``probe_old_opt3.old_table_row``（逐格新建 + 逐项写入，
与 HEAD 相同），AFTER 用当前源码。
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
from markdown.document import BodyStyle, render_markdown  # noqa: E402
from probe_group_sweep import mixed_md, para_md, struct_md  # noqa: E402
from probe_old_opt3 import old_table_row  # noqa: E402

ROUNDS = 5

REAL_ROW = mdoc._Renderer._table_row


def render(md_text, style, group, before):
    saved_plan = mdoc._chunk_plan
    mdoc._chunk_plan = lambda blocks: group
    if before:
        mdoc._Renderer._table_row = old_table_row
    try:
        start = time.perf_counter()
        doc = render_markdown(QTextDocument(), md_text, style, 676.0, None)
        return (time.perf_counter() - start) * 1000.0, doc
    finally:
        mdoc._chunk_plan = saved_plan
        mdoc._Renderer._table_row = REAL_ROW


def layout(doc):
    doc.setTextWidth(696.0)
    doc.documentLayout()
    return doc.toHtml(), doc.blockCount(), doc.size().height()


def main():
    QApplication.instance() or QApplication([])
    style = BodyStyle()
    out = {}

    # 1) 交替 A/B：400 轮 mixed，分组取判据实际会给的 32
    md_text = mixed_md(400)
    best = {"before": float("inf"), "after": float("inf")}
    docs = {}
    for _ in range(ROUNDS):
        for mode in ("before", "after"):              # 交替，避免顺序偏差
            took, doc = render(md_text, style, 32, mode == "before")
            best[mode] = min(best[mode], took)
            docs[mode] = doc
    for doc in docs.values():
        layout(doc)
    out["alternating"] = {
        "turns": 400, "group": 32, "rounds": ROUNDS,
        "before_ms": round(best["before"], 1), "after_ms": round(best["after"], 1),
        "speedup": round(best["before"] / best["after"], 2),
        "delta_ms": round(best["before"] - best["after"], 1),
        "html_eq": docs["before"].toHtml() == docs["after"].toHtml(),
        "blocks_eq": docs["before"].blockCount() == docs["after"].blockCount(),
        "height_eq": docs["before"].size().height() == docs["after"].size().height(),
    }
    print("alternating", json.dumps(out["alternating"], ensure_ascii=False), flush=True)

    # 2) 多文档、多分组保真
    cases = {"mixed": mixed_md, "struct": struct_md, "para": para_md}
    out["fidelity"] = {}
    for name, build in cases.items():
        for turns in (12, 30, 120, 400):
            text = build(turns)
            for group in (0, 5, 32, 50):
                _, before = render(text, style, group, True)
                _, after = render(text, style, group, False)
                before_html, before_blocks, before_h = layout(before)
                after_html, after_blocks, after_h = layout(after)
                key = "%s_t%d_g%s" % (name, turns, group or "whole")
                ok = (before_html == after_html and before_blocks == after_blocks
                      and before_h == after_h)
                out["fidelity"][key] = {"ok": ok, "blocks": after_blocks}
                if not ok:
                    print("MISMATCH", key, flush=True)
        print("fidelity %s done" % name, flush=True)
    out["fidelity_all_ok"] = all(v["ok"] for v in out["fidelity"].values())
    print("CELLREUSE " + json.dumps(out, ensure_ascii=False))
    return 0 if out["fidelity_all_ok"] and out["alternating"]["html_eq"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
