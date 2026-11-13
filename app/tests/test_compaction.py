"""上下文压缩的离线测试（Deva `compaction.ts` 的移植）。

全部用脚本化假 provider，不联网、不需要密钥：测的是真实的边界选取、转录、把关与插入逻辑。
"""
from __future__ import annotations

import asyncio

import pytest

from mvvm.models.chat_models import Message, StoredNotice, StoredSession, TextPart, ToolResultPart, ToolUsePart
from mvvm.services import compaction as cp
from mvvm.services.model_view import COMPACT_MARKER, model_messages
from mvvm.services.provider_gateway import (
    Done,
    GenerateRequest,
    NormalizedError,
    Provider,
    StreamError,
    TextDelta,
)
from mvvm.services.transport import CancelToken

MODEL = cp.CompactModel("anthropic", "p1", "https://api.anthropic.com", "claude-sonnet-5-5")
# 测试统一用 2 万窗口的模型：触发线 8000、保留量 6000，几十条消息就能走到压缩，
# 又不用造几十万 token 的假数据。窗口取值依据见 context_window.py。
MODELS = {
    "providers": [
        {
            "id": "p1",
            "adapter": "anthropic",
            "models": [{"id": "claude-sonnet-5-5", "contextWindow": 20_000}],
        },
    ]
}
# OpenAI Chat 协议的「自动」输出上限是 None，学到的预算才会参与计算（见 test_remember_output_budget）。
# 用大窗口，避免「输出上限封顶半个窗口」把差异吃掉。
OPENAI_MODEL = cp.CompactModel("openai", "p2", "https://api.deepseek.com", "deepseek-chat")
OPENAI_MODELS = {
    "providers": [
        {
            "id": "p2",
            "adapter": "openai",
            "models": [{"id": "deepseek-chat", "contextWindow": 200_000}],
        }
    ]
}
TRIGGER = 8_000  # 20000 - 10000（输出上限封顶半个窗口）- 2000（余量一成）
KEEP = 6_000  # 窗口的 30%


class ScriptedProvider(Provider):
    """按给定脚本回放；`text` 便捷构造「若干 TextDelta + Done」。"""

    name = "scripted"

    def __init__(self, script=None, text: str = "") -> None:
        if script is None:
            script = [TextDelta(text[i : i + 8]) for i in range(0, len(text), 8)] or [TextDelta("")]
            script = [*script, Done("end_turn")]
        self._script = list(script)
        self.requests: list[GenerateRequest] = []

    async def stream(self, request):  # type: ignore[override]
        self.requests.append(request)
        for event in self._script:
            yield event


def factory_for(*providers):
    """依次返回给定的 provider（第 N 次尝试用第 N 个）；用完后重复最后一个。"""
    queue = list(providers)
    made = []

    def factory(cancel: CancelToken) -> Provider:
        index = min(len(made), len(queue) - 1)
        made.append(cancel)
        if not queue:
            raise AssertionError("没有可用的 provider")
        return queue[index]

    factory.made = made  # type: ignore[attr-defined]
    return factory


def user(text: str) -> Message:
    return Message(role="user", content=text)


def assistant(text: str) -> Message:
    return Message(role="assistant", content=text)


def long_turn(label: str, chars: int = 400) -> list[Message]:
    """一轮够大的问答（默认约 2 × 400 token）。"""
    return [user(f"{label} 的问题" + "问" * chars), assistant(f"{label} 的回答" + "答" * chars)]


def session_with(messages: list[Message]) -> StoredSession:
    return StoredSession(id="s1", title="t", messages=messages)


def _big_turn(label: str, chars: int = 2_400) -> list[Message]:
    """一轮明显超过保留量（6000 token）的问答：保证压缩有足够收益。"""
    return [user(f"{label} 的问题" + "问" * chars), assistant(f"{label} 的回答" + "答" * chars)]


# ── 配置 / 窗口 ───────────────────────────────────────────────────────────────
def test_compaction_config_defaults_and_validation():
    assert cp.compaction_config(None) == cp.CompactionConfig(True, None, 128_000)
    cfg = cp.compaction_config({"enabled": False, "triggerRatio": 0.5, "defaultWindow": 64_000})
    assert cfg.enabled is False
    assert cfg.trigger_ratio == 0.5
    assert cfg.default_window == 64_000
    # 非法值回退默认（比例必须在 (0,1)）
    bad = cp.compaction_config({"triggerRatio": 1.5, "defaultWindow": -1, "enabled": "yes"})
    assert bad == cp.CompactionConfig(True, None, 128_000)


