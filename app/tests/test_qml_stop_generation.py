"""停止生成：原版 Composer 的停止键（busy 时同位置切成 Square 中性键）。

判据来源（只读）：
- deva `apps/desktop/src/renderer/src/redesign/Composer.tsx:973-991`：回合进行中
  输入框为空时同一枚键显示停止，`onClick={stopTurn}`；
- deva `redesign.css:2798-2829`：`.cf-send` 最小宽度 68（两态同宽不跳动），
  `.cf-send.is-stop` 用 `--bg-hover` 中性底色 + `--fg` 图标，Square size=14 fill。
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


def _find_item(root, name: str):
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


def _center(item) -> tuple[float, float]:
    from PySide6.QtCore import QPointF

    point = item.mapToScene(QPointF(item.property("width") / 2.0, item.property("height") / 2.0))
    return point.x(), point.y()


def _click(window, x: float, y: float) -> None:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(x), round(y)), 100)


def _pump(app, seconds: float = 0.3) -> None:
    from qml_shell import _pump as pump

    pump(app, lambda: False, seconds)


def _build_window(tmp_path, monkeypatch, transport, sessions=("s-1",)):
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
    from test_qml_shell import MODELS

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
    for session_id in sessions:
        store.ensure_session(session_id)
        store.save(session_id)
    PersonaStore(home).ensure_seeded()

    box: dict = {}

    def emit(payload):
        box["bridge"].emit(payload)

    host, _gateway = build_chat_host(
        settings=settings,
        vault=vault,
        store=store,
        guard=WorkspaceGuard(),
        home=home,
        emit=emit,
        emit_sessions_changed=lambda: None,
        transport=transport,
    )
    bridge = ShellBridge(
        host=host,
        store=store,
        plain=_plain_mode(),
        settings=settings,
        vault=vault,
        skills=SkillStore(home),
    )
    box["bridge"] = bridge

    engine = QQmlApplicationEngine()
    bridge._engine = engine
    engine.rootContext().setContextProperty("shellBridge", bridge)
    engine.load(QUrl.fromLocalFile(str(qml_main())))
    roots = engine.rootObjects()
    assert len(roots) == 1, "Main.qml 必须能独立加载"
    window = roots[0]
    bridge.bind_window(window)
    bridge.initial()
    window.setProperty("page", "chat")
    window.show()
    ticker = _start_ticker(bridge)
    return window, bridge, store, ticker, engine


def test_stop_button_is_a_real_click_that_aborts_the_turn(qapp, tmp_path, monkeypatch):
    """真实鼠标点停止键：busy 时按钮切成 Square 中性态，点击后回合以 aborted 收尾。"""
    import threading

    from test_qml_shell import gated_stream

    gate = threading.Event()
    window, bridge, store, ticker, engine = _build_window(
        tmp_path, monkeypatch, gated_stream("开头", gate)
    )
    try:
        _pump(qapp, 0.5)
        assert bridge.openSession("s-1") is True
        assert bridge.send("问题") is True
        # 等到达第一个 delta、busy 属性真的写进 QML。
        deadline = __import__("time").time() + 10
        while __import__("time").time() < deadline and not (window.property("busy") and bridge.deltas):
            _pump(qapp, 0.1)
        assert window.property("busy") is True
        assert bridge.deltas == ["开头"], "先出现一段增量，再验证停止保留半截正文"
        send = _find_item(window.contentItem(), "sendBtn")
        glyph = _find_item(window.contentItem(), "stopGlyph")
        assert send is not None and glyph is not None
        assert glyph.property("visible") is True, "busy 时必须显示停止图标，不是发送文字"

        x, y = _center(send)
        _click(window, x, y)
        # 等回合收尾；ChatHost 的 abort 会让 VM 返回 stopReason=aborted。
        from qml_shell import _pump as pump

        pump(qapp, lambda: bridge.turn_finished(), 10)
        assert bridge.turn_finished() is True
        assert bridge.stop == "aborted"
        session = store.load_session("s-1")
        assert [m.role for m in session.messages] == ["user", "assistant"]
        assert "开头" in session.messages[-1].text()
        # 停止后按钮恢复发送态。
        assert window.property("busy") is False
        assert glyph.property("visible") is False
    finally:
        gate.set()
        ticker.stop()
        window.close()
        engine.deleteLater()


def test_stop_without_a_running_turn_reports_false(qapp, tmp_path, monkeypatch, capsys):
    """没有回合可停时明确返回 False，不假装已停止。"""
    from test_qml_shell import text_stream

    window, bridge, _store, ticker, engine = _build_window(tmp_path, monkeypatch, text_stream("好"))
    try:
        assert bridge.stopGeneration() is False
        assert "QML STOP IGNORED" in capsys.readouterr().err
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()
