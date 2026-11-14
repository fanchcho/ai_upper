"""本工程的真实入口：承载原版渲染层的 `DevaWebWindow`。

`main.py` 仍然是模板参考应用的入口（`application.main()` → GreetingService /
MainWindow），这里**不改它的语义**；`[tool.ai_upper].entry` 指向本模块，所以打包
产物起的是原版界面，而不是模板窗口。

入口只做装配与启动：数据目录、密钥库、角色种子都从 `AI_UPPER_HOME`
（缺省 `~/.ai_upper`，旧 `DEVA_HOME` / `~/.deva` 仍被读取）读取，窗口内部再装配回合
宿主、模型网关与工具运行时（见 `mvvm.webui.assembly`）。装配写两份就会漂移，
因此这里不重复。

环境变量：
- `AI_UPPER_HOME`：数据目录，缺省 `~/.ai_upper`（旧 `DEVA_HOME` 兼容）；
- `DEVA_APP_WORKSPACE`：启动时登记为受信根的工作区（不设则没有受信根，工具一律拒绝）；
- `AI_UPPER_HEADLESS=1`：offscreen 装配、等渲染层 `loadFinished`、打印结果后退出
  （旧 `DEVA_APP_HEADLESS` 仍被接受）。

`AI_UPPER_HEADLESS` 是打包后的冒烟路径：失败时返回非零并打印原因，绝不假装启动成功。
CI 的 `build.py --run` 用的就是它——两个入口（本模块与 `application.py`）认同一个
变量，否则设了变量却 blocker 在窗口服务器上。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

HEADLESS_ENV = "AI_UPPER_HEADLESS"
LEGACY_HEADLESS_ENV = "DEVA_APP_HEADLESS"
HEADLESS_TIMEOUT_S = 90.0


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"


def _headless_requested() -> bool:
    return _env_flag(HEADLESS_ENV) or _env_flag(LEGACY_HEADLESS_ENV)


def _prepare_environment(headless: bool) -> None:
    """Chromium 与平台插件在 QtWebEngine 被导入**之前**就要定好。

    以 root 运行时 Chromium 的 setuid sandbox 不可用；没有可用 GPU 的机器上
    软渲染才不会黑屏。用户显式设置这两个变量时以用户的为准。
    """
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
    window.view.page().runJavaScript(
        "!!(window.deva && window.deva.chat)", 0,
        lambda value: bridged.setdefault("value", value),
    )
    _pump(app, lambda: "value" in bridged, timeout)
    return {"loaded": True, "bridge": bridged.get("value")}


def run(headless: Optional[bool] = None) -> int:
    if headless is None:
        headless = _headless_requested()
    _prepare_environment(headless)

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
    sys.exit(main())