def test_context_window_for_user_override_and_learned_limit():
    cp.reset_learned()
    models = {
        "providers": [
            {
                "id": "p1",
                "adapter": "anthropic",
                "models": [{"id": "claude-sonnet-5-5", "contextWindow": 100_000}],
            }
        ]
    }
    assert cp.context_window_for(MODEL, models) == 100_000

    # 学习到的上限只在更小时生效
    assert cp.remember_context_limit(MODEL, 64_000, models) is True
    assert cp.context_window_for(MODEL, models) == 64_000
    assert cp.remember_context_limit(MODEL, 80_000, models) is False
    assert cp.context_window_for(MODEL, models) == 64_000  # 取小，不放大
    cp.reset_learned()
    assert cp.context_window_for(MODEL, models) == 100_000


def test_remember_output_budget_affects_trigger():
    cp.reset_learned()
    # OpenAI Chat 协议的「自动」输出上限是 None → 学到的预算才生效。
    # 未知时预留 OUTPUT_RESERVE_UNKNOWN(20K)；学到更大的预算（服务商实际预留更多）会把触发线拉低。
    base = cp.trigger_tokens_for(OPENAI_MODEL, OPENAI_MODELS)
    cp.remember_output_budget(OPENAI_MODEL, 64_000)
    assert cp.learned_output_budget(OPENAI_MODEL) == 64_000
    assert cp.trigger_tokens_for(OPENAI_MODEL, OPENAI_MODELS) < base
    cp.reset_learned()


def test_estimate_tokens_counts_parts():
    messages = [
        user("abcd"),
        Message(role="assistant", content=[TextPart(text="你好"), ToolUsePart(id="c1", name="read_file", input={"path": "a"})]),
        Message(role="user", content=[ToolResultPart(toolUseId="c1", content="内容", isError=False)]),
    ]
    total = cp.estimate_tokens(messages)
    assert total > 0
    # 文本 + 工具调用 + 工具结果三部分都要算进去
    assert total >= 4 + 2 + 4 + 2 + 8 + 4


def test_needs_compaction_uses_real_usage_first():
    cp.reset_learned()
    session = session_with(long_turn("一"))
    # 真实读数极小 → 不压（字符估算说该压，但真实 usage 优先）
    session.lastInputTokens = 10
    assert cp.needs_compaction(session, MODEL, MODELS) is False
    session.lastInputTokens = 20_000
    assert cp.needs_compaction(session, MODEL, MODELS) is True
    # 关掉压缩后一律为 False
    assert cp.needs_compaction(session, MODEL, MODELS, cp.CompactionConfig(enabled=False)) is False


def test_needs_compaction_mid_turn_adds_new_messages():
    cp.reset_learned()
    messages = long_turn("一")
    trigger = cp.trigger_tokens_for(MODEL, MODELS)
    # 读数刚好在触发线下方，但之后又追加了一大段工具结果
    last_at = len(messages)
    messages = messages + [user("结" * 4_000)]
    assert (
        cp.needs_compaction_mid_turn(messages, MODEL, trigger - 100, last_at, MODELS)
        is True
    )
    # 没有读数时回退模型视图估算
    small = [user("hi")]
    assert cp.needs_compaction_mid_turn(small, MODEL, 0, 0, MODELS) is False


def test_compaction_worth_retry_needs_twice_keep():
    cp.reset_learned()
    keep = cp.keep_tokens_for(cp.context_window_for(MODEL, MODELS))
    assert cp.compaction_worth_retry([], MODEL, keep * 2, 0, MODELS) is True
    assert cp.compaction_worth_retry([], MODEL, keep, 0, MODELS) is False


# ── 边界 ──────────────────────────────────────────────────────────────────────
def test_pick_boundary_returns_minus_one_on_short_history():
    assert cp.pick_boundary([user("a"), assistant("b")], 10) == -1


def test_pick_boundary_snaps_to_genuine_user_turn():
    messages = []
    for index in range(6):
        messages += long_turn(f"第{index}轮", 300)
    boundary = cp.pick_boundary(messages, 500)
    assert boundary >= cp.MIN_COMPACT_MESSAGES
    assert messages[boundary].role == "user"
    assert isinstance(messages[boundary].content, str)
    # 保留部分从真实用户轮起
    assert boundary % 2 == 0


