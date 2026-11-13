"""聊天窗口（P1 最小界面）：历史、输入框、发送按钮、状态与错误。

只做功能，不做样式：没有自定义 delegate、没有 Markdown 渲染、没有流式刷新
（回合是同步跑完再刷新，见 `ChatViewModel` 的说明）。

绑定关系全部走 `ViewBase`：
- `transcript` -> QTextBrowser 的纯文本（值转换器把条目列表拼成文本）
- `status` / `error` -> QLabel
- `input_text` <-> QPlainTextEdit（双向：显式给 getter_name='toPlainText'）
- `send_command` -> 按钮 clicked
"""
from __future__ import annotations

from typing import Any

from mvvm.view_models.chat_vm import ChatViewModel
from mvvm.views.base_view import ViewBase

SEND_BUTTON_TEXT = "发送"
INPUT_PLACEHOLDER = "输入消息，回车发送"

ROLE_PREFIX = {"user": "你", "assistant": "助手", "tool": "工具", "error": "错误"}


def transcript_to_text(entries: Any) -> str:
    """展示条目 -> 纯文本。角色前缀让测试与截图都能一眼分辨谁说的话。"""
    lines: list[str] = []
    for entry in entries or []:
        role = str(entry.get("role", ""))
        head = ROLE_PREFIX.get(role, role)
        if entry.get("is_error"):
            head = f"{head}（失败）"
        lines.append(f"[{head}] {entry.get('text', '')}")
    return "\n\n".join(lines)


class ChatWindow(ViewBase):
    def __init__(self, viewmodel: ChatViewModel) -> None:
        super().__init__(viewmodel)
        from utils.qt_compat import QtWidgets

        window = QtWidgets.QMainWindow()
        window.setWindowTitle("Deva")
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)

        transcript = QtWidgets.QTextBrowser()
        transcript.setPlainText(transcript_to_text(viewmodel.transcript))
        status = QtWidgets.QLabel(viewmodel.status)
        error = QtWidgets.QLabel("")
        error.setWordWrap(True)
        input_box = QtWidgets.QPlainTextEdit()
        input_box.setPlaceholderText(INPUT_PLACEHOLDER)
        input_box.setFixedHeight(72)
        send_button = QtWidgets.QPushButton(SEND_BUTTON_TEXT)

        layout.addWidget(transcript, 1)
        layout.addWidget(status)
        layout.addWidget(error)
        layout.addWidget(input_box)
        layout.addWidget(send_button)
        window.setCentralWidget(central)
        window.resize(720, 560)

        self._window = window
        self._transcript = transcript
        self._status = status
        self._error = error
        self._input = input_box
        self._send_button = send_button

        binding = self.bind_property("transcript", transcript, "setPlainText")
        binding.add_value_converter(transcript_to_text)
        # 值转换器只在 ViewModel -> UI 方向生效；初始值要自己铺一遍，
        # 否则订阅之后的第一个事件之前窗口是空的（bind_property 不会回放当前值）。
        transcript.setPlainText(transcript_to_text(viewmodel.transcript))
        self.bind_property("status", status, "setText")
        self.bind_property("error", error, "setText")
        self.bind_property("input_text", input_box, "setPlainText", getter_name="toPlainText")
        self.bind_command("send", send_button)

        # 输入框内容变化要写回 ViewModel，否则 send_command 的 can_execute 永远看不到文本。
        input_box.textChanged.connect(self._sync_input)

    def _sync_input(self) -> None:
        for binding in self._bindings:
            if binding.property_name == "input_text":
                binding.update_viewmodel_from_ui()
                return

    def show(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def close(self) -> None:
        self._window.close()
