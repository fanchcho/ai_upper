"""Provider 抽象层：归一化的请求/事件类型 + 流式接口。

类型口径取自 Deva `apps/desktop/src/main/providers/types.ts` 与 `providers/index.ts`：

- 消息归一化：连续的相同角色消息合并（Deva `normalizeMessages`），否则部分服务端会拒绝；
- 事件归一化：文本增量 / 思考增量 / 工具调用 / 用量 / 错误 / 结束，由适配器翻译成同一套事件；
- 错误归一化：HTTP 状态与错误正文 → `NormalizedError(kind, retryable, message)`，
  界面按 kind 决定提示与「重试」按钮是否出现。

P1 只做「单轮文本流 + 错误归一」这条主干。真正的网络适配器（Anthropic / OpenAI）
尚未实现：只有离线假实现 `FakeProvider`。没有实现的适配器必须显式 `NotImplementedError`，
不得返回假数据冒充可用。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Literal, Optional, Sequence

from mvvm.models.chat_models import ContentPart, Message

ErrorKind = Literal[
    "output_limit",
    "auth",
    "rate_limit",
    "effort_unsupported",
    "context_length",
    "server",
    "invalid_request",
    "network",
]


@dataclass(frozen=True)
class NormalizedError:
    """归一化后的失败原因。`retryable` 只表示「再试一次可能成功」，不代表界面要自动重试。"""

    kind: ErrorKind
    message: str
    retryable: bool = False
    status: Optional[int] = None


class ProviderError(Exception):
    """适配器抛出的可归一化错误；携带 NormalizedError 供上层原样展示。"""

    def __init__(self, error: NormalizedError) -> None:
        super().__init__(error.message)
        self.error = error


def http_error(status: int, body: str = "") -> NormalizedError:
    """HTTP 状态 → NormalizedError（Deva `httpError` 的映射）。"""
    if status in (401, 403):
        return NormalizedError("auth", f"鉴权失败（HTTP {status}）：请检查密钥是否有权访问该模型", False, status)
    if status == 429:
        return NormalizedError("rate_limit", "请求过于频繁（HTTP 429），请稍后再试", True, status)
    if status == 413 or status == 400 and "context" in body.lower():
        return NormalizedError("context_length", "上下文超出模型上限，请压缩或新建对话", False, status)
    if 500 <= status < 600:
        return NormalizedError("server", f"服务端错误（HTTP {status}），可稍后重试", True, status)
    return NormalizedError("invalid_request", f"请求被拒绝（HTTP {status}）：{body.strip()[:200]}", False, status)


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


StreamEvent = TextDelta | ThinkingDelta | ToolCall | Usage | StreamError | Done


@dataclass(frozen=True)
class GenerateRequest:
    model: str
    messages: Sequence[Message]
    system: Optional[str] = None
    tools: Sequence[dict] = field(default_factory=tuple)
    max_tokens: Optional[int] = None


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
    "Usage",
    "http_error",
    "normalize_messages",
]
