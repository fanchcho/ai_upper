"""三个面板的行为：会话列表、设置页，以及把它们装起来的主窗口。

Qt 仍用假控件（`fake_qt_ui.py`），因为它们测的是「用户动作 → ViewModel 调用 →
控件刷新」这条链；真实 Qt 上的信号时序由 `scripts/deva_qt_smoke.py` 与
`scripts/deva_ui_shots.py` 在 offscreen 会话里验证。
"""
from __future__ import annotations

import time

import pytest

from fake_qt_ui import (  # noqa: F401 - fixture 需要出现在模块命名空间里
    FakeInputDialog,
    FakeMessageBox,
    fake_qt,
)
from mvvm.models.chat_models import Message
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.fake_provider import FakeProvider
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.settings_service import SettingsService
from mvvm.services.tool_runtime import ToolRuntime
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.view_models.chat_sessions_vm import ChatSessionsViewModel
from mvvm.view_models.chat_vm import ChatViewModel
from mvvm.view_models.settings_vm import SettingsViewModel
from mvvm.views.deva_main_window import DevaMainWindow
from mvvm.views.session_list import SessionListPane
from mvvm.views.settings_pane import SettingsPane

MODELS = {
    "activeModelId": "p1:claude-sonnet-5-5",
    "activeEffort": "high",
    "providers": [
        {
            "id": "p1",
            "name": "Anthropic",
            "adapter": "anthropic",
            "apiHost": "https://api.anthropic.com",
            "enabled": True,
            "models": [
                {"id": "claude-sonnet-5-5", "enabled": True, "contextWindow": 200_000},
                {"id": "claude-haiku-5-5", "enabled": False},
            ],
        },
        {
            "id": "p2",
            "name": "DeepSeek",
            "adapter": "openai",
            "apiHost": "https://api.deepseek.com",
            "enabled": False,
            "models": [{"id": "deepseek-chat", "enabled": True}],
        },
    ],
}


# ── 夹具 ────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _fake_qt_binding(fake_qt):
    """本模块每个用例都摸控件：统一装假绑定，免得漏写的用例碰到真 Qt。"""
    return fake_qt


@pytest.fixture()
def store(tmp_path) -> ChatSessionStore:
    return ChatSessionStore(tmp_path / "home")


def seed(store: ChatSessionStore, session_id: str, title: str, *, age_ms: int = 0) -> None:
    session = store.ensure_session(session_id)
    session.messages.append(Message(role="user", content=title))
    session.title = title
    store.save(session_id)
    if age_ms:
        session.updatedAt = int(time.time() * 1000) - age_ms
        store.save(session_id)


@pytest.fixture()
def settings_env(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    settings = SettingsService(tmp_path)
    settings.set_config({"models": MODELS})
    vault = SecretsVault(tmp_path)
    return settings, vault


@pytest.fixture()
def main_window(tmp_path, settings_env, fake_qt):
    settings, vault = settings_env
    store = ChatSessionStore(tmp_path / "home")
    seed(store, "a", "甲", age_ms=20_000)
    seed(store, "b", "乙")

    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "notes.txt").write_text("你好\n", encoding="utf-8")
    guard = WorkspaceGuard([workspace])
    chat = ChatViewModel(store, FakeProvider(), ToolRuntime(guard, workspace))
    chat.open_session("b")

    sessions = ChatSessionsViewModel(store)
    sessions.set_active("b")
    pane = DevaMainWindow(chat, sessions, SettingsViewModel(settings, vault))
    yield pane, chat, sessions, settings, vault
    pane.close()


# ── 会话列表面板 ────────────────────────────────────────────────────────
def test_session_list_rebuild_shows_sessions_and_hint(store):
    vm = ChatSessionsViewModel(store)
    pane = SessionListPane(vm)
    assert pane.list_widget().count() == 0
    assert pane.list_widget().visible is False
    assert pane.current_session_id() == ""

    seed(store, "a", "甲")
    vm.refresh()
    pane.rebuild()
    widget = pane.list_widget()
    assert widget.count() == 1
    assert widget.visible is True
    # 列表项文本 = 标题 + 相对时间
    assert widget.item(0).text().splitlines()[0] == "甲"


