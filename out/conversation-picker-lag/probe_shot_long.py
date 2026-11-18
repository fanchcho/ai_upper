"""真实壳截图：400 轮大会话里代码着色 / 表格 / 列表 / h2 下划线是否正常。

不是「渲染成功」就算：截图后从 QML 文本控件读回块数，并把图裁成三段分别保存，
便于人工核对（整图 + 代码块区 + 表格区）。滚动到指定位置靠 QML 控件的
``contentY``，不是伪造一张图。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path("/home/agent/shared_workspace/ai_upper")
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(ROOT / "out" / "conversation-picker-lag"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def main():
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/render-chunking-shots")
    out_dir.mkdir(parents=True, exist_ok=True)
    home = Path(tempfile.mkdtemp(prefix="ai-upper-shot-"))
    os.environ["AI_UPPER_HOME"] = str(home)

    from probe_heavy import make_home
    make_home(home, 12, 400)

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

    def emit(payload):
        box["bridge"].emit(payload)

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

    bridge.openSession("heavy-000")
    for _ in range(120):
        app.processEvents()

    info = {}
    image = window.grabWindow()
    info["full"] = str(out_dir / "long-session-top.png")
    image.save(info["full"])

    # 找到正文 TextEdit 与它的文档，确认块数/是否含表格，再滚到中段截第二张。
    found = {}
    for obj in window.findChildren(object):
        name = obj.objectName() if hasattr(obj, "objectName") else ""
        if name:
            found.setdefault(name, obj)

    body = found.get("bodyView")
    if body is None:
        for obj in window.findChildren(object):
            if hasattr(obj, "property") and obj.property("textDocument") is not None:
                body = obj
                break

    if body is not None:
        quick_doc = body.property("textDocument")  # QQuickTextDocument
        doc = quick_doc.textDocument()
        scroll = found.get("bodyScroll")
        info["object_name"] = body.objectName()
        info["block_count"] = doc.blockCount()
        info["character_count"] = doc.characterCount()
        if scroll is not None:
            info["content_height"] = float(scroll.property("contentHeight"))
            info["visible_height"] = float(scroll.height())
        # 中段（表格区）
        if scroll is not None:
            span = float(scroll.property("contentHeight")) - float(scroll.height())
            scroll.setProperty("contentY", max(0.0, span) * 0.45)
        for _ in range(60):
            app.processEvents()
        info["mid"] = str(out_dir / "long-session-mid.png")
        window.grabWindow().save(info["mid"])
        # 末段（接近底部；Flickable 到边界会回弹，取 0.92 保证可见区不空）
        if scroll is not None:
            scroll.setProperty("contentY", max(0.0, span) * 0.92)
        for _ in range(60):
            app.processEvents()
        info["content_y_end"] = float(scroll.property("contentY")) if scroll is not None else None
        info["bottom"] = str(out_dir / "long-session-bottom.png")
        window.grabWindow().save(info["bottom"])
    else:
        info["body"] = "未找到正文 TextEdit"

    print("SHOT " + json.dumps(info, ensure_ascii=False))
    window.close()


if __name__ == "__main__":
    main()
