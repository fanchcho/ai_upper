"""渲染层看到的平台名，单一来源。

前端产物是从 Electron 工程拷贝过来的（`app/assets/renderer`），它的判断写的是
`process.platform` 的取值：`'darwin'`、`'win32'`、`'linux'`。这份取值既注入
`window.deva.platform`（shim 的 `__PLATFORM__`），也由 `app:get-platform` 回给
渲染层；两处必须同源，否则设置页读到的平台和页面启动时拿到的不一致。

此前两处都写死 `'linux'`：在 Windows / macOS 上界面按 Linux 分支渲染
（例如窗口装饰与快捷键提示），而单元测试也把这个错误值钉成了期望值。
"""
from __future__ import annotations

import sys


def runtime_platform() -> str:
    """当前进程的平台，按 Electron `process.platform` 的拼写返回。"""
    if sys.platform == "darwin":
        return "darwin"
    if sys.platform == "win32":
        return "win32"
    return "linux"


__all__ = ["runtime_platform"]
