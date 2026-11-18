"""高亮发生在哪一段：在**任何实例构造之前**安装 highlightBlock 计时。

PySide 的虚函数派发在对象构造时绑定，构造后再改类属性拦不到已有实例——上一版
探针因此报出 0 次调用。这里在 import 之后、创建 ``BodyDocument`` 之前装好探针。

分段：
- ``openSession`` 整体（同步段）；
- 其中 ``BodyDocument.render``（写自有文档，高亮器此时挂在自己文档上）；
- 其中 ``attach``（换绑 + insertFragment，contentsChange 会驱动目标文档的高亮）。

用法：``python probe_highlight_phase2.py [会话数=12] [轮数=400]``
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path("/home/agent/shared_workspace/ai_upper")
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(ROOT / "out" / "conversation-picker-lag"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    home = Path(tempfile.mkdtemp(prefix="ai-upper-hlphase2-"))
    os.environ["AI_UPPER_HOME"] = str(home)

    from probe_heavy import make_home
    make_home(home, count, turns)

    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication

    from markdown.highlight import CodeHighlighter

    # ── 必须先于 BodyDocument 构造 ───────────────────────────────────────
    calls = {"n": 0, "ms": 0.0}
    orig_block = CodeHighlighter.highlightBlock

    def counted(self, text):
        t = time.perf_counter()
        try:
            return orig_block(self, text)
        finally:
            calls["n"] += 1
            calls["ms"] += (time.perf_counter() - t) * 1000.0

    CodeHighlighter.highlightBlock = counted

    from markdown.body import BodyDocument
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.settings_service import SettingsService
    from mvvm.services.skill_store import SkillStore
    from mvvm.services.workspace_guard import WorkspaceGuard
    from mvvm.webui.assembly import build_chat_host
    from qml_shell import ShellBridge, qml_main

    app = QApplication.instance() or QApplication([])
    settings, vault, store = SettingsService(home), SecretsVault(home), ChatSessionStore(home)
    PersonaStore(home).ensure_seeded()
    box = {}

    def emit(p):
        box["bridge"].emit(p)

    host, _ = build_chat_host(settings=settings, vault=vault, store=store,
                              guard=WorkspaceGuard(), home=home, emit=emit,
                              emit_sessions_changed=lambda: None)
    bridge = ShellBridge(host=host, store=store, plain=False, settings=settings,
                         vault=vault, skills=SkillStore(home))
    box["bridge"] = bridge
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("shellBridge", bridge)
    engine.load(QUrl.fromLocalFile(str(qml_main())))
    window = engine.rootObjects()[0]
    bridge.bind_window(window)
    bridge.initial()
    window.show()
    for _ in range(200):
        app.processEvents()

    body = bridge._body
    phases = {}

    def wrap(owner, name, key):
        original = getattr(owner, name)

        def inner(*a, **k):
            n0, ms0 = calls["n"], calls["ms"]
            t = time.perf_counter()
            try:
                return original(*a, **k)
            finally:
                row = phases.setdefault(key, {"ms": [], "hl_calls": [], "hl_ms": []})
                row["ms"].append((time.perf_counter() - t) * 1000.0)
                row["hl_calls"].append(calls["n"] - n0)
                row["hl_ms"].append(calls["ms"] - ms0)

        setattr(owner, name, inner)

    wrap(BodyDocument, "render", "body_render")
    wrap(BodyDocument, "attach", "attach")

    def run_open(sid):
        phases.clear()
        n0, ms0 = calls["n"], calls["ms"]
        t = time.perf_counter()
        bridge.openSession(sid)
        total = (time.perf_counter() - t) * 1000.0
        return {"session": sid, "open_session_ms": round(total, 1),
                "hl_calls_total": calls["n"] - n0, "hl_ms_total": round(calls["ms"] - ms0, 1),
                "phases": {k: {"ms": round(min(v["ms"]), 1),
                               "hl_calls": v["hl_calls"][-1],
                               "hl_ms": round(v["hl_ms"][-1], 1)}
                           for k, v in phases.items()}}

    rows = [run_open("heavy-000"), run_open("heavy-001"), run_open("heavy-000")]
    for _ in range(20):
        app.processEvents()
    print("PHASE2 " + json.dumps({"turns": turns, "blocks": body.document.blockCount(),
                                  "rows": rows}, ensure_ascii=False))
    window.close()


if __name__ == "__main__":
    main()
