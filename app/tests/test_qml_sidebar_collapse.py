"""会话列表收起：原版 Ctrl/Cmd+B 切换 + 收起后悬停「对话」图标 200ms 浮出（peek）。

判据来源（只读）：deva `redesign/ChatFirstShell.tsx:143-199`：`listCollapsed` 存
`loadLayout().sidebarCollapsed`；Ctrl/Cmd+B 只在本页切换；浮出 200ms、收回 150ms。
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication

    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


def _find_item(root, name):
    try:
        if root.objectName() == name:
            return root
    except Exception:
        pass
    for child in root.childItems():
        found = _find_item(child, name)
        if found is not None:
            return found
    return None


def _build(tmp_path, monkeypatch):
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.settings_service import SettingsService
    from mvvm.services.skill_store import SkillStore
    from mvvm.services.workspace_guard import WorkspaceGuard
    from mvvm.webui.assembly import build_chat_host
    from qml_shell import ShellBridge, _plain_mode, _start_ticker, qml_main
    from test_qml_shell import MODELS, text_stream

    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    monkeypatch.setenv("DEVA_ASSETS_DIR", os.path.join(ROOT, "app", "assets"))
    home = tmp_path / "home"
    home.mkdir(parents=True)
    monkeypatch.setenv("AI_UPPER_HOME", str(home))
    settings = SettingsService(home)
    settings.set_config({"models": MODELS})
    vault = SecretsVault(home)
    vault.set_secret("p1", "sk-test")
    store = ChatSessionStore(home)
    for sid, title in (("s-1", "会话一"), ("s-2", "会话二")):
        store.ensure_session(sid)
        session = store.load_session(sid)
        session.title = title
        store.save(sid)
    PersonaStore(home).ensure_seeded()
    box = {}

    def emit(payload):
        box["bridge"].emit(payload)

    host, _ = build_chat_host(settings=settings, vault=vault, store=store, guard=WorkspaceGuard(),
                              home=home, emit=emit, emit_sessions_changed=lambda: None,
                              transport=text_stream("x"))
    bridge = ShellBridge(host=host, store=store, plain=_plain_mode(), settings=settings, vault=vault,
                         skills=SkillStore(home))
    box["bridge"] = bridge
    engine = QQmlApplicationEngine()
    # These pixel fixtures use the non-macOS 56px rail geometry.
    engine.setInitialProperties({"macChrome": False})
    bridge._engine = engine
    engine.rootContext().setContextProperty("shellBridge", bridge)
    engine.load(QUrl.fromLocalFile(str(qml_main())))
    window = engine.rootObjects()[0]
    bridge.bind_window(window)
    bridge.initial()
    window.setProperty("page", "chat")
    window.show()
    ticker = _start_ticker(bridge)
    from qml_shell import _pump
    _pump(qapp_inst(), lambda: False, 0.6)
    return window, bridge, settings, ticker, engine


def qapp_inst():
    from PySide6.QtGui import QGuiApplication
    return QGuiApplication.instance()


def test_ctrl_b_collapses_and_peek_hover_restores_list(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    from qml_shell import _pump

    window, bridge, settings, ticker, engine = _build(tmp_path, monkeypatch)
    try:
        side = _find_item(window.contentItem(), "sessionSide")
        conv = _find_item(window.contentItem(), "convColumn")
        chats = _find_item(window.contentItem(), "railChats")
        assert side is not None and conv is not None and chats is not None
        assert side.property("width") == 300
        assert conv.property("x") == 56 + 300

        QTest.keyClick(window, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.Key_B,
                       __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.ControlModifier)
        _pump(qapp, lambda: False, 0.4)
        assert window.property("sideCollapsed") is True
        assert side.property("width") == 0 and side.property("visible") is False
        assert conv.property("x") == 56, "收起后正文要占回列表的 300px"
        assert settings.get_config_sync().get("sidebarCollapsed") is True, "Ctrl+B 必须落盘"

        # 悬停「对话」图标：200ms 后浮出，正文宽度不变（覆盖式 peek）。
        QTest.mouseMove(window, QPoint(28, 88))
        _pump(qapp, lambda: False, 0.35)
        assert window.property("sidePeek") is True
        assert side.property("width") == 300 and side.property("visible") is True
        assert conv.property("x") == 56, "peek 是覆盖层，不该把正文挤走"

        # 移出图标与列表：150ms 后收回。
        QTest.mouseMove(window, QPoint(700, 500))
        _pump(qapp, lambda: False, 0.4)
        assert window.property("sidePeek") is False
        assert side.property("visible") is False

        # 再按一次恢复。
        QTest.keyClick(window, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.Key_B,
                       __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.ControlModifier)
        _pump(qapp, lambda: False, 0.3)
        assert window.property("sideCollapsed") is False
        assert side.property("width") == 300
        assert conv.property("x") == 356
        assert settings.get_config_sync().get("sidebarCollapsed") is False
    finally:
        ticker.stop(); window.close(); engine.deleteLater()
