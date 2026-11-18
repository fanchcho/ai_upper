"""判据在「真实正文」上的抽查：用会话存储里的真实 Markdown 复核密度与分组。

前几个探针都用合成正文（每 N 段一张表/代码/引用）。这里直接读 ``probe_heavy`` 生成的
40×400 会话正文，统计每份的真实块数、加权结构量、密度与 ``_chunk_plan`` 的选择，
确认判据在真实内容上不会退化成「总是整篇」或「总是小组」。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(ROOT / "out" / "conversation-picker-lag"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main():
    home = Path(tempfile.mkdtemp(prefix="ai-upper-planreal-"))
    os.environ["AI_UPPER_HOME"] = str(home)

    from probe_heavy import make_home
    make_home(home, 40, 400)

    from mvvm.services.chat_session_store import ChatSessionStore
    from qml_shell_sessions import transcript_markdown
    from markdown import document as mdoc
    from markdown.document import parse_markdown

    store = ChatSessionStore(home)
    rows = []
    for summary in store.list_sessions():
        session = store.load_session(summary.id)
        text = transcript_markdown(session.messages) if session is not None else ""
        blocks = parse_markdown(text)
        load = mdoc._structural_load(blocks)
        rows.append({
            "id": summary.id,
            "turns": len(getattr(session, "messages", []) or []),
            "chars": len(text),
            "blocks": len(blocks),
            "load": round(load, 1),
            "density": round(load / max(1, len(blocks)), 3),
            "plan": mdoc._chunk_plan(blocks),
        })
    for row in sorted(rows, key=lambda r: -r["blocks"])[:8]:
        print("%-10s turns=%-4d chars=%-7d blocks=%-6d load=%-8.1f d=%.3f plan=%s"
              % (row["id"], row["turns"], row["chars"], row["blocks"], row["load"],
                 row["density"], row["plan"] or "whole"), flush=True)
    print("REALPLAN " + json.dumps(rows, ensure_ascii=False))


if __name__ == "__main__":
    main()
