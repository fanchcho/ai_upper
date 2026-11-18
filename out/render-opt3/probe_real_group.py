"""真实 400 轮会话正文上的分组对比：g16 / g24 / g32 / g50 / 整篇。

合成正文可以调密度，但最终要回答的是「真实会话落在哪一档」。这里直接用
``probe_heavy`` 生成的 heavy-000（400 轮、3200 块、164578 字符、密度 0.307），
交替测量，每档取 3 次最小值。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(ROOT / "out" / "conversation-picker-lag"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main():
    home = Path(tempfile.mkdtemp(prefix="ai-upper-realgrp-"))
    os.environ["AI_UPPER_HOME"] = str(home)

    from probe_heavy import make_home
    make_home(home, 2, 400)

    from PySide6.QtGui import QTextDocument
    from PySide6.QtWidgets import QApplication

    from markdown import document as mdoc
    from markdown.document import BodyStyle, parse_markdown, render_markdown
    from mvvm.services.chat_session_store import ChatSessionStore
    from qml_shell_sessions import transcript_markdown

    store = ChatSessionStore(home)
    session = store.load_session("heavy-000")
    text = transcript_markdown(session.messages)
    blocks = parse_markdown(text)
    load = mdoc._structural_load(blocks)

    QApplication.instance() or QApplication([])
    style = BodyStyle()
    groups = (0, 16, 24, 32, 50)
    best = {g: float("inf") for g in groups}
    docs = {}
    for _ in range(3):
        for group in groups:                      # 交替，避免顺序偏差
            saved = mdoc._chunk_plan
            mdoc._chunk_plan = lambda b, g=group: g
            try:
                start = time.perf_counter()
                doc = render_markdown(QTextDocument(), text, style, 676.0, None)
                took = (time.perf_counter() - start) * 1000.0
            finally:
                mdoc._chunk_plan = saved
            best[group] = min(best[group], took)
            docs[group] = doc

    for doc in docs.values():
        doc.setTextWidth(696.0)
        doc.documentLayout()
    baseline = docs[0].toHtml()
    out = {
        "blocks": len(blocks),
        "chars": len(text),
        "density": round(load / len(blocks), 3),
        "plan": mdoc._chunk_plan(blocks),
        "ms": {str(g): round(best[g], 1) for g in groups},
        "html_eq": {str(g): docs[g].toHtml() == baseline for g in groups},
    }
    fastest = min(groups[1:], key=lambda g: best[g])
    print("heavy-000 blocks=%d chars=%d density=%.3f plan=%s"
          % (len(blocks), len(text), out["density"], out["plan"]))
    for g in groups:
        print("  g%-4s %8.1f ms  %+6.1f%% vs fastest  html_eq=%s"
              % (g or "whole", best[g], (best[g] - best[fastest]) / best[fastest] * 100,
                 out["html_eq"][str(g)]))
    print("REALGROUP " + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
