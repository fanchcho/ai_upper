"""`todo_write` 接进对话回合：边车落盘、界面状态、跨轮提醒、用户取消。

对照 Deva `chat.ts` 的 `todo_write` 执行分支（约 5729 行）与「随用户消息带给模型的
清单说明」（约 6053 行）：清单只落会话边车，不进 messages。
"""
from __future__ import annotations

import json

import pytest

from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.provider_gateway import Done, TextDelta, ToolCall
from mvvm.services.tool_runtime import ToolRuntime
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.view_models.chat_vm import ChatViewModel


class ScriptedProvider:
    """按脚本回放：每次 `stream` 取下一组事件；用完就只回一句收尾。"""

    name = "scripted"

    def __init__(self, scripts):
        self._scripts = list(scripts)
        self.requests = []

    async def stream(self, request):
        self.requests.append(request)
        script = self._scripts.pop(0) if self._scripts else [TextDelta("完成。"), Done("end_turn")]
        for event in script:
            yield event


@pytest.fixture()
def home(tmp_path):
    return tmp_path / "deva-home"


@pytest.fixture()
def workspace(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    return root


def make_vm(home, workspace, provider):
    store = ChatSessionStore(home)
    tools = ToolRuntime(WorkspaceGuard([workspace]), workspace)
    return ChatViewModel(store, provider, tools, model="fake-model"), store


def run_turn(vm, text):
    vm.input_text_property.set_value(text)
    vm.send()
    assert vm.wait_idle(5.0), "回合没有在 5 秒内结束"
    assert vm.error == "", vm.error


def test_todo_write_updates_session_sidecar_and_viewmodel_state(home, workspace):
    provider = ScriptedProvider(
        [
            [
                TextDelta("先列个清单。"),
                ToolCall(
                    id="todo1",
                    name="todo_write",
                    input={
                        "title": "迁移工具层",
                        "todos": [
                            {"content": "读 Deva 源码", "status": "completed"},
                            {"content": "写实现", "status": "in_progress"},
                        ],
                    },
                ),
                Done("tool_use"),
            ],
            [TextDelta("清单已建立，开始写实现。"), Done("end_turn")],
        ]
    )
    vm, store = make_vm(home, workspace, provider)
    vm.open_session("s1")
    run_turn(vm, "帮我迁移工具层")

    session = store.ensure_session("s1")
    # 清单状态落在边车（不进 messages）：messages 仍是 user / assistant+tool_use / tool_result / assistant，
    # 侧车只记录折叠所需的快照；模型从自己的 tool_use 入参知道清单内容（Deva 同口径）。
    assert session.todos and len(session.todos) == 1
    assert session.todos[0]["title"] == "迁移工具层"
    assert session.todos[0]["items"][1]["status"] == "in_progress"
    assert len(session.messages) == 4

    # ViewModel 的清单状态（界面胶囊条数据源）与展示流里的工具结果
    assert vm.todos is not None and vm.todos["title"] == "迁移工具层"
    tool_entries = [entry for entry in vm.transcript if entry["role"] == "tool"]
    assert tool_entries and tool_entries[0]["name"] == "todo_write"
    assert "已完成 1/2" in tool_entries[0]["text"]

    # 重启读回：清单仍在边车里
    restarted, _ = make_vm(home, workspace, provider)
    restarted.open_session("s1")
    assert restarted.todos is not None and restarted.todos["title"] == "迁移工具层"
    raw = json.loads((store.session_path("s1")).read_text(encoding="utf-8"))
    assert raw["todos"][0]["listId"] == "l_todo1"


def test_unfinished_todo_is_reminded_in_next_turn(home, workspace):
    provider = ScriptedProvider(
        [
            [
                ToolCall(
                    id="todo1",
                    name="todo_write",
                    input={"todos": [{"content": "第一步", "status": "in_progress"}]},
                ),
                Done("tool_use"),
            ],
            [TextDelta("好。"), Done("end_turn")],
            [TextDelta("继续。"), Done("end_turn")],
        ]
    )
    vm, store = make_vm(home, workspace, provider)
    vm.open_session("s1")
    run_turn(vm, "开始")
    run_turn(vm, "继续吧")

    second_request = provider.requests[2]
    user_texts = [
        part.text
        for message in second_request.messages
        if message.role == "user"
        for part in (message.content if isinstance(message.content, list) else [])
        if getattr(part, "type", "") == "text"
    ]
    assert any("【待办清单提醒】" in text for text in user_texts), user_texts
    assert any("继续吧" == text for text in user_texts)


def test_user_cancel_marks_list_and_notifies_model(home, workspace):
    provider = ScriptedProvider(
        [
            [
                ToolCall(
                    id="todo1",
                    name="todo_write",
                    input={"todos": [{"content": "第一步", "status": "in_progress"}]},
                ),
                Done("tool_use"),
            ],
            [TextDelta("好。"), Done("end_turn")],
            [TextDelta("收到。"), Done("end_turn")],
        ]
    )
    vm, store = make_vm(home, workspace, provider)
    vm.open_session("s1")
    run_turn(vm, "开始")
    assert vm.todos is not None

    assert vm.cancel_todos() is True
    assert vm.todos is None
    session = store.ensure_session("s1")
    assert session.todoCancelled == ["l_todo1"]
    assert session.todoCancelNote and "用户已手动取消" in session.todoCancelNote

    run_turn(vm, "换个方向")
    # 取消说明只带一次，且确实随本轮用户消息发出
    assert store.ensure_session("s1").todoCancelNote is None
    user_texts = [
        part.text
        for message in provider.requests[2].messages
        if message.role == "user"
        for part in (message.content if isinstance(message.content, list) else [])
        if getattr(part, "type", "") == "text"
    ]
    assert any("用户已手动取消" in text for text in user_texts)
    assert not any("【待办清单提醒】" in text for text in user_texts)


def test_cancel_without_active_list_is_noop(home, workspace):
    provider = ScriptedProvider([])
    vm, store = make_vm(home, workspace, provider)
    vm.open_session("s1")
    assert vm.cancel_todos() is False


def test_all_done_clears_active_list_and_emits_done_event(home, workspace):
    provider = ScriptedProvider(
        [
            [
                ToolCall(
                    id="t1",
                    name="todo_write",
                    input={"todos": [{"content": "唯一一步", "status": "in_progress"}]},
                ),
                Done("tool_use"),
            ],
            [
                ToolCall(
                    id="t2",
                    name="todo_write",
                    input={"todos": [{"content": "唯一一步", "status": "completed"}]},
                ),
                Done("tool_use"),
            ],
            [TextDelta("做完了。"), Done("end_turn")],
        ]
    )
    vm, store = make_vm(home, workspace, provider)
    events = []
    vm.emit = events.append
    vm.open_session("s1")
    run_turn(vm, "做一件事")

    assert vm.todos is None
    todo_events = [event for event in events if event["type"] in ("todos", "todo_done")]
    assert any(event["type"] == "todo_done" for event in todo_events)
    # 先推新状态（清单收起），再推「清单完成」卡事件（Deva 同一顺序）。
    assert [event["type"] for event in todo_events][-2:] == ["todos", "todo_done"]
    assert todo_events[-2]["state"] is None
