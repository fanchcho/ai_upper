"""Deva 应用入口：`python -m deva_app`。

与参考实现 `main.py` 的关系：主入口 `python -m main` 仍打开参考窗口，本模块是
**新应用**的独立入口，复用同一个 `MVVMQtApplication` 容器与同一套绑定机制，
只换对象图（`DevaApplication`）。

环境变量：
- `DEVA_HOME`：数据目录，缺省 `~/.deva`（与 Deva 桌面端同口径，两边可互相读写）；
- `DEVA_APP_HEADLESS=1`：offscreen 装配一次就退出，供 CI/验收真实启动；
- `DEVA_APP_WORKSPACE`：启动时登记为受信根的工作区目录（不设则没有受信根，工具一律拒绝）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from mvvm.mvvm_bootstrap import MVVMQtApplication
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.fake_provider import FakeProvider
from mvvm.services.tool_runtime import ToolRuntime
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.view_models.chat_vm import ChatViewModel

HEADLESS_ENV = "DEVA_APP_HEADLESS"
WORKSPACE_ENV = "DEVA_APP_WORKSPACE"
DEFAULT_SESSION_ID = "main"


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"


class DevaApplication(MVVMQtApplication):
    """Deva 的装配：service、ViewModel、View 都只在这里认识彼此。"""

    def initialize_viewmodels(self) -> None:
        app = self.mvvm_app
        home = os.environ.get("DEVA_HOME") or None
        store = ChatSessionStore(home)
        guard = WorkspaceGuard()
        workspace = os.environ.get(WORKSPACE_ENV, "").strip()
        if workspace:
            guard.trust_root(workspace)
        tools = ToolRuntime(guard, workspace or None)

        app.register_service("chat_store", store)
        app.register_service("workspace_guard", guard)
        app.register_service("tool_runtime", tools)

        viewmodel = ChatViewModel(store, FakeProvider(), tools)
        viewmodel.open_session(DEFAULT_SESSION_ID)
        app.register_viewmodel("chat", viewmodel)

    def initialize_views(self) -> None:
        # 延迟 import：没有 Qt 时这个模块（以及它的测试）照样能导入。
        from mvvm.views.chat_window import ChatWindow

        app = self.mvvm_app
        app.register_view("chat", ChatWindow(app.get_viewmodel("chat")))


def run(headless: Optional[bool] = None) -> int:
    """真实启动 Qt 应用。headless 时走 offscreen 装配一次再退出。"""
    if headless is None:
        headless = _env_flag(HEADLESS_ENV)
    if headless:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    application = DevaApplication()
    if headless:
        application.prepare()
        application.qt_app.processEvents()
        viewmodel = application.mvvm_app.get_viewmodel("chat")
        print(
            "DEVA GUI OK",
            application.qt_app.platformName(),
            f"session={viewmodel.session_id}",
            f"title={viewmodel.title!r}",
        )
        application.mvvm_app.stop()
        return 0
    return application.run()


def main(argv: Optional[list[str]] = None) -> int:
    del argv  # 入口暂不接受参数：会话 id 由默认值/界面决定
    return run()


if __name__ == "__main__":
    sys.exit(main())
