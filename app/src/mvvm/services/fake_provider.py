"""离线假 provider：不联网、不需要密钥，用来跑通「发送 → 回复 → 工具调用」全链路。

它只做三件事：
1. 按脚本回放一串事件（测试可精确控制流的内容与顺序）；
2. 没给脚本时，按「读文件」这个固定意图把请求转成一次 `read_file` 工具调用
   ——这样纵向切片能真实走到工具沙箱的允许/拒绝两条分支；
3. 每次调用记录收到的 `GenerateRequest`，测试据此断言「发给模型的历史是什么」。

它不是「假装的真实适配器」：类名、构造参数与失败行为都明确表明这是测试替身，
真实网络适配器在 `provider_gateway.NotImplementedProvider` 里显式报未实现。
"""
from __future__ import annotations

from typing import AsyncIterator, Optional, Sequence

from mvvm.models.chat_models import Message, ToolResultPart
from mvvm.services.provider_gateway import (
    Done,
    GenerateRequest,
    Provider,
    StreamEvent,
    StreamError,
    TextDelta,
    ToolCall,
    Usage,
)


class FakeProvider(Provider):
    """确定性的本地 provider。

    Args:
        script: 依次回放的事件序列；None 时走内置的「读文件」剧本。
        fail_with: 直接发一个 StreamError 再结束（模拟鉴权失败 / 限流等）。
    """

    name = "fake"

    def __init__(
        self,
        script: Optional[Sequence[StreamEvent]] = None,
        *,
        fail_with: Optional[str] = None,
        tool_path: str = "notes.txt",
    ) -> None:
        self._script = list(script) if script is not None else None
        self._fail_with = fail_with
        self._tool_path = tool_path
        self.requests: list[GenerateRequest] = []

    async def stream(self, request: GenerateRequest) -> AsyncIterator[StreamEvent]:  # type: ignore[override]
        self.requests.append(request)
        if self._fail_with is not None:
            from mvvm.services.provider_gateway import NormalizedError

            yield StreamError(NormalizedError("auth", self._fail_with, False, 401))
            yield Done("error")
            return

        if self._script is not None:
            for event in self._script:
                yield event
            return

        async for event in self._default_script(request):
            yield event

    async def _default_script(self, request: GenerateRequest) -> AsyncIterator[StreamEvent]:
        """内置剧本：首轮请求 `read_file`，拿到工具结果后给一句总结。

        「首轮」判定看历史里有没有 tool_result——这正是真实 agent 循环的判据，
        不依赖任何外部状态，重复调用也稳定。
        """
        if _has_tool_result(request.messages):
            last = _last_tool_result(request.messages)
            ok = last is not None and not last.isError
            text = (
                f"已经读取 {self._tool_path}，内容是：{last.content}"
                if ok and last is not None
                else f"读取 {self._tool_path} 失败：{last.content if last else '没有工具结果'}"
            )
            for chunk in _chunks(text):
                yield TextDelta(chunk)
            yield Usage(input_tokens=32, output_tokens=len(text))
            yield Done("end_turn")
            return

        yield TextDelta("我先看一下工作区里的文件。")
        yield Usage(input_tokens=24, output_tokens=8)
        yield ToolCall(
            id=f"call_{len(self.requests)}",
            name="read_file",
            input={"path": self._tool_path},
        )
        yield Done("tool_use")


def _has_tool_result(messages: Sequence[Message]) -> bool:
    for message in messages:
        if isinstance(message.content, list):
            if any(isinstance(p, ToolResultPart) for p in message.content):
                return True
    return False


def _last_tool_result(messages: Sequence[Message]) -> Optional[ToolResultPart]:
    found: Optional[ToolResultPart] = None
    for message in messages:
        if isinstance(message.content, list):
            for part in message.content:
                if isinstance(part, ToolResultPart):
                    found = part
    return found


def _chunks(text: str, size: int = 8) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)] or [""]


def tool_result_message(call: ToolCall, content: str, is_error: bool) -> Message:
    """把工具结果包成 user 消息（Anthropic 风味：工具结果挂在 user 上）。"""
    return Message(
        role="user",
        content=[
            ToolResultPart(toolUseId=call.id, content=content, isError=True if is_error else None)
        ],
    )


__all__ = ["FakeProvider", "tool_result_message"]
