"""单窗口聊天壳（ChatPane 的 QMainWindow 外壳）。

主窗口（`DevaMainWindow`）把 `ChatPane` 嵌在左侧列表右边；这个类保留给
「只有聊天、没有列表」的脚本与测试用：同一个 `ChatPane`，套一层 QMainWindow。
"""
from __future__ import annotations

from mvvm.view_models.chat_vm import ChatViewModel
from mvvm.views.base_view import ViewBase
from mvvm.views.chat_pane import (
    DRAIN_INTERVAL_MS,
    INPUT_PLACEHOLDER,
    ROLE_PREFIX,
    SEND_BUTTON_TEXT,
    STOP_BUTTON_TEXT,
    ChatPane,
    streaming_to_text,
    transcript_to_text,
)


class ChatWindow(ViewBase):
    def __init__(self, viewmodel: ChatViewModel) -> None:
        super().__init__(viewmodel)
        from utils.qt_compat import QtWidgets

        self._pane = ChatPane(viewmodel)
        window = QtWidgets.QMainWindow()
        window.setWindowTitle("Deva")
        window.setCentralWidget(self._pane.widget())
        window.resize(720, 560)
        self._window = window

        # 兼容旧的内部字段名：测试与脚本按 _input/_send_button/_transcript 摸控件。
        self._transcript = self._pane._transcript
        self._streaming = self._pane._streaming
        self._status = self._pane._status
        self._error = self._pane._error
        self._input = self._pane._input
        self._send_button = self._pane._send_button
        self._stop_button = self._pane._stop_button
        self._timer = self._pane._timer

    def show(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def close(self) -> None:
        self._pane.close()
        self._window.close()


__all__ = [
    "ChatWindow",
    "DRAIN_INTERVAL_MS",
    "INPUT_PLACEHOLDER",
    "ROLE_PREFIX",
    "SEND_BUTTON_TEXT",
    "STOP_BUTTON_TEXT",
    "streaming_to_text",
    "transcript_to_text",
]
