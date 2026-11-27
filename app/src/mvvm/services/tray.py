"""系统托盘与回复通知（deva apps/desktop/src/main/index.ts:235-272、reply-notify.ts:15-80）。

QML 没有托盘控件，只能用 QSystemTrayIcon。无托盘环境（offscreen / 无桌面会话）不伪造：
打印原始平台与 isSystemTrayAvailable()，让调用方按真实失败降级。
"""
from __future__ import annotations

import sys
from typing import Any, Callable, Optional

from utils.qt_compat import QtGui, QtWidgets


class TrayController:
    def __init__(self, app: "QtWidgets.QApplication", window: Any) -> None:
        self.app = app
        self.window = window
        self.icon: Optional[Any] = None
        self.available = False

    def install(self) -> bool:
        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            print(
                "TRAY UNAVAILABLE platform=%s isSystemTrayAvailable=False"
                % QtWidgets.QApplication.platformName(),
                file=sys.stderr,
                flush=True,
            )
            return False
        self.icon = QtWidgets.QSystemTrayIcon(
            QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon), self.app
        )
        menu = QtWidgets.QMenu()
        show_action = menu.addAction("显示 Deva")
        show_action.triggered.connect(self.show)
        task_action = menu.addAction("定时任务")
        task_action.triggered.connect(lambda: (self.show(), self.window.setProperty("page", "tasks")))
        menu.addSeparator()
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(self.app.quit)
        self.icon.setContextMenu(menu)
        self.icon.setToolTip("Deva")
        self.icon.activated.connect(self._activated)
        self.icon.show()
        self.available = True
        return True

    def _activated(self, reason: "QtWidgets.QSystemTrayIcon.ActivationReason") -> None:
        if reason == QtWidgets.QSystemTrayIcon.Trigger:
            if self.window.isVisible() and not self.window.isMinimized():
                self.window.hide()
            else:
                self.show()

    def show(self) -> None:
        if self.window.isMinimized():
            self.window.showNormal()
        self.window.show()
        self.window.raise_()
        self.window.requestActivate()

    def notify(self, title: str, body: str) -> bool:
        """窗口失焦时弹系统通知（deva reply-notify.ts 同语义）；不可用返回 False。"""
        if not self.available or self.icon is None or not QtWidgets.QSystemTrayIcon.supportsMessages():
            print(
                "NOTIFY UNAVAILABLE tray_available=%s supportsMessages=%s"
                % (self.available, QtWidgets.QSystemTrayIcon.supportsMessages()),
                file=sys.stderr,
                flush=True,
            )
            return False
        self.icon.showMessage(title or "Deva", body, QtWidgets.QSystemTrayIcon.Information, 5000)
        print("NOTIFY SHOWN " + title, flush=True)
        return True
