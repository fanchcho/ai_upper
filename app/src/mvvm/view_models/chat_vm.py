"""聊天 ViewModel：把「发一条消息」串成 会话 → provider → 工具 → 持久化 的完整回合。

这里承载逻辑，View 只做绑定：
- 输入、状态、错误、消息列表都是可观察属性（`PropertyFactory.create`），View 绑定即可；
- `send_command` 是 RelayCommand，按钮点击直接走它；
- 回合本身是异步的（provider 是异步生成器），`send()` 用 `asyncio.run` 把它跑完。

关于线程：P1 只做**同步驱动**的回合——按钮点下去后界面要等回合结束才刷新。真正的
逐字流式刷新需要把回合放进 Qt 的异步循环（qasync）或工作线程，那是后续阶段的事；
现在不假装做到了，`status` 只有「思考中/就绪/失败」三态。
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from mvvm.core import BaseViewModel, ObservableProperty, PropertyFactory, RelayCommand
from mvvm.models.chat_models import Message, TextPart, ToolUsePart
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.fake_provider import tool_result_message
from mvvm.services.provider_gateway import (
    Done,
    GenerateRequest,
    Provider,
    ProviderError,
    StreamError,
    TextDelta,
    ThinkingDelta,
    ToolCall,
    Usage,
)
from mvvm.services.tool_runtime import ToolResult, ToolRuntime

MAX_TOOL_STEPS = 4  # 单回合最多几次「调工具 → 再问模型」，防失控循环


class ChatViewModel(BaseViewModel):
    """一条会话的聊天状态与回合逻辑。"""

    def __init__(
        self,
        store: ChatSessionStore,
        provider: Provider,
        tools: ToolRuntime,
        session_id: Optional[str] = None,
        model: str = "fake-model",
    ) -> None:
        self.store = store
        self.provider = provider
        self.tools = tools
        self.model = model
        self._session_id = session_id
        self._tool_results: list[ToolResult] = []
        super().__init__()

    # ── 属性 ──────────────────────────────────────────────────────────────
    def _initialize_properties(self) -> None:
        self.title_property = PropertyFactory.create("", "title")
        self._register_property("title", self.title_property)

        self.transcript_property = PropertyFactory.create([], "transcript")
        self._register_property("transcript", self.transcript_property)

        self.input_text_property = PropertyFactory.create("", "input_text")
        self._register_property("input_text", self.input_text_property)

        self.status_property = PropertyFactory.create("就绪", "status")
        self._register_property("status", self.status_property)

        self.error_property = PropertyFactory.create("", "error")
        self._register_property("error", self.error_property)

        self.busy_property = ObservableProperty(False)
        self._register_property("busy", self.busy_property)

        self.send_command = RelayCommand(execute=self.send, can_execute=self.can_send)

    # ── 只读视图（给 View/测试用；不用绑定时可读）─────────────────────────
    @property
    def title(self) -> str:
        return str(self.title_property.get_value() or "")

    @property
    def transcript(self) -> list[dict[str, Any]]:
        return list(self.transcript_property.get_value() or [])

    @property
    def status(self) -> str:
        return str(self.status_property.get_value() or "")

    @property
    def error(self) -> str:
        return str(self.error_property.get_value() or "")

    @property
    def busy(self) -> bool:
        return bool(self.busy_property.get_value())

    @property
    def session_id(self) -> str:
        return str(self._session_id or "")

    @property
    def tool_results(self) -> list[ToolResult]:
        """本 VM 生命周期内执行过的工具结果（测试断言允许/拒绝两条分支用）。"""
        return list(self._tool_results)

    def can_send(self, parameter: Any = None) -> bool:
        return not self.busy and bool(str(self.input_text_property.get_value() or "").strip())

    # ── 会话 ──────────────────────────────────────────────────────────────
    def open_session(self, session_id: str) -> None:
        """打开（或新建）一条会话，把历史读进 transcript。"""
        session = self.store.ensure_session(session_id)
        self._session_id = session.id
        self.title_property.set_value(session.title)
        self.transcript_property.set_value(
            [entry for entry in map(_display, session.messages) if entry is not None]
        )
        self.status_property.set_value("就绪")
        self.error_property.set_value("")

    # ── 回合 ──────────────────────────────────────────────────────────────
    def send(self, parameter: Any = None) -> None:
        """按钮/命令入口：取输入框文本，跑完一个完整回合。"""
        text = str(self.input_text_property.get_value() or "").strip()
        if not text:
            return
        self.input_text_property.set_value("")
        try:
            asyncio.run(self.run_turn(text))
        except RuntimeError as exc:
            # 已有事件循环在跑（例如将来接入 qasync）时 asyncio.run 会拒绝。
            # 这不是可吞掉的错误：明确告诉调用方用 run_turn() 的异步入口。
            self._fail(f"同步回合无法启动（已有事件循环）：{exc}")

    async def run_turn(self, text: str) -> None:
        """完整回合：用户消息落盘 → provider 流 → 工具（允许/拒绝）→ 最终回复落盘。"""
        if not self._session_id:
            raise RuntimeError("没有打开会话：先调用 open_session()")
        self.busy_property.set_value(True)
        self.error_property.set_value("")
        self.status_property.set_value("思考中…")
        try:
            session = self.store.ensure_session(self._session_id)
            user_message = Message(role="user", content=[TextPart(text=text)])
            self.store.append_message(session.id, user_message)
            self._append_display("user", text)
            self.title_property.set_value(session.title)

            answer = await self._agent_loop(session.id)
            if answer:
                self.store.append_message(
                    session.id, Message(role="assistant", content=[TextPart(text=answer)])
                )
                self._append_display("assistant", answer)
            self.status_property.set_value("就绪")
        except ProviderError as exc:
            self._fail(exc.error.message)
        except Exception as exc:  # noqa: BLE001 - 回合边界：任何异常都要变成界面可见的错误
            self._fail(f"回合失败：{exc}")
        finally:
            self.busy_property.set_value(False)

    async def _agent_loop(self, session_id: str) -> str:
        """模型 ↔ 工具循环。返回最终正文（可能为空字符串）。"""
        answer = ""
        for _ in range(MAX_TOOL_STEPS + 1):
            session = self.store.ensure_session(session_id)
            request = GenerateRequest(
                model=self.model,
                messages=list(session.messages),
                tools=[_spec_dict(s) for s in self.tools.specs()],
            )
            text_parts: list[str] = []
            calls: list[ToolCall] = []
            stop_reason = "end_turn"
            async for event in self.provider.stream(request):
                if isinstance(event, TextDelta):
                    text_parts.append(event.text)
                elif isinstance(event, ThinkingDelta):
                    continue  # P1 不展示思考，只记在事件流里
                elif isinstance(event, ToolCall):
                    calls.append(event)
                elif isinstance(event, StreamError):
                    raise ProviderError(event.error)
                elif isinstance(event, Usage):
                    session.lastInputTokens = event.input_tokens or None
                elif isinstance(event, Done):
                    stop_reason = event.stop_reason

            text = "".join(text_parts)
            if calls:
                # 工具调用这一轮的 assistant 消息先落盘。正文与 tool_use 放进**同一条**消息
                # （Deva 的 content parts 就是这样），否则重启后开场白会丢、只剩一个空助手气泡。
                parts: list[Any] = [TextPart(text=text)] if text else []
                parts.extend(
                    ToolUsePart(id=c.id, name=c.name, input=c.input) for c in calls
                )
                message = Message(role="assistant", content=parts)
                self.store.append_message(session_id, message)
                if text:
                    self._append_display("assistant", text)
                for call in calls:
                    result = self.tools.execute(call.name, call.input)
                    self._tool_results.append(result)
                    self.store.append_message(
                        session_id, tool_result_message(call, result.content, result.is_error)
                    )
                    self._append_display(
                        "tool", result.content, is_error=result.is_error, name=call.name
                    )
                answer = text
                continue

            if stop_reason == "tool_use":
                # 声明要调工具却没给调用：适配器行为异常，明确报错而不是当作正常结束。
                raise ProviderError(
                    _normalized("invalid_request", "provider 声明 tool_use 但未返回工具调用")
                )
            answer = text
            break
        else:
            raise ProviderError(
                _normalized("invalid_request", f"工具调用超过 {MAX_TOOL_STEPS} 轮，已中止")
            )
        if not answer:
            raise ProviderError(_normalized("server", "模型没有返回任何正文"))
        return answer

    # ── 内部 ──────────────────────────────────────────────────────────────
    def _append_display(self, role: str, text: str, **extra: Any) -> None:
        entries = self.transcript
        entries.append({"role": role, "text": text, **extra})
        self.transcript_property.set_value(entries)

    def _fail(self, message: str) -> None:
        self.error_property.set_value(message)
        self.status_property.set_value("失败")
        self._append_display("error", message)


def _normalized(kind: str, message: str):  # noqa: ANN202 - 局部小工具
    from mvvm.services.provider_gateway import NormalizedError

    return NormalizedError(kind, message)  # type: ignore[arg-type]


def _display(message: Message) -> Optional[dict[str, Any]]:
    """把存储消息转成展示条目（P1 只区分 user / assistant / tool / error 四类）。

    纯 tool_use 且没有正文的消息返回 None：它是一次调用，不是一句话，画成空助手气泡
    会让「重启后历史多一条空气泡」。工具结果来自 tool_result 消息，单独成条目。
    """
    if isinstance(message.content, str):
        return {"role": message.role, "text": message.content}
    texts = [p.text for p in message.content if isinstance(p, TextPart)]
    tool_results = [p for p in message.content if getattr(p, "type", "") == "tool_result"]
    if tool_results:
        return {
            "role": "tool",
            "text": tool_results[0].content,
            "is_error": bool(getattr(tool_results[0], "isError", False)),
        }
    text = "".join(texts)
    if not text:
        return None
    return {"role": message.role, "text": text}


def _spec_dict(spec: Any) -> dict[str, Any]:
    return {
        "name": spec.name,
        "description": spec.description,
        "inputSchema": spec.input_schema,
    }


__all__ = ["ChatViewModel", "MAX_TOOL_STEPS"]
