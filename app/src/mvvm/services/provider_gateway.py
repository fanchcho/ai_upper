"""Provider 抽象层：归一化的请求/事件类型 + 流式接口。

类型口径取自 Deva `apps/desktop/src/main/providers/types.ts` 与 `providers/index.ts`：

- 消息归一化：连续的相同角色消息合并（Deva `normalizeMessages`），否则部分服务端会拒绝；
- 事件归一化：文本增量 / 思考增量 / 工具调用 / 用量 / 错误 / 结束，由适配器翻译成同一套事件；
- 错误归一化：HTTP 状态与错误正文 → `NormalizedError(kind, retryable, message)`，
  界面按 kind 决定提示与「重试」按钮是否出现。

P1 只做「单轮文本流 + 错误归一」这条主干。真正的网络适配器见 `anthropic_provider.py` /
`openai_provider.py` / `responses_provider.py`；离线假实现是 `FakeProvider`。没有实现的适配器必须显式
`NotImplementedError`，不得返回假数据冒充可用。
"""
from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Literal, Optional, Sequence, TYPE_CHECKING

from mvvm.models.chat_models import ContentPart, Message, StopReason

if TYPE_CHECKING:  # 运行时不导入：effort 只提供纯数据类型，避免循环依赖
    from mvvm.services.effort import EffortRequest

ErrorKind = Literal[
    "output_limit",
    "auth",
    "rate_limit",
    "effort_unsupported",
    "context_length",
    "server",
    "invalid_request",
    "network",
    "aborted",
    "unknown",
]


@dataclass(frozen=True)
class ContextOverflow:
    """「输入 + 输出预留超出窗口」报错里的三个数（Deva `parseContextOverflow`）。"""

    input: int
    output: int
    limit: int


@dataclass(frozen=True)
class NormalizedError:
    """归一化后的失败原因。`retryable` 只表示「再试一次可能成功」，不代表界面要自动重试。"""

    kind: ErrorKind
    message: str
    retryable: bool = False
    status: Optional[int] = None
    # 服务端建议的重试等待（毫秒，来自 retry-after 头）；缺省由调用方按指数退避自定。
    retry_after_ms: Optional[int] = None
    # 上下文超限报错里写明的真实窗口（token）。
    limit: Optional[int] = None
    # 「输入 + 输出预留超出窗口」的三个数。
    overflow: Optional[ContextOverflow] = None


class ProviderError(Exception):
    """适配器抛出的可归一化错误；携带 NormalizedError 供上层原样展示。"""

    def __init__(self, error: NormalizedError) -> None:
        super().__init__(error.message)
        self.error = error


# ── 上下文窗口的解析（Deva shared/context.ts 的两个纯函数，供错误归类用）──────
CONTEXT_WINDOW_RANGE = (1_000, 20_000_000)

_CONTEXT_LIMIT_PATTERNS = (
    re.compile(r"prompt is too long:\s*\d+\s*tokens?\s*>\s*(\d+)", re.I),  # Anthropic
    re.compile(r"exceeds? (?:the )?context limit:\s*\d+\s*\+\s*\d+\s*>\s*(\d+)", re.I),  # Anthropic
    re.compile(r"maximum context length is\s*(\d+)", re.I),  # OpenAI / DeepSeek / vLLM
    re.compile(r"maximum number of tokens allowed\s*\((\d+)\)", re.I),  # Gemini
    re.compile(r"input length should be\s*\[\s*\d+\s*,\s*(\d+)\s*\]", re.I),  # DashScope
    re.compile(r"model token limit:?\s*(\d+)", re.I),  # Moonshot
    re.compile(r"context (?:window|length) (?:of|is)\s*(\d+)", re.I),
)


def _valid_limit(value: int, bounds: tuple[int, int] = CONTEXT_WINDOW_RANGE) -> bool:
    return bounds[0] <= value <= bounds[1]