def test_pick_boundary_skips_tool_result_turns():
    """工具结果回灌的 user 消息不是轮起点，不能在那里切。"""
    messages = [
        user("问一" + "问" * 400),
        Message(role="assistant", content=[ToolUsePart(id="c1", name="read_file", input={})]),
        Message(role="user", content=[ToolResultPart(toolUseId="c1", content="结" * 2_000)]),
        assistant("答一"),
        user("问二"),
        assistant("答二"),
    ]
    boundary = cp.pick_boundary(messages, 100)
    assert boundary == 4


def test_pick_in_turn_cut_requires_a_full_step():
    messages = [
        user("本轮请求"),
        Message(role="assistant", content=[ToolUsePart(id="c1", name="read_file", input={})]),
        Message(role="user", content=[ToolResultPart(toolUseId="c1", content="结" * 3_000)]),
        Message(role="assistant", content=[ToolUsePart(id="c2", name="read_file", input={})]),
        Message(role="user", content=[ToolResultPart(toolUseId="c2", content="结果" * 300)]),
    ]
    cut = cp.pick_in_turn_cut(messages, 0, 100)
    assert cut == 3  # 至少落在第二步（start+3）
    # 保留量大于本轮总量 → 不值得压
    assert cp.pick_in_turn_cut(messages, 0, 10_000_000) == -1


def test_pick_in_turn_cut_falls_back_to_last_step():
    """最后一条工具结果自己就超过保留量时，退到最后一步。"""
    messages = [
        user("请求"),
        Message(role="assistant", content=[ToolUsePart(id="c1", name="read_file", input={})]),
        Message(role="user", content=[ToolResultPart(toolUseId="c1", content="小结果")]),
        Message(role="assistant", content=[ToolUsePart(id="c2", name="read_file", input={})]),
        Message(role="user", content=[ToolResultPart(toolUseId="c2", content="巨" * 50_000)]),
    ]
    assert cp.pick_in_turn_cut(messages, 0, 1_000) == 3


# ── 转录 ──────────────────────────────────────────────────────────────────────
def test_build_transcript_flattens_parts():
    messages = [
        user("普通提问"),
        Message(
            role="assistant",
            content=[
                TextPart(text="我先看看"),
                ToolUsePart(id="c1", name="read_file", input={"path": "a.txt"}),
            ],
        ),
        Message(role="user", content=[ToolResultPart(toolUseId="c1", content="文件内容", isError=True)]),
    ]
    text = cp.build_transcript(messages, "zh-CN")
    assert "用户: 普通提问" in text
    assert "助手: 我先看看" in text
    assert "调用工具 read_file" in text
    assert '{"path": "a.txt"}' in text
    assert "[工具结果·错误]: 文件内容" in text


def test_build_transcript_skips_listing_and_auto_nudge():
    messages = [
        Message(role="user", content=[TextPart(text="清单块", listing={"kind": "skill"})]),
        user("⟦deva:auto⟧自愈引导"),
        user("真实提问"),
    ]
    text = cp.build_transcript(messages, "zh-CN")
    assert "清单块" not in text
    assert "自愈引导" not in text
    assert "真实提问" in text


def test_build_transcript_keeps_insert_as_user():
    inserted = f"⟦deva:insert⟧（说明行）\n补充要求"
    text = cp.build_transcript([Message(role="user", content=[TextPart(text=inserted)])], "zh-CN")
    assert "用户: 补充要求" in text
    assert "说明行" not in text


def test_build_transcript_renders_notification_and_clips():
    notice = user("⟦deva:notify⟧后台任务完成")
    text = cp.build_transcript([notice], "zh-CN")
    assert "[系统通知]: 后台任务完成" in text

    long_result = Message(role="user", content=[ToolResultPart(toolUseId="c1", content="x" * 5_000)])
    clipped = cp.build_transcript([long_result], "zh-CN")
    assert len(clipped) < 2_100
    assert clipped.endswith("…")


def test_build_transcript_truncates_head_with_note():
    messages = [user("甲" * 60_000), user("乙")]
    text = cp.build_transcript(messages, "zh-CN", max_chars=100)
    assert text.startswith("…（更早内容已省略）")
    assert text.endswith("乙")


