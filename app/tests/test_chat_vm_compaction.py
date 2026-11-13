"""把压缩接进对话回合：轮首自动压、轮中自动压、手动 `/compact`、界面事件。

压缩模块本身已在 test_compaction.py 里测透；这里只验证 `ChatViewModel` 的接线：
什么时候查阈值、压完历史怎么变、事件发给了谁、没配置压缩模型时不受影响。
"""
from __future__ import annotations

import asyncio

from mvvm.models.chat_models import Message, StoredSession
from mvvm.services import compaction as cp
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.compaction import CompactModel
from mvvm.services.fake_provider import FakeProvider
from mvvm.services.model_view import COMPACT_MARKER
from mvvm.services.provider_gateway import Done, GenerateRequest, Provider, TextDelta
from mvvm.services.tool_runtime import ToolRuntime
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.view_models.chat_vm import ChatViewModel

MODEL = CompactModel("anthropic", "p1", "https://api.anthropic.com", "claude-sonnet-5-5")
MODELS = {
    "providers": [
        {
            "id": "p1",
            "adapter": "anthropic",
            "models": [{"id": "claude-sonnet-5-5", "contextWindow": 20_000}],
        },
    ],
}
# 20k 窗口 → 触发线 8k、保留量 6k；中文一字一 token，40 条 300 字的旧消息足够触发。
BIG = "旧" * 300


class SummaryProvider(Provider):
    """压缩摘要用的假 provider：只回一段固定摘要。"""

    name = "summary"

    def __init__(self, text: str = "旧对话讲了甲、乙、丙三件事。") -> None:
        self._text = text
        self.requests: list[GenerateRequest] = []

    async def stream(self, request):  # type: ignore[override]
        self.requests.append(request)
        yield TextDelta(self._text)
        yield Done("end_turn")


class PlainProvider(Provider):
    """只回一句话的正常 provider：避免 FakeProvider 自带的工具调用把消息条数搅乱。"""

    name = "plain"

    def __init__(self, text: str = "好的") -> None:
        self._text = text

    async def stream(self, request):  # type: ignore[override]
        yield TextDelta(self._text)
        yield Done("end_turn")


def _seed_session(store: ChatSessionStore, count: int = 40) -> StoredSession:
    session = store.ensure_session("long")
    for index in range(count):
        session.messages.append(Message(role="user", content=f"{BIG}-{index}"))
        session.messages.append(Message(role="assistant", content=f"{BIG}-{index}"))
    store.save("long")
    return session


def make_vm(tmp_path, *, summary: SummaryProvider | None = None, compact: bool = True):
    root = tmp_path / "work"
    root.mkdir(exist_ok=True)
    home = tmp_path / "home"
    store = ChatSessionStore(home)
    vm = ChatViewModel(
        store,
        PlainProvider(),
        ToolRuntime(WorkspaceGuard([root]), root),
        model="claude-sonnet-5-5",
        provider_factory=(lambda cancel: summary or SummaryProvider()) if compact else None,
        compact_model=MODEL if compact else None,
        models_section=MODELS if compact else None,
    )
    return vm, store


def test_turn_start_auto_compaction_inserts_summary_without_deleting(tmp_path):
    vm, store = make_vm(tmp_path)
    session = _seed_session(store)
    before = len(session.messages)
    events: list[dict] = []
    vm.emit = events.append

    vm.open_session("long")
    vm.input_text_property.set_value("再说一件事")
    vm.send()
    assert vm.wait_idle(10.0)

    assert vm.error == "", vm.error
    session = store.ensure_session("long")
    summaries = [m for m in session.messages if str(m.content).startswith(COMPACT_MARKER)]
    assert len(summaries) == 1
    # 一条都没删：原文还在，压缩只是插了一条摘要（Deva 语义）
    assert len(session.messages) == before + 3  # 原 80 条 + 摘要 + 用户提问 + 助手回答
    summary_index = session.messages.index(summaries[0])
    assert 0 < summary_index < len(session.messages) - 2
    assert "旧对话讲了甲、乙、丙三件事。" in str(summaries[0].content)

    types = [event["type"] for event in events]
    assert "compacting" in types
    assert types.count("compacting") == 2  # 开始与结束各一次
    compacted = [event for event in events if event["type"] == "compacted"]
    assert compacted and compacted[0]["status"] == "compacted"
    # 压缩事件先于本次回复的正文增量：先压再问模型
    assert types.index("compacting") < types.index("text_delta")

    # 展示流里有压缩块，摘要正文不带标记前缀
    from mvvm.services.compaction import display_summary

    assert display_summary(str(summaries[0].content)).startswith("旧对话讲了甲")

    # 落盘也按拆分格式写：主文件不再包含被压掉的早期消息
    assert list(store.chats_dir.glob("long.compacted-*.jsonl"))