def test_session_list_callbacks_receive_the_session_id(store):
    seen: list = []
    vm = ChatSessionsViewModel(store)
    pane = SessionListPane(
        vm,
        on_select=seen.append,
        on_new=lambda: seen.append("new"),
        on_rename=lambda sid: seen.append(("rename", sid)),
        on_archive=lambda sid: seen.append(("archive", sid)),
        on_delete=lambda sid: seen.append(("delete", sid)),
        on_settings=lambda: seen.append("settings"),
    )
    seed(store, "a", "甲")
    vm.refresh()
    pane.rebuild()

    # 选中一行即回调（重建过程中的程序化选中不会触发）
    pane.list_widget().setCurrentRow(0)
    assert seen == ["a"]

    buttons = pane.buttons()
    buttons["rename"].click()
    buttons["archive"].click()
    buttons["delete"].click()
    buttons["new"].click()
    buttons["settings"].click()
    assert seen[1:] == [
        ("rename", "a"),
        ("archive", "a"),
        ("delete", "a"),
        "new",
        "settings",
    ]


def test_session_list_buttons_disabled_without_selection(store):
    vm = ChatSessionsViewModel(store)
    pane = SessionListPane(vm)
    buttons = pane.buttons()
    for name in ("rename", "archive", "delete"):
        assert buttons[name].isEnabled() is False

    seed(store, "a", "甲")
    vm.refresh()
    vm.set_active("a")
    pane.rebuild()
    for name in ("rename", "archive", "delete"):
        assert buttons[name].isEnabled() is True


# ── 设置页 ──────────────────────────────────────────────────────────────
@pytest.fixture()
def settings_pane(settings_env):
    settings, vault = settings_env
    vm = SettingsViewModel(settings, vault)
    notices: list = []
    pane = SettingsPane(vm, on_back=lambda: notices.append("back"), on_notice=notices.append)
    return pane, vm, settings, vault, notices


def test_settings_pane_opens_on_provider_list(settings_pane):
    pane, vm, settings, vault, notices = settings_pane
    assert pane.page() == "list"
    assert pane.widgets()["provider_list"].count() == 2
    assert pane.widgets()["active_label"].text() == "默认模型：p1:claude-sonnet-5-5"
    # 思考等级跟随配置，且程序化赋值不触发写盘
    assert pane.widgets()["effort"].currentIndex() == 3  # high
    assert settings.models_section()["activeEffort"] == "high"


def test_settings_pane_drill_down_and_back(settings_pane):
    pane, vm, settings, vault, notices = settings_pane
    widgets = pane.widgets()
    widgets["provider_list"].setCurrentRow(0)
    widgets["open_provider"].click()
    assert pane.page() == "provider"
    assert pane.current_provider_id() == "p1"
    assert widgets["name"].text() == "Anthropic"
    assert widgets["key_status"].text() == "未配置密钥"
    assert widgets["model_list"].count() == 2

    widgets["back"].click()
    assert pane.page() == "list"
    assert pane.current_provider_id() == ""
    # 从服务商详情返回会提示「下一轮生效」
    assert notices[-1] == "设置已更新，下一轮对话生效"

    widgets["back"].click()
    assert notices[-1] == "back"


def test_settings_pane_edits_provider_and_persists(settings_pane, tmp_path):
    pane, vm, settings, vault, notices = settings_pane
    widgets = pane.widgets()
    widgets["provider_list"].setCurrentRow(1)
    widgets["open_provider"].click()

    widgets["name"].setText("DeepSeek 官方")
    widgets["base_url"].setText("https://api.deepseek.com/v1")
    widgets["adapter"].setCurrentIndex(0)  # Anthropic 协议
    widgets["enabled"].setChecked(True)
    widgets["save_provider"].click()

    saved = next(p for p in settings.models_section()["providers"] if p["id"] == "p2")
    assert saved["name"] == "DeepSeek 官方"
    assert saved["apiHost"] == "https://api.deepseek.com/v1"
    assert saved["adapter"] == "anthropic"
    assert saved["enabled"] is True
    assert notices[-1] == "服务商已保存"
    # 其它兄弟字段没被这次保存抹掉
    assert settings.models_section()["activeModelId"] == "p1:claude-sonnet-5-5"


def test_settings_pane_saves_key_and_never_echoes_it(settings_pane):
    pane, vm, settings, vault, notices = settings_pane
    widgets = pane.widgets()
    widgets["provider_list"].setCurrentRow(1)
    widgets["open_provider"].click()

    widgets["key"].setText("sk-deepseek-secret")
    widgets["save_key"].click()

    assert vault.get_secret("p2") == "sk-deepseek-secret"
    assert widgets["key"].text() == ""  # 输入框保存后清空
    assert widgets["key_status"].text() == "已配置密钥"
    assert notices[-1] == "密钥已保存"

    widgets["clear_key"].click()
    assert vault.has_secret("p2") is False
    assert widgets["key_status"].text() == "未配置密钥"


