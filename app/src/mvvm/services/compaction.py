"""上下文压缩：把较早的对话写成摘要，此后模型只看「摘要 + 近期原文」。

逐条对齐 Deva `apps/desktop/src/main/services/compaction.ts`。设计要点（与 Deva 一致）：

- **对话记录不删任何消息**：压缩只在边界插入一条带标记的摘要消息，界面照常显示完整记录；
  发给模型的内容由 `model_messages` 从记录里截取；
- 触发优先用上一轮真实 `usage.input`（持久化在会话上，最准，天然覆盖图片/工具）；
  无则回退字符估算；
- 边界吸附到真实用户轮，绝不切开 assistant(tool_use) ↔ user(tool_result)，且必留本轮问题；
- 摘要失败绝不改动历史（宁可不压，也不破坏真源）。

本模块不认识 Qt。配置（`compaction` 段、`models` 段）与落盘钩子都由调用方传进来，
便于离线测试；进程内「学到的」窗口/输出预算和 Deva 一样是模块级缓存（不落盘）。

与 Deva 的两处差异，均因尚未移植对应子系统，不是行为选择：

1. 转录前不套 `stubLongInforms`（定时任务交接的占位），本工程还没有任务交接消息；
2. 压缩触发后的「通知」由调用方（聊天视图模型）负责，这里只返回结果。
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, Sequence

from mvvm.models.chat_models import (
    DocumentPart,
    ImagePart,
    Message,
    StoredSession,
    TextPart,
    ToolResultPart,
    ToolUsePart,
    now_ms,
)
from mvvm.services.context_window import (
    CHARS_PER_TOKEN,
    COMPACT_BUFFER,
    DEFAULT_CONTEXT_WINDOW,
    DOC_TOKENS,
    IMAGE_TOKENS,
    KEEP_RATIO,
    KEEP_TOKENS_MAX,
    KEEP_TOKENS_MIN,
    OUTPUT_RESERVE_UNKNOWN,
    auto_context_window,
    auto_output_budget,
    estimate_text_tokens,
)
from mvvm.services.model_resolve import model_overrides
from mvvm.services.model_view import (
    COMPACT_MARKER,
    insert_body,
    is_auto_nudge,
    is_genuine_user_turn,
    is_task_notification,
    last_turn_start,
    model_messages,
    model_range,
)
from mvvm.services.provider_gateway import (
    Done,
    GenerateRequest,
    Provider,
    StreamError,
    TextDelta,
)
from mvvm.services.repetition import find_repetition
from mvvm.services.todos import todo_snapshot_text
from mvvm.services.transport import CancelToken

# ── 配置 ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CompactModel:
    """压缩请求要用的模型配置（与 Deva `CompactModelConfig` 同字段）。"""

    adapter: str
    provider_id: str
    base_url: str
    model: str


@dataclass(frozen=True)
class CompactionConfig:
    enabled: bool = True
    """手动指定的触发比例（窗口的几成）；None = 按窗口与输出上限算（见 trigger_tokens）。"""
    trigger_ratio: Optional[float] = None
    default_window: int = DEFAULT_CONTEXT_WINDOW


DEFAULTS = CompactionConfig()


def compaction_config(section: Any = None) -> CompactionConfig:
    """从 config.json 的 `compaction` 段读配置（明文可手改即设置面），非法值回退默认。"""
    raw: Mapping[str, Any] = section if isinstance(section, Mapping) else {}
    enabled = raw.get("enabled")
    ratio = raw.get("trigger_ratio", raw.get("triggerRatio"))
    window = raw.get("default_window", raw.get("defaultWindow"))
    return CompactionConfig(
        enabled=enabled if isinstance(enabled, bool) else DEFAULTS.enabled,
        trigger_ratio=(
            float(ratio)
            if isinstance(ratio, (int, float)) and not isinstance(ratio, bool) and 0 < ratio < 1
            else None
        ),
        default_window=(
            int(window)
            if isinstance(window, (int, float))
            and not isinstance(window, bool)
            and window > 0
            else DEFAULTS.default_window
        ),
    )


# 进程内记住的真实窗口（键 `providerId:model`）：服务商报「上下文超限」时从报错里解析出的
# 上限。只在比配置 / 内置值小时生效——中转常把上游窗口开小，记住它，后续压缩就按真实上限来，
# 不必每轮先撞一次超限。不落盘：换了中转或上游扩窗，重启即复原。
_learned_windows: dict[str, int] = {}
# 进程内记住的输出预算（键同上）：本不传 max_tokens 的模型（OpenAI Chat 协议的「自动」），
# 服务商按模型最大输出预留、输入 + 预留超窗被拒时改为显式发送的预算。不落盘。
_learned_outputs: dict[str, int] = {}


def _model_key(model: CompactModel) -> str:
    return f"{model.provider_id}:{model.model}"


def reset_learned() -> None:
    """清空进程内学到的窗口 / 输出预算（测试用；生产不调用）。"""
    _learned_windows.clear()
    _learned_outputs.clear()


def context_window_for(
    model: CompactModel,
    models_section: Any = None,
    cfg: CompactionConfig = DEFAULTS,
) -> int:
    """某模型生效的窗口：用户填写 > 自动（ID 自带 > 内置表 > 全局默认），再与学到的上限取小。"""
    overrides = model_overrides(model.provider_id, model.model, models_section or {})
    configured = (
        overrides.context_window
        if overrides.context_window is not None
        else auto_context_window(model.model, cfg.default_window)
    )
    learned = _learned_windows.get(_model_key(model))
    return min(configured, learned) if learned else configured


def remember_context_limit(
    model: CompactModel,
    limit: int,
    models_section: Any = None,
    cfg: CompactionConfig = DEFAULTS,
) -> bool:
    """记下报错里解析出的真实窗口；比当前生效值小（即确实改变了判定）时返回 True。"""
    before = context_window_for(model, models_section, cfg)
    key = _model_key(model)
    _learned_windows[key] = min(limit, _learned_windows.get(key, limit))
    return limit < before


def remember_output_budget(model: CompactModel, budget: int) -> None:
    _learned_outputs[_model_key(model)] = budget


def learned_output_budget(model: CompactModel) -> Optional[int]:
    return _learned_outputs.get(_model_key(model))


def _output_budget(
    model: CompactModel, models_section: Any = None
) -> int:
    overrides = model_overrides(model.provider_id, model.model, models_section or {})
    return (
        overrides.max_output
        if overrides.max_output is not None
        else auto_output_budget(model.adapter, model.model)
        or learned_output_budget(model)
        or OUTPUT_RESERVE_UNKNOWN
    )


def trigger_tokens_for(
    model: CompactModel,
    models_section: Any = None,
    cfg: CompactionConfig = DEFAULTS,
) -> int:
    """触发压缩的输入量：窗口 − 输出上限 − 余量（Deva `triggerTokens`）。

    输出上限必须扣：Anthropic 等要求「输入 + max_tokens」不超窗口；它封顶半个窗口，
    防填错值时每轮都压。用户写了 `triggerRatio` 时取两者中更早的那个。
    """
    window = context_window_for(model, models_section, cfg)
    output = _output_budget(model, models_section)
    by_window = window - min(output, window // 2) - min(COMPACT_BUFFER, window * 0.1)
    if cfg.trigger_ratio is not None:
        return int(min(window * cfg.trigger_ratio, by_window))
    return int(by_window)


def keep_tokens_for(window: int) -> int:
    """压缩后保留尾部的目标 token 数：窗口的 30%，夹在 [2000, 40000]。

    大窗口按比例算压完仍留几十万 token，上下文降不下来，故封顶。
    """
    return min(KEEP_TOKENS_MAX, max(KEEP_TOKENS_MIN, round(window * KEEP_RATIO)))


# ── token 估算（字符法，中日韩文字另计；图片/文档按固定成本）──────────────────


def _part_tokens(part: Any) -> float:
    if isinstance(part, TextPart):
        return estimate_text_tokens(part.text)
    if isinstance(part, ToolUsePart):
        return estimate_text_tokens(json.dumps(part.input if part.input is not None else {}, ensure_ascii=False)) + 8
    if isinstance(part, ToolResultPart):
        images = len(part.images or ())
        return estimate_text_tokens(part.content) + 8 + images * IMAGE_TOKENS
    if isinstance(part, ImagePart):
        return IMAGE_TOKENS
    if isinstance(part, DocumentPart):
        return DOC_TOKENS
    return 0


def _message_tokens(message: Message) -> float:
    if isinstance(message.content, str):
        return estimate_text_tokens(message.content) + 4
    total = 4.0
    for part in message.content:
        total += _part_tokens(part)
    return total


def estimate_tokens(messages: Sequence[Message]) -> int:
    """全历史 token 估算（触发判定的字符法回退）。"""
    return round(sum(_message_tokens(m) for m in messages))


def used_tokens_mid_turn(messages: Sequence[Message], last_input: int, last_input_at: int) -> int:
    """一轮进行中的上下文用量：最近一次真实读数 + 其后新增消息的估算。

    只看上一步读数会低估——工具结果常常很大（读了一个大文件），它们不在那次读数里、
    却要随下一步整个发出去。没有读数时估算模型视图。
    """
    if last_input > 0:
        return last_input + estimate_tokens(list(messages)[last_input_at:])
    return estimate_tokens(model_messages(messages))


def needs_compaction(
    session: StoredSession,
    model: CompactModel,
    models_section: Any = None,
    cfg: CompactionConfig = DEFAULTS,
) -> bool:
    """是否需要压缩：优先真实 usage.input，回退字符估算（只算模型看到的部分）。"""
    if not cfg.enabled:
        return False
    last_input = session.lastInputTokens or 0
    used = (
        last_input
        if last_input > 0
        else estimate_tokens(model_messages(session.messages))
    )
    return used >= trigger_tokens_for(model, models_section, cfg)


def needs_compaction_mid_turn(
    messages: Sequence[Message],
    model: CompactModel,
    last_input: int,
    last_input_at: int,
    models_section: Any = None,
    cfg: CompactionConfig = DEFAULTS,
) -> bool:
    """一轮进行中（Agent 循环两步之间）是否已接近窗口。"""
    if not cfg.enabled:
        return False
    return (
        used_tokens_mid_turn(messages, last_input, last_input_at)
        >= trigger_tokens_for(model, models_section, cfg)
    )


def compaction_worth_retry(
    messages: Sequence[Message],
    model: CompactModel,
    last_input: int,
    last_input_at: int,
    models_section: Any = None,
    cfg: CompactionConfig = DEFAULTS,
) -> bool:
    """模型输出复读后，先压缩再重试是否值得：用量至少是压缩后保留量的两倍。

    长上下文是模型退化的常见诱因，压短了再试才有意义；上下文本就不长时复读多是采样偶发，
    压缩只会白丢细节，直接重试即可。
    """
    if not cfg.enabled:
        return False
    keep = keep_tokens_for(context_window_for(model, models_section, cfg))
    return used_tokens_mid_turn(messages, last_input, last_input_at) >= 2 * keep


# ── 边界选取 ──────────────────────────────────────────────────────────────────


def _has_tool_use(message: Message) -> bool:
    return (
        message.role == "assistant"
        and not isinstance(message.content, str)
        and any(isinstance(part, ToolUsePart) for part in message.content)
    )


def _model_view(messages: Sequence[Message]) -> tuple[list[Message], Callable[[int], int]]:
    """模型视图 + 视图下标到记录下标的换算（在视图上选边界，再把摘要插回记录）。"""
    head, start = model_range(messages)
    view = model_messages(messages)
    offset = 1 if head >= 0 else 0

    def to_record(index: int) -> int:
        return head if index < offset else start + index - offset

    return view, to_record


MIN_COMPACT_MESSAGES = 4


def pick_boundary(messages: Sequence[Message], keep_tokens: int) -> int:
    """选定保留尾部的起点下标：从末尾向前累加 token 至 keep_tokens，再吸附到真实用户轮。

    返回 boundary：`[0, boundary)` 待压缩、`[boundary, end)` 保留。压缩收益不足时返回 -1。
    """
    n = len(messages)
    if n < MIN_COMPACT_MESSAGES + 2:
        return -1

    acc = 0.0
    idx = n
    for i in range(n - 1, -1, -1):
        acc += _message_tokens(messages[i])
        if acc >= keep_tokens:
            idx = i
            break
    if idx == n:
        return -1  # 历史本就不大，累加从未达标 → 不压

    # 吸附：从 idx 向后找第一条真实用户轮作为尾部起点（保证尾部以真实用户轮开头）
    boundary = -1
    for i in range(idx, n):
        if is_genuine_user_turn(messages[i]):
            boundary = i
            break
    if boundary < MIN_COMPACT_MESSAGES:
        return -1  # 无合适边界，或可压段过短，不值得
    return boundary


def pick_in_turn_cut(messages: Sequence[Message], start: int, keep_tokens: int) -> int:
    """轮内切点（仅轮中压缩用）：本轮自身已大到 pick_boundary 找不到边界时，在本轮内部切。

    从末尾累加到 keep_tokens，再吸附到一条带工具调用的助手消息——以它起头的尾部，
    其每个 tool_use 的结果都在尾部内，配对不会被切开。返回 cut；至少压掉一整步才值得，否则 -1。
    """
    n = len(messages)
    acc = 0.0
    idx = -1
    for i in range(n - 1, start, -1):
        acc += _message_tokens(messages[i])
        if acc >= keep_tokens:
            idx = i
            break
    if idx < 0:
        return -1  # 本轮到目前为止也不大：该压的是此前的轮，那是 pick_boundary 的事

    cut = -1
    for i in range(idx, n):
        if _has_tool_use(messages[i]):
            cut = i
            break
    # 最后一条工具结果自己就超过保留量（比如刚读了个大文件）：退到最后一步，尾部只留这一步。
    if cut < 0:
        for i in range(idx - 1, start, -1):
            if _has_tool_use(messages[i]):
                cut = i
                break
    # start 是用户请求，start+1 / start+2 是第一步的助手消息与工具结果：cut 至少落在第二步上。
    return cut if cut >= start + 3 else -1


# ── 转录与摘要 ────────────────────────────────────────────────────────────────

# 转录总量上限：窗口的 1/4（摘要请求与主对话同一个模型，装得下），不低于 48K 字符。
# 写死 48K 时，1M 窗口下待压段动辄几十万 token，摘要模型却只看得到最后一万多 token，前面全丢。
MIN_TRANSCRIPT_CHARS = 48_000
TRANSCRIPT_WINDOW_RATIO = 0.25
MAX_TOOL_RESULT_CHARS = 2_000
MAX_TOOL_ARGS_CHARS = 400


def transcript_budget(window: int) -> int:
    return max(MIN_TRANSCRIPT_CHARS, round(window * TRANSCRIPT_WINDOW_RATIO * CHARS_PER_TOKEN))


def build_transcript(
    messages: Sequence[Message],
    locale: str = "zh-CN",
    max_chars: int = MIN_TRANSCRIPT_CHARS,
) -> str:
    """把待压段拍平成纯文本转录（丢 base64、截断超长工具结果、总量头部截断保留较近）。"""
    zh = locale != "en"
    user_label = "用户" if zh else "User"
    assistant_label = "助手" if zh else "Assistant"
    lines: list[str] = []

    def clip(text: str, maximum: int) -> str:
        return text[:maximum] + "…" if len(text) > maximum else text

    for message in messages:
        if is_auto_nudge(message):
            continue
        if is_task_notification(message) and isinstance(message.content, str):
            from mvvm.services.model_view import NOTIFY_MARKER

            lines.append(
                f"[{'系统通知' if zh else 'system notice'}]: {message.content[len(NOTIFY_MARKER):]}"
            )
            continue
        label = user_label if message.role == "user" else assistant_label
        if isinstance(message.content, str):
            if message.content.strip():
                lines.append(f"{label}: {message.content}")
            continue
        for part in message.content:
            if isinstance(part, TextPart):
                # 清单块（技能 / 记忆）不进转录：它不是对话内容，被摘要掉后引擎会按需重新附上。
                if part.listing is not None:
                    continue
                # 插入消息附在工具结果之后，却是用户说的话：去掉标记与说明行，记成用户发言。
                inserted = insert_body(part.text)
                if inserted is not None:
                    if inserted.strip():
                        lines.append(f"{user_label}: {inserted}")
                    continue
                if part.text.strip():
                    lines.append(f"{label}: {part.text}")
            elif isinstance(part, ToolUsePart):
                args = clip(json.dumps(part.input if part.input is not None else {}, ensure_ascii=False), MAX_TOOL_ARGS_CHARS)
                lines.append(f"{label} [{'调用工具' if zh else 'tool'} {part.name}]: {args}")
            elif isinstance(part, ToolResultPart):
                if zh:
                    tag = "工具结果·错误" if part.isError else "工具结果"
                else:
                    tag = "tool result·error" if part.isError else "tool result"
                lines.append(f"[{tag}]: {clip(part.content, MAX_TOOL_RESULT_CHARS)}")
            elif isinstance(part, ImagePart):
                lines.append(f"{label} [{'图片' if zh else 'image'}]")
            elif isinstance(part, DocumentPart):
                lines.append(f"{label} [{'文档' if zh else 'document'}]")

    text = "\n".join(lines)
    if len(text) > max_chars:
        omitted = "…（更早内容已省略）\n" if zh else "…(earlier content omitted)\n"
        text = omitted + text[len(text) - max_chars:]
    return text


# 单次摘要请求的总时长上限：只用来兜住「一直慢吞吞吐字却永不收尾」的跑飞流。真正的死连接
# 判定交给 SSE 层的空闲看门狗（STREAM_IDLE_MS：静默 60s 即判中断、可重试）。此处曾是 60s
# 总时长——长转录 + 慢模型（尤其先吐一大段思维链的推理模型）正常也跑不完。
SUMMARY_TIMEOUT_MS = 300_000
# 摘要输出预算。留足余量：推理模型的思维链同样吃这份预算，给太小会挤得吐不出正文。
SUMMARY_MAX_TOKENS = 4096
# 摘要请求的重试次数（与主循环 MAX_RECONNECT 同值）：摘要是一次性请求，断一次就前功尽弃。
SUMMARY_MAX_RETRY = 3

SUMMARY_SYSTEM_ZH = "\n".join(
    [
        "你是一个对话压缩器。请把以下开发者与 AI 助手的对话，压缩成一份简洁但信息完整的摘要，供后续对话继续参考。",
        "必须保留：",
        "1. 用户的核心目标与明确指令（尤其是尚未完成的要求）；",
        "2. 关键决定、结论与已达成的共识；",
        "3. 已完成的改动：涉及的文件、函数、命令及其结果；",
        "4. 尚未完成的任务与下一步计划；",
        "5. 重要的事实、约束、报错与踩过的坑。",
        "要求：用要点式罗列；代码片段、文件路径、命令、标识符一律保留原文；不要臆造未发生的内容；只输出摘要正文，不要客套或额外解释。",
    ]
)

SUMMARY_SYSTEM_EN = "\n".join(
    [
        "You are a conversation compactor. Compress the following developer–AI conversation into a concise but complete summary for the conversation to continue from.",
        "You must preserve:",
        "1. The user's core goals and explicit instructions (especially unfinished requests);",
        "2. Key decisions, conclusions, and agreements reached;",
        "3. Completed changes: files, functions, and commands involved and their results;",
        "4. Outstanding tasks and next steps;",
        "5. Important facts, constraints, errors, and pitfalls encountered.",
        "Rules: use bullet points; keep code snippets, file paths, commands, and identifiers verbatim; do not invent anything; output only the summary body, no pleasantries or extra explanation.",
    ]
)


class SummaryAborted(Exception):
    """摘要中止（用户按下停止）：与「摘要失败」区分开，调用方据此给不同结论。"""


class SummaryError(Exception):
    """摘要失败（鉴权、参数、无正文等致命错误的原文）。"""


@dataclass
class _Collected:
    text: str
    fatal: str
    retryable: str
    interrupted: bool


async def _collect(provider: Provider, request: GenerateRequest) -> _Collected:
    text: list[str] = []
    fatal = retryable = ""
    interrupted = False
    async for event in provider.stream(request):
        if isinstance(event, TextDelta):
            text.append(event.text)
        elif isinstance(event, StreamError):
            if event.error.retryable:
                retryable = event.error.message
            else:
                fatal = event.error.message
        elif isinstance(event, Done):
            if event.stop_reason in ("error", "aborted"):
                interrupted = True
    return _Collected("".join(text), fatal, retryable, interrupted)


async def _watch_cancel(outer: Optional[CancelToken], inner: CancelToken) -> None:
    if outer is None:
        await asyncio.Event().wait()  # 永不返回，由调用方取消
        return
    await outer.wait()
    inner.cancel()


async def summarize(
    model: CompactModel,
    transcript: str,
    provider_factory: Callable[[CancelToken], Provider],
    locale: str = "zh-CN",
    cancel: Optional[CancelToken] = None,
    mid_turn: bool = False,
    session_id: str = "",
    timeout_ms: int = SUMMARY_TIMEOUT_MS,
    sleep: Optional[Callable[[float], Any]] = None,
) -> str:
    """请模型产出摘要。**只接受「干净收尾且有正文」的结果**。

    半截摘要一旦被采信就会顶替掉真实历史，且不可逆，故宁可整轮不压也不要残缺摘要。
    断流 / 限流 / 超时按可重试处理（指数退避，至多 `SUMMARY_MAX_RETRY` 次）；
    鉴权、参数等致命错误立即抛出——重试无益，把原文抛给用户看才有用。

    `provider_factory` 每次尝试都用一个新的 `CancelToken` 构造适配器：超时或用户中止时
    能从传输层真正掐断请求，而不是让它继续跑。`timeout_ms` / `sleep` 仅用于离线测试缩短等待。
    """
    zh = locale != "en"
    system = SUMMARY_SYSTEM_ZH if zh else SUMMARY_SYSTEM_EN
    if mid_turn:
        hint = (
            "注意：记录里最后一条用户请求仍在执行中。请重点保留围绕它已经完成的步骤、查到的关键信息、改过的文件与下一步要做什么。\n\n"
            if zh
            else "Note: the last user request in this transcript is still being worked on. Focus on the steps already completed for it, key findings, files changed, and what to do next.\n\n"
        )
    else:
        hint = ""
    user_text = (
        f"{hint}以下是需要压缩的对话记录，请据此产出摘要：\n\n{transcript}"
        if zh
        else f"{hint}Here is the conversation to compact. Produce the summary accordingly:\n\n{transcript}"
    )

    async def backoff(seconds: float) -> None:
        if sleep is not None:
            result = sleep(seconds)
            if asyncio.iscoroutine(result):
                await result
            return
        if cancel is not None:
            # 取消或超时都继续往下走：循环开头会先看是否已中止。
            await cancel.wait_timeout(seconds)
            return
        await asyncio.sleep(seconds)

    last_reason = "摘要请求未能完成"

    for attempt in range(SUMMARY_MAX_RETRY + 1):
        if cancel is not None and cancel.cancelled:
            raise SummaryAborted("已中止")

        attempt_cancel = CancelToken()
        provider = provider_factory(attempt_cancel)
        request = GenerateRequest(
            model=model.model,
            messages=[Message(role="user", content=user_text)],
            system=system,
            max_tokens=SUMMARY_MAX_TOKENS,
            # 不传 temperature：新版 Claude（如 Opus）已弃用该参数，传了直接 400。
            session_id=session_id or None,
        )

        timed_out = False
        watcher = asyncio.ensure_future(_watch_cancel(cancel, attempt_cancel))
        collected = _Collected("", "", "", False)
        try:
            collected = await asyncio.wait_for(_collect(provider, request), timeout=timeout_ms / 1000)
        except asyncio.TimeoutError:
            timed_out = True
            attempt_cancel.cancel()
        except Exception as exc:  # 适配器之外的意外：按可重试处理，最后一次仍败则原文上报
            collected = _Collected("", "", str(exc) or exc.__class__.__name__, False)
        finally:
            watcher.cancel()
            try:
                await watcher
            except (asyncio.CancelledError, RuntimeError):
                pass

        if cancel is not None and cancel.cancelled:
            raise SummaryAborted("已中止")
        if collected.fatal:
            raise SummaryError(collected.fatal)

        body = collected.text.strip()
        if not (collected.retryable or timed_out or collected.interrupted):
            if body:
                return body
            raise SummaryError("模型没有返回摘要正文（可能只输出了思维链，或被内容策略拦截）")

        last_reason = (
            f"摘要请求超过 {round(timeout_ms / 1000)}s 仍未完成"
            if timed_out
            else (collected.retryable or "连接中断")
        )
        if attempt >= SUMMARY_MAX_RETRY:
            raise SummaryError(f"{last_reason}（已重试 {SUMMARY_MAX_RETRY} 次）")

        await backoff(min(1000 * 2**attempt, 8000) / 1000)

    raise SummaryError(last_reason)  # pragma: no cover - 循环内必然返回或抛出


# ── 压缩主流程 ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CompactResult:
    status: str  # compacted | none | failed
    message: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "message": self.message}


async def compact_session(
    session: StoredSession,
    model: CompactModel,
    provider_factory: Callable[[CancelToken], Provider],
    cancel: Optional[CancelToken] = None,
    models_section: Any = None,
    cfg: Optional[CompactionConfig] = None,
    locale: str = "zh-CN",
    mid_turn: bool = False,
    on_start: Optional[Callable[[], None]] = None,
    save: Optional[Callable[[str], None]] = None,
    timeout_ms: int = SUMMARY_TIMEOUT_MS,
    sleep: Optional[Callable[[float], Any]] = None,
) -> CompactResult:
    """压缩一个会话：在模型视图上选边界 → 转录待压段 → 一次性摘要 → 插入并落盘。

    不删除任何消息：被压的部分照常显示，只是此后不再发给模型。
    成功 `compacted`；无可压 `none`；摘要失败或未过把关（复读 / 压完不变短）`failed`
    （历史保持不变）。**就地改写** `session.messages`：轮中压缩时 Agent 循环正拿着这个列表
    往里追加。
    """
    config = cfg or compaction_config(None)
    window = context_window_for(model, models_section, config)
    keep_tokens = keep_tokens_for(window)
    messages = session.messages
    # 边界、转录、把关都在模型视图上算（上一份摘要及其后的原文）；之前的部分已在上一份摘要里。
    view, to_record = _model_view(messages)

    boundary = pick_boundary(view, keep_tokens)
    # 轮内切时原样保留的本轮用户请求（视图下标；-1 = 普通压缩，不保留）
    keep_head = -1
    if boundary < 0 and mid_turn:
        start = last_turn_start(view)
        cut = pick_in_turn_cut(view, start, keep_tokens) if start >= 0 else -1
        if cut > 0:
            boundary = cut
            keep_head = start
    if boundary < 0:
        return CompactResult("none")

    to_summarize = view[:boundary]
    tail = view[boundary:]
    transcript = build_transcript(to_summarize, locale, transcript_budget(window))

    if on_start is not None:
        on_start()
    try:
        summary = await summarize(
            model,
            transcript,
            provider_factory,
            locale=locale,
            cancel=cancel,
            mid_turn=keep_head >= 0,
            session_id=session.id,
            timeout_ms=timeout_ms,
            sleep=sleep,
        )
    except SummaryAborted:
        return CompactResult("failed", "已中止")
    except SummaryError as exc:
        # 失败原因原样带回（鉴权 / 断流 / 超时 / 无正文）。历史在此之前一个字都没动。
        return CompactResult("failed", str(exc))
    if cancel is not None and cancel.cancelled:
        return CompactResult("failed", "已中止")
    if not summary:
        return CompactResult("failed", "模型没有返回摘要正文")

    zh = locale != "en"
    # 摘要把关①：模型退化时摘要也会复读，采信就会用垃圾顶替真实历史，此后每一轮都被它带偏。
    if find_repetition(summary):
        return CompactResult(
            "failed",
            "摘要里有大段重复内容，模型输出可能异常"
            if zh
            else "The summary contains long repeated text; the model output may be degenerate",
        )
    if keep_head >= 0:
        header = (
            "以下是此前对话以及本轮任务已完成部分的摘要（为节省上下文，较早的消息已压缩）。"
            "上面那条是用户本轮的原始请求，任务仍在进行中：请在此基础上接着做，不要从头再来，也不要重复已经完成的步骤。"
            if zh
            else "The following summarizes the earlier conversation and the work already done on the current task (older messages were compacted to save context). The message above is the user's original request for this turn, and the task is still in progress: continue from here — do not start over or repeat steps already completed."
        )
    else:
        header = (
            "以下是此前对话的摘要（为节省上下文，较早的消息已压缩）。请在此基础上继续。"
            if zh
            else "The following is a summary of the earlier conversation (older messages were compacted to save context). Continue from here."
        )
    # 未完成的当前待办清单附在摘要后：写它的 tool_use 可能刚被压掉，模型从此只能从这里知道清单进度。
    todo = todo_snapshot_text(session.todos, session.todoCancelled, zh)
    summary_msg = Message(
        role="user",
        content=f"{COMPACT_MARKER}\n{header}\n\n{summary}" + (f"\n\n{todo}" if todo else ""),
    )
    head_messages = [view[keep_head]] if keep_head >= 0 else []

    # 摘要把关②：压完反而不比原来短（被压段本就不大、摘要却写得长），白白丢掉原文细节。
    if estimate_tokens([*head_messages, summary_msg, *tail]) >= estimate_tokens(view):
        return CompactResult(
            "failed",
            "摘要不比被压缩的内容短"
            if zh
            else "The summary is not shorter than the content it replaces",
        )

    # 插在保留部分的第一条消息前；记录里的消息一条不删，检查点、各边车都不受影响。
    at = to_record(boundary)
    messages.insert(at, summary_msg)
    # 终态提示边车：after = 提示前方的消息条数，插入点之后的整体后移一位（恰在插入点的仍排在摘要前）。
    if session.notices:
        for notice in session.notices:
            if notice.after > at:
                notice.after += 1
    session.lastInputTokens = None  # 发给模型的内容已缩短，旧计数失效
    session.updatedAt = now_ms()
    if save is not None:
        save(session.id)
    return CompactResult("compacted")


def display_summary(content: str) -> str:
    """界面展示用的摘要正文：去掉标记前缀与开头写给模型的那段说明，只留摘要本身（及其后附的待办）。"""
    body = content[len(COMPACT_MARKER):].lstrip("\n") if content.startswith(COMPACT_MARKER) else content
    cut = body.find("\n\n")
    return body[cut + 2:] if cut >= 0 else body


__all__ = [
    "CompactModel",
    "CompactResult",
    "CompactionConfig",
    "DEFAULTS",
    "MIN_TRANSCRIPT_CHARS",
    "SUMMARY_MAX_RETRY",
    "SUMMARY_MAX_TOKENS",
    "SUMMARY_TIMEOUT_MS",
    "SUMMARY_SYSTEM_EN",
    "SUMMARY_SYSTEM_ZH",
    "SummaryAborted",
    "SummaryError",
    "build_transcript",
    "compact_session",
    "compaction_config",
    "compaction_worth_retry",
    "context_window_for",
    "display_summary",
    "estimate_tokens",
    "keep_tokens_for",
    "learned_output_budget",
    "needs_compaction",
    "needs_compaction_mid_turn",
    "pick_boundary",
    "pick_in_turn_cut",
    "remember_context_limit",
    "remember_output_budget",
    "reset_learned",
    "summarize",
    "transcript_budget",
    "trigger_tokens_for",
    "used_tokens_mid_turn",
]