def parse_context_limit(body: str) -> Optional[int]:
    """从「上下文超限」报错里解析真实窗口；认不出返回 None。

    只认明确写着上下文上限的句式——输出上限超限（max_tokens > N）的数字不能当成窗口。
    """
    for pattern in _CONTEXT_LIMIT_PATTERNS:
        match = pattern.search(body)
        if not match:
            continue
        n = int(match.group(1))
        if _valid_limit(n):
            return n
    return None


def parse_context_overflow(body: str) -> Optional[ContextOverflow]:
    """从「输入 + 输出预留超出窗口」报错里解析三个数；认不出返回 None。"""

    def pick(match: re.Match[str], i: int, o: int, limit: int) -> Optional[ContextOverflow]:
        values = ContextOverflow(int(match.group(i)), int(match.group(o)), int(match.group(limit)))
        if _valid_limit(values.limit) and values.input > 0 and values.output > 0:
            return values
        return None

    # OpenAI 兼容（DeepSeek / vLLM 新版）
    modern = re.search(
        r"maximum context length is\s*(\d+)[\s\S]*?requested\s*(\d+)\s*output tokens"
        r"[\s\S]*?prompt contains\s*(?:at least\s*)?(\d+)\s*input tokens",
        body,
        re.I,
    )
    if modern:
        return pick(modern, 3, 2, 1)
    # OpenAI 旧版 / vLLM 旧版
    legacy = re.search(
        r"maximum context length is\s*(\d+)[\s\S]*?\((\d+) in the messages,\s*(\d+) in the completion\)",
        body,
        re.I,
    )
    if legacy:
        return pick(legacy, 2, 3, 1)
    # Anthropic：input length and `max_tokens` exceed context limit: I + O > L
    anthropic = re.search(r"exceeds? (?:the )?context limit:\s*(\d+)\s*\+\s*(\d+)\s*>\s*(\d+)", body, re.I)
    if anthropic:
        return pick(anthropic, 1, 2, 3)
    return None


def _body_hint(body: str) -> str:
    text = " ".join(body.split())[:200]
    return f"：{text}" if text else ""


def _parse_retry_after(value: Optional[str]) -> Optional[int]:
    """retry-after 头（秒数或 HTTP 日期）→ 毫秒；无效返回 None。"""
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        return None
    if seconds >= 0:
        return int(round(seconds * 1000))
    return None


def _is_output_limit_rejection(status: int, body: str) -> bool:
    return status == 400 and re.search(r"max_(output_|completion_)?tokens", body, re.I) is not None


def _is_effort_rejection(status: int, body: str) -> bool:
    return status == 400 and re.search(
        r"reasoning_effort|reasoning|effort|output_config|thinking|adaptive", body, re.I
    ) is not None


def http_error(
    status: int,
    body: str = "",
    retry_after: Optional[str] = None,
    effort_sent: bool = False,
) -> NormalizedError:
    """HTTP 状态 → NormalizedError（Deva `httpError` 的映射，含自愈所需的两类）。"""
    if _is_output_limit_rejection(status, body):
        return NormalizedError(
            "output_limit",
            f"请求的输出上限超出该模型允许范围（{status}）{_body_hint(body)}",
            False,
            status,
            limit=parse_context_limit(body),
            overflow=parse_context_overflow(body),
        )
    if status in (401, 403):
        return NormalizedError("auth", f"鉴权失败（{status}）：请检查 API 密钥。", False, status)
    if status == 429:
        return NormalizedError(
            "rate_limit",
            f"触发限流（429），请稍后重试{_body_hint(body)}",
            True,
            status,
            retry_after_ms=_parse_retry_after(retry_after),
        )
    # 须在 context_length 之前：后者的正则很宽（token / maximum…），参数被拒的报错常被它误吞。
    if effort_sent and _is_effort_rejection(status, body):
        return NormalizedError(
            "effort_unsupported",
            f"该模型不支持所选思考等级（{status}）{_body_hint(body)}",
            False,
            status,
        )
    if status == 400 and re.search(r"context|token|length|maximum", body, re.I):
        return NormalizedError(
            "context_length",
            "对话长度已超出该模型的上下文上限，无法继续。请新建对话，或换用上下文更大的模型后重试。",
            False,
            status,
            limit=parse_context_limit(body),
            overflow=parse_context_overflow(body),
        )
    if status >= 500:
        return NormalizedError(
            "server",
            f"服务端错误（{status}）{_body_hint(body)}",
            True,
            status,
            retry_after_ms=_parse_retry_after(retry_after),
        )
    return NormalizedError(
        "invalid_request",
        f"请求失败（{status}）：{body[:300]}",
        False,
        status,
    )


