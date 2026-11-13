"""流式刷新与「停止」：回合跑在后台线程，增量经事件队列回到 UI 线程。

这里验证三件事：
1. 增量在回合**进行中**就能取到（而不是等整轮跑完才有正文）；
2. `drain()` 只在 UI 线程执行队列里的写入，队列为空时是空操作；
3. 停止按钮对应的 `cancel()` 能让回合在下一个检查点收尾，并落盘已收到的半截正文。
"""
from __future__ import annotations

import threading
import time

from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.provider_gateway import Done, Provider, TextDelta
from mvvm.services.tool_runtime import ToolRuntime
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.view_models.chat_vm import ChatViewModel


class GatedProvider(Provider):
    """分两次放行：第一段先出，等测试看到「流式正文」后再出剩下的。"""

    name = "gated"

    def __init__(self, parts=("第一段", "第二段", "第三段")) -> None:
        self.parts = parts
        self.gate = threading.Event()
        self.tail_gate = threading.Event()

    async def stream(self, request):  # type: ignore[override]
        self.gate.wait(10.0)
        yield TextDelta(self.parts[0])
        # 停在这里等测试确认：只有分两次出，UI 线程才有机会在回合中途 drain 到正文。
        self.tail_gate.wait(10.0)
        for part in self.parts[1:]:
            yield TextDelta(part)

        yield Done("end_turn")


class CancellableProvider(Provider):
    """收到取消标记就提前返回：用来验证「停止」在正文之间生效。"""

    name = "cancellable"

    def __init__(self, cancel=None) -> None:
        self.cancel = cancel
        self.started = threading.Event()

    async def stream(self, request):  # type: ignore[override]
        yield TextDelta("开头")
        self.started.set()
        deadline = time.time() + 10.0
        while time.time() < deadline:
            if self.cancel is not None and self.cancel.cancelled:
                return
            time.sleep(0.01)
        yield Done("end_turn")


def make_vm(tmp_path, provider, *, turn_factory=None):
    root = tmp_path / "work"
    root.mkdir(exist_ok=True)
    store = ChatSessionStore(tmp_path / "home")
    vm = ChatViewModel(
        store,
        provider,
        ToolRuntime(WorkspaceGuard([root]), root),
        turn_factory=turn_factory,
    )
    return vm, store


def test_streaming_text_appears_while_the_turn_is_running(tmp_path):
    provider = GatedProvider()
    vm, _ = make_vm(tmp_path, provider)
    vm.open_session("s")
    vm.input_text_property.set_value("讲三段")

    # 门还没开：回合在等，界面已经是「忙碌」但没有正文。
    vm.send()
    deadline = time.time() + 2.0
    while time.time() < deadline and not vm.busy:
        vm.drain()  # 「忙碌」这条也是回合线程经队列送回来的，要靠 UI 线程执行
        time.sleep(0.01)
    assert vm.busy is True
    assert vm.streaming == ""

    # 放行后，UI 线程的 drain 把队列里的增量落到属性上——此时回合尚未结束。
    provider.gate.set()
    deadline = time.time() + 5.0
    seen = ""
    while time.time() < deadline:
        vm.drain()
        seen = vm.streaming
        if seen:
            break
        time.sleep(0.01)
    assert seen, "回合进行中没有出现过流式正文"
    assert vm.busy is True

    provider.tail_gate.set()
    assert vm.wait_idle(10.0)
    assert vm.error == ""
    # 回合结束后流式区清空，正文已作为一条助手消息落盘
    assert vm.streaming == ""
    assert vm.transcript[-1]["role"] == "assistant"
    assert vm.transcript[-1]["text"] == "第一段第二段第三段"


def test_drain_is_a_noop_when_queue_is_empty(tmp_path):
    vm, _ = make_vm(tmp_path, GatedProvider())
    vm.open_session("s")
    assert vm.drain() == 0
    assert vm.drain() == 0


def test_stop_cancels_the_turn_and_keeps_partial_text(tmp_path):
    holder: dict = {}

    def turn_factory(cancel, session_model):
        provider = CancellableProvider(cancel)
        holder["provider"] = provider
        return provider, "paced"

    vm, store = make_vm(tmp_path, None, turn_factory=turn_factory)
    vm.open_session("s")
    vm.input_text_property.set_value("慢慢说")
    vm.send()

    # 工厂在回合线程里被调用，主线程要等一下才能拿到 provider 句柄。
    deadline = time.time() + 5.0
    while time.time() < deadline and "provider" not in holder:
        time.sleep(0.01)
    assert "provider" in holder, "回合线程没有调用 turn_factory"
    assert holder["provider"].started.wait(10.0)
    vm.drain()  # 「忙碌」由回合线程入队，UI 线程取走后才生效
    assert vm.busy is True
    vm.cancel()
    assert vm.status == "正在停止…"
    assert vm.wait_idle(10.0)

    assert vm.status == "已停止"
    session = store.ensure_session("s")
    assistant = [m for m in session.messages if m.role == "assistant"]
    assert assistant and "开头" in str(assistant[-1].content)
    assert vm.transcript[-1]["role"] == "assistant"
    assert vm.streaming == ""
