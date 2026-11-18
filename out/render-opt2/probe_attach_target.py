"""确认 attach 的 782 ms「endEditBlock」是不是 QML 文档特有的重排。

同一份正文片段分别搬进三种目标文档，逐句计时：

1. ``qml``   —— QML ``TextEdit`` 的 QQuickTextDocument（线上路径）；
2. ``plain`` —— 新建的普通 QTextDocument（没有 QQuickTextEdit 观察）；
3. ``plain_highlighter`` —— 普通文档 + 高亮器，看高亮器是否被 contentsChange 驱动。

同时记录 attach 之后 ``processEvents`` 驱动出的高亮调用次数与耗时——用来判断
「高亮到底发生在同步段里，还是发生在后面的帧里」。
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
    home = Path(tempfile.mkdtemp(prefix="ai-upper-attachtarget-"))
    os.environ["AI_UPPER_HOME"] = str(home)

    from probe_heavy import make_home
    make_home(home, count, turns)

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QTextCursor, QTextDocument, QTextDocumentFragment
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication

    from markdown.body import BodyDocument
    from markdown.highlight import CodeHighlighter
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
    bridge.openSession("heavy-000")
    for _ in range(200):
        app.processEvents()

    found = {}
    for obj in window.findChildren(object):
        name = obj.objectName() if hasattr(obj, "objectName") else ""
        if name:
            found.setdefault(name, obj)
    quick = found["bodyView"].property("textDocument")
    source_doc = body.document

    calls = {"n": 0, "ms": 0.0}
    orig_hl = CodeHighlighter.highlightBlock

    def counted(self, text):
        t = time.perf_counter()
        try:
            return orig_hl(self, text)
        finally:
            calls["n"] += 1
            calls["ms"] += (time.perf_counter() - t) * 1000.0

    CodeHighlighter.highlightBlock = counted

    def transfer(target, with_highlighter=False):
        hl = CodeHighlighter(target, body.style) if with_highlighter else None
        calls["n"] = calls["ms"] = 0
        t0 = time.perf_counter()
        target.setDocumentMargin(0)
        cursor = QTextCursor(target)
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.removeSelectedText()
        t_remove = time.perf_counter()
        fragment = QTextDocumentFragment(source_doc)
        t_frag = time.perf_counter()
        cursor.insertFragment(fragment)
        t_insert = time.perf_counter()
        cursor.endEditBlock()
        t_end = time.perf_counter()
        return {
            "remove_ms": round((t_remove - t0) * 1000.0, 1),
            "fragment_ctor_ms": round((t_frag - t_remove) * 1000.0, 1),
            "insertFragment_ms": round((t_insert - t_frag) * 1000.0, 1),
            "endEditBlock_ms": round((t_end - t_insert) * 1000.0, 1),
            "sync_total_ms": round((t_end - t0) * 1000.0, 1),
            "hl_calls_sync": calls["n"],
            "hl_ms_sync": round(calls["ms"], 1),
            "_hl": hl,
        }

    def frames():
        calls["n"] = calls["ms"] = 0
        t = time.perf_counter()
        for _ in range(30):
            app.processEvents()
        return round((time.perf_counter() - t) * 1000.0, 1), calls["n"], round(calls["ms"], 1)

    results = {}
    for label, factory in (
        ("qml", lambda: quick.textDocument()),
        ("plain", lambda: QTextDocument()),
    ):
        target = factory()
        row = transfer(target)
        target.documentLayout() if hasattr(target, "documentLayout") else None
        row.pop("_hl", None)
        results[label] = row

    # 普通文档 + 高亮器：它会被 contentsChange 驱动吗？
    plain_hl_target = QTextDocument()
    row = transfer(plain_hl_target, with_highlighter=True)
    hl = row.pop("_hl")
    row["hl_calls_after_ctor_only"] = row.pop("hl_calls_sync")
    row["hl_ms_after_ctor_only"] = row.pop("hl_ms_sync")
    calls["n"] = calls["ms"] = 0
    t = time.perf_counter()
    hl.rehighlight()
    row["explicit_rehighlight_ms"] = round((time.perf_counter() - t) * 1000.0, 1)
    row["hl_calls_explicit"] = calls["n"]
    results["plain_highlighter"] = row

    frame_ms, frame_calls, frame_hl_ms = frames()
    results["after_attach_frames"] = {"processEvents_30x_ms": frame_ms,
                                      "hl_calls": frame_calls, "hl_ms": frame_hl_ms}
    print("TARGET " + json.dumps({"turns": turns, "results": results}, ensure_ascii=False))
    window.close()


if __name__ == "__main__":
    main()
