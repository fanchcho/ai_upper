"""聊天 ViewModel：把「发一条消息」串成 会话 → provider → 工具 → 持久化 的完整回合。

View 只做绑定：输入、状态、错误、消息列表都是可观察属性，`send_command` 是 RelayCommand。

## 线程

回合跑在一条后台线程自己的 asyncio 事件循环里，UI 线程只负责把输入交给回合、把产出的
事件渲染出来。回合线程永远不碰 Qt 控件，UI 线程永远不等网络；两者通过 `emit` 回调连接
（界面层把它桥到 Qt 队列信号上）。

`run_turn()` 是纯异步入口（不碰线程），测试可直接 await，将来接 qasync 也能直接驱动；
`send()` / `cancel()` 是给界面用的线程包装。

## 压缩

回合请求模型前检查上下文用量（`needs_compaction`），Agent 循环每一步前再查一次
（`needs_compaction_mid_turn`）；接近窗口就插入一条摘要，**不删任何消息**。手动压缩走
`compact_now()`（对应 Deva 的 `/compact`）。
"""
from __future__ import annotations

import asyncio
import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable, Optional

from mvvm.core import BaseViewModel, ObservableProperty, PropertyFactory, RelayCommand
from mvvm.models.chat_models import Message, TextPart, ToolUsePart
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.compaction import (
    DEFAULT_CONTEXT_WINDOW,
    CompactModel,
    CompactResult,
    CompactionConfig,
    compact_session,
    display_summary,
    needs_compaction,
    needs_compaction_mid_turn,
)
from mvvm.services.fake_provider import tool_result_message
from mvvm.services.model_view import (
    COMPACT_MARKER,
    is_auto_nudge,
    is_compaction_summary,
    is_task_notification,
    model_messages,
)
from mvvm.services.provider_gateway import (
    Done,
    GenerateRequest,
    NormalizedError,
    Provider,
    ProviderError,
    StreamError,
    TextDelta,
    ThinkingDelta,
    ToolCall,
    Usage,
)
from mvvm.services.tool_runtime import ToolResult, ToolRuntime
from mvvm.services.transport import CancelToken

MAX_TOOL_STEPS = 4  # 单回合最多几次「调工具 → 再问模型」，防失控循环

# provider 工厂：给压缩摘要用。每次调用都造一个新适配器，以便超时/取消能真正掐断请求。
ProviderFactory = Callable[[Optional[CancelToken]], Provider]


@dataclass
class TurnOutcome:
    """一个回合的结束原因。"""

    text: str = ""
    stop: str = "end_turn"  # end_turn | aborted | error | max_steps


