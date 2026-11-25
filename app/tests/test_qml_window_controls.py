"""标题栏窗口控件：真实 QML 窗口 + 像素几何 + ``QTest.mouseClick`` 状态断言。

判据来源（只读）：
- deva `apps/desktop/src/main/index.ts:79-81`：Linux 叠加层底色 #ffffff / #1e1e20；
- deva `apps/desktop/src/main/index.ts:89-97`：`overlayOptions` 的 `height: 40`；
- deva `apps/desktop/src/main/index.ts:112-116`：`titleBarStyle:'hidden'` + `titleBarOverlay`；
- deva 原版 1280×820 实拍 `out/latest-parity/deva/chat-deva.png` 逐像素：
  右上 96×40 实色块，三个 32×40 按钮 x=1184/1216/1248；最小化 10×2 @ (1195,23)；
  最大化 10×10 框 @ (1227,15)；关闭 10×10 X @ (1259,15)；图标 #5F6368。

这里不直接调 QML 槽位：全部走 ``QTest`` 真实鼠标事件，证明按钮点得动、窗口状态真的变。
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
    """QML 的 Repeater 委托不是 QObject 子节点，必须走视觉树 ``childItems()``。"""
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

    point = item.mapToScene(
        QPointF(item.property("width") / 2.0, item.property("height") / 2.0)
    )
    return point.x(), point.y()


def _click(window, x: float, y: float) -> None:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(x), round(y)), 100)


def _click_item(window, item) -> None:
    x, y = _center(item)
    _click(window, x, y)


def _pump(app, seconds: float = 0.4) -> None:
    from qml_shell import _pump as pump

    pump(app, lambda: False, seconds)


def _build_window(tmp_path, monkeypatch, sessions=None, mac_chrome=None):
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
    for index, (session_id, title) in enumerate(sessions or []):
        session = store.ensure_session(session_id)
        session.title = title
        session.createdAt = 1000 + index
        session.updatedAt = 1000 + index
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
    if mac_chrome is not None:
        engine.setInitialProperties({"macChrome": mac_chrome})
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
    return window, bridge, ticker, engine


def _pixel(image, x: int, y: int) -> tuple[int, int, int]:
    color = image.pixelColor(x, y)
    return color.red(), color.green(), color.blue()


def _dark_bbox(image, x0: int, x1: int, threshold: int = 200):
    coords = []
    for y in range(40):
        for x in range(x0, x1):
            red, green, blue = _pixel(image, x, y)
            if max(red, green, blue) < threshold:
                coords.append((x, y))
    if not coords:
        return None
    return (
        min(x for x, _ in coords),
        min(y for _, y in coords),
        max(x for x, _ in coords),
        max(y for _, y in coords),
        len(coords),
    )


@pytest.mark.skipif(sys.platform == "darwin", reason="macOS uses native traffic lights")
def test_window_controls_geometry_and_colors_match_deva(qapp, tmp_path, monkeypatch):
    """96×40 实色块、三个 32×40 命中区、三条字形逐像素落在 deva 实测位置。"""
    window, _bridge, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        _pump(qapp, 0.6)
        controls = _find_item(window.contentItem(), "windowControls")
        assert controls is not None and controls.property("visible") is True
        assert (
            controls.property("x"),
            controls.property("y"),
            controls.property("width"),
            controls.property("height"),
        ) == (1184, 0, 96, 40)

        buttons = [
            _find_item(window.contentItem(), name)
            for name in ("windowControlMinimize", "windowControlMaximize", "windowControlClose")
        ]
        assert all(button is not None for button in buttons)
        assert [
            (
                button.property("x"),
                button.property("y"),
                button.property("width"),
                button.property("height"),
            )
            for button in buttons
        ] == [(0, 0, 32, 40), (32, 0, 32, 40), (64, 0, 32, 40)]

        image = window.grabWindow()
        # 实色底：四角与字形间隙都是 #ffffff（设置弹框遮罩也压不暗它）。
        for point in ((1184, 0), (1279, 0), (1184, 39), (1279, 39), (1200, 5)):
            assert _pixel(image, *point) == (255, 255, 255), point

        # 三个字形 bbox / 像素数：与 deva 原版实拍逐值相同。
        assert _dark_bbox(image, 1184, 1216) == (1195, 23, 1204, 24, 20)
        assert _dark_bbox(image, 1216, 1248) == (1227, 15, 1236, 24, 64)
        assert _dark_bbox(image, 1248, 1280) == (1259, 15, 1268, 24, 48)
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


@pytest.mark.skipif(sys.platform == "darwin", reason="custom chrome is Linux/Windows only")
def test_window_controls_hover_and_real_state_changes(qapp, tmp_path, monkeypatch):
    """hover 底色 18/255 黑；最小化/最大化切换/关闭都改真实窗口状态。"""
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QWindow
    from PySide6.QtTest import QTest

    window, _bridge, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        _pump(qapp, 0.6)
        controls = _find_item(window.contentItem(), "windowControls")
        assert controls is not None

        # hover：白底叠 18/255 黑 = 237。
        QTest.mouseMove(window, QPoint(1200, 20))
        _pump(qapp, 0.2)
        assert _pixel(window.grabWindow(), 1200, 20) == (237, 237, 237)
        QTest.mouseMove(window, QPoint(800, 400))
        _pump(qapp, 0.2)
        assert _pixel(window.grabWindow(), 1200, 20) == (255, 255, 255)

        minimize = _find_item(window.contentItem(), "windowControlMinimize")
        maximize = _find_item(window.contentItem(), "windowControlMaximize")
        close = _find_item(window.contentItem(), "windowControlClose")

        # 最小化：点 32×40 命中区中心 → 窗口真的进入 Minimized。
        _click_item(window, minimize)
        _pump(qapp, 0.4)
        assert window.visibility() == QWindow.Minimized
        window.showNormal()
        _pump(qapp, 0.3)
        assert window.visibility() == QWindow.Windowed

        # 最大化：一次进入 Maximized，再点一次回 Normal（原版 toggle-maximize 语义）。
        _click_item(window, maximize)
        _pump(qapp, 0.4)
        assert window.visibility() == QWindow.Maximized
        # offscreen 的“最大化”会把窗口改成屏幕尺寸，按钮坐标必须按当前几何重算。
        _click_item(window, maximize)
        _pump(qapp, 0.4)
        assert window.visibility() == QWindow.Windowed

        # 关闭：窗口 hide/close，visible=False。
        _click_item(window, close)
        _pump(qapp, 0.4)
        assert window.isVisible() is False
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


@pytest.mark.skipif(sys.platform == "darwin", reason="custom chrome is Linux/Windows only")
def test_frameless_drag_and_resize_hit_regions(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QMargins, QPointF, Qt

    window, _bridge, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        _pump(qapp)
        assert window.flags() & Qt.FramelessWindowHint
        assert window.frameMargins() == QMargins(0, 0, 0, 0)
        assert (window.minimumWidth(), window.minimumHeight()) == (940, 600)
        root = window.contentItem()
        for name, accepted, excluded in [
            ("Rail", (28, 300), (28, 90)),
            ("Sidebar", (150, 6), (100, 25)),
            ("Header", (700, 15), (1200, 20)),
        ]:
            item = _find_item(root, "windowDrag" + name)
            assert item.contains(item.mapFromScene(QPointF(*accepted)))
            assert not item.contains(item.mapFromScene(QPointF(*excluded)))
        points = [(2, 2), (640, 2), (1278, 2), (2, 410),
                  (1278, 410), (2, 818), (640, 818), (1278, 818)]
        edges = [Qt.TopEdge | Qt.LeftEdge, Qt.TopEdge, Qt.TopEdge | Qt.RightEdge,
                 Qt.LeftEdge, Qt.RightEdge, Qt.BottomEdge | Qt.LeftEdge,
                 Qt.BottomEdge, Qt.BottomEdge | Qt.RightEdge]
        for index, (point, edge) in enumerate(zip(points, edges)):
            item = _find_item(root, "windowResize" + str(index))
            assert item.property("edges") == edge.value
            assert item.contains(item.mapFromScene(QPointF(*point)))
            assert not item.contains(item.mapFromScene(QPointF(640, 410)))
        window.showMaximized()
        _pump(qapp)
        assert _find_item(root, "windowResize7").property("enabled") is False
    finally:
        ticker.stop()
        window.close()
        _pump(qapp, 0.1)
        del engine


@pytest.mark.parametrize("mac", [False, True])
def test_platform_chrome_branch(qapp, tmp_path, monkeypatch, mac):
    from PySide6.QtCore import QPointF, Qt
    window, bridge, ticker, engine = _build_window(tmp_path, monkeypatch, mac_chrome=mac)
    try:
        _pump(qapp)
        assert bool(window.flags() & Qt.FramelessWindowHint) is (not mac)
        assert _find_item(window.contentItem(), "windowControls").isVisible() is (not mac)
        if mac:
            assert window.flags() & Qt.WindowCloseButtonHint
            assert window.flags() & Qt.WindowMinMaxButtonsHint
            assert window.flags() & Qt.ExpandedClientAreaHint
            assert not _find_item(window.contentItem(), "windowDragRail").contains(QPointF(20, 20))
            assert _find_item(window.contentItem(), "windowResize0").property("enabled") is False
    finally:
        ticker.stop()
        window.close()
        _pump(qapp, 0.1)
        del engine
