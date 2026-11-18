"""切换会话后，代码着色还在不在：数目标文档里 QTextLayout.FormatRange 的覆盖字符。

``QSyntaxHighlighter`` 把颜色写在 ``block.layout().formats()``（布局格式），
不是字符格式，``insertFragment`` 不搬运它们。这里在真实壳里连续切换多个会话，
分别统计同步段与首帧之后目标文档里的着色覆盖，确认「第二次打开还有没有颜色」。
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


def tint(doc):
    """返回 (着色块数, 着色字符数, 代码块数)。按布局格式统计，不依赖颜色值。"""
    from markdown.document import CODE_LANGUAGE_PROPERTY
    colored_blocks = colored_chars = code_blocks = 0
    want_next = 0
    block = doc.begin()
    while block.isValid():
        tag = block.blockFormat().property(CODE_LANGUAGE_PROPERTY)
        if isinstance(tag, str) and tag:
            code_blocks += 1
        layout = block.layout()
        ranges = layout.formats() if layout is not None else []
        chars = sum(r.length for r in ranges)
        if chars:
            colored_blocks += 1
            colored_chars += chars
        block = block.next()
    return colored_blocks, colored_chars, code_blocks


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    home = Path(tempfile.mkdtemp(prefix="ai-upper-tint-"))
    os.environ["AI_UPPER_HOME"] = str(home)

    from probe_heavy import make_home
    make_home(home, count, turns)

    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication

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

    found = {}
    for obj in window.findChildren(object):
        name = obj.objectName() if hasattr(obj, "objectName") else ""
        if name:
            found.setdefault(name, obj)
    qdoc = found["bodyView"].property("textDocument").textDocument()

    rows = []
    ids = ["heavy-000", "heavy-001", "heavy-000", "heavy-002", "heavy-000"]
    for sid in ids:
        t = time.perf_counter()
        bridge.openSession(sid)
        sync_ms = round((time.perf_counter() - t) * 1000.0, 1)
        after_sync = tint(qdoc)
        t = time.perf_counter()
        for _ in range(5):
            app.processEvents()
        frame_ms = round((time.perf_counter() - t) * 1000.0, 1)
        after_frame = tint(qdoc)
        rows.append({"id": sid, "sync_ms": sync_ms, "frame_ms": frame_ms,
                     "colors_after_sync": after_sync, "colors_after_frame": after_frame})

    print("TINT " + json.dumps(rows, ensure_ascii=False))
    window.close()


if __name__ == "__main__":
    main()