def test_transcript_budget_scales_with_window():
    assert cp.transcript_budget(1_000) == cp.MIN_TRANSCRIPT_CHARS
    assert cp.transcript_budget(1_000_000) > cp.MIN_TRANSCRIPT_CHARS


# ── 摘要请求 ──────────────────────────────────────────────────────────────────
def test_summarize_returns_body_on_clean_finish():
    provider = ScriptedProvider(text="摘要正文")
    factory = factory_for(provider)
    result = asyncio.run(
        cp.summarize(MODEL, "转录", lambda cancel: provider, cancel=CancelToken(), session_id="s1")
    )
    assert result == "摘要正文"
    request = provider.requests[0]
    assert request.max_tokens == cp.SUMMARY_MAX_TOKENS
    assert request.session_id == "s1"
    assert request.temperature is None
    assert "对话压缩器" in request.system


def test_summarize_retries_on_retryable_error():
    bad = ScriptedProvider(
        [StreamError(NormalizedError("server", "服务器错误", True)), Done("error")]
    )
    good = ScriptedProvider(text="第二次成功")
    attempts: list[ScriptedProvider] = [bad, good]
    made = []

    def factory(cancel):
        made.append(cancel)
        return attempts[min(len(made) - 1, len(attempts) - 1)]

    result = asyncio.run(
        cp.summarize(MODEL, "转录", factory, cancel=CancelToken(), sleep=lambda s: None)
    )
    assert result == "第二次成功"
    assert len(made) == 2


def test_summarize_gives_up_after_max_retries():
    bad = ScriptedProvider([StreamError(NormalizedError("server", "服务器错误", True)), Done("error")])
    sleeps: list[float] = []
    with pytest.raises(cp.SummaryError) as excinfo:
        asyncio.run(
            cp.summarize(MODEL, "转录", lambda cancel: bad, cancel=CancelToken(), sleep=sleeps.append)
        )
    assert "已重试 3 次" in str(excinfo.value)
    assert sleeps == [1.0, 2.0, 4.0]  # 指数退避，封顶 8s


def test_summarize_raises_immediately_on_fatal_error():
    bad = ScriptedProvider([StreamError(NormalizedError("auth", "密钥无效", False, 401)), Done("error")])
    with pytest.raises(cp.SummaryError) as excinfo:
        asyncio.run(cp.summarize(MODEL, "转录", lambda cancel: bad, cancel=CancelToken(), sleep=lambda s: None))
    assert "密钥无效" in str(excinfo.value)


def test_summarize_rejects_empty_body():
    provider = ScriptedProvider(text="")
    with pytest.raises(cp.SummaryError) as excinfo:
        asyncio.run(cp.summarize(MODEL, "转录", lambda cancel: provider, cancel=CancelToken()))
    assert "没有返回摘要正文" in str(excinfo.value)


def test_summarize_treats_interrupted_stream_as_failure():
    """done 的 stop_reason 是 error/aborted：手里的正文必定残缺，不可采信。"""
    provider = ScriptedProvider([TextDelta("半截摘"), Done("aborted")])
    with pytest.raises(cp.SummaryError) as excinfo:
        asyncio.run(
            cp.summarize(MODEL, "转录", lambda cancel: provider, cancel=CancelToken(), sleep=lambda s: None)
        )
    assert "连接中断" in str(excinfo.value)


def test_summarize_aborts_when_cancelled():
    cancel = CancelToken()
    cancel.cancel()
    provider = ScriptedProvider(text="不该被调用")
    with pytest.raises(cp.SummaryAborted):
        asyncio.run(cp.summarize(MODEL, "转录", lambda c: provider, cancel=cancel))
    assert provider.requests == []


def test_summarize_times_out_and_retries():
    async def slow_stream(request):
        await asyncio.sleep(1)
        yield TextDelta("迟到的摘要")

    class Slow(Provider):
        name = "slow"

        def __init__(self):
            self.requests = []

        async def stream(self, request):
            self.requests.append(request)
            async for event in slow_stream(request):
                yield event

    provider = Slow()
    with pytest.raises(cp.SummaryError) as excinfo:
        asyncio.run(
            cp.summarize(
                MODEL, "转录", lambda cancel: provider, cancel=CancelToken(), timeout_ms=10, sleep=lambda s: None
            )
        )
    assert "仍未完成" in str(excinfo.value)
    assert len(provider.requests) == cp.SUMMARY_MAX_RETRY + 1