def test_settings_pane_adds_toggles_and_removes_model(settings_pane):
    pane, vm, settings, vault, notices = settings_pane
    widgets = pane.widgets()
    widgets["provider_list"].setCurrentRow(1)
    widgets["open_provider"].click()

    widgets["new_model"].setText("deepseek-reasoner")
    widgets["add_model"].click()
    assert "deepseek-reasoner" in [m["id"] for m in vm.models_of("p2")]
    assert notices[-1] == "模型已添加"

    # 新加的模型默认启用，排在最后一行；点「停用」再点「启用」都要生效
    assert next(m for m in vm.models_of("p2") if m["id"] == "deepseek-reasoner")["enabled"] is True
    widgets["model_list"].setCurrentRow(1)
    assert widgets["toggle_model"].text() == "停用"
    widgets["toggle_model"].click()
    assert next(m for m in vm.models_of("p2") if m["id"] == "deepseek-reasoner")["enabled"] is False
    widgets["toggle_model"].click()
    assert next(m for m in vm.models_of("p2") if m["id"] == "deepseek-reasoner")["enabled"] is True

    widgets["set_default"].click()
    assert vm.active_model == "p2:deepseek-reasoner"
    assert notices[-1] == "已设为默认模型"

    widgets["remove_model"].click()
    assert "deepseek-reasoner" not in [m["id"] for m in vm.models_of("p2")]
    # 删掉的正是默认模型：默认清空（不留悬空引用）
    assert vm.active_model == ""
    assert notices[-1] == "模型已删除"


def test_settings_pane_model_detail_saves_and_restores_auto(settings_pane):
    pane, vm, settings, vault, notices = settings_pane
    widgets = pane.widgets()
    widgets["provider_list"].setCurrentRow(0)
    widgets["open_provider"].click()
    widgets["model_list"].setCurrentRow(0)
    widgets["edit_model"].click()

    assert pane.page() == "model"
    assert widgets["context_window"].value() == 200_000

    widgets["model_name"].setText("Sonnet")
    widgets["context_window"].setValue(100_000)
    widgets["max_output"].setValue(8_192)
    widgets["save_model"].click()
    model = vm.models_of("p1")[0]
    assert (model["name"], model["context_window"], model["max_output"]) == ("Sonnet", 100_000, 8_192)

    widgets["restore_auto"].click()
    model = vm.models_of("p1")[0]
    assert model["context_window"] is None and model["max_output"] is None
    # 「恢复自动」只删这两个键，显示名保留
    assert model["name"] == "Sonnet"


def test_settings_pane_effort_change_writes_config(settings_pane):
    pane, vm, settings, vault, notices = settings_pane
    pane.widgets()["effort"].setCurrentIndex(5)  # max
    assert settings.models_section()["activeEffort"] == "max"
    assert notices[-1] == "思考等级已更新，下一轮对话生效"


def test_settings_pane_add_provider_opens_detail(settings_pane):
    pane, vm, settings, vault, notices = settings_pane
    pane.widgets()["add_provider"].click()
    assert pane.page() == "provider"
    new_id = pane.current_provider_id()
    assert new_id.startswith("custom-")
    entry = vm.provider(new_id)
    assert entry["enabled"] is False and entry["models"] == []
    assert pane.widgets()["base_url"].text() == "https://"


def test_settings_pane_fetch_delegates_to_window(settings_env):
    settings, vault = settings_env
    vm = SettingsViewModel(settings, vault)
    calls: list = []
    pane = SettingsPane(vm, on_fetch=calls.append)
    pane.widgets()["provider_list"].setCurrentRow(0)
    pane.widgets()["open_provider"].click()
    pane.widgets()["fetch_models"].click()
    # 网络 I/O 必须由窗口层在后台跑：面板只把 provider id 交出去
    assert calls == ["p1"]


def test_settings_pane_refreshes_when_viewmodel_changes(settings_pane):
    """ViewModel 被别处改动（例如后台拉取后写配置）时界面要跟着重建。"""
    pane, vm, settings, vault, notices = settings_pane
    vm.set_active_model("p2", "deepseek-chat")
    assert pane.widgets()["active_label"].text() == "默认模型：p2:deepseek-chat"


