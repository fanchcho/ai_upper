"""本工程的唯一入口：装配 QML 三栏壳（`qml/Main.qml`）并启动。

启动逻辑（环境准备、`QApplication`、窗口装配、headless 探针、退出码语义）只存在
于本模块一处；`tools/ai_upper/config.py` 生成的启动器就是
`from main import main`，因此打包产物与源码树走的是同一条路径。

界面只有一条原生路线：**QML 壳 + `QTextDocument` 正文**。仓库里不再有第二套界面
装配（原 `AI_UPPER_UI=web` 的 QtWebEngine 承载窗口已随 `mvvm.views.web_shell_window`
一并删除），因此这里既没有界面路由，也不设 Chromium 相关环境变量。

入口只做装配与启动：数据目录、密钥库、角色种子都从 `AI_UPPER_HOME`
（缺省 `~/.ai_upper`，旧 `DEVA_HOME` / `~/.deva` 仍被读取）读取，窗口内部再装配回合
宿主、模型网关与工具运行时（见 `mvvm.webui.assembly`）。

环境变量：
- `AI_UPPER_HOME`：数据目录，缺省 `~/.ai_upper`（旧 `DEVA_HOME` 兼容）；
- `DEVA_APP_WORKSPACE`：启动时登记为受信根的工作区（不设则没有受信根，工具一律拒绝）；
- `AI_UPPER_HEADLESS=1`：offscreen 装配、等首帧画出来后 `grabWindow()` 存 PNG 到
  `out/qml-shell/shot.png`，成功打印 `QML OK`，失败打印具体原因后退出
  （旧 `DEVA_APP_HEADLESS` 仍被接受）。

`AI_UPPER_HEADLESS` 是打包后的冒烟路径：失败时返回非零并打印原因，绝不假装启动成功。
CI 的 `build.py --run` 用的就是它，因此打包产物默认验证的就是 QML 壳。
"""
from __future__ import annotations

import os
import sys
from typing import Optional

HEADLESS_ENV = "AI_UPPER_HEADLESS"
LEGACY_HEADLESS_ENV = "DEVA_APP_HEADLESS"
HEADLESS_TIMEOUT_S = 90.0


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip() == "1"


def _headless_requested() -> bool:
    return _env_flag(HEADLESS_ENV) or _env_flag(LEGACY_HEADLESS_ENV)


def _prepare_environment(headless: bool) -> None:
    """平台插件与 Quick 后端在 `QGuiApplication` 建起来**之前**就要定好。

    无 GPU 的机器（CI runner、容器、offscreen）上 Quick 默认的 OpenGL 后端会直接
    起不来，`QT_QUICK_BACKEND=software` 用栅格化渲染顶上；用户显式设置时以用户的为准。
    """
    os.environ.setdefault("QT_QUICK_BACKEND", "software")
    if headless:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def run(headless: Optional[bool] = None) -> int:
    if headless is None:
        headless = _headless_requested()
    _prepare_environment(headless)

    from qml_shell import run as run_qml

    return run_qml(headless)


def main(argv: Optional[list[str]] = None) -> int:
    del argv  # 入口暂不接受参数：会话与模型都由界面/配置决定
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