def test_summarize_mid_turn_hint_and_english_system():
    provider = ScriptedProvider(text="summary")
    asyncio.run(
        cp.summarize(MODEL, "t", lambda cancel: provider, locale="en", mid_turn=True)
    )
    request = provider.requests[0]
    assert "conversation compactor" in request.system
    assert "still being worked on" in request.messages[0].content


# ── 压缩主流程 ────────────────────────────────────────────────────────────────
def _long_session() -> StoredSession:
    """8 轮、每轮约 1400 token（总量约 11K），压缩线 8000、保留量 6000：
    边界会落在中间某轮的真实用户消息上，可压段足够长。"""
    messages: list[Message] = []
    for index in range(8):
        messages += long_turn(f"第{index}轮", 2_400)
    return session_with(messages)


def test_compact_session_inserts_summary_without_deleting():
    cp.reset_learned()
    session = _long_session()
    original = list(session.messages)
    provider = ScriptedProvider(text="要点一；要点二")
    saved: list[str] = []
    started: list[bool] = []

    result = asyncio.run(
        cp.compact_session(
            session,
            MODEL,
            lambda cancel: provider,
            cancel=CancelToken(),
            models_section=MODELS,
            save=saved.append,
            on_start=lambda: started.append(True),
        )
    )

    assert result.status == "compacted"
    assert started == [True]
    assert saved == ["s1"]
    # 一条不删：只多一条
    assert len(session.messages) == len(original) + 1
    inserted = [m for m in session.messages if m.role == "user" and str(m.content).startswith(COMPACT_MARKER)]
    assert len(inserted) == 1
    assert "要点一；要点二" in str(inserted[0].content)
    assert "以下是此前对话的摘要" in str(inserted[0].content)
    # 原消息顺序不变（去掉插入的那条后完全一致）
    remaining = [m for m in session.messages if m is not inserted[0]]
    assert remaining == original
    assert session.lastInputTokens is None


def test_compact_session_returns_none_when_nothing_to_compact():
    session = session_with([user("hi"), assistant("hello")])
    provider = ScriptedProvider(text="不该调用")
    result = asyncio.run(
        cp.compact_session(session, MODEL, lambda cancel: provider, models_section=MODELS)
    )
    assert result.status == "none"
    assert provider.requests == []


def test_compact_session_shifts_notices_after_insert_point():
    cp.reset_learned()
    session = _long_session()
    session.notices = [
        StoredNotice(after=0, kind="notice", code="a"),
        StoredNotice(after=10_000, kind="notice", code="b"),
    ]
    provider = ScriptedProvider(text="摘要")
    asyncio.run(
        cp.compact_session(session, MODEL, lambda cancel: provider, models_section=MODELS)
    )
    # 找到插入点：摘要消息的下标
    at = next(i for i, m in enumerate(session.messages) if str(m.content).startswith(COMPACT_MARKER))
    assert [n.after for n in session.notices] == [0, 10_001]  # 只有 after > at 的后移


def test_compact_session_failure_leaves_history_untouched():
    session = _long_session()
    original = list(session.messages)
    original_updated = session.updatedAt
    provider = ScriptedProvider([StreamError(NormalizedError("auth", "密钥无效", False, 401)), Done("error")])
    saved: list[str] = []

    result = asyncio.run(
        cp.compact_session(session, MODEL, lambda cancel: provider, models_section=MODELS, save=saved.append)
    )
    assert result.status == "failed"
    assert "密钥无效" in result.message
    assert session.messages == original
    assert session.updatedAt == original_updated
    assert saved == []


def test_compact_session_rejects_repetitive_summary():
    session = _long_session()
    original = list(session.messages)
    provider = ScriptedProvider(text="同一段话。" * 200)
    result = asyncio.run(
        cp.compact_session(session, MODEL, lambda cancel: provider, models_section=MODELS)
    )
    assert result.status == "failed"
    assert "重复" in result.message
    assert session.messages == original