class ChatViewModel(BaseViewModel):
    """一条会话的聊天状态与回合逻辑。"""

    def __init__(
        self,
        store: ChatSessionStore,
        provider: Provider,
        tools: ToolRuntime,
        session_id: Optional[str] = None,
        model: str = "fake-model",
        *,
        provider_factory: Optional[ProviderFactory] = None,
        compact_model: Optional[CompactModel] = None,
        models_section: Optional[dict[str, Any]] = None,
        compaction_config: Optional[CompactionConfig] = None,
        locale: str = "zh-CN",
    ) -> None:
        self.store = store
        self.provider = provider
        self.tools = tools
        self.model = model
        # 压缩用的模型配置与 provider 工厂：没给就视为「不支持压缩」（纯文本测试场景）。
        self.provider_factory = provider_factory
        self.compact_model = compact_model
        self.models_section = models_section or {}
        self.compaction_config = compaction_config or CompactionConfig(
            default_window=DEFAULT_CONTEXT_WINDOW
        )
        self.locale = locale
        self._session_id = session_id
        self._tool_results: list[ToolResult] = []
        self._cancel: Optional[CancelToken] = None
        self._thread: Optional[threading.Thread] = None
        # 回合线程只往队列里放「到 UI 线程再执行」的属性写入；UI 线程用 drain() 取走执行。
        # 这样 Qt 控件与可观察属性永远只被一个线程碰（见模块开头的线程说明）。
        self._events: queue.Queue[Callable[[], None]] = queue.Queue()
        self._worker_ident: Optional[int] = None
        self.emit: Callable[[dict[str, Any]], None] = lambda event: None
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

    # ── 只读视图 ──────────────────────────────────────────────────────────
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
        self.transcript_property.set_value(_display_messages(session.messages))
        self.status_property.set_value("就绪")
        self.error_property.set_value("")

    # ── 线程包装（界面用）─────────────────────────────────────────────────
    def send(self, parameter: Any = None) -> None:
        """按钮/命令入口：在后台线程跑一个回合，立即返回（界面不冻结）。"""
        text = str(self.input_text_property.get_value() or "").strip()
        if not text or self.busy:
            return
        self.input_text_property.set_value("")
        self.start_turn(text)

    def start_turn(self, text: str) -> threading.Thread:
        """起后台线程跑 `run_turn`；已有一个回合在跑时直接返回当前线程。"""
        if self._thread is not None and self._thread.is_alive():
            return self._thread
        self._cancel = CancelToken()

        def runner() -> None:
            self._worker_ident = threading.get_ident()
            try:
                asyncio.run(self.run_turn(text, cancel=self._cancel))
            except Exception as exc:  # noqa: BLE001 - 线程边界：异常必须变成界面可见的错误
                self._fail(f"回合失败：{exc}")
            finally:
                self._worker_ident = None
                self._thread = None

        thread = threading.Thread(target=runner, name="chat-turn", daemon=True)
        self._thread = thread
        thread.start()
        return thread

    def wait_idle(self, timeout: Optional[float] = None) -> bool:
        """等当前回合结束并把队列里剩下的事件全部执行完。返回 True 表示已空闲。"""
        thread = self._thread
        if thread is not None:
            thread.join(timeout)
            if thread.is_alive():
                return False
        self.drain()
        return True

    def drain(self) -> int:
        """在 UI 线程执行回合线程攒下的状态更新。返回执行了几条。

        界面层用 QTimer 周期性调用，或在工作线程结束后调用一次；测试里由 `wait_idle()` 调。
        队列为空时是空操作，可以高频调用。
        """
        count = 0
        while True:
            try:
                apply = self._events.get_nowait()
            except queue.Empty:
                return count
            apply()
            count += 1

    def _ui(self, action: Callable[[], None]) -> None:
        """把一次状态写入调度到 UI 线程。

        界面线程自己调用时直接执行（Qt 不允许跨线程改控件，但同线程没问题）；回合线程
        调用时只入队，等 UI 线程 `drain()`。这样纯 Python 测试不依赖 Qt 也能跑。
        """
        if threading.get_ident() == self._worker_ident:
            self._events.put(action)
        else:
            action()

    def cancel(self) -> None:
        """用户点停止：只置取消标记，由回合内部在下一步检查点收尾。"""
        if self._cancel is not None and self.busy:
            self._cancel.cancel()
            self.status_property.set_value("正在停止…")

    # ── 回合 ──────────────────────────────────────────────────────────────
    async def run_turn(
        self, text: str, *, cancel: Optional[CancelToken] = None
    ) -> TurnOutcome:
        """完整回合：用户消息落盘 → 轮首压缩 → provider 流 → 工具 → 最终回复落盘。"""
        if not self._session_id:
            raise RuntimeError("没有打开会话：先调用 open_session()")
        self._ui(lambda: self.busy_property.set_value(True))
        self._ui(lambda: self.error_property.set_value(""))
        self._ui(lambda: self.status_property.set_value("思考中…"))
        try:
            session = self.store.ensure_session(self._session_id)
            user_message = Message(role="user", content=[TextPart(text=text)])
            self.store.append_message(session.id, user_message)
            self._append_display("user", text)
            self._ui(lambda: self.title_property.set_value(session.title))
            self.emit({"type": "user", "text": text})

            await self._auto_compact(session, cancel=cancel, mid_turn=False)

            answer, stop = await self._agent_loop(session.id, cancel=cancel)
            if answer:
                self.store.append_message(
                    session.id, Message(role="assistant", content=[TextPart(text=answer)])
                )
                self._append_display("assistant", answer)
            if stop == "aborted":
                self._ui(lambda: self.status_property.set_value("已停止"))
            else:
                self._ui(lambda: self.status_property.set_value("就绪"))
            self.emit({"type": "done", "stop": stop, "text": answer})
            return TurnOutcome(answer, stop)
        except ProviderError as exc:
            self._fail(exc.error.message)
            return TurnOutcome("", "error")
        except Exception as exc:  # noqa: BLE001 - 回合边界：任何异常都要变成界面可见的错误
            self._fail(f"回合失败：{exc}")
            return TurnOutcome("", "error")
        finally:
            self._ui(lambda: self.busy_property.set_value(False))

    async def _agent_loop(
        self, session_id: str, *, cancel: Optional[CancelToken] = None
    ) -> tuple[str, str]:
        """模型 ↔ 工具循环。返回（最终正文，结束原因）。"""
        answer = ""
        for step in range(MAX_TOOL_STEPS + 1):
            session = self.store.ensure_session(session_id)
            if step > 0:
                # 轮中压缩：上一步的工具结果已回灌，历史里没有悬空的 tool_use，可以安全改写。
                await self._auto_compact(session, cancel=cancel, mid_turn=True)
            if cancel is not None and cancel.cancelled:
                return answer, "aborted"
            request = GenerateRequest(
                model=self.model,
                messages=model_messages(session.messages),
                tools=[_spec_dict(s) for s in self.tools.specs()],
                cache=True,
                session_id=session_id,
            )
            text_parts: list[str] = []
            calls: list[ToolCall] = []
            stop_reason = "end_turn"
            aborted = False
            async for event in self.provider.stream(request):
                if cancel is not None and cancel.cancelled:
                    aborted = True
                    break
                if isinstance(event, TextDelta):
                    text_parts.append(event.text)
                    self.emit({"type": "text_delta", "text": event.text})
                elif isinstance(event, ThinkingDelta):
                    self.emit({"type": "thinking_delta", "text": event.text})
                elif isinstance(event, ToolCall):
                    calls.append(event)
                    self.emit({"type": "tool_call", "name": event.name, "input": event.input})
                elif isinstance(event, StreamError):
                    if aborted:
                        break
                    raise ProviderError(event.error)
                elif isinstance(event, Usage):
                    session.lastInputTokens = event.input_tokens or None
                elif isinstance(event, Done):
                    stop_reason = event.stop_reason

            text = "".join(text_parts)
            if aborted:
                # 中止：把已收到的半截正文落盘（重开后看得出这一轮被打断）。
                if text:
                    self.store.append_message(
                        session_id, Message(role="assistant", content=[TextPart(text=text)])
                    )
                return text, "aborted"

            if calls:
                # 工具调用这一轮的 assistant 消息先落盘；正文与 tool_use 放进**同一条**消息，
                # 否则重启后开场白会丢、只剩一个空助手气泡。
                parts: list[Any] = [TextPart(text=text)] if text else []
                parts.extend(ToolUsePart(id=c.id, name=c.name, input=c.input) for c in calls)
                self.store.append_message(session_id, Message(role="assistant", content=parts))
                if text:
                    self._append_display("assistant", text)
                for call in calls:
                    if cancel is not None and cancel.cancelled:
                        self.store.append_message(
                            session_id,
                            tool_result_message(call, "本轮已被用户停止，工具未执行。", True),
                        )
                        return text, "aborted"
                    result = self.tools.execute(call.name, call.input)
                    self._tool_results.append(result)
                    self.store.append_message(
                        session_id, tool_result_message(call, result.content, result.is_error)
                    )
                    self._append_display(
                        "tool", result.content, is_error=result.is_error, name=call.name
                    )
                    self.emit(
                        {
                            "type": "tool_result",
                            "name": call.name,
                            "content": result.content,
                            "is_error": result.is_error,
                        }
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
        return answer, "end_turn"

    # ── 压缩 ──────────────────────────────────────────────────────────────
    async def _auto_compact(
        self,
        session: Any,
        *,
        cancel: Optional[CancelToken],
        mid_turn: bool,
    ) -> bool:
        """按阈值自动压缩；返回是否真的压了。失败不阻断本回合（宁可这一轮不压）。"""
        if self.provider_factory is None or self.compact_model is None:
            return False
        if mid_turn:
            ready = needs_compaction_mid_turn(
                session.messages,
                self.compact_model,
                session.lastInputTokens or 0,
                len(session.messages),
                self.models_section,
                self.compaction_config,
            )
        else:
            ready = needs_compaction(
                session, self.compact_model, self.models_section, self.compaction_config
            )
        if not ready:
            return False
        result = await compact_session(
            session,
            self.compact_model,
            self.provider_factory,
            cancel=cancel,
            models_section=self.models_section,
            cfg=self.compaction_config,
            locale=self.locale,
            mid_turn=mid_turn,
            on_start=lambda: self.emit({"type": "compacting", "active": True}),
            save=self.store.save,
        )
        self.emit({"type": "compacting", "active": False})
        if result.status == "compacted":
            self._refresh_transcript(session)
            self.emit({"type": "compacted", "scope": "auto", "status": result.status})
            return True
        if result.status == "failed":
            self.emit(
                {
                    "type": "compacted",
                    "scope": "auto",
                    "status": result.status,
                    "message": result.message,
                }
            )
        return False

    async def compact_now(self, cancel: Optional[CancelToken] = None) -> CompactResult:
        """手动压缩（`/compact`）。回调 `emit` 发 compacted 事件。"""
        if self.provider_factory is None or self.compact_model is None:
            return CompactResult("failed", "未配置压缩所需的模型服务")
        session = self.store.ensure_session(self._session_id)
        result = await compact_session(
            session,
            self.compact_model,
            self.provider_factory,
            cancel=cancel,
            models_section=self.models_section,
            cfg=self.compaction_config,
            locale=self.locale,
            on_start=lambda: self.emit({"type": "compacting", "active": True}),
            save=self.store.save,
        )
        self.emit({"type": "compacting", "active": False})
        if result.status == "compacted":
            self._refresh_transcript(session)
        self.emit(
            {
                "type": "compacted",
                "scope": "manual",
                "status": result.status,
                "message": result.message,
            }
        )
        return result

    def _refresh_transcript(self, session: Any) -> None:
        entries = [entry for entry in map(_display, session.messages) if entry is not None]
        self._ui(lambda: self.transcript_property.set_value(list(entries)))

    # ── 内部 ──────────────────────────────────────────────────────────────
    def _append_display(self, role: str, text: str, **extra: Any) -> None:
        def apply() -> None:
            entries = self.transcript
            entries.append({"role": role, "text": text, **extra})
            self.transcript_property.set_value(entries)

        self._ui(apply)

    def _fail(self, message: str) -> None:
        def apply() -> None:
            self.error_property.set_value(message)
            self.status_property.set_value("失败")
            self._append_display("error", message)

        self._ui(apply)
        self.emit({"type": "error", "message": message})


def _normalized(kind: str, message: str) -> NormalizedError:
    return NormalizedError(kind, message)  # type: ignore[arg-type]


def _display_messages(messages: list[Message]) -> list[dict[str, Any]]:
    return [entry for entry in map(_display, messages) if entry is not None]


def _display(message: Message) -> Optional[dict[str, Any]]:
    """把存储消息转成展示条目（user / assistant / tool / error / compaction 五类）。

    纯 tool_use 且没有正文的消息返回 None：它是一次调用，不是一句话，画成空助手气泡
    会让「重启后历史多一条空气泡」。工具结果来自 tool_result 消息，单独成条目。
    """
    if is_compaction_summary(message):
        return {"role": "compaction", "text": display_summary(str(message.content))}
    if isinstance(message.content, str):
        role = message.role
        if is_auto_nudge(message):
            return None
        if is_task_notification(message):
            return {"role": "notice", "text": message.content[len("⟦deva:notify⟧"):].strip()}
        return {"role": role, "text": message.content}
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


__all__ = ["ChatViewModel", "MAX_TOOL_STEPS", "COMPACT_MARKER", "TurnOutcome"]