# ── 主窗口装配 ──────────────────────────────────────────────────────────
def test_main_window_starts_on_chat_with_session_list(main_window):
    window, chat, sessions, settings, vault = main_window
    assert window.status_text == "就绪"
    assert window.settings_visible is False
    assert window.session_pane().list_widget().count() == 2
    assert window.chat_pane().widget().visible is True


def test_main_window_switches_session(main_window):
    window, chat, sessions, settings, vault = main_window
    assert chat.session_id == "b"
    window.session_pane().list_widget().setCurrentRow(1)  # 甲
    assert chat.session_id == "a"
    assert sessions.active_id == "a"
    assert window.status_text == "就绪"


def test_main_window_refuses_switch_while_busy(main_window, monkeypatch):
    window, chat, sessions, settings, vault = main_window
    monkeypatch.setattr(type(chat), "busy", property(lambda self: True))
    window.session_pane().list_widget().setCurrentRow(1)
    assert chat.session_id == "b"  # 没切
    assert "停止后才能切换" in window.status_text


def test_main_window_new_session_is_lazy(main_window):
    window, chat, sessions, settings, vault = main_window
    window.session_pane().buttons()["new"].click()
    assert chat.session_id.startswith("sess_")
    assert chat.session_id != "b"
    # 惰性建档：没有消息的会话不进列表
    assert window.session_pane().list_widget().count() == 2
    assert window.status_text == "新对话"


def test_main_window_rename_updates_list_and_title(main_window):
    window, chat, sessions, settings, vault = main_window
    FakeInputDialog.answer = "乙（改名）"
    FakeInputDialog.accepted = True
    try:
        window.session_pane().buttons()["rename"].click()
    finally:
        FakeInputDialog.accepted = False
    titles = [s["title"] for s in sessions.sessions]
    assert "乙（改名）" in titles
    assert chat.title == "乙（改名）"
    assert window.status_text == "已重命名"


def test_main_window_rename_rejects_blank(main_window):
    window, chat, sessions, settings, vault = main_window
    FakeInputDialog.answer = "   "
    FakeInputDialog.accepted = True
    try:
        window.session_pane().buttons()["rename"].click()
    finally:
        FakeInputDialog.accepted = False
    assert chat.title == "乙"
    assert window.status_text == "标题不能为空"


def test_main_window_archive_moves_off_list_and_opens_next(main_window):
    window, chat, sessions, settings, vault = main_window
    assert chat.session_id == "b"
    window.session_pane().buttons()["archive"].click()
    assert "已归档" in window.status_text
    assert [s["id"] for s in sessions.sessions] == ["a"]
    assert chat.session_id == "a"
    assert window.session_pane().list_widget().count() == 1


def test_main_window_delete_asks_and_removes(main_window, tmp_path):
    window, chat, sessions, settings, vault = main_window
    path = ChatSessionStore(tmp_path / "home").session_path("b")
    assert path.exists()

    FakeMessageBox.answer = FakeMessageBox.No
    try:
        window.session_pane().buttons()["delete"].click()
    finally:
        FakeMessageBox.answer = FakeMessageBox.No
    assert path.exists()  # 点了「否」什么都不做
    assert chat.session_id == "b"

    FakeMessageBox.answer = FakeMessageBox.Yes
    try:
        window.session_pane().buttons()["delete"].click()
    finally:
        FakeMessageBox.answer = FakeMessageBox.No
    assert not path.exists()
    assert window.status_text == "已删除"
    assert chat.session_id == "a"
    assert [s["id"] for s in sessions.sessions] == ["a"]


def test_main_window_toggles_settings_view(main_window):
    window, chat, sessions, settings, vault = main_window
    window.session_pane().buttons()["settings"].click()
    assert window.settings_visible is True
    assert window.chat_pane().widget().visible is False
    assert window.status_text == "设置"

    window.settings_pane().widgets()["back"].click()
    assert window.settings_visible is False
    assert window.chat_pane().widget().visible is True
    assert window.status_text == "就绪"


def test_main_window_sends_message_in_chat_pane(main_window):
    window, chat, sessions, settings, vault = main_window
    pane = window.chat_pane()
    chat.input_text_property.set_value("看一下 notes.txt")
    pane._send_button.click()
    assert chat.wait_idle(5.0)
    assert chat.transcript[-1]["role"] == "assistant"
    assert "你好" in pane._transcript.plain_text
    assert window.status_text == "就绪"


