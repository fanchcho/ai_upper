"""新应用入口与主窗口：装配跑得起来、绑定把界面刷对。

Qt 在这里用假实现（与 test_mvvm_example.py 同一套思路）：这一层测的是装配与绑定，
真实 Qt 的启动由 `QT_QPA_PLATFORM=offscreen python -m deva_app` 在 CI/验收里跑。

控件替身集中在 `fake_qt_ui.py`，和 `test_deva_panes.py` 共用；这里只保留入口装配
相关的用例。
"""
from __future__ import annotations

from fake_qt_ui import (  # noqa: F401 - fixture 需要出现在模块命名空间里
    FakeButton,
    FakeLabel,
    FakeListItem,
    FakeListWidget,
    FakeMessageBox,
    fake_qt,
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
        assert app.get_view("main") is not None
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
    assert window._status.text() == "就绪"
    assert window._error.text() == ""
    window.close()


def test_main_window_has_one_registered_view_so_only_one_window_opens(monkeypatch, tmp_path, fake_qt):
    """框架的 `start()` 会 show() 所有注册的 View：多注册一个就多开一个窗口。"""
    monkeypatch.setenv("DEVA_HOME", str(tmp_path / "home"))

    from deva_app.__main__ import DevaApplication

    application = DevaApplication()
    app = application.prepare()
    try:
        assert list(app.views.keys()) == ["main"]
        window = app.get_view("main")
        assert isinstance(window.status_text, str)
        assert window.status_text == "就绪"
        assert window.settings_visible is False
    finally:
        app.stop()
