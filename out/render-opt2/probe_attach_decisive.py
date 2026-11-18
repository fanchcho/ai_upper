"""决定性对照：attach 的 endEditBlock 780 ms 是否由目标文档的高亮器造成。

探针在构造前安装（PySide 虚函数派发在构造时绑定）。五种情形，各取 3 次最小值：

1. ``with_highlighter``   —— 线上路径：高亮器挂目标文档；
2. ``without_highlighter``—— 高亮器留在自有文档，目标文档没有高亮器；
3. ``plain_target``      —— 同一片段搬进普通 QTextDocument（下限）；
4. ``empty_commit``       —— 空编辑块，量 begin/endEditBlock 自身的固定开销；
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
    home = Path(tempfile.mkdtemp(prefix="ai-upper-decide-"))
    os.environ["AI_UPPER_HOME"] = str(home)

    from probe_heavy import make_home
    make_home(home, count, turns)

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QTextCursor, QTextDocument, QTextDocumentFragment
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication

    from markdown.highlight import CodeHighlighter

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
    hl = body._highlighter

    def move(target, source):
        target.setDocumentMargin(0)
        cursor = QTextCursor(target)
        n0, ms0 = calls["n"], calls["ms"]
        t0 = time.perf_counter()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.removeSelectedText()
        cursor.beginEditBlock()
        cursor.insertFragment(QTextDocumentFragment(source))
        mid = time.perf_counter()
        cursor.endEditBlock()
        end = time.perf_counter()
        return {"insert_ms": round((mid - t0) * 1000.0, 1),
                "commit_ms": round((end - mid) * 1000.0, 1),
                "total_ms": round((end - t0) * 1000.0, 1),
                "hl_calls": calls["n"] - n0,
                "hl_ms": round(calls["ms"] - ms0, 1)}

    def best(fn, reps=3):
        rows = [fn() for _ in range(reps)]
        return min(rows, key=lambda r: r["total_ms"])

    target = quick.textDocument()

    def with_hl():
        if hl is not None and hl.document() is not target:
            hl.setDocument(target)
        return move(target, src)

    def without_hl():
        if hl is not None:
            hl.setDocument(src)  # 离开目标文档；目标文档不再有高亮器
        return move(target, src)

    def plain():
        return move(QTextDocument(), src)

    def empty_commit():
        cursor = QTextCursor(target)
        t = time.perf_counter()
        cursor.beginEditBlock()
        cursor.endEditBlock()
        return {"insert_ms": 0.0, "commit_ms": round((time.perf_counter() - t) * 1000.0, 2),
                "total_ms": round((time.perf_counter() - t) * 1000.0, 2),
                "hl_calls": 0, "hl_ms": 0.0}

    results = {
        "with_highlighter": best(with_hl),
        "without_highlighter": best(without_hl),
        "plain_target": best(plain),
        "empty_commit": empty_commit(),
    }

    print("DECIDE " + json.dumps({"turns": turns, "rows": results}, ensure_ascii=False))
    window.close()


if __name__ == "__main__":
    main()
