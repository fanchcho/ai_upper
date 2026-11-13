"""聊天面板（可嵌进主窗口的 QWidget）：历史、流式正文、输入框、发送/停止、状态与错误。

功能优先，不做样式：没有自定义 delegate、没有 Markdown 渲染。流式输出通过
`ChatViewModel.streaming` 属性刷新——回合跑在后台线程，VM 把每次增量经事件队列
交回 UI 线程；这里用一个 QTimer 周期性 `drain()`，把队列里的状态写入真正落到控件上。

绑定关系全部走 `ViewBase`：
- `transcript` -> QTextBrowser（值转换器把条目列表拼成文本）
- `streaming` -> 时间线末尾的「正在输出」区域
- `status` / `error` -> QLabel
- `input_text` <-> QPlainTextEdit（双向：显式给 getter_name='toPlainText'）
- `send_command` -> 发送按钮 clicked；`stop_command` -> 停止按钮 clicked

面板不拥有 ViewModel 的生命周期（它由应用容器持有）；`close()` 只停定时器。
"""
from __future__ import annotations

from typing import Any, Optional

from mvvm.view_models.chat_vm import ChatViewModel
from mvvm.views.base_view import ViewBase

# 与 ChatWindow 共用的文案常量放在这里，窗口只是薄壳。
SEND_BUTTON_TEXT = "发送"
STOP_BUTTON_TEXT = "停止"
INPUT_PLACEHOLDER = "输入消息，回车发送"
DRAIN_INTERVAL_MS = 40

ROLE_PREFIX = {
    "user": "你",
    "assistant": "助手",
    "tool": "工具",
    "error": "错误",
    "compaction": "压缩摘要",
    "notice": "提示",
}


def transcript_to_text(entries: Any) -> str:
    """展示条目 -> 纯文本。角色前缀让测试与截图都能一眼分辨谁说的话。"""
    lines: list[str] = []
    for entry in entries or []:
        role = str(entry.get("role", ""))
        head = ROLE_PREFIX.get(role, role)
        if entry.get("is_error"):
            head = f"{head}（失败）"
        name = entry.get("name")
        if name:
            head = f"{head} {name}"
        lines.append(f"[{head}] {entry.get('text', '')}")
    return "\n\n".join(lines)


def streaming_to_text(streaming: Any) -> str:
    """流式区：有增量时带前缀，空串时整块收起（不占一行空白）。"""
    text = str(streaming or "")
    if not text:
        return ""
    return f"[助手·输出中] {text}"


class ChatPane(ViewBase):
    """一条会话的聊天界面。挂在 `ChatViewModel` 上；窗口层负责把它放进主窗口。"""

    def __init__(self, viewmodel: ChatViewModel) -> None:
        super().__init__(viewmodel)
        from utils.qt_compat import QtCore, QtWidgets

        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        transcript = QtWidgets.QTextBrowser()
        streaming = QtWidgets.QLabel("")
        streaming.setWordWrap(True)
        streaming.hide()
        status = QtWidgets.QLabel(viewmodel.status)
        error = QtWidgets.QLabel("")
        error.setWordWrap(True)
        input_box = QtWidgets.QPlainTextEdit()
        input_box.setPlaceholderText(INPUT_PLACEHOLDER)
        input_box.setFixedHeight(72)
        send_button = QtWidgets.QPushButton(SEND_BUTTON_TEXT)
        stop_button = QtWidgets.QPushButton(STOP_BUTTON_TEXT)
        stop_button.setEnabled(False)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(send_button)
        buttons.addWidget(stop_button)

        layout.addWidget(transcript, 1)
        layout.addWidget(streaming)
        layout.addWidget(status)
        layout.addWidget(error)
        layout.addWidget(input_box)
        layout.addLayout(buttons)

        self._widget = widget
        self._transcript = transcript
        self._streaming = streaming
        self._status = status
        self._error = error
        self._input = input_box
        self._send_button = send_button
        self._stop_button = stop_button

        self.bind_property("transcript", transcript, "setPlainText").add_value_converter(
            transcript_to_text
        )
        # 值转换器只在 ViewModel -> UI 方向生效；初始值要自己铺一遍，
        # 否则订阅之后的第一个事件之前窗口是空的（bind_property 不会回放当前值）。
        transcript.setPlainText(transcript_to_text(viewmodel.transcript))
        self.bind_property("streaming", streaming, "setText").add_value_converter(
            streaming_to_text
        )
        self.bind_property("status", status, "setText")
        self.bind_property("error", error, "setText")
        self.bind_property("busy", stop_button, "setEnabled")
        self.bind_property("input_text", input_box, "setPlainText", getter_name="toPlainText")
        self.bind_command("send", send_button)
        self.bind_command("stop", stop_button)

        # 输入框内容变化要写回 ViewModel，否则 send_command 的 can_execute 永远看不到文本。
        input_box.textChanged.connect(self._sync_input)

        # 流式区显示/隐藏跟着正文走（空串时收起）；文本本身由上一条绑定写入。
        viewmodel.streaming_property.subscribe(self._toggle_streaming)
        self._toggle_streaming(None)

        # 后台回合的增量在队列里；UI 线程定期取走执行（40ms 一次，肉眼是连续的）。
        self._timer = QtCore.QTimer()
        self._timer.setInterval(DRAIN_INTERVAL_MS)
        self._timer.timeout.connect(self._drain)
        self._timer.start()
        # 回合结束时 VM 会调用这个回调，不必等下一个 tick。保留装配时已有的回调并串起来。
        previous = viewmodel._notifier
        if previous is None:
            viewmodel._notifier = self._drain
        else:
            viewmodel._notifier = lambda: (previous(), self._drain())

    # 供窗口/测试直接摸控件
    def widget(self) -> Any:
        return self._widget

    def _drain(self) -> None:
        self.viewmodel.drain()

    def _toggle_streaming(self, event: Any = None) -> None:
        text = streaming_to_text(self.viewmodel.streaming)
        if text:
            self._streaming.setText(text)
            self._streaming.show()
        else:
            self._streaming.hide()

    def _sync_input(self) -> None:
        for binding in self._bindings:
            if binding.property_name == "input_text":
                binding.update_viewmodel_from_ui()
                return

    def close(self) -> None:
        self._timer.stop()


def bind_session_id(pane: ChatPane, viewmodel: ChatViewModel) -> Callable[[], str]:
    """便利函数：返回「当前会话 id」读取器（会话切换时主窗口据此重建/重置面板）。"""

    def current() -> str:
        return viewmodel.session_id

    return current


__all__ = [
    "ChatPane",
    "DRAIN_INTERVAL_MS",
    "INPUT_PLACEHOLDER",
    "ROLE_PREFIX",
    "SEND_BUTTON_TEXT",
    "STOP_BUTTON_TEXT",
    "bind_session_id",
    "streaming_to_text",
    "transcript_to_text",
]
