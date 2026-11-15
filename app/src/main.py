"""本工程的唯一入口：装配原版渲染层 `DevaWebWindow` 并启动。

启动逻辑（环境准备、`QApplication`、窗口装配、headless 探针、退出码语义）只存在
于本模块一处；`tools/ai_upper/config.py` 生成的启动器就是
`from main import main`，因此打包产物与源码树走的是同一条路径。

入口只做装配与启动：数据目录、密钥库、角色种子都从 `AI_UPPER_HOME`
（缺省 `~/.ai_upper`，旧 `DEVA_HOME` / `~/.deva` 仍被读取）读取，窗口内部再装配回合
宿主、模型网关与工具运行时（见 `mvvm.webui.assembly`）。

环境变量：
- `AI_UPPER_HOME`：数据目录，缺省 `~/.ai_upper`（旧 `DEVA_HOME` 兼容）；
- `DEVA_APP_WORKSPACE`：启动时登记为受信根的工作区（不设则没有受信根，工具一律拒绝）；
- `AI_UPPER_HEADLESS=1`：offscreen 装配、等渲染层 `loadFinished`、打印结果后退出
  （旧 `DEVA_APP_HEADLESS` 仍被接受）；
- `AI_UPPER_UI`：界面路线。**缺省走 QML 三栏壳**（`qml/Main.qml`，正文由
  `QTextDocument` 承载）；`AI_UPPER_UI=web` 才装配原 WebEngine 窗口（兜底开关）；
  与 `AI_UPPER_HEADLESS=1` 同时给出时，等首帧画出来后 `grabWindow()` 存 PNG 到
  `out/qml-shell/shot.png`，成功打印 `QML OK`，失败打印具体原因。

`AI_UPPER_HEADLESS` 是打包后的冒烟路径：失败时返回非零并打印原因，绝不假装启动成功。
CI 的 `build.py --run` 用的就是它，因此打包产物默认验证的是 QML 壳。

**默认路线是 QML**（用户已定死「QML 壳 + QTextDocument 正文」）。`AI_UPPER_UI=web`
是保留的兜底开关：只有当 QML 路线在本机起不来（Quick 插件缺失、显卡驱动直接把
`QQuickWindow` 打崩）时才用，日常不启用。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

HEADLESS_ENV = "AI_UPPER_HEADLESS"
LEGACY_HEADLESS_ENV = "DEVA_APP_HEADLESS"
UI_ENV = "AI_UPPER_UI"
QML_UI = "qml"
WEB_UI = "web"
WEBENGINE_UI = "webengine"
HEADLESS_TIMEOUT_S = 90.0


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"


def _headless_requested() -> bool:
    return _env_flag(HEADLESS_ENV) or _env_flag(LEGACY_HEADLESS_ENV)


def _qml_requested() -> bool:
    """默认 QML；只有显式 `AI_UPPER_UI=web`（或 `webengine`）才回退 WebEngine 窗口。

    **macOS headless 例外**：CI 的 macOS runner 没有可用的 WindowServer 会话，
    `offscreen` 平台插件也不给 Quick 场景做栅格化，`QQuickWindow.grabWindow()` 拿回
    空图（macos-arm64 的 Full integration run 因此判失败，日志尾部是
    `[6/6] Target runtime smoke`）。这条路径上默认回退到 WebEngine 渲染层，保持
    「产物能起来、能探到渲染层」的冒烟语义；要强制 QML 就显式设 `AI_UPPER_UI=qml`。
    桌面 macOS（有窗口会话）不受影响，仍然默认 QML。
    """
    value = os.environ.get(UI_ENV, "").strip().lower()
    if value == QML_UI:
        return True
    if value in (WEB_UI, WEBENGINE_UI):
        return False
    return not (sys.platform == "darwin" and _headless_requested())


def _prepare_environment(headless: bool) -> None:
    """Chromium 与平台插件在 QtWebEngine 被导入**之前**就要定好。

    以 root 运行时 Chromium 的 setuid sandbox 不可用；没有可用 GPU 的机器上
    软渲染才不会黑屏。用户显式设置这两个变量时以用户的为准。

    只给 WebEngine 路径设 Chromium 开关：QML 路径根本不加载 QtWebEngine，把
    `--no-sandbox` 之类的 Chromium 参数留在环境里没有作用，只会让日志误导。
    """
    if _qml_requested():
        os.environ.setdefault("QT_QUICK_BACKEND", "software")
    else:
        os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")
    if headless:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _data_home() -> Path:
    from utils.app_home import app_home

    return app_home()


def _create_window() -> Any:
    """建窗口。延迟 import：没有 Qt 时本模块照样能导入（构建工具会 import 入口）。"""
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.settings_service import SettingsService
    from mvvm.views.web_shell_window import DevaWebWindow

    home = _data_home()
    settings = SettingsService(home)
    personas = PersonaStore(home)
    personas.ensure_seeded()
    return DevaWebWindow(
        settings=settings,
        personas=personas,
        store=ChatSessionStore(home),
        vault=SecretsVault(home),
    )


def _pump(app: Any, predicate: Any, timeout: float) -> bool:
    """跑事件循环直到条件成立或超时（headless 没有窗口服务器，不能阻塞）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


def _probe_renderer(app: Any, window: Any, timeout: float) -> dict[str, Any]:
    """等渲染层加载完成，并确认 shim 装上了 `window.deva`。"""
    state: dict[str, Any] = {}
    window.view.loadFinished.connect(lambda ok: state.setdefault("loaded", bool(ok)))
    _pump(app, lambda: "loaded" in state, timeout)
    if not state.get("loaded"):
        return {"loaded": False}

    bridged: dict[str, Any] = {}
    # 用字符串而不是布尔值回报：PySide6 6.6 的 runJavaScript 把 JS 的 true/false
    # 转成空串（6.11 才转成 bool），只按真假判断会让这条 readiness 在旧 binding 上
    # 永远读不到结果。字符串在 PySide2/PySide6 各版本上转换一致。
    window.view.page().runJavaScript(
        "String(!!(window.deva && window.deva.chat))", 0,
        lambda value: bridged.setdefault("value", value),
    )
    _pump(app, lambda: "value" in bridged, timeout)
    return {"loaded": True, "bridge": bridged.get("value") == "true"}


def run(headless: Optional[bool] = None) -> int:
    if headless is None:
        headless = _headless_requested()
    _prepare_environment(headless)

    if _qml_requested():
        from qml_shell import run as run_qml

        return run_qml(headless)

    from utils.qt_compat import QtWidgets, exec_loop

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = _create_window()
    window.show()
    if not headless:
        return exec_loop(app)

    result = _probe_renderer(app, window, HEADLESS_TIMEOUT_S)
    url = window.view.url().toLocalFile()
    if not result.get("loaded") or not result.get("bridge"):
        print(
            "DEVA WEB FAILED",
            f"platform={app.platformName()}",
            f"url={url}",
            f"loaded={result.get('loaded')}",
            f"bridge={result.get('bridge')}",
            file=sys.stderr,
            flush=True,
        )
        window.view.stop()
        window.close()
        app.processEvents()
        return 1

    print(
        "DEVA WEB OK",
        f"platform={app.platformName()}",
        f"title={window.windowTitle()!r}",
        f"url={url}",
        "bridge=True",
        flush=True,
    )
    window.view.stop()
    window.close()
    app.processEvents()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    del argv  # 入口暂不接受参数：会话与模型都由界面/配置决定
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
