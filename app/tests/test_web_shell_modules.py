"""Web 承载层三个模块在**真实 binding** 下的导入与构造（豁免名单的替代证据）。

`test_mvvm.py::test_every_mvvm_module_imports` 用空 submodule 的假 binding 遍历整棵树，
而这三个模块在**类体求值**时就要 Qt：`TitleBarOverlay(QWidget)`、`DevaWebWindow(QMainWindow)`、
`DevaBridge(QObject)` 且带 `Signal(...)`。懒导入只能推迟到函数体，类体推迟不了，所以它们在
那个用例里被显式豁免——本文件负责补上被豁免的覆盖，而不是让检查变绿了事。

无 Qt binding 的解释器上这些用例 skip（skip 原因写明），不假装通过。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

QtWidgets = pytest.importorskip(
    "PySide6.QtWidgets",
    reason="需要真实 Qt binding 才能对类体求值（假 binding 只有空 submodule）",
)
try:  # QtWebEngineWidgets 在部分裁剪安装里缺失；缺了就只跑叠加层与桥。
    import PySide6.QtWebEngineWidgets  # noqa: F401
    HAS_WEBENGINE = True
except ImportError:  # pragma: no cover - 取决于环境
    HAS_WEBENGINE = False


@pytest.fixture(scope="module")
def qapp():
    """必须有一个 QApplication 才能建 QWidget/QObject。"""
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


# ── 三个豁免模块都能导入 ──────────────────────────────────────────────────
def test_exempt_modules_import_with_real_binding():
    import mvvm.views.title_bar_overlay  # noqa: F401
    import mvvm.views.web_shell_window  # noqa: F401
    import mvvm.webui.bridge  # noqa: F401


# ── 标题栏叠加层 ──────────────────────────────────────────────────────────
def test_overlay_geometry_matches_electron_linux_overlay(qapp):
    from mvvm.views.title_bar_overlay import (
        BUTTON_WIDTH,
        TITLEBAR_HEIGHT,
        TitleBarOverlay,
    )

    overlay = TitleBarOverlay()
    overlay.resize(BUTTON_WIDTH * 3, TITLEBAR_HEIGHT)
    # 原版 Linux 的叠加层是右上角 96x40 实色块，三个 32x40 按钮右对齐。
    assert overlay.strip_size().width() == 96
    assert overlay.strip_size().height() == 40
    assert overlay.button_rect(0).x() == 0
    assert overlay.button_rect(2).x() == 64


def test_overlay_paints_opaque_background(qapp):
    """不透明是必需的：设置弹框的遮罩不能把叠加层压暗（原版 Linux 叠加层是实色）。"""
    from utils.qt_compat import QtGui

    from mvvm.views.title_bar_overlay import OVERLAY_BG, TITLEBAR_HEIGHT, TitleBarOverlay

    overlay = TitleBarOverlay()
    overlay.resize(96, TITLEBAR_HEIGHT)
    image = overlay.grab().toImage()
    pixel = image.pixelColor(0, 0)
    assert pixel.alpha() == 255
    assert (pixel.red(), pixel.green(), pixel.blue()) == (
        OVERLAY_BG.red(),
        OVERLAY_BG.green(),
        OVERLAY_BG.blue(),
    )


def test_overlay_dark_theme_switches_background(qapp):
    from mvvm.views.title_bar_overlay import OVERLAY_BG_DARK, TITLEBAR_HEIGHT, TitleBarOverlay

    overlay = TitleBarOverlay()
    overlay.resize(96, TITLEBAR_HEIGHT)
    overlay.set_dark(True)
    pixel = overlay.grab().toImage().pixelColor(0, 0)
    assert (pixel.red(), pixel.green(), pixel.blue()) == (
        OVERLAY_BG_DARK.red(),
        OVERLAY_BG_DARK.green(),
        OVERLAY_BG_DARK.blue(),
    )


# ── 桥接层：频道契约与错误语义（不建 WebEngine 页面）──────────────────────
def test_bridge_registers_contract_channels(qapp, tmp_path):
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.settings_service import SettingsService
    from mvvm.webui.bridge import DevaBridge

    home = tmp_path / "deva-home"
    bridge = DevaBridge(
        settings=SettingsService(home),
        personas=PersonaStore(home),
        store=ChatSessionStore(home),
        home=home,
    )
    for channel in (
        "config:get",
        "chat:list-sessions",
        "chat:attach-session",
        "skills:list",
        "skills:get",
        "browser:state",
        "window:set-overlay",
    ):
        assert bridge.handles(channel), f"桥接层缺少契约通道 {channel}"


def test_bridge_unknown_channel_is_explicit_not_silent(qapp, tmp_path):
    """未实现的通道必须在桥边界变成显式 reject，不能返回假成功。"""
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.settings_service import SettingsService
    from mvvm.webui.bridge import DevaBridge

    home = tmp_path / "deva-home"
    bridge = DevaBridge(
        settings=SettingsService(home),
        personas=PersonaStore(home),
        store=ChatSessionStore(home),
        home=home,
    )
    resolved: list[tuple] = []
    bridge._resolve = lambda *args: resolved.append(args)  # type: ignore[method-assign]

    bridge.invoke("7", "no:such-channel", "[]")

    assert len(resolved) == 1
    request_id, ok, payload = resolved[0]
    assert (request_id, ok) == ("7", False)
    assert payload["unimplemented"] is True
    assert "no:such-channel" in payload["message"]


def test_bridge_browser_state_carries_every_contract_key(qapp, tmp_path):
    """少一个键渲染层就整棵树抛错白屏（handoff 曾是这个坑），键集必须齐全。"""
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.settings_service import SettingsService
    from mvvm.webui.bridge import DevaBridge

    home = tmp_path / "deva-home"
    bridge = DevaBridge(
        settings=SettingsService(home),
        personas=PersonaStore(home),
        store=ChatSessionStore(home),
        home=home,
    )
    assert set(bridge._browser_state()) == {
        "open",
        "pinned",
        "active",
        "tabs",
        "current",
        "operating",
        "handoff",
    }


def test_bridge_skills_list_serves_builtins(qapp, tmp_path):
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.settings_service import SettingsService
    from mvvm.webui.bridge import DevaBridge

    home = tmp_path / "deva-home"
    bridge = DevaBridge(
        settings=SettingsService(home),
        personas=PersonaStore(home),
        store=ChatSessionStore(home),
        home=home,
    )
    assert [s["id"] for s in bridge._handlers["skills:list"]()] == [
        "create-skill",
        "create-agent",
        "create-mcp",
    ]


# ── 承载窗口（需要 QtWebEngine；缺了就 skip 并说明）───────────────────────
@pytest.mark.skipif(not HAS_WEBENGINE, reason="该安装没有 QtWebEngineWidgets")
def test_shell_window_builds_with_overlay(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.settings_service import SettingsService
    from mvvm.views.web_shell_window import DevaWebWindow

    home = tmp_path / "deva-home"
    window = DevaWebWindow(
        settings=SettingsService(home),
        personas=PersonaStore(home),
        store=ChatSessionStore(home),
    )
    # 1280x820 / 最小 940x600 与原版 BrowserWindow 同值。
    assert (window.width(), window.height()) == (1280, 820)
    assert (window.minimumWidth(), window.minimumHeight()) == (940, 600)
    # 叠加层贴右上角、只占 96x40。
    geo = window.overlay.geometry()
    assert (geo.x(), geo.y(), geo.width(), geo.height()) == (
        window.view.width() - 96,
        0,
        96,
        40,
    )
    window.view.stop()
    window.close()


def test_shell_shim_source_substitutes_placeholders(tmp_path):
    """shim 里两个占位符必须被替换掉；漏一个渲染层就拿到不是 JSON 的配置。"""
    from mvvm.views.web_shell_window import DevaWebWindow

    source = DevaWebWindow._shim_source({"theme": "light"})
    assert "__CONFIG_JSON__" not in source
    assert "__PLATFORM__" not in source
    assert '"theme": "light"' in source
    assert "'linux'" in source
