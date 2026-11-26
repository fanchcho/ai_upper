"""聊天面板（可嵌进主窗口的 QWidget）：历史、待办胶囊、流式正文、输入框、发送/停止、状态与错误。

功能优先，不做样式主题：没有自定义 delegate、没有 Markdown 渲染。历史用 Qt 富文本画，
因为工具结果要成「卡片」、图片要内联——纯文本做不了这两件事。渲染规则全在
`transcript_render.py`（纯函数、可单测），这里只负责把它们塞进控件。

流式输出通过 `ChatViewModel.streaming` 属性刷新——回合跑在后台线程，VM 把每次增量经
事件队列交回 UI 线程；这里用一个 QTimer 周期性 `drain()`，把队列里的状态写入真正落到控件上。

绑定关系：
- `transcript` -> QTextBrowser（自定义渲染：先注册图片资源，再 setHtml）
- `streaming` -> 时间线末尾的「正在输出」区域
- `todos_state` -> 输入框上方的待办胶囊（可展开条目、可取消清单）
- `status` / `error` -> QLabel
- `input_text` <-> QPlainTextEdit（双向：显式给 getter_name='toPlainText'）
- `send_command` -> 发送按钮 clicked；`stop_command` -> 停止按钮 clicked

图片资源为什么要先注册：`QTextDocument` 在 `setHtml` 时就把 `<img src>` 解析成资源引用，
之后再 `addResource` 需要 `markContentsDirty` 才会重新布局，四个绑定上的行为并不一致。
先 `addResource` 再 `setHtml` 在所有绑定上一致。

面板不拥有 ViewModel 的生命周期（它由应用容器持有）；`close()` 只停定时器。
"""
from __future__ import annotations
from locale_runtime import tr

from typing import Any, Optional

from mvvm.view_models.chat_vm import ChatViewModel
from mvvm.views.base_view import ViewBase
from mvvm.views.transcript_render import (
    IMAGE_URL_PREFIX,
    decode_images,
    image_placeholder,
    todo_capsule_text,
    todo_item_lines,
    transcript_html,
)

# 与 ChatWindow 共用的文案常量放在这里，窗口只是薄壳。
SEND_BUTTON_TEXT = tr('legacy.1214d633a448')
STOP_BUTTON_TEXT = tr('legacy.a17f70a8d3d6')
INPUT_PLACEHOLDER = tr('legacy.fc4f2f83ab0b')
DRAIN_INTERVAL_MS = 40