def test_main_window_reports_missing_fetch_gateway(tmp_path, settings_env, fake_qt):
    settings, vault = settings_env
    store = ChatSessionStore(tmp_path / "home")
    chat = ChatViewModel(store, FakeProvider(), ToolRuntime(WorkspaceGuard(), None))
    chat.open_session("x")
    sessions = ChatSessionsViewModel(store)
    window = DevaMainWindow(chat, sessions, SettingsViewModel(settings, vault))
    try:
        window._fetch_models_async("p1")  # 没装配网关（on_fetch 为 None）
        assert window.status_text == "未装配模型网关，无法拉取模型清单"
    finally:
        window.close()


# ── 聊天面板：工具卡、图片、待办胶囊 ─────────────────────────────────────
def test_chat_window_binds_transcript_status_and_send(tmp_path, monkeypatch, fake_qt):
    """ChatWindow 的属性绑定与发送命令：输入 → ViewModel → 回合 → 界面刷新。

    原在 `test_deva_app.py` 里（那个模块测的是已移除的 `deva_app` 入口装配），
    用例本身只碰 `ChatWindow` 与 ViewModel，随入口一起删会白白丢掉这条断言。
    """
    monkeypatch.setenv("DEVA_HOME", str(tmp_path / "home"))

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


def _pane(tmp_path):
    from mvvm.views.chat_pane import ChatPane

    store = ChatSessionStore(tmp_path / "home")
    chat = ChatViewModel(store, FakeProvider(), ToolRuntime(WorkspaceGuard(), None))
    chat.open_session("pane")
    return chat, ChatPane(chat)


def test_chat_pane_renders_tool_result_as_card(tmp_path, fake_qt):
    chat, pane = _pane(tmp_path)
    chat._append_display(
        "tool", "第一行\n第二行", name="read_file", summary="2 行"
    )
    chat.drain()

    html = pane._transcript.html
    assert "<table" in html
    assert "read_file · 2 行" in html
    assert "第一行<br/>第二行" in html


def test_chat_pane_registers_inline_image_as_document_resource(tmp_path, fake_qt):
    import base64

    from helpers_png import png_bytes  # noqa: PLC0415 - 只需图片字节的用例才导入

    chat, pane = _pane(tmp_path)
    data = base64.b64encode(png_bytes()).decode()
    chat._append_display(
        "tool",
        "已读取图片",
        name="read_file",
        images=[{"mediaType": "image/png", "name": "a.png", "data": data}],
    )
    chat.drain()

    # 假控件的 document() 只记录 addResource 的调用；这里验证「先注册资源、HTML 里用占位 URL」。
    assert len(pane._transcript.document().resources) == 1
    assert 'src="deva-image:0"' in pane._transcript.html


def test_chat_pane_todo_capsule_expands_and_collapses(tmp_path, fake_qt):
    chat, pane = _pane(tmp_path)
    state = {
        "id": "l1",
        "title": "迁移",
        "items": [
            {"content": "读源码", "status": "completed"},
            {"content": "写实现", "status": "in_progress"},
        ],
    }
    chat.todos_state_property.set_value(state)
    widgets = pane.todo_widgets()
    assert widgets["row"].visible is True
    assert "写实现" in widgets["pill"].text()
    assert "已完成 1/2" in widgets["pill"].text()
    assert widgets["details"].visible is False

    widgets["toggle"].click()
    assert widgets["details"].visible is True
    assert "[x] 读源码" in widgets["details"].text()
    widgets["toggle"].click()
    assert widgets["details"].visible is False

    chat.todos_state_property.set_value(None)
    assert widgets["row"].visible is False


def test_chat_pane_cancel_button_cancels_active_list(tmp_path, fake_qt):
    chat, pane = _pane(tmp_path)
    chat.todos_state_property.set_value(
        {"id": "l1", "items": [{"content": "a", "status": "in_progress"}]}
    )
    # 清单状态是从会话边车读的：这里先真的写一份，再点取消。
    session = chat.store.ensure_session("pane")
    session.todos = [{"id": "t", "listId": "l1", "at": 1, "title": "", "items": [{"content": "a", "status": "in_progress"}]}]
    chat.store.save("pane")

    pane.todo_widgets()["cancel"].click()
    assert chat.store.ensure_session("pane").todoCancelled == ["l1"]
    assert pane.todo_widgets()["row"].visible is False