_INBAND_CONTEXT = re.compile(
    r"context[ _-]?(length|window)|prompt is too long|too many (input )?tokens"
    r"|exceeds? (the )?(maximum )?context",
    re.I,
)


def inband_error(text: str, fallback: NormalizedError) -> NormalizedError:
    """带内错误（HTTP 200 之后在流里报的错）归类。

    正文认得出上下文超限 / 输出上限被拒的，与 HTTP 400 同样归类，引擎的自愈才用得上；
    其余照旧按 fallback（多为服务端错误）。
    """
    if _INBAND_CONTEXT.search(text) or parse_context_limit(text) is not None:
        return http_error(400, text)
    return fallback


# ── 事件 ────────────────────────────────────────────────────────────────────
@dataclass
class TextDelta:
    text: str
    type: Literal["text_delta"] = "text_delta"


@dataclass
class ThinkingDelta:
    text: str
    type: Literal["thinking_delta"] = "thinking_delta"


@dataclass
class ToolCall:
    """模型请求调用工具。`index` 用于并行调用的流式拼接（P1 只用单次调用）。"""

    id: str
    name: str
    input: dict
    type: Literal["tool_call"] = "tool_call"


@dataclass
class ToolCallTruncated:
    """参数没能完整解析的工具调用（Deva `tool_call_truncated`）。

    参数原文残缺、不可执行；`cause` 说明原因：撞输出上限 / 被内容策略截断 / 流正常结束但 JSON 坏了。
    上层把它记成一次失败的工具调用并把原因回灌给模型——绝不能当成参数为 `{}` 的完整调用去执行。
    """

    id: str
    name: str
    partial_args: str
    cause: str  # max_tokens | refusal | invalid
    type: Literal["tool_call_truncated"] = "tool_call_truncated"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read: int = 0
    cache_write: int = 0
    type: Literal["usage"] = "usage"


@dataclass
class StreamError:
    error: NormalizedError
    type: Literal["error"] = "error"


@dataclass
class Done:
    """流结束。`stop_reason` 区分正常结束 / 还要调工具 / 被截断等。"""

    stop_reason: str = "end_turn"
    type: Literal["done"] = "done"


StreamEvent = TextDelta | ThinkingDelta | ToolCall | ToolCallTruncated | Usage | StreamError | Done


@dataclass(frozen=True)
class GenerateRequest:
    model: str
    messages: Sequence[Message]
    system: Optional[str] = None
    tools: Sequence[dict] = field(default_factory=tuple)
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None
    # 是否给本次请求打提示缓存断点（只有 Anthropic 协议支持显式断点）。
    # 只有「带着同一前缀反复重发」的场景才该开——Agent 循环每步都重发全量历史，正是典型。
    cache: bool = False
    # 思考参数（已按模型能力表收敛，见 effort.py 的 effort_request）。
    effort: Optional[EffortRequest] = None
    # 所属对话 id（需要「每对话一个稳定会话 id」的网关用）。
    session_id: Optional[str] = None