def test_mid_turn_compaction_runs_between_tool_steps(tmp_path):
    """第二步之前再查一次阈值：工具结果把上下文顶过线时会压（轮中压缩）。"""
    vm, store = make_vm(tmp_path)
    _seed_session(store, count=28)  # 56 条 × ~304 token ≈ 17k，已超过 8k 触发线
    calls: list[str] = []

    class ToolCallingProvider(Provider):
        name = "tool-loop"

        async def stream(self, request):  # type: ignore[override]
            calls.append("call")
            if len(calls) == 1:
                from mvvm.services.provider_gateway import ToolCall

                yield ToolCall(id="c1", name="read_file", input={"path": "notes.txt"})
                yield Done("tool_use")
            else:
                yield TextDelta("读完了")
                yield Done("end_turn")

    (tmp_path / "work" / "notes.txt").write_text("会议纪要\n", encoding="utf-8")
    vm.provider = ToolCallingProvider()
    events: list[dict] = []
    vm.emit = events.append

    vm.open_session("long")
    vm.input_text_property.set_value("看一下 notes.txt")
    vm.send()
    assert vm.wait_idle(10.0)

    assert vm.error == "", vm.error
    # 轮首压过一次（旧历史），第二步前又压过一次（含第一步的工具结果）。
    # 轮中压缩的目标是「这一步仍要发出去的内容」不比上一步多，故只要求至少压过一次。
    compacted = [event for event in events if event["type"] == "compacted"]
    assert compacted and compacted[0]["status"] == "compacted"
    assert len(calls) == 2
    session = store.ensure_session("long")
    summaries = [m for m in session.messages if str(m.content).startswith(COMPACT_MARKER)]
    assert len(summaries) >= 1
    # 工具调用与结果没被拆散：最后一步请求能发出去（没有悬空 tool_use 导致的报错）
    assert vm.status == "就绪"


def test_compact_now_is_manual_and_emits_manual_scope(tmp_path):
    vm, store = make_vm(tmp_path)
    _seed_session(store)
    events: list[dict] = []
    vm.emit = events.append
    vm.open_session("long")

    result = asyncio.run(vm.compact_now())

    assert result.status == "compacted"
    assert any(e["type"] == "compacted" and e.get("scope") == "manual" for e in events)
    session = store.ensure_session("long")
    assert any(str(m.content).startswith(COMPACT_MARKER) for m in session.messages)


def test_compact_now_without_compaction_model_reports_failure(tmp_path):
    vm, _ = make_vm(tmp_path, compact=False)
    vm.open_session("plain")
    result = asyncio.run(vm.compact_now())
    assert result.status == "failed"
    assert "未配置" in str(result.message)


def test_no_compaction_model_leaves_history_untouched(tmp_path):
    """纯文本场景（测试/未配置模型）：不压缩、不发压缩事件，回合照常跑完。"""
    vm, store = make_vm(tmp_path, compact=False)
    _seed_session(store, count=20)
    events: list[dict] = []
    vm.emit = events.append

    vm.open_session("long")
    vm.input_text_property.set_value("继续")
    vm.send()
    assert vm.wait_idle(10.0)

    assert vm.error == ""
    assert not any(e["type"] == "compacted" for e in events)
    session = store.ensure_session("long")
    assert not any(str(m.content).startswith(COMPACT_MARKER) for m in session.messages)


def test_compaction_failure_does_not_block_the_turn(tmp_path):
    """摘要失败（模型报错）不阻断本回合：这一轮不压，照常回复。"""
    vm, store = make_vm(tmp_path, summary=SummaryProvider(text=""))
    _seed_session(store)
    events: list[dict] = []
    vm.emit = events.append

    vm.open_session("long")
    vm.input_text_property.set_value("继续")
    vm.send()
    assert vm.wait_idle(10.0)

    assert vm.error == "", vm.error
    assert vm.status == "就绪"
    compacted = [e for e in events if e["type"] == "compacted"]
    assert compacted and compacted[0]["status"] == "failed"
