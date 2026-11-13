"""纵向切片：发送一条消息 → 假 provider 回复 → 工具调用被允许/被拒 → 持久化 → 重启读回。

这是本轮验收的核心用例，断言的是**全链路**而不是各层单测之和：
ViewModel 驱动回合，provider 决定调工具，工具过路径守卫，消息落盘，
再用一个全新的 Store + ViewModel 从磁盘读回。
"""
from __future__ import annotations

import asyncio
import json

import pytest

from mvvm.models.chat_models import StoredSession
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.fake_provider import FakeProvider
from mvvm.services.provider_gateway import Done, TextDelta, ToolCall
from mvvm.services.tool_runtime import ToolRuntime
from mvvm.services.workspace_guard import DENIED, WorkspaceGuard
from mvvm.view_models.chat_vm import ChatViewModel

GENERATED_ID = "acct-approval"


@pytest.fixture()
def workspace(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    (root / "notes.txt").write_text("会议纪要：上线时间定在周五\n", encoding="utf-8")
    return root


def make_vm(home, workspace, *, provider=None, trust_workspace=True):
    store = ChatSessionStore(home)
    guard = WorkspaceGuard([workspace] if trust_workspace else [])
    tools = ToolRuntime(guard, workspace)
    return ChatViewModel(store, provider or FakeProvider(), tools, model="fake-model")


def test_full_slice_allowed_then_persisted_then_read_back(tmp_path, workspace):
    home = tmp_path / "deva-home"
    vm = make_vm(home, workspace)
    vm.open_session("session-1")
    vm.input_text_property.set_value("看一下 notes.txt")

    vm.send()
    assert vm.wait_idle(5.0)

    assert vm.error == "", vm.error
    assert vm.status == "就绪"
    assert vm.busy is False
    # 工具真的被执行并返回了文件内容
    assert len(vm.tool_results) == 1
    assert vm.tool_results[0].is_error is False
    assert "会议纪要" in vm.tool_results[0].content
    # 展示流：用户 → 助手开场白 → 工具结果 → 助手总结
    roles = [entry["role"] for entry in vm.transcript]
    assert roles == ["user", "assistant", "tool", "assistant"]
    assert vm.transcript[1]["text"] == "我先看一下工作区里的文件。"
    assert "会议纪要" in vm.transcript[-1]["text"]
    assert vm.title == "看一下 notes.txt"

    # 磁盘上真的有完整记录（用户 / tool_use / tool_result / 助手）
    raw = json.loads((store_path(home) / "session-1.json").read_text(encoding="utf-8"))
    assert len(raw["messages"]) == 4
    parts = [p["type"] for p in raw["messages"][1]["content"]]
    assert parts == ["text", "tool_use"]  # 正文与调用同一条消息

    # 重启：全新 Store + 全新 ViewModel，只从磁盘读
    restarted = make_vm(home, workspace)
    restarted.open_session("session-1")
    # 重启后历史与运行时一致：开场白与 tool_use 同属一条 assistant 消息
    assert [e["role"] for e in restarted.transcript] == ["user", "assistant", "tool", "assistant"]
    assert restarted.transcript[1]["text"] == "我先看一下工作区里的文件。"
    assert "会议纪要" in restarted.transcript[-1]["text"]


def test_denied_tool_is_reported_to_model_and_persisted(tmp_path, workspace):
    home = tmp_path / "deva-home"
    outside = workspace.parent / "outside.txt"
    outside.write_text("机密", encoding="utf-8")
    # 假 provider 指向根外绝对路径，工具必须拒绝
    provider = FakeProvider(tool_path=str(outside))
    vm = make_vm(home, workspace, provider=provider)
    vm.open_session("denied-1")
    vm.input_text_property.set_value("读一下外面那个文件")

    vm.send()
    assert vm.wait_idle(5.0)

    assert len(vm.tool_results) == 1
    denied = vm.tool_results[0]
    assert denied.is_error is True
    assert denied.content == DENIED
    # 拒绝原因作为 tool_result 回灌给了模型：假 provider 的总结里必须出现「失败」
    assert "失败" in vm.transcript[-1]["text"]
    assert DENIED in vm.transcript[-1]["text"]
    assert vm.transcript[2]["is_error"] is True

    session = StoredSession.model_validate_json(
        (store_path(home) / "denied-1.json").read_text(encoding="utf-8")
    )
    assert session.messages[2].content[0].type == "tool_result"
    assert session.messages[2].content[0].isError is True
    assert session.messages[2].content[0].content == DENIED


def test_no_trusted_roots_means_denied(tmp_path, workspace):
    provider = FakeProvider(tool_path=str(workspace / "notes.txt"))
    vm = make_vm(tmp_path / "home", workspace, provider=provider, trust_workspace=False)
    vm.open_session("no-roots")
    vm.input_text_property.set_value("读文件")
    vm.send()
    assert vm.wait_idle(5.0)

    assert vm.tool_results[0].is_error is True
    assert vm.tool_results[0].content == DENIED


def test_provider_failure_surfaces_as_visible_error(tmp_path, workspace):
    vm = make_vm(tmp_path / "home", workspace, provider=FakeProvider(fail_with="密钥无效"))
    vm.open_session("auth-fail")
    vm.input_text_property.set_value("你好")
    vm.send()
    assert vm.wait_idle(5.0)

    assert vm.status == "失败"
    assert vm.error == "密钥无效"
    # 用户消息仍然落盘了（失败不该吞掉用户输入）
    assert vm.transcript[0] == {"role": "user", "text": "你好"}
    assert vm.transcript[-1]["role"] == "error"


def test_empty_input_does_nothing(tmp_path, workspace):
    vm = make_vm(tmp_path / "home", workspace)
    vm.open_session("empty")
    vm.input_text_property.set_value("   ")
    assert vm.can_send() is False
    vm.send()
    assert vm.wait_idle(5.0)
    assert vm.transcript == []
    assert not (store_path(tmp_path / "home") / "empty.json").exists()


def test_send_requires_an_open_session(tmp_path, workspace):
    vm = make_vm(tmp_path / "home", workspace)
    vm.input_text_property.set_value("hi")
    vm.send()
    assert vm.wait_idle(5.0)
    assert vm.status == "失败"
    assert "没有打开会话" in vm.error


def test_run_turn_is_awaitable_without_qt(tmp_path, workspace):
    """异步入口可被直接 await（将来接 qasync 时用它），不经过 asyncio.run。"""
    vm = make_vm(tmp_path / "home", workspace)
    vm.open_session("async")

    async def scenario():
        await vm.run_turn("看一下 notes.txt")

    asyncio.run(scenario())
    assert vm.error == ""
    assert len(vm.tool_results) == 1


def test_tool_loop_stops_when_provider_keeps_calling_tools(tmp_path, workspace):
    """provider 无限要工具时必须中止，不能死循环。"""
    looping = FakeProvider(
        script=[
            TextDelta("再看看"),
            ToolCall(id="loop", name="read_file", input={"path": "notes.txt"}),
            Done("tool_use"),
        ]
    )
    vm = make_vm(tmp_path / "home", workspace, provider=looping)
    vm.open_session("loop")
    vm.input_text_property.set_value("循环")

    vm.send()
    assert vm.wait_idle(5.0)

    assert vm.status == "失败"
    assert "工具调用超过" in vm.error


def test_reopening_a_session_shows_stored_history(tmp_path, workspace):
    home = tmp_path / "home"
    vm = make_vm(home, workspace)
    vm.open_session("reopen")
    vm.input_text_property.set_value("看一下 notes.txt")
    vm.send()
    assert vm.wait_idle(5.0)
    before = len(vm.transcript)

    same_session = make_vm(home, workspace)
    same_session.open_session("reopen")
    assert len(same_session.transcript) == before


def store_path(home):
    return ChatSessionStore(home).chats_dir


def test_turn_end_notifier_runs_on_the_draining_thread(tmp_path, workspace):
    """回合结束回调必须在 `drain()` 的线程执行，不能在工作线程直接改界面。

    回归用例：`run_turn` 曾在工作线程的 finally 里直接调 `_notifier`，界面回调
    因此从工作线程写 Qt 控件（`QObject: Cannot create children for a parent that
    is in a different thread`，随后进程崩溃）。
    """
    import threading

    calls: list[int] = []
    store = ChatSessionStore(tmp_path / "home")
    vm = ChatViewModel(
        store,
        FakeProvider(),
        ToolRuntime(WorkspaceGuard([workspace]), workspace),
        notifier=lambda: calls.append(threading.get_ident()),
    )
    vm.open_session("notify")
    main_ident = threading.get_ident()

    vm.start_turn("看一下 notes.txt")
    worker = vm._thread
    assert worker is not None
    worker.join(5.0)
    assert calls == []          # 回合跑完但界面还没取事件：回调不该已在工作线程执行
    assert vm.drain() > 0
    assert calls == [main_ident]
