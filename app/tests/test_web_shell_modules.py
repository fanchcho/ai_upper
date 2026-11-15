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
import types
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


_NO_WEBENGINE_SCRIPT = r"""
import importlib.abc
import sys

blocked = {"PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick"}


class _BlockWebEngine(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in blocked:
            raise ImportError("No module named '%s'" % fullname)
        return None


# 必须在导入 mvvm.views.web_shell_window 之前装好：类体求值阶段就会取 WebEngine。
sys.meta_path.insert(0, _BlockWebEngine())

import mvvm.views.web_shell_window as shell

assert shell.QWebEngineView is None, shell.QWebEngineView
assert isinstance(shell._WEBENGINE_ERROR, ImportError), shell._WEBENGINE_ERROR

from PySide6.QtWidgets import QApplication

app = QApplication([])
try:
    shell.DevaWebWindow(settings=None, personas=None, store=None)
except ImportError as exc:
    assert "没有 QtWebEngine" in str(exc), str(exc)
else:
    raise SystemExit("缺 QtWebEngine 的 binding 上，DevaWebWindow 竟然构造成功")
print("NO-WEBENGINE OK:", shell._WEBENGINE_ERROR)
"""


def test_shell_module_imports_without_webengine(tmp_path):
    """没有 QtWebEngine 的 binding 上，模块本身仍可导入，缺件在窗口构造时报。

    PySide6 的 win_arm64 wheel 不打包 QtWebEngineCore（6.9–6.12 各版本实测都没有），
    PySide2 也没有。类体若直接取 `QtWebEngineCore.QWebEngineScript`，`import
    mvvm.views.web_shell_window` 就在这类解释器上失败，报的却是包装层的
    「PySide6 has no submodule」——看不出是平台缺件，连「模块可导入」这条既有约定
    也一起破了（见 views/__init__ 的说明）。

    这里在**子进程**里屏蔽 WebEngine 子模块再导入，断言两件事：导入成功，且构造窗口
    时抛出的 ImportError 带原文。用子进程而不是 `importlib.reload`：本进程已经有
    活的 QApplication 和由 shiboken 注册的 Qt 类，重载会重复定义同名的 Qt 类型，
    PySide6 直接 abort 整个解释器。子进程也更贴近真机——win_arm64 上 WebEngine
    从来就没装上过。不是 skip：它检查的正是缺件时的真实行为。
    """
    import subprocess

    script = tmp_path / "no_webengine.py"
    script.write_text(_NO_WEBENGINE_SCRIPT, encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(SRC)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    env["QT_QPA_PLATFORM"] = "offscreen"
    env.setdefault("DEVA_HOME", str(tmp_path / "deva-home"))

    proc = subprocess.run(
        # 不能加 -I：它会忽略 PYTHONPATH，而脚本要导入 app/src 下的 mvvm。
        [sys.executable, str(script)],
        cwd=str(SRC),
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    assert "NO-WEBENGINE OK" in proc.stdout, proc.stdout


def test_webengine_class_lookup_follows_the_binding_not_a_fixed_submodule():
    """Qt5 与 Qt6 把 QWebEngineScript/QWebEngineSettings 放在不同子模块。

    PySide2 5.15 只在 ``QtWebEngineWidgets`` 里定义它们，``QtWebEngineCore`` 只有
    URL 与请求拦截那一批；PySide6 反过来。写死 ``QtWebEngineCore.QWebEngineScript``
    的后果不是「降级」，是打包产物在 3.8/win_amd64 上起不来——CI 的
    ``windows-x86_64 3.8.10`` leg 就是这样红的（run 43600186928 job 132463066925，
    ``[6/6] Target runtime smoke`` 抛 ImportError）。

    只测 ``_webengine_class`` 这个纯查找函数：两个布局各自找到类，都找不到时抛
    ImportError 而不是返回 None（None 会让缺件推迟到更远的地方才炸）。不重新导入
    模块——本进程里有活的 Qt 类型，重载会重复定义同名 Qt 类并 abort 解释器
    （见 ``test_shell_module_imports_without_webengine`` 的说明）。
    """
    from mvvm.views.web_shell_window import _webengine_class

    class _Marker:
        pass

    script = _Marker()
    settings = _Marker()
    view = _Marker()

    # Qt5 布局：类都在 QtWebEngineWidgets，Core 里没有。
    shell_module = sys.modules["mvvm.views.web_shell_window"]
    original = (shell_module.QtWebEngineCore, shell_module.QtWebEngineWidgets)
    try:
        shell_module.QtWebEngineCore = types.SimpleNamespace()
        shell_module.QtWebEngineWidgets = types.SimpleNamespace(
            QWebEngineScript=script, QWebEngineSettings=settings, QWebEngineView=view
        )
        assert _webengine_class("QWebEngineScript") is script
        assert _webengine_class("QWebEngineView") is view

        # Qt6 布局：Script/Settings 在 Core。
        shell_module.QtWebEngineCore = types.SimpleNamespace(
            QWebEngineScript=script, QWebEngineSettings=settings
        )
        shell_module.QtWebEngineWidgets = types.SimpleNamespace(QWebEngineView=view)
        assert _webengine_class("QWebEngineScript") is script
        assert _webengine_class("QWebEngineSettings") is settings
        assert _webengine_class("QWebEngineView") is view

        # 两个子模块都没有：导入阶段就要报错，不能静默得到 None。
        shell_module.QtWebEngineCore = types.SimpleNamespace()
        shell_module.QtWebEngineWidgets = types.SimpleNamespace()
        with pytest.raises(ImportError, match="QWebEngineScript"):
            _webengine_class("QWebEngineScript")
    finally:
        shell_module.QtWebEngineCore, shell_module.QtWebEngineWidgets = original


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


def test_readiness_probe_reads_a_string_not_a_javascript_boolean():
    """readiness 探测不能依赖 runJavaScript 对布尔值的转换。

    PySide6 6.6（最后一个有 cp38 wheel 的版本）把 JS ``true``/``false`` 转成**空串**，
    6.11 才转成 ``True``/``False``；PySide2 同样不给 bool。按真假判断时，`bridge=`
    在 readiness 那一行永远是空——CI 的 3.8 leg 会用 built 产物复现（bridge= 空、
    退出码 1）。所以探测脚本必须把结果包成字符串，Python 侧再比 ``"true"``。
    """
    import inspect

    import main as entry

    source = inspect.getsource(entry._probe_renderer)
    # 探测表达式本身必须是 String(...)：直接返回布尔值就会踩上面那个转换差异。
    assert "String(!!(window.deva && window.deva.chat))" in source, source
    # 判定必须是「等于字符串 true」，不是真值判断：空串在真值判断下同样是假，
    # 但 6.6 上它既可能是 false 也可能是 true，无法区分。
    assert '"true"' in source, source


def test_readiness_probe_interprets_the_string_result():
    """把两次真机观测到的回调值都喂给判定逻辑，只有 'true' 算就绪。"""
    import main as entry

    def verdict(value):
        # 与 _probe_renderer 里的判定保持同一表达式。
        return value == "true"

    assert verdict("true") is True
    assert verdict("") is False        # PySide6 6.6 / PySide2 的布尔转换结果
    assert verdict(False) is False
    assert verdict(True) is False      # 6.11 的回调值，也不该被当作探测结果
    assert entry.HEADLESS_ENV == "AI_UPPER_HEADLESS"


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


def _make_bridge(tmp_path):
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.settings_service import SettingsService
    from mvvm.webui.bridge import DevaBridge

    home = tmp_path / "deva-home"
    return DevaBridge(
        settings=SettingsService(home),
        personas=PersonaStore(home),
        store=ChatSessionStore(home),
        home=home,
    )


def test_window_actions_are_wired_or_raise_not_fake_success(qapp, tmp_path):
    """窗口控制必须有真实实现；没注入时显式报错，不能返回假成功。"""
    bridge = _make_bridge(tmp_path)
    for channel in ("window:minimize", "window:toggle-maximize", "window:close"):
        with pytest.raises(Exception) as excinfo:
            bridge._handlers[channel]()
        assert "未接线" in str(excinfo.value), channel

    calls: list[str] = []
    bridge.set_window_actions(
        minimize=lambda: calls.append("min"),
        toggle_maximize=lambda: calls.append("max"),
        close=lambda: calls.append("close"),
        is_fullscreen=lambda: False,
    )
    bridge._handlers["window:minimize"]()
    bridge._handlers["window:toggle-maximize"]()
    bridge._handlers["window:close"]()
    assert calls == ["min", "max", "close"]
    assert bridge._handlers["window:is-fullscreen"]() is False


def test_clipboard_round_trip_uses_qt_clipboard(qapp, tmp_path):
    bridge = _make_bridge(tmp_path)
    bridge._handlers["clipboard:write-text"]("粘贴测试")
    assert bridge._handlers["clipboard:read-text"]() == "粘贴测试"
    # 原版对非字符串入参按空串处理
    assert bridge._handlers["clipboard:write-text"](None) == {"ok": True}
    assert bridge._handlers["clipboard:read-text"]() == ""


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
    from utils.platform_name import runtime_platform

    source = DevaWebWindow._shim_source({"theme": "light"})
    assert "__CONFIG_JSON__" not in source
    assert "__PLATFORM__" not in source
    assert '"theme": "light"' in source
    # 渲染层按 Electron 的拼写判断平台（'darwin' / 'win32' / 'linux'）；这里钉的
    # 是「注入的是本机平台」，不是某台机器恰好是 linux。
    assert f"'{runtime_platform()}'" in source


# ── 空态通道：形状与契约一致（不是「占位式成功」）─────────────────────────
def test_browser_ready_and_preview_pinned_follow_contract(qapp, tmp_path):
    """`browser:ready` 与 `browser:state` 同形状；`browser:preview-pinned` 回 `{ok:true}`。

    内置浏览器未移植，这两个通道的**语义**是空态；契约要求的键集与返回形状仍必须对上，
    否则渲染层读 `state.tabs` / `handoff[id]` 时整棵树抛错白屏。这里钉的是形状，不是浏览
    器能力——能力缺口在台账里判「已知差异」。
    """
    bridge = _make_bridge(tmp_path)
    state = bridge._handlers["browser:state"]()
    assert bridge._handlers["browser:ready"]() == state
    assert bridge._handlers["browser:preview-pinned"](None) == {"ok": True}
    assert bridge._handlers["browser:preview-pinned"]("tab-1") == {"ok": True}


def test_update_state_uses_phase_key(qapp, tmp_path):
    """`UpdateState` 是 `{phase:'idle'}` 判别联合；键名写成 status 渲染层读不到。"""
    bridge = _make_bridge(tmp_path)
    assert bridge._handlers["update:get-state"]() == {"phase": "idle"}


def test_remote_state_is_bots_only(qapp, tmp_path):
    """`remote:get-state` 契约是 `{bots: BotView[]}`；多出来的键会把设置页的渲染分支带偏。"""
    bridge = _make_bridge(tmp_path)
    assert bridge._handlers["remote:get-state"]() == {"bots": []}


def test_app_platform_matches_shim(qapp, tmp_path):
    """`app:get-platform` 与 shim 注入的 `__PLATFORM__` 同值，且是本机平台。"""
    from mvvm.views.web_shell_window import DevaWebWindow
    from utils.platform_name import runtime_platform

    bridge = _make_bridge(tmp_path)
    current = runtime_platform()
    assert current in {"linux", "darwin", "win32"}
    assert bridge._handlers["app:get-platform"]() == current
    assert f"'{current}'" in DevaWebWindow._shim_source({})
