"""ai_upper 端口启动器（供逐页截图用）。

在指定 DISPLAY 上真实打开承载原版渲染层的窗口，窗口 1280x820 置于 (0,0)，
不自动退出——截图脚本用 xdotool + import 从根窗口取图，与原版 Walk-through 走同一条路径。

用法: DISPLAY=:96 DEVA_HOME=/tmp/xxx .venv/bin/python scripts/parity/port_run.py

与 `deva_original_shots.sh` 配合：两边窗口位置、尺寸、截取方式完全一致，像素差才有意义。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from mvvm.services.chat_session_store import ChatSessionStore  # noqa: E402
from mvvm.services.persona_store import PersonaStore  # noqa: E402
from mvvm.services.secrets_vault import SecretsVault  # noqa: E402
from mvvm.services.settings_service import SettingsService  # noqa: E402
from mvvm.views.web_shell_window import DevaWebWindow  # noqa: E402

# 回合宿主、模型网关与工具运行时由窗口内部装配（mvvm.webui.assembly），
# 这里只负责起窗口——装配写两份就会漂移。


def main() -> int:
    app = QApplication(sys.argv)
    home = Path(os.environ.get("DEVA_HOME") or (Path.home() / ".deva"))
    settings = SettingsService(home)
    personas = PersonaStore(home)
    personas.ensure_seeded()
    store = ChatSessionStore(home)
    vault = SecretsVault(home)

    win = DevaWebWindow(settings=settings, personas=personas, store=store, vault=vault)
    win.resize(1280, 820)
    win.move(0, 0)
    win.setWindowFlag(Qt.FramelessWindowHint, True)
    win.show()
    win.raise_()
    win.activateWindow()

    # 渲染层加载完成前不要截：首帧是空白，会给后续像素对比引入噪声。
    def ready(ok: bool) -> None:
        if ok:
            print("renderer loaded", flush=True)

    win.view.loadFinished.connect(ready)
    QTimer.singleShot(600, lambda: print("window ready", flush=True))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
