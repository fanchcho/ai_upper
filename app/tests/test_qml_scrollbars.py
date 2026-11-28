"""会话侧栏 / 正文区滚动条：真实 QML ScrollBar 的几何、配色与滚动行为。

判据来自 deva（只读）：
- `apps/desktop/src/renderer/src/styles/app.css:45-62`：
  `::-webkit-scrollbar { width: 8px; height: 8px; }`；
  thumb `border-radius: var(--radius-full)`（tokens.css:26 = 999px）、
  `border: 2px solid transparent` + `background-clip: content-box`（可见宽 4px）；
  `:: -webkit-scrollbar-thumb:hover { background: var(--fg-subtle); }`；
  `::-webkit-scrollbar-track` 没有规则 → 透明；
- `tokens.css:81` 浅色 `--scrollbar: rgba(0,0,0,0.18)`；`:51` `--fg-subtle: #8a8a94`；
- deva 1280×820 实拍 `out/latest-parity/deva/chat-deva.png`：侧栏 thumb 在 x349..352，
  正文 thumb 在 x1274..1277，常态色分别 (202,202,203)（#f7f7f8 上）与 (209,209,209)（#fff 上）。

测试不直接改 `contentY`：滚轮事件与鼠标拖动都走真实 Qt 事件，证明附件滚动条真的可用。
"""
from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication

    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


def _find_item(root, name: str):
    """QML 的 Repeater 委托不是 QObject 子节点，必须走视觉树 `childItems()`。"""
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


def _pump(app, seconds: float = 0.35) -> None:
    from qml_shell import _pump as pump

    pump(app, lambda: False, seconds)


def _seed_home(home):
    """30 条会话（列表溢出）+ 第一条会话的超长正文（正文区溢出）。"""
    from mvvm.models.chat_models import Message
    from mvvm.services.chat_session_store import ChatSessionStore

    store = ChatSessionStore(home)
    now = int(time.time() * 1000)
    long_paragraphs = []
    for index in range(60):
        long_paragraphs.append(
            "## 滚动验证段落 %02d\n\n%s" % (index, "这一步只验证正文区能真实滚动。" * 12)
        )
    for index in range(30):
        session = store.ensure_session("scroll-%02d" % index, persona_id="general")
        session.title = "会话 %03d：滚动条验证" % index
        session.createdAt = now - index * 1000
        session.updatedAt = now - index * 1000
        if index == 0:
            session.messages = [
                Message(role="user", content="请从长文里核对滚动条。"),
                Message(role="assistant", content="\n\n".join(long_paragraphs)),
            ]
        else:
            session.messages = [Message(role="user", content="会话 %03d 的内容" % index)]
        store.save(session.id)
    return store


def _build_window(tmp_path, monkeypatch):
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine

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
    store = _seed_home(home)
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
        transport=text_stream("x"),
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
    # These pixel fixtures use the non-macOS 56px rail geometry.
    engine.setInitialProperties({"macChrome": False})
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
    window.requestActivate()
    ticker = _start_ticker(bridge)
    return window, bridge, ticker, engine


def _color_name(item) -> str:
    color = item.property("color")
    return color.name() if color is not None else ""


def _pixel(image, x: int, y: int) -> tuple[int, int, int]:
    color = image.pixelColor(x, y)
    return color.red(), color.green(), color.blue()


def _wheel(window, x: float, y: float, delta: int = -120) -> None:
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtTest import QTest

    QTest.wheelEvent(window, QPointF(x, y), QPoint(0, delta))


def _thumb_center(scrollbar) -> tuple[int, int]:
    from PySide6.QtCore import QPointF

    content = scrollbar.property("contentItem")
    center = content.mapToScene(QPointF(content.property("width") / 2.0,
                                        content.property("height") / 2.0))
    return round(center.x()), round(center.y())


def _drag_thumb(window, scrollbar, dy: float) -> None:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    x, y = _thumb_center(scrollbar)
    start = QPoint(x, y)
    end = QPoint(x, y + round(dy))
    QTest.mousePress(window, Qt.LeftButton, Qt.NoModifier, start, 100)
    QTest.mouseMove(window, end, 150)
    QTest.mouseRelease(window, Qt.LeftButton, Qt.NoModifier, end, 100)


