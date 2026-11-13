"""新应用入口与最小界面：装配跑得起来、绑定把界面刷对。

Qt 在这里用假实现（与 test_mvvm_example.py 同一套思路）：这一层测的是装配与绑定，
真实 Qt 的启动由 `QT_QPA_PLATFORM=offscreen python -m deva_app` 在 CI/验收里跑。
"""
from __future__ import annotations

import os

import pytest

from conftest import install_fake_binding


class FakeSignal:
    def __init__(self) -> None:
        self.handlers: list = []

    def connect(self, handler) -> None:
        self.handlers.append(handler)

    def emit(self, *args) -> None:
        for handler in list(self.handlers):
            handler(*args)


class FakeWindow:
    def __init__(self) -> None:
        self.visible = False
        self.title = ""
        self.central_widget = None
        self.size = None
        self.raised = False
        self.activated = False

    def setWindowTitle(self, title: str) -> None:  # noqa: N802
        self.title = title

    def setCentralWidget(self, widget) -> None:  # noqa: N802
        self.central_widget = widget

    def resize(self, *size: int) -> None:
        self.size = size

    def show(self) -> None:
        self.visible = True

    def raise_(self) -> None:  # noqa: N802
        self.raised = True

    def activateWindow(self) -> None:  # noqa: N802
        self.activated = True

    def close(self) -> None:
        self.visible = False


class FakeLabel:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.visible = True

    def setText(self, value: str) -> None:  # noqa: N802
        self.text = value

    def setWordWrap(self, value: bool) -> None:  # noqa: N802
        self.word_wrap = value

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False


class FakeButton:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.clicked = FakeSignal()
        self.enabled = True

    def setEnabled(self, value: bool) -> None:  # noqa: N802
        self.enabled = value

    def click(self) -> None:
        self.clicked.emit(False)


class FakeTextBrowser:
    def __init__(self) -> None:
        self.plain_text = ""

    def setPlainText(self, value: str) -> None:  # noqa: N802
        self.plain_text = value


class FakePlainTextEdit:
    def __init__(self) -> None:
        self.plain_text = ""
        self.textChanged = FakeSignal()

    def setPlainText(self, value: str) -> None:  # noqa: N802
        self.plain_text = value
        self.textChanged.emit()

    def toPlainText(self) -> str:  # noqa: N802
        return self.plain_text

    def setPlaceholderText(self, value: str) -> None:  # noqa: N802
        self.placeholder = value

    def setFixedHeight(self, value: int) -> None:  # noqa: N802
        self.fixed_height = value


class FakeLayout:
    def __init__(self, parent=None) -> None:
        self.widgets: list = []

    def addWidget(self, widget, *args) -> None:  # noqa: N802
        self.widgets.append(widget)

    def addLayout(self, layout) -> None:  # noqa: N802
        self.widgets.append(layout)

    def setContentsMargins(self, *args) -> None:  # noqa: N802
        pass


class FakeTimer:
    """QTimer 的假实现：只记录连接，由测试决定何时触发（Qt 事件循环不在这里跑）。"""

    def __init__(self) -> None:
        self.interval = 0
        self.started = False
        self.timeout = FakeSignal()

    def setInterval(self, value: int) -> None:  # noqa: N802
        self.interval = value

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False


class FakeApplication:
    def __init__(self, argv=None) -> None:
        self.argv = argv

    @classmethod
    def instance(cls):
        return None

    @classmethod
    def setAttribute(cls, attribute) -> None:  # noqa: N802
        pass

    def processEvents(self) -> None:  # noqa: N802
        pass

    def platformName(self) -> str:  # noqa: N802
        return os.environ.get("QT_QPA_PLATFORM", "unknown")

    def quit(self) -> None:
        pass


@pytest.fixture()
def fake_qt(monkeypatch):
    widgets = {
        "QApplication": FakeApplication,
        "QMainWindow": FakeWindow,
        "QWidget": FakeWindow,
        "QVBoxLayout": FakeLayout,
        "QLabel": FakeLabel,
        "QPushButton": FakeButton,
        "QTextBrowser": FakeTextBrowser,
        "QPlainTextEdit": FakePlainTextEdit,
        "QHBoxLayout": FakeLayout,
    }
    install_fake_binding(
        monkeypatch,
        {
            "PySide6": {
                "QtCore": {"Qt": object(), "QTimer": FakeTimer},
                "QtWidgets": widgets,
            }
        },
    )


def test_headless_entry_assembles_and_prints(monkeypatch, tmp_path, capsys, fake_qt):
    monkeypatch.setenv("DEVA_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("DEVA_APP_WORKSPACE", raising=False)

    from deva_app.__main__ import run

    assert run(headless=True) == 0
    out = capsys.readouterr().out
    assert "DEVA GUI OK offscreen" in out
    assert "session=main" in out


def test_assembly_registers_services_viewmodel_and_view(monkeypatch, tmp_path, fake_qt):
    monkeypatch.setenv("DEVA_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("DEVA_APP_WORKSPACE", str(tmp_path))
    monkeypatch.setattr("sys.argv", ["deva"])

    from deva_app.__main__ import DevaApplication
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.tool_runtime import ToolRuntime
    from mvvm.services.workspace_guard import WorkspaceGuard

    application = DevaApplication()
    app = application.prepare()
    try:
        assert isinstance(app.get_service("chat_store"), ChatSessionStore)
        assert isinstance(app.get_service("workspace_guard"), WorkspaceGuard)
        assert isinstance(app.get_service("tool_runtime"), ToolRuntime)
        assert app.get_viewmodel("chat").session_id == "main"
        assert app.get_view("chat") is not None
        # 工作区环境变量真的登记成了受信根
        assert app.get_service("workspace_guard").list_roots() == [tmp_path]
    finally:
        app.stop()


def test_window_binds_transcript_status_and_send(monkeypatch, tmp_path, fake_qt):
    monkeypatch.setenv("DEVA_HOME", str(tmp_path / "home"))

    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.fake_provider import FakeProvider
    from mvvm.services.tool_runtime import ToolRuntime
    from mvvm.services.workspace_guard import WorkspaceGuard
    from mvvm.view_models.chat_vm import ChatViewModel
    from mvvm.views.chat_window import ChatWindow

    (tmp_path / "notes.txt").write_text("你好\n", encoding="utf-8")
    guard = WorkspaceGuard([tmp_path])
    vm = ChatViewModel(
        ChatSessionStore(tmp_path / "home"),
        FakeProvider(),
        ToolRuntime(guard, tmp_path),
    )
    vm.open_session("ui")
    window = ChatWindow(vm)
    window.show()

    # 输入框 → ViewModel（双向绑定），再点发送：回合跑完，界面被命令与属性推送刷新
    window._input.setPlainText("看一下 notes.txt")
    assert vm.input_text_property.get_value() == "看一下 notes.txt"
    assert vm.can_send() is True

    window._send_button.click()
    # 按钮只在后台线程起回合、立即返回；等回合结束 + 事件落地后再断言界面。
    assert vm.wait_idle(5.0)

    assert vm.transcript[-1]["role"] == "assistant"
    assert "你好" in window._transcript.plain_text
    assert window._status.text == "就绪"
    assert window._error.text == ""
    window.close()