def parse_tool_args(raw: str) -> Optional[Any]:
    """解析工具参数 JSON：空串视为无参数 `{}`；解析失败返回 None（多半是被截在了中途）。"""
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def settle_broken_calls(
    broken: Sequence[tuple[str, str, str]], stop_reason: str
) -> list[ToolCallTruncated]:
    """参数没法解析的工具调用统一收尾（Deva `settleBrokenCalls`）。

    按 stop_reason 定性：撞 max_tokens → 被输出上限截断；内容策略 → 被截断；否则流正常结束但 JSON 坏了。
    此前非截断的坏参数会被当成参数为 `{}` 的完整调用交出去执行，工具只报「缺少 path 参数」，
    模型以为漏填了参数又原样重发同一个超长调用——连续失败也不停。
    """
    if stop_reason == "max_tokens":
        cause = "max_tokens"
    elif stop_reason == "refusal":
        cause = "refusal"
    else:
        cause = "invalid"
    return [
        ToolCallTruncated(id=call_id, name=name, partial_args=raw, cause=cause)
        for call_id, name, raw in broken
    ]


def tool_images_note(images: Sequence[Any]) -> str:
    """工具结果附带图片时的文字说明（Deva `toolImagesNote`）。

    OpenAI 系协议的 tool 消息只收文本，工具返回的图片只能挪到紧随其后的 user 消息里；
    这句说明留在原处，模型才明白下面几张图是上一步工具的附件。
    """
    names = "、".join(image.name for image in images if getattr(image, "name", None))
    tail = f"：{names}" if names else ""
    return f"[以下 {len(images)} 张图片是上方工具结果的附件{tail}]"


def normalize_messages(messages: Sequence[Message]) -> list[Message]:
    """合并连续的相同角色消息（Deva `normalizeMessages`）。

    Deva 的注释说明了原因：部分服务端不接受连续同角色（尤其连续两条 user），
    而工具结果与用户输入在 Anthropic 风味里都挂在 user 上，不合并就会 400。
    合并时内容块数组直接相接，纯文本则退化为文本块数组。
    """
    merged: list[Message] = []
    for message in messages:
        if merged and merged[-1].role == message.role:
            prev = merged[-1]
            prev_parts = _as_parts(prev.content)
            merged[-1] = Message(role=prev.role, content=prev_parts + _as_parts(message.content))
        else:
            merged.append(Message(role=message.role, content=message.content))
    return merged


def _as_parts(content: str | list[ContentPart]) -> list[ContentPart]:
    from mvvm.models.chat_models import TextPart

    if isinstance(content, str):
        return [TextPart(text=content)] if content else []
    return list(content)


class Provider(ABC):
    """模型服务商适配器。实现方只负责把协议差异翻译成归一化事件。"""

    name: str = "provider"

    @abstractmethod
    def stream(self, request: GenerateRequest) -> AsyncIterator[StreamEvent]:
        """流式生成。实现为异步生成器；失败抛 ProviderError 或发 StreamError 事件。"""
        raise NotImplementedError


class NotImplementedProvider(Provider):
    """显式占位：P1 未实现的真实适配器挂在这里，调用即报错，不返回假数据。"""

    def __init__(self, name: str, reason: str) -> None:
        self.name = name
        self._reason = reason

    async def stream(self, request: GenerateRequest) -> AsyncIterator[StreamEvent]:  # type: ignore[override]
        raise NotImplementedError(f"provider {self.name!r} 尚未实现：{self._reason}")
        yield  # unreachable, keeps the async-generator type honest


__all__ = [
    "ContextOverflow",
    "Done",
    "ErrorKind",
    "GenerateRequest",
    "NormalizedError",
    "NotImplementedProvider",
    "Provider",
    "ProviderError",
    "StreamError",
    "StreamEvent",
    "TextDelta",
    "ThinkingDelta",
    "ToolCall",
    "ToolCallTruncated",
    "Usage",
    "http_error",
    "inband_error",
    "normalize_messages",
    "parse_context_limit",
    "parse_context_overflow",
    "parse_tool_args",
    "settle_broken_calls",
    "tool_images_note",
]