def test_scrollbars_exist_and_match_deva_tokens(tmp_path, monkeypatch, qapp):
    window, _bridge, _ticker, _engine = _build_window(tmp_path, monkeypatch)
    _pump(qapp)

    sidebar = _find_item(window.contentItem(), "sidebar-scrollbar")
    body = _find_item(window.contentItem(), "body-scrollbar")
    assert sidebar is not None, "侧栏必须有真实的 QML ScrollBar（objectName=sidebar-scrollbar）"
    assert body is not None, "正文区必须有真实的 QML ScrollBar（objectName=body-scrollbar）"

    for bar in (sidebar, body):
        assert round(bar.property("width")) == 8
        assert round(bar.property("padding")) == 2
        content = bar.property("contentItem")
        assert round(content.property("width")) == 4, "2px 透明内缩后可见滑块宽必须为 4px"
        assert _color_name(content) == "#000000", "常态 thumb 是 rgba(0,0,0,0.18)"

    image = window.grabWindow()
    # 侧栏：ListView 右侧 8px 轨道 x347..354，2px 内缩后 thumb x349..352。
    assert _pixel(image, 350, 100) == (202, 202, 203), "侧栏滚动条常态色必须等于 deva 实拍"
    # 正文：贴窗口右缘，thumb x1274..1277；纵向按当前滚动位置取滑块中心。
    body_x, body_y = _thumb_center(body)
    assert body_x in (1275, 1276), "正文 thumb 必须落在 deva 实拍的 x1274..1277 内"
    assert _pixel(image, body_x, body_y) == (209, 209, 209), "正文滚动条常态色必须等于 deva 实拍"

    # hover：thumb 色切到 --fg-subtle #8a8a94（两处都测）。
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest

    QTest.mouseMove(window, QPoint(350, 100), 100)
    _pump(qapp, 0.2)
    assert _color_name(sidebar.property("contentItem")) == "#8a8a94"
    image = window.grabWindow()
    assert _pixel(image, 350, 100) == (138, 138, 148)

    QTest.mouseMove(window, QPoint(body_x, body_y), 100)
    _pump(qapp, 0.2)
    assert _color_name(body.property("contentItem")) == "#8a8a94"

    _ticker.stop()
    window.close()
    _engine.deleteLater()


def test_scrollbars_scroll_with_wheel_and_drag(tmp_path, monkeypatch, qapp):
    window, _bridge, _ticker, _engine = _build_window(tmp_path, monkeypatch)
    _pump(qapp)

    sidebar = _find_item(window.contentItem(), "sidebar-scrollbar")
    body = _find_item(window.contentItem(), "body-scrollbar")
    session_list = _find_item(window.contentItem(), "sessionList")
    body_scroll = _find_item(window.contentItem(), "bodyScroll")
    assert sidebar is not None and body is not None

    assert session_list.property("contentHeight") > session_list.property("height")
    assert body_scroll.property("contentHeight") > body_scroll.property("height")

    # 列表：滚轮向下 → contentY 增加。
    before = session_list.property("contentY")
    _wheel(window, 200, 300, -120)
    _pump(qapp, 0.3)
    after_wheel = session_list.property("contentY")
    assert after_wheel > before, "侧栏滚轮必须真的滚动 ListView"

    # 列表：拖动滚动条滑块向下 → contentY 继续增加。
    _drag_thumb(window, sidebar, 60)
    _pump(qapp, 0.3)
    assert session_list.property("contentY") > after_wheel, "侧栏滚动条拖动必须真的滚动"

    # 正文：打开会话时已停在底部（最新消息），滚轮向上 → contentY 减小。
    before_body = body_scroll.property("contentY")
    _wheel(window, 800, 400, 120)
    _pump(qapp, 0.3)
    after_body_wheel = body_scroll.property("contentY")
    assert after_body_wheel < before_body, "正文滚轮必须真的滚动 Flickable"

    # 正文：拖动滚动条滑块向上 → contentY 继续减小。
    _drag_thumb(window, body, -60)
    _pump(qapp, 0.3)
    assert body_scroll.property("contentY") < after_body_wheel, "正文滚动条拖动必须真的滚动"

    _ticker.stop()
    window.close()
    _engine.deleteLater()
