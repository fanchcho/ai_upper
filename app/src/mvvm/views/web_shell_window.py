"""原版渲染层承载窗口：QtWebEngine 显示 Deva 的构建产物，Python 侧接管 `window.deva`。

选型（详见 docs/BUILD-PROGRESS.md「界面一致性」章节）：原版界面的富文本输入、代码块、
动效与图标体系是 React/Lexical/xterm 的产物，用 Qt 控件重画不可能逐像素一致；用户的硬要求是
「与原版完全一致」，因此这里直接复用原版前端产物（`app/assets/renderer`，构建自 deva 工程，
只读拷贝），由本窗口承载，`DevaBridge` 提供数据与事件。

窗口尺寸与装饰对齐原版 `main/index.ts`：
- 1280x820，最小 940x600（原版 BrowserWindow 同值）；
- `titleBarStyle: 'hidden'` + 标题栏叠加层：Qt 侧用无边框窗口 + 自绘右上角三个按钮补足；
- 背景色随主题（浅色 #ffffff / 深色 #1e1e20），避免加载瞬间闪白。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from utils.qt_compat import QtCore, QtWebChannel, QtWebEngineCore, QtWebEngineWidgets, QtWidgets

QFile = QtCore.QFile
QIODevice = QtCore.QIODevice
QSize = QtCore.QSize
Qt = QtCore.Qt
QUrl = QtCore.QUrl
QWebChannel = QtWebChannel.QWebChannel
QWebEngineScript = QtWebEngineCore.QWebEngineScript
QWebEngineSettings = QtWebEngineCore.QWebEngineSettings
QWebEngineView = QtWebEngineWidgets.QWebEngineView
QMainWindow = QtWidgets.QMainWindow
QWidget = QtWidgets.QWidget

from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.persona_store import PersonaStore
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.views.title_bar_overlay import TITLEBAR_HEIGHT, TitleBarOverlay
from mvvm.webui.assembly import build_chat_host, trusted_workspace_from_env
from mvvm.webui.bridge import DevaBridge

# 回合线程攒下的界面写入（busy / status / streaming）由 GUI 线程周期性 drain。
DRAIN_INTERVAL_MS = 50

ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets" / "renderer"


def assets_dir() -> Path:
    """打包后资产目录可能被拷到别处：先看常量，再看环境变量覆盖。"""
    import os

    override = os.environ.get("DEVA_RENDERER_DIR")
    return Path(override) if override else ASSETS_DIR


def _read_qwebchannel_source() -> str:
    file = QFile(":/qtwebchannel/qwebchannel.js")
    if not file.open(QIODevice.ReadOnly):
        raise RuntimeError("Qt 资源里没有 qwebchannel.js：QtWebChannel 未安装？")
    try:
        return bytes(file.readAll()).decode("utf-8")
    finally:
        file.close()


def _script(name: str, source: str) -> QWebEngineScript:
    script = QWebEngineScript()
    script.setName(name)
    script.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    script.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    script.setRunsOnSubFrames(False)
    script.setSourceCode(source)
    return script


class DevaWebWindow(QMainWindow):
    """承载原版渲染层的窗口。菜单/工具栏一概不加，避免任何「Qt 风格」额外像素。"""

    def __init__(
        self,
        *,
        settings: Any,
        personas: PersonaStore,
        store: Any,
        vault: Any = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Deva")
        self.resize(1280, 820)
        self.setMinimumSize(940, 600)

        self.view = QWebEngineView(self)
        self.view.setContextMenuPolicy(Qt.NoContextMenu)
        page = self.view.page()
        page.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        page.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        page.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows, False)

        self.channel = QWebChannel(self)
        home = Path(settings.home)
        vault = vault if vault is not None else SecretsVault(home)
        self.bridge = DevaBridge(settings=settings, personas=personas, store=store, home=home)
        self.bridge.vault = vault

        # ── 回合装配：写通道（chat:send / abort / …）由宿主执行 ──────────────
        # 受信根：启动时按 DEVA_APP_WORKSPACE 登记；会话里的 focusRoot 在
        # `chat:list-sessions` 时补登记（与原版一致，否则重启后 git/fs 报拒绝访问）。
        self.guard = WorkspaceGuard()
        workspace = trusted_workspace_from_env()
        if workspace:
            self.guard.trust_root(workspace)
        self.host, self.gateway = build_chat_host(
            settings=settings,
            vault=vault,
            store=store,
            guard=self.guard,
            home=home,
            # 回合在后台线程跑，事件从那里推；桥内部会回到 GUI 线程再写页面。
            emit=lambda payload: self.bridge.emit_event("chat:event", payload),
            emit_sessions_changed=lambda: self.bridge.emit_event("chat:sessions-changed", None),
        )
        self.bridge.chat_host = self.host
        self.bridge.model_gateway = self.gateway

        self.bridge.attach_view(self.view)
        self.channel.registerObject("bridge", self.bridge)
        page.setWebChannel(self.channel)

        page.scripts().insert(_script("qwebchannel", _read_qwebchannel_source()))
        page.scripts().insert(
            _script(
                "deva-shim",
                self._shim_source(settings.get_config_sync()),
            )
        )

        self.view.load(QUrl.fromLocalFile(str(assets_dir() / "index.html")))
        self.setCentralWidget(self.view)

        # 无边框 + 自绘窗口控件：原版 Electron 用 titleBarStyle:'hidden' + titleBarOverlay，
        # 装饰画在内容区右上角；这里用无边框窗口 + 覆盖层保持同一几何。
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.overlay = TitleBarOverlay(self.view)
        self._place_overlay()
        self.overlay.raise_()
        self.overlay.minimizeRequested.connect(self.showMinimized)
        self.overlay.maximizeRequested.connect(self._toggle_maximize)
        self.overlay.closeRequested.connect(self.close)
        self.bridge.set_overlay_callback(self.overlay.set_dark)
        self.bridge.set_window_actions(
            minimize=self.showMinimized,
            toggle_maximize=self._toggle_maximize,
            close=self.close,
            is_fullscreen=self.isFullScreen,
        )

        # 回合线程只把界面写入排进队列（见 ChatViewModel._ui）；这里在 GUI 线程定时取走执行，
        # 否则 busy/status/streaming 永远停在旧值——渲染层的「正在输出」状态就不会亮起。
        self._drain_timer = QtCore.QTimer(self)
        self._drain_timer.setInterval(DRAIN_INTERVAL_MS)
        self._drain_timer.timeout.connect(self.host.drain)
        self._drain_timer.start()

    def _place_overlay(self) -> None:
        """叠加层只占右上角那块实色矩形（原版 Linux：3 个 32px 按钮宽、40 高），不铺满整条。"""
        size = self.overlay.strip_size()
        top = 0
        width = self.view.width()
        self.overlay.setGeometry(width - size.width(), top, size.width(), size.height())

    # ── shim 组装 ─────────────────────────────────────────────────────────
    @staticmethod
    def _shim_source(config: dict[str, Any]) -> str:
        source = (assets_dir() / "shim.js").read_text(encoding="utf-8")
        return (
            source.replace("__CONFIG_JSON__", json.dumps(config, ensure_ascii=False))
            .replace("__PLATFORM__", "linux")
        )

    def _toggle_maximize(self) -> None:
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt 接口
        super().resizeEvent(event)
        self._place_overlay()

    # ── 尺寸辅助（截图脚本用）──────────────────────────────────────────────
    def content_size(self) -> QSize:
        """渲染层视口尺寸（不含我们自绘的任何装饰）。"""
        return self.view.size()


__all__ = ["ASSETS_DIR", "DevaWebWindow", "TITLEBAR_HEIGHT", "assets_dir"]
