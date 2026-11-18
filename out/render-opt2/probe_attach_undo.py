"""attach 的 endEditBlock 开销能不能绕开：撤销栈 / 排版触发点 / 文档可见性。

已知：400 轮正文搬进 QML 文档时，``endEditBlock`` 里花掉约 780 ms；同一份片段搬进
普通 ``QTextDocument`` 只要 2 ms。差别在 ``QQuickTextEdit`` 对 ``contentsChange``
的处理（整篇排版）。这里逐个排查可控开关：

- ``undo_off``   —— 搬运前 ``setUndoRedoEnabled(False)``；
- ``layout_before_commit`` —— 提交前先问一次 ``documentSize()``，看排版发生在哪；
- ``two_edits``  —— 拆成两个编辑块，确认不是「编辑块数量」本身的问题；
- ``plain_reference`` —— 普通文档同一片段的耗时，作为下限。
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
    home = Path(tempfile.mkdtemp(prefix="ai-upper-undo-"))
    os.environ["AI_UPPER_HOME"] = str(home)

    from probe_heavy import make_home
    make_home(home, count, 400)

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QTextCursor, QTextDocument, QTextDocumentFragment
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication

    from markdown import document as mdoc
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
    src = body.document

    def run(target, *, undo_off=False, ask_size=False, split=False):
        target.setDocumentMargin(0)
        if undo_off:
            target.setUndoRedoEnabled(False)
        cursor = QTextCursor(target)
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.removeSelectedText()
        fragment = QTextDocumentFragment(src)
        t0 = time.perf_counter()
        cursor.beginEditBlock()
        cursor.insertFragment(fragment)
        mid = time.perf_counter()
        size = None
        if ask_size:
            size = target.documentLayout().documentSize().height()
        after_ask = time.perf_counter()
        cursor.endEditBlock()
        end = time.perf_counter()
        if undo_off:
            target.setUndoRedoEnabled(True)
        return {
            "insert_ms": round((mid - t0) * 1000.0, 1),
            "ask_size_ms": round((after_ask - mid) * 1000.0, 1),
            "commit_ms": round((end - after_ask) * 1000.0, 1),
            "total_ms": round((end - t0) * 1000.0, 1),
            "size_seen": size,
        }

    def best(fn, reps=2):
        rows = [fn() for _ in range(reps)]
        return min(rows, key=lambda r: r["total_ms"])

    target = quick.textDocument()
    results = {
        "qml_baseline": best(lambda: run(target)),
        "qml_undo_off": best(lambda: run(target, undo_off=True)),
        "qml_ask_size": best(lambda: run(target, ask_size=True)),
        "plain": best(lambda: run(QTextDocument())),
        "undo_enabled_state": bool(target.isUndoRedoEnabled()),
        "blocks": target.blockCount(),
    }
    print("UNDO " + json.dumps(results, ensure_ascii=False))
    window.close()


if __name__ == "__main__":
    main()
