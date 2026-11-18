"""attach 的 782 ms 到底是不是 QQuickTextEdit 的整篇排版，能不能分摊。

同一份片段搬进 QML 文档，比较：

- ``one_edit_block``：现状，一次 begin/endEditBlock；
- ``chunked``：每 N 个顶层块一个编辑块（模拟分块搬运），看排版是否被分摊；
- ``layout_after``：搬完再显式 ``documentLayout()``，确认排版是否已经发生过。

另测不同轮数（60/120/400）下 endEditBlock 的规模关系，判断它是线性还是二次。
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
    home = Path(tempfile.mkdtemp(prefix="ai-upper-attachlayout-"))
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

    # 从正文源码重新渲染出几份不同规模的源文档
    source = body.source
    style, width = body.style, body.content_width
    blocks = mdoc.parse_markdown(source)
    per_turn = len(blocks) // 400

    def source_doc(turns):
        doc = QTextDocument()
        doc.setDocumentMargin(0)
        renderer = mdoc._Renderer(doc, style, width, None)
        renderer.render_blocks(blocks[: turns * per_turn], QTextCursor(doc))
        mdoc._collapse_edge_margins(doc)
        return doc

    def transfer(target, src, per_edit=None):
        target.setDocumentMargin(0)
        cursor = QTextCursor(target)
        t0 = time.perf_counter()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.removeSelectedText()
        removed = time.perf_counter()
        if per_edit is None:
            fragment = QTextDocumentFragment(src)
            cursor.beginEditBlock()
            cursor.insertFragment(fragment)
            cursor.endEditBlock()
            total = time.perf_counter() - t0
            return {"total_ms": round(total * 1000.0, 1),
                    "insert_and_commit_ms": round(total * 1000.0, 1),
                    "remove_ms": round((removed - t0) * 1000.0, 1)}
        # 分编辑块搬运：按源文档的顶层块分段，每段一个 fragment。
        t_start = time.perf_counter()
        block = src.begin()
        group = []
        commit_ms = 0.0
        inserted = 0
        while block.isValid():
            group.append(block.blockNumber())
            if len(group) >= per_edit:
                commit_ms += _insert_group(cursor, src, group)
                inserted += len(group)
                group = []
            block = block.next()
        if group:
            commit_ms += _insert_group(cursor, src, group)
            inserted += len(group)
        total = time.perf_counter() - t_start
        return {"total_ms": round(total * 1000.0, 1),
                "commit_ms": round(commit_ms, 1),
                "remove_ms": round((removed - t0) * 1000.0, 1),
                "groups": (inserted + per_edit - 1) // per_edit}

    def _insert_group(cursor, src, numbers):
        start = src.findBlockByNumber(numbers[0]).position()
        end_block = src.findBlockByNumber(numbers[-1])
        end = end_block.position() + end_block.length() - 1
        cursor.beginEditBlock()
        partial = QTextCursor(src)
        partial.setPosition(start)
        partial.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertFragment(QTextDocumentFragment(partial))
        t = time.perf_counter()
        cursor.endEditBlock()
        return (time.perf_counter() - t) * 1000.0

    def layout_now(target):
        t = time.perf_counter()
        target.documentLayout().documentSize()
        return round((time.perf_counter() - t) * 1000.0, 2)

    results = {}
    for turns in (60, 120, 400):
        src = source_doc(turns)
        target = quick.textDocument()
        row = {"source_blocks": src.blockCount()}
        row["one_edit_block"] = transfer(target, src)
        row["layout_after_ms"] = layout_now(target)
        for per_edit in (200, 800):
            if src.blockCount() <= per_edit:
                continue
            row["chunked_%d" % per_edit] = transfer(target, src, per_edit=per_edit)
        results["turns_%d" % turns] = row
    print("LAYOUT " + json.dumps(results, ensure_ascii=False))
    window.close()


if __name__ == "__main__":
    main()