TODO_EXPAND_TEXT = tr('legacy.2a9ab4d435e8')
TODO_COLLAPSE_TEXT = tr('legacy.e453ed23f866')
TODO_CANCEL_TEXT = tr('legacy.d37451998387')


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

        # 待办胶囊：一行摘要 + 展开/取消；展开后是多行条目。没有进行中的清单时整块收起。
        todo_row = QtWidgets.QWidget()
        todo_layout = QtWidgets.QHBoxLayout(todo_row)
        todo_layout.setContentsMargins(0, 0, 0, 0)
        todo_pill = QtWidgets.QLabel("")
        todo_pill.setWordWrap(True)
        todo_toggle = QtWidgets.QPushButton((tr('legacy.2a9ab4d435e8')))
        todo_cancel = QtWidgets.QPushButton((tr('legacy.d37451998387')))
        todo_layout.addWidget(todo_pill, 1)
        todo_layout.addWidget(todo_toggle)
        todo_layout.addWidget(todo_cancel)
        todo_details = QtWidgets.QLabel("")
        todo_details.setWordWrap(True)
        todo_row.hide()
        todo_details.hide()

        status = QtWidgets.QLabel(viewmodel.status)
        error = QtWidgets.QLabel("")
        error.setWordWrap(True)
        input_box = QtWidgets.QPlainTextEdit()
        input_box.setPlaceholderText((tr('legacy.fc4f2f83ab0b')))
        input_box.setFixedHeight(72)
        send_button = QtWidgets.QPushButton((tr('legacy.1214d633a448')))
        stop_button = QtWidgets.QPushButton((tr('legacy.a17f70a8d3d6')))
        stop_button.setEnabled(False)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(send_button)
        buttons.addWidget(stop_button)

        layout.addWidget(transcript, 1)
        layout.addWidget(todo_row)
        layout.addWidget(todo_details)
        layout.addWidget(streaming)
        layout.addWidget(status)
        layout.addWidget(error)
        layout.addWidget(input_box)
        layout.addLayout(buttons)

        self._widget = widget
        self._transcript = transcript
        self._streaming = streaming
        self._todo_row = todo_row
        self._todo_pill = todo_pill
        self._todo_toggle = todo_toggle
        self._todo_cancel = todo_cancel
        self._todo_details = todo_details
        self._todos_expanded = False
        self._status = status
        self._error = error
        self._input = input_box
        self._send_button = send_button
        self._stop_button = stop_button

        # 历史是自定义渲染（要先把图片注册成文档资源），因此不用 bind_property 的
        # 「属性值直接塞给 setter」路径；其余纯文本属性照常绑定。
        viewmodel.transcript_property.subscribe(self._on_transcript_changed)
        self._render_transcript(viewmodel.transcript)
        self.bind_property("streaming", streaming, "setText").add_value_converter(
            streaming_to_text
        )
        viewmodel.todos_state_property.subscribe(self._on_todos_changed)
        self._render_todos(viewmodel.todos_state_property.get_value())
        self.bind_property("status", status, "setText")
        self.bind_property("error", error, "setText")
        self.bind_property("busy", stop_button, "setEnabled")
        self.bind_property("input_text", input_box, "setPlainText", getter_name="toPlainText")
        self.bind_command("send", send_button)
        self.bind_command("stop", stop_button)
        todo_toggle.clicked.connect(lambda _=False: self._toggle_todos())
        todo_cancel.clicked.connect(lambda _=False: viewmodel.cancel_todos())

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

    def todo_widgets(self) -> dict[str, Any]:
        """待办胶囊的控件（测试与截图脚本用）。"""
        return {
            "row": self._todo_row,
            "pill": self._todo_pill,
            "toggle": self._todo_toggle,
            "cancel": self._todo_cancel,
            "details": self._todo_details,
        }

    @property
    def todos_expanded(self) -> bool:
        return self._todos_expanded

    def _drain(self) -> None:
        self.viewmodel.drain()

    # ── 历史渲染 ──────────────────────────────────────────────────────────
    def _on_transcript_changed(self, _event: Any = None) -> None:
        self._render_transcript(self.viewmodel.transcript)

    def _render_transcript(self, entries: Any) -> None:
        self._register_images(entries)
        from markdown.document import LIGHT, DARK
        palette = LIGHT
        if hasattr(self._transcript, 'palette'):
            palette = DARK if self._transcript.palette().base().color().lightness() < 128 else LIGHT
            self._transcript.setStyleSheet('QTextBrowser { color: %s; background: %s; }' % (palette.fg, palette.bg))
        self._transcript.setHtml(transcript_html(entries, palette=palette))

    def _register_images(self, entries: Any) -> None:
        """把内联图片注册成文档资源（占位 URL 与正文里的 `<img src>` 对应）。"""
        document = getattr(self._transcript, "document", None)
        if not callable(document):
            return  # 假控件/无文档环境：图片不显示，正文照常
        doc = document()
        for index, (media_type, raw) in enumerate(decode_images(entries)):
            image = _load_image(raw, media_type)
            if image is None:
                continue
            from utils.qt_compat import QtCore, QtGui

            doc.addResource(
                _image_resource_type(QtGui),
                QtCore.QUrl(f"{IMAGE_URL_PREFIX}{index}"),
                image,
            )

    # ── 待办胶囊 ──────────────────────────────────────────────────────────
    def _on_todos_changed(self, event: Any = None) -> None:
        state = getattr(event, "new_value", None) if event is not None else None
        self._render_todos(state)

    def _render_todos(self, state: Optional[dict[str, Any]]) -> None:
        text = todo_capsule_text(state)
        if not text:
            self._todos_expanded = False
            self._todo_details.setText("")
            self._todo_details.hide()
            self._todo_toggle.setText((tr('legacy.2a9ab4d435e8')))
            self._todo_row.hide()
            self._todo_pill.setText("")
            return
        self._todo_pill.setText(text)
        self._todo_details.setText("\n".join(todo_item_lines(state)))
        self._todo_row.show()
        # 清单被取消/换新后保持展开会很突兀；这里跟着当前状态刷新可见性即可。
        if self._todos_expanded:
            self._todo_details.show()
        else:
            self._todo_details.hide()
        self._todo_toggle.setText((tr('legacy.e453ed23f866')) if self._todos_expanded else (tr('legacy.2a9ab4d435e8')))

    def _toggle_todos(self) -> None:
        """展开/收起条目。没有条目可展开时保持收起（胶囊只剩摘要，不该装成能展开）。"""
        if not self._todo_details.text():
            self._todos_expanded = False
            self._todo_details.hide()
        else:
            self._todos_expanded = not self._todos_expanded
            if self._todos_expanded:
                self._todo_details.show()
            else:
                self._todo_details.hide()
        self._todo_toggle.setText(
            (tr('legacy.e453ed23f866')) if self._todos_expanded else (tr('legacy.2a9ab4d435e8'))
        )

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


def streaming_to_text(streaming: Any) -> str:
    """流式区：有增量时带前缀，空串时整块收起（不占一行空白）。"""
    text = str(streaming or "")
    if not text:
        return ""
    return tr('legacy.957dc00c1d47' ,p1=text)


def _image_resource_type(QtGui: Any) -> Any:
    """`QTextDocument.ImageResource` 在 Qt5 是枚举、Qt6 是枚举成员。"""
    document = QtGui.QTextDocument
    enum = getattr(document, "ResourceType", None)
    if enum is not None:
        return enum.ImageResource
    return document.ImageResource


def _load_image(raw: bytes, media_type: str) -> Any:
    """字节 → QImage；解不出图（坏数据）返回 None，不阻断整份历史渲染。"""
    from utils.qt_compat import QtGui

    image = QtGui.QImage.fromData(raw, media_type.split("/")[-1].upper() if media_type else None)
    if image is None or image.isNull():
        return None
    return image


__all__ = [
    "ChatPane",
    "DRAIN_INTERVAL_MS",
    "INPUT_PLACEHOLDER",
    "SEND_BUTTON_TEXT",
    "STOP_BUTTON_TEXT",
    "TODO_CANCEL_TEXT",
    "TODO_COLLAPSE_TEXT",
    "TODO_EXPAND_TEXT",
    "streaming_to_text",
]
