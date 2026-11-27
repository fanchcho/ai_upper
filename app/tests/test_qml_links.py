"""正文链接点击：原版 `<a>` 由 Chromium 打开，QML 侧必须显式接 linkActivated。

判据来源（只读）：deva `apps/desktop/src/renderer/src/redesign/ConvMessage.tsx` 用
ReactMarkdown 渲染链接（`<a href>` 原生可点）；`markdown/document.py:1108-1113` 已在
QTextDocument 写入 anchor href，缺的是 QML TextEdit 的 onLinkActivated 接线。
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


def _build(tmp_path, monkeypatch, messages):
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine

    from mvvm.models.chat_models import Message
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
    store.ensure_session("s-1")
    session = store.load_session("s-1")
    for role, content in messages:
        session.messages.append(Message(role=role, content=content))
    store.save("s-1")
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
    _pump(qapp_instance(), lambda: False, 0.7)
    return window, bridge, ticker, engine


def qapp_instance():
    from PySide6.QtGui import QGuiApplication

    return QGuiApplication.instance()


def test_slot_rejects_non_web_schemes(monkeypatch):
    from qml_shell import ShellBridge

    called = []
    monkeypatch.setattr("qml_shell._open_external", lambda url: called.append(url) or True)
    # 只测方案白名单，不构造窗口：用未初始化实例仍可调纯函数路径。
    assert ShellBridge.openExternal(object(), "javascript:alert(1)") is False
    assert ShellBridge.openExternal(object(), "") is False
    assert called == []
    assert ShellBridge.openExternal(object(), "https://example.com/a") is True
    assert called == ["https://example.com/a"]


def test_clicking_a_rendered_link_opens_it(qapp, tmp_path, monkeypatch):
    """真实鼠标点击正文中的链接，ShellBridge 收到完整 href。"""
    from PySide6.QtCore import QPointF
    from PySide6.QtTest import QTest
    from PySide6.QtCore import QPoint, Qt

    opened = []
    monkeypatch.setattr("qml_shell._open_external", lambda url: opened.append(url) or True)
    window, bridge, ticker, engine = _build(
        tmp_path, monkeypatch,
        [("user", "看这个链接"), ("assistant", "点这里：[示例站点](https://example.com/docs) 结束")],
    )
    try:
        body = _find_item(window.contentItem(), "bodyView")
        assert body is not None
        document = body.property("textDocument").textDocument()
        text = document.toPlainText()
        index = text.index("示例站点")
        block = document.findBlock(index)
        layout = block.layout()
        line = layout.lineForTextPosition(index - block.position())
        rect = line.rect()
        block_rect = document.documentLayout().blockBoundingRect(block)
        # 链接不是整行：用 QTextLine.cursorToX 取链接首字符的 x，再点字符中心。
        link_x = line.cursorToX(index - block.position())[0] + 10
        point = body.mapToScene(QPointF(link_x, block_rect.y() + rect.y() + rect.height() / 2))
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(point.x()), round(point.y())), 100)
        from qml_shell import _pump
        _pump(qapp, lambda: bool(opened), 3)
        assert opened == ["https://example.com/docs"]
    finally:
        ticker.stop(); window.close(); engine.deleteLater()