def test_compact_session_rejects_summary_not_shorter():
    """摘要写得比被压段还长：白白丢细节，放弃这次结果。"""
    session = _long_session()
    original = list(session.messages)
    # 内容各不相同，免得先被复读检测拦下；总量要超过被压段的估算
    provider = ScriptedProvider(text="".join(f"{i}段无重复的摘要内容。" for i in range(6_000)))
    result = asyncio.run(
        cp.compact_session(session, MODEL, lambda cancel: provider, models_section=MODELS)
    )
    assert result.status == "failed"
    assert "不比被压缩的内容短" in result.message
    assert session.messages == original


def test_compact_session_mid_turn_keeps_current_request():
    """轮中压缩：此前轮次太小、本轮自身装不下 → 在本轮内部切，摘要插在本轮中间。

    模型此后看到 [本轮请求, 摘要, ...近期步骤]；记录里一条不删，请求原文仍在原位置。
    """
    cp.reset_learned()
    messages: list[Message] = []
    # 此前只有 3 小轮：总量不到保留量，pick_boundary 找不到边界 → 走轮内切
    for index in range(3):
        messages += long_turn(f"第{index}轮", 100)
    request_at = len(messages)
    messages.append(user("本轮请求"))
    for step in range(12):
        messages.append(Message(role="assistant", content=[ToolUsePart(id=f"c{step}", name="read_file", input={})]))
        messages.append(Message(role="user", content=[ToolResultPart(toolUseId=f"c{step}", content="结" * 900)]))
    session = session_with(messages)
    provider = ScriptedProvider(text="本轮已完成步骤摘要")

    result = asyncio.run(
        cp.compact_session(session, MODEL, lambda cancel: provider, models_section=MODELS, mid_turn=True)
    )
    assert result.status == "compacted"
    at = next(i for i, m in enumerate(session.messages) if str(m.content).startswith(COMPACT_MARKER))
    # 请求原文原地不动，摘要插在它后面的某步工具结果之后
    assert session.messages[request_at].content == "本轮请求"
    assert request_at < at
    assert "本轮任务已完成部分" in str(session.messages[at].content)
    # 摘要后的第一条是带工具调用的助手消息（tool_use 与结果配对不被切开）
    assert isinstance(session.messages[at + 1].content, list)
    assert any(isinstance(p, ToolUsePart) for p in session.messages[at + 1].content)
    # 发给模型的视图：本轮请求在最前，其后是摘要与近期步骤
    view = model_messages(session.messages)
    assert view[0].content == "本轮请求"
    assert str(view[1].content).startswith(COMPACT_MARKER)


def test_compact_session_appends_todo_snapshot():
    cp.reset_learned()
    session = _long_session()
    session.todos = [
        {
            "id": "c1",
            "listId": "l1",
            "at": 1,
            "title": "计划",
            "items": [{"content": "甲", "status": "in_progress"}],
        }
    ]
    provider = ScriptedProvider(text="摘要")
    result = asyncio.run(
        cp.compact_session(session, MODEL, lambda cancel: provider, models_section=MODELS)
    )
    assert result.status == "compacted"
    inserted = next(m for m in session.messages if str(m.content).startswith(COMPACT_MARKER))
    assert "当前待办清单：计划" in str(inserted.content)
    assert "- [~] 甲" in str(inserted.content)


def test_compact_session_english_locale():
    cp.reset_learned()
    session = _long_session()
    provider = ScriptedProvider(text="Summary body")
    result = asyncio.run(
        cp.compact_session(
            session, MODEL, lambda cancel: provider, models_section=MODELS, locale="en"
        )
    )
    assert result.status == "compacted"
    inserted = next(m for m in session.messages if str(m.content).startswith(COMPACT_MARKER))
    assert "summary of the earlier conversation" in str(inserted.content)


def test_compact_session_disabled_config_returns_none():
    """enabled=False 时由调用方判断；compact_session 本身不读 enabled（与 Deva 一致）。"""
    session = _long_session()
    provider = ScriptedProvider(text="摘要")
    result = asyncio.run(
        cp.compact_session(
            session,
            MODEL,
            lambda cancel: provider,
            models_section=MODELS,
            cfg=cp.CompactionConfig(enabled=False),
        )
    )
    assert result.status == "compacted"  # 调用方（needs_compaction）负责按 enabled 拦住


def test_display_summary_strips_header():
    content = f"{COMPACT_MARKER}\n以下是此前对话的摘要（说明）。\n\n摘要正文\n\n【当前待办清单】"
    assert cp.display_summary(content).startswith("摘要正文")
    assert cp.display_summary("普通文本") == "普通文本"
