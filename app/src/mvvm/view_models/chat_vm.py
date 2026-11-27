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
from locale_runtime import tr
from locale_runtime import tr

import asyncio
import queue
import threading
from dataclasses import dataclass
from typing import Any, Callable, Optional

from mvvm.core import BaseViewModel, ObservableProperty, PropertyFactory, RelayCommand
from mvvm.models.chat_models import Message, TextPart, ToolUsePart
from mvvm.models.chat_models import now_ms
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
from mvvm.services.todos import (
    active_todo_list,
    fold_todos,
    todo_reminder_text,
    todo_user_cancel_note_text,
)
from mvvm.services.tool_results import (
    apply_todo_write_to,
    record_delivered,
    tool_result_message,
)
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
# 回合工厂：给一次对话回合用。入参（取消标记、会话定格的模型引用），返回（适配器，模型 id）。
# 模型在回合开头定死，之后就算设置页换了模型也不影响这一轮（Deva 一轮内模型不变）。
TurnFactory = Callable[[Optional[CancelToken], Optional[str]], "tuple[Provider, str]"]


@dataclass
class TurnOutcome:
    """一个回合的结束原因。"""

    text: str = ""
    stop: str = "end_turn"  # end_turn | aborted | error | max_steps


class ChatViewModel(BaseViewModel):
    """一条会话的聊天状态与回合逻辑。

    `provider` 是**缺省适配器**（测试与单会话场景）；真实应用给的是 `provider_factory`：
    每轮按会话定格的模型引用现解析、现取密钥、现造适配器（Deva `streamChat` 的口径），
    这样在设置页换模型 / 换密钥后下一轮立即生效，不必重建 ViewModel。
    """

    def __init__(
        self,
        store: ChatSessionStore,
        provider: Optional[Provider],
        tools: ToolRuntime,
        session_id: Optional[str] = None,
        model: str = "fake-model",
        *,
        provider_factory: Optional[ProviderFactory] = None,
        turn_factory: Optional[TurnFactory] = None,
        compact_model: Optional[CompactModel] = None,
        models_section: Optional[dict[str, Any]] = None,
        compaction_config: Optional[CompactionConfig] = None,
        locale: str = "zh-CN",
        compact_model_provider: Optional[Callable[[], Optional[CompactModel]]] = None,
        models_section_provider: Optional[Callable[[], dict[str, Any]]] = None,
        compaction_config_provider: Optional[Callable[[], CompactionConfig]] = None,
        effort_provider: Optional[Callable[[Optional[str]], Any]] = None,
        notifier: Optional[Callable[[], None]] = None,
        identity_service: Any = None,
    ) -> None:
        self.store = store
        self.provider = provider
        self.tools = tools
        self.model = model
        # 压缩用的模型配置与 provider 工厂：没给就视为「不支持压缩」（纯文本测试场景）。
        self.provider_factory = provider_factory
        # 真实应用的回合工厂：按会话定格的模型引用现解析、现取密钥、现造适配器。
        # 给了它就用它，否则用缺省 `provider`（测试与单模型场景）。
        self.turn_factory: Optional[TurnFactory] = turn_factory
        self.compact_model = compact_model
        self.models_section = models_section or {}
        self.compaction_config = compaction_config or CompactionConfig(
            default_window=DEFAULT_CONTEXT_WINDOW
        )
        # 真实应用里压缩模型、模型段与压缩配置都是「按当前配置现查」的（设置页改了东西，
        # 下一轮就按新值判定）；直接给固定值的是测试与单模型场景。
        self._models_section_provider = models_section_provider
        self._compaction_config_provider = compaction_config_provider
        self._compact_model_provider = compact_model_provider
        # 思考等级（Deva `effort`）：按会话定格值现算请求参数；没给就不发思考参数。
        self._effort_provider = effort_provider
        # 回合结束时唤醒界面的回调（如把 QTimer 的下一次 drain 提前）。
        self._notifier = notifier
        self.locale = locale
        self.identity_service = identity_service
        self._session_id = session_id
        self._tool_results: list[ToolResult] = []
        self._cancel: Optional[CancelToken] = None
        self._thread: Optional[threading.Thread] = None
        # 回合线程只往队列里放「到 UI 线程再执行」的属性写入；UI 线程用 drain() 取走执行。
        # 这样 Qt 控件与可观察属性永远只被一个线程碰（见模块开头的线程说明）。
        self._events: queue.Queue[Callable[[], None]] = queue.Queue()
        self._inserts: queue.Queue = queue.Queue()
        self._worker_ident: Optional[int] = None
        self.emit: Callable[[dict[str, Any]], None] = lambda event: None
        # `todo_write` 的落点：写会话边车并推给界面（Deva 的胶囊条数据源）。
        # 工具层与界面层互不认识，靠这个回调对接。
        self.tools.todo_sink = self._apply_todo
        super().__init__()

    # ── 属性 ──────────────────────────────────────────────────────────────
    def _initialize_properties(self) -> None:
        self.title_property = PropertyFactory.create("", "title")
        self._register_property("title", self.title_property)

        self.transcript_property = PropertyFactory.create([], "transcript")
        self._register_property("transcript", self.transcript_property)

        self.input_text_property = PropertyFactory.create("", "input_text")
        self._register_property("input_text", self.input_text_property)

        self.status_property = PropertyFactory.create(tr('legacy.b796f2d4ca85'), "status")
        self._register_property("status", self.status_property)

        self.error_property = PropertyFactory.create("", "error")
        self._register_property("error", self.error_property)

        self.busy_property = ObservableProperty(False)
        self._register_property("busy", self.busy_property)

        # 正在流式输出的助手正文（未落盘）。界面把它画在时间线末尾，回合结束时清空。
        self.streaming_property = PropertyFactory.create("", "streaming")
        self._register_property("streaming", self.streaming_property)

        # 当前进行中的待办清单（`todo_write` 写会话边车后同步到这里，界面画胶囊条）。
        self.todos_state_property = ObservableProperty(None)
        self._register_property("todos_state", self.todos_state_property)

        self.send_command = RelayCommand(execute=self.send, can_execute=self.can_send)
        self.stop_command = RelayCommand(execute=self.cancel, can_execute=lambda _=None: self.busy)

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
    def streaming(self) -> str:
        """本轮已经收到、但还没落盘的助手正文（流式刷新的数据源）。"""
        return str(self.streaming_property.get_value() or "")

    @property
    def session_id(self) -> str:
        return str(self._session_id or "")

    @property
    def tool_results(self) -> list[ToolResult]:
        """本 VM 生命周期内执行过的工具结果（测试断言允许/拒绝两条分支用）。"""
        return list(self._tool_results)

    @property
    def todos(self) -> Optional[dict[str, Any]]:
        """当前进行中的待办清单（胶囊条数据）；没有则 None。"""
        session = self.store.ensure_session(self._session_id) if self._session_id else None
        if session is None:
            return None
        return active_todo_list(session.todos, session.todoCancelled)

    # ── 待办清单 ──────────────────────────────────────────────────────────
    def _apply_todo(self, tool_use_id: str, arguments: Any) -> ToolResult:
        """`todo_write` 的执行落点：写会话边车（todos / todoCancelled）并推给界面。"""
        if not self._session_id:
            return ToolResult(tr('legacy.03e273ff3b25'), True, tr('legacy.946734eab024'))
        session = self.store.ensure_session(self._session_id)
        applied = apply_todo_write_to(
            session.todos, session.todoCancelled, tool_use_id, arguments, now_ms()
        )
        if applied.changed:
            session.todos = applied.entries
            session.todoCancelled = applied.cancelled
            session.touch()
            self.store.save(session.id)
            state = applied.active
            self._ui(lambda: self.todos_state_property.set_value(state))
            self.emit({"type": "todos", "state": state})
            if applied.done is not None:
                self.emit({"type": "todo_done", **applied.done})
        return applied.result

    def cancel_todos(self) -> bool:
        """用户在清单面板里手动取消当前清单；返回是否确有可取消的清单。"""
        session = self.store.ensure_session(self._session_id) if self._session_id else None
        if session is None:
            return False
        current = active_todo_list(session.todos, session.todoCancelled)
        if current is None:
            return False
        session.todoCancelled = [*(session.todoCancelled or []), current["id"]]
        # 下一条用户消息里告诉模型清单已被用户取消（Deva `todoCancelNote`）。
        session.todoCancelNote = todo_user_cancel_note_text(current)
        self.store.save(session.id)
        self.todos_state_property.set_value(active_todo_list(session.todos, session.todoCancelled))
        self.emit({"type": "todos", "state": None})
        return True

    def _todo_reminder(self, session: Any) -> str:
        """新一轮开始时仍留着未完成的清单：随本轮用户消息提醒模型取舍（Deva 同口径）。"""
        return todo_reminder_text(session.todos, session.todoCancelled)

    def can_send(self, parameter: Any = None) -> bool:
        return not self.busy and bool(str(self.input_text_property.get_value() or "").strip())

    # ── 会话 ──────────────────────────────────────────────────────────────
    def open_session(self, session_id: str) -> None:
        """打开（或新建）一条会话，把历史读进 transcript。"""
        session = self.store.ensure_session(session_id)
        self._session_id = session.id
        self.tools.set_session(session.id)
        self.title_property.set_value(session.title)
        self.transcript_property.set_value(_display_messages(session.messages))
        self.todos_state_property.set_value(active_todo_list(session.todos, session.todoCancelled))
        self.status_property.set_value(tr('legacy.b796f2d4ca85'))
        self.error_property.set_value("")

    # ── 线程包装（界面用）─────────────────────────────────────────────────
    def send(self, parameter: Any = None) -> None:
        """按钮/命令入口：在后台线程跑一个回合，立即返回（界面不冻结）。"""
        text = str(self.input_text_property.get_value() or "").strip()
        if not text or self.busy:
            return
        self.input_text_property.set_value("")
        self.start_turn(text)

    def start_turn(
        self,
        text: str,
        *,
        cancel: Optional[CancelToken] = None,
        parts: Optional[list[Any]] = None,
        question: Optional[str] = None,
    ) -> threading.Thread:
        """起后台线程跑 `run_turn`；已有一个回合在跑时直接返回当前线程。

        `cancel` 由调用方（Web 承载层的回合宿主）传入，好让 `chat:abort` 拿同一个标记
        止损——否则中止只能等 `busy` 属性被 UI 线程 drain 到才有反应。

        `parts`：附件读出来的内容块（图片 / PDF / 文本注入 / 只给位置），按原版顺序
        **排在提问正文之前**与本条用户消息一起落盘（见 Deva `chat.ts` sendMessage）。
        `question`：真正落进历史的提问正文（原版 `questionText`，可能带「已忽略…」说明）；
        `text` 仍用作标题来源（原版 `deriveTitle(text) || deriveTitle(questionText)`）。
        """
        if self._thread is not None and self._thread.is_alive():
            return self._thread
        self._cancel = cancel if cancel is not None else CancelToken()

        def runner() -> None:
            self._worker_ident = threading.get_ident()
            try:
                asyncio.run(
                    self.run_turn(
                        text, cancel=self._cancel, parts=parts, question=question
                    )
                )
            except Exception as exc:  # noqa: BLE001 - 线程边界：异常必须变成界面可见的错误
                self._fail(tr('legacy.eb4efbaeb4ad' ,p1=exc))
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

    def insert_message(self, text, delivered):
        """Only the turn worker writes history; member dispatches enter at a model boundary."""
        self._inserts.put((text, delivered))

    def withdraw_inserts(self):
        """Take back all not-yet-consumed mid-turn inserts (chat:withdraw-inserts)."""
        out = []
        while True:
            try:
                text, _delivered = self._inserts.get_nowait()
            except queue.Empty:
                return out
            out.append(text)
    def _consume_inserts(self, session_id):
        count = 0
        while True:
            try:
                text, delivered = self._inserts.get_nowait()
            except queue.Empty:
                return count
            self.store.append_message(session_id, Message(role='user', content=text))
            delivered()
            self._append_display('user', text)
            count += 1

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
            self.status_property.set_value(tr('legacy.a6dd18c3f246'))

    # ── 流式刷新 ──────────────────────────────────────────────────────────
    def _push_streaming(self, text: str) -> None:
        """把本轮已收到的正文推给界面（未落盘）。后台线程调用时经队列转到 UI 线程。"""
        self._ui(lambda: self.streaming_property.set_value(text))

    def _clear_streaming(self) -> None:
        def apply() -> None:
            if self.streaming_property.get_value():
                self.streaming_property.set_value("")

        self._ui(apply)

    # ── 回合 ──────────────────────────────────────────────────────────────
    def _provider_for(
        self, cancel: Optional[CancelToken], session_id: str, session_model: Optional[str]
    ) -> tuple[Provider, str]:
        """本轮要用的适配器与模型 id。工厂可能抛出「未配置」，交由回合边界转成界面错误。"""
        if self.turn_factory is not None:
            return self.turn_factory(cancel, session_model)
        model = session_model or self.model
        if self.provider is None:
            raise RuntimeError(tr('legacy.aa91387b01cf'))
        return self.provider, model

    def _compact_model_now(self) -> Optional[CompactModel]:
        if self._compact_model_provider is not None:
            return self._compact_model_provider()
        return self.compact_model

    def _models_section_now(self) -> dict[str, Any]:
        if self._models_section_provider is not None:
            return self._models_section_provider()
        return self.models_section

    def _compaction_config_now(self) -> CompactionConfig:
        if self._compaction_config_provider is not None:
            return self._compaction_config_provider()
        return self.compaction_config

    async def run_turn(
        self,
        text: str,
        *,
        cancel: Optional[CancelToken] = None,
        parts: Optional[list[Any]] = None,
        question: Optional[str] = None,
    ) -> TurnOutcome:
        """完整回合：用户消息落盘 → 轮首压缩 → provider 流 → 工具 → 最终回复落盘。

        `question`：真正落进历史的提问正文；`text` 只作标题来源（原版
        `deriveTitle(text) || deriveTitle(questionText)`）。两者不同只在「只发了附件、
        输入框为空」以及带「已忽略…」说明时。
        """
        if not self._session_id:
            raise RuntimeError(tr('legacy.43738492f456'))
        body = question if question is not None else text
        self._ui(lambda: self.busy_property.set_value(True))
        self._ui(lambda: self.error_property.set_value(""))
        self._ui(lambda: self.streaming_property.set_value(""))
        self._ui(lambda: self.status_property.set_value(tr('legacy.29653ff32b4f')))
        try:
            session = self.store.ensure_session(self._session_id)
            from mvvm.services.checkpoint_recovery import close_pending_tools
            resume = None
            if body.strip() == '/resume' and self.tools.interactions is not None:
                self.tools.cancel_check = (lambda: False) if cancel is None else (lambda: cancel.cancelled)
                # Only a persisted pre-execution interaction may be reattached. A
                # started operation is resolved from its journal and never rerun.
                resume = lambda call: self.tools.execute(call.name, call.input, tool_use_id=call.id) if self.tools.interactions.has_operation(session.id, call.id) else None
                body = tr('legacy.a1e0818aab10')
            if close_pending_tools(session, self.tools.checkpoint, resume):
                self.store.save(session.id)
            if self.identity_service is not None:
                from mvvm.services.plugin_identity import apply_input
                body, reply = apply_input(self.identity_service, session, body)
                self.store.save(session.id)
                if reply:
                    self.store.append_message(session.id, Message(role='user', content=[TextPart(text=text)]))
                    self.store.append_message(session.id, Message(role='assistant', content=[TextPart(text=reply)]))
                    self._append_display('user', text)
                    self._append_display('assistant', reply)
                    self._ui(lambda: self.status_property.set_value(tr('legacy.b796f2d4ca85')))
                    self.emit({'type': 'done', 'stop': 'end_turn', 'text': reply})
                    return TurnOutcome(reply, 'end_turn')
            # 模型在回合开头定一次：中途改设置不影响这一轮（与 Deva 一轮内模型不变一致）。
            provider, model = self._provider_for(cancel, session.id, session.model)
            # 待办清单的两条随用户消息带给模型的说明（Deva `chat.ts` 约 6053 行）：
            # 用户手动取消清单的告知（只带一次），以及上一轮遗留的未完成清单的取舍提醒。
            notes: list[str] = []
            if session.todoCancelNote:
                notes.append(session.todoCancelNote)
                session.todoCancelNote = None
            reminder = self._todo_reminder(session)
            if reminder:
                notes.append(reminder)
            user_parts: list[Any] = [TextPart(text=note) for note in notes]
            # 附件内容块排在提问正文之前（Deva `chat.ts` sendMessage 的 parts 顺序）。
            if parts:
                user_parts.extend(parts)
            user_parts.append(TextPart(text=body))
            user_message = Message(role="user", content=user_parts)
            self.store.append_message(session.id, user_message, title_seed=text)
            # 取消标记要能掐断正在执行的 `run_command`：把「本轮是否已取消」交给工具层。
            self.tools.cancel_check = (lambda: False) if cancel is None else (
                lambda: cancel.cancelled
            )
            self._append_display("user", body)
            self._ui(lambda: self.title_property.set_value(session.title))
            self.emit({"type": "user", "text": body})

            await self._auto_compact(session, cancel=cancel, mid_turn=False)

            answer, stop = await self._agent_loop(
                session.id, provider=provider, model=model, cancel=cancel
            )
            if answer:
                # 中止时 `_agent_loop` 已经落盘并展示过半截正文；这里只补正常结束的最终回复。
                if stop != "aborted":
                    self.store.append_message(
                        session.id, Message(role="assistant", content=[TextPart(text=answer)])
                    )
                    self._append_display("assistant", answer)
            if stop == "aborted":
                self._ui(lambda: self.status_property.set_value(tr('legacy.75dddf524e4c')))
            else:
                self._ui(lambda: self.status_property.set_value(tr('legacy.b796f2d4ca85')))
            self.emit({"type": "done", "stop": stop, "text": answer})
            return TurnOutcome(answer, stop)
        except ProviderError as exc:
            self._fail(exc.error.message)
            return TurnOutcome("", "error")
        except Exception as exc:  # noqa: BLE001 - 回合边界：任何异常都要变成界面可见的错误
            self._fail(tr('legacy.eb4efbaeb4ad' ,p1=exc))
            return TurnOutcome("", "error")
        finally:
            self.tools.close()
            self._ui(lambda: self.busy_property.set_value(False))
            # 通知界面「回合结束」也要回到 UI 线程：本方法跑在工作线程，直接调回调会让
            # 界面在自己的线程之外改控件（Qt 会拒绝创建子对象，进程随后崩溃）。
            if self._notifier is not None:
                self._ui(self._notifier)

    async def _agent_loop(
        self,
        session_id: str,
        *,
        provider: Optional[Provider] = None,
        model: Optional[str] = None,
        cancel: Optional[CancelToken] = None,
    ) -> tuple[str, str]:
        """模型 ↔ 工具循环。返回（最终正文，结束原因）。"""
        answer = ""
        provider = provider if provider is not None else self.provider
        if provider is None:
            raise RuntimeError(tr('legacy.969a2eb8d325'))
        model = model or self.model
        for step in range(MAX_TOOL_STEPS + 1):
            self._consume_inserts(session_id)
            session = self.store.ensure_session(session_id)
            if step > 0:
                # 轮中压缩：上一步的工具结果已回灌，历史里没有悬空的 tool_use，可以安全改写。
                await self._auto_compact(session, cancel=cancel, mid_turn=True)
            if cancel is not None and cancel.cancelled:
                return answer, "aborted"
            effort = None
            if self._effort_provider is not None:
                effort = self._effort_provider(session.effort)
            request = GenerateRequest(
                model=model,
                system=self.identity_service.identity_prompt(session.personaId) if self.identity_service else None,
                messages=model_messages(session.messages),
                tools=[_spec_dict(s) for s in self.tools.specs()],
                cache=True,
                effort=effort,
                session_id=session_id,
            )
            text_parts: list[str] = []
            calls: list[ToolCall] = []
            stop_reason = "end_turn"
            aborted = False
            async for event in provider.stream(request):

                if cancel is not None and cancel.cancelled:
                    aborted = True
                    break
                if isinstance(event, TextDelta):
                    text_parts.append(event.text)
                    self._push_streaming("".join(text_parts))
                    self.emit({"type": "text_delta", "text": event.text})
                elif isinstance(event, ThinkingDelta):
                    self.emit({"type": "thinking_delta", "text": event.text})
                elif isinstance(event, ToolCall):
                    calls.append(event)
                    # 带上 id：渲染层按 id 把 tool_result 回填到这张工具卡上，缺了就对不上。
                    self.emit(
                        {"type": "tool_call", "id": event.id, "name": event.name, "input": event.input}
                    )
                elif isinstance(event, StreamError):
                    if aborted:
                        break
                    raise ProviderError(event.error)
                elif isinstance(event, Usage):
                    session.lastInputTokens = event.input_tokens or None
                elif isinstance(event, Done):
                    stop_reason = event.stop_reason

            # 适配器收到取消后直接收流（不给 Done）：这里补一次检查，别把半截流当正常结束。
            if cancel is not None and cancel.cancelled:
                aborted = True
            text = "".join(text_parts)
            # 这一步的正文要么进了工具调用消息、要么就是最终回复；都落盘了，清掉流式区。
            self._clear_streaming()
            if aborted:
                # 中止：把已收到的半截正文落盘并展示（重开后看得出这一轮被打断）。
                if text:
                    self.store.append_message(
                        session_id, Message(role="assistant", content=[TextPart(text=text)])
                    )
                    self._append_display("assistant", text)
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
                            tool_result_message(call, tr('legacy.e1c6be578222'), True),
                        )
                        return text, "aborted"
                    result = self.tools.execute(call.name, call.input, tool_use_id=call.id)
                    self._tool_results.append(result)
                    # 交付文件：解析后的路径写进会话边车（Deva `chat.ts:5294-5297`），必须**先于**
                    # tool_result 事件落盘——渲染层收到成功就会来取交付卡数据。messages 里保留
                    # 模型原样发出的参数，改写会让模型以为自己没照做而反复重试。
                    if result.delivered:
                        session = self.store.ensure_session(session_id)
                        session.delivered = record_delivered(
                            session.delivered, call.id, result
                        )
                        session.touch()
                        self.store.save(session.id)
                    self.store.append_message(
                        session_id,
                        tool_result_message(
                            call, result.content, result.is_error, images=result.images
                        ),
                    )
                    self._append_display(
                        "tool",
                        result.content,
                        is_error=result.is_error,
                        name=call.name,
                        summary=result.summary,
                        images=[
                            {"mediaType": part.mediaType, "name": part.name, "data": part.data}
                            for part in (result.images or [])
                        ],
                    )
                    self.emit(
                        {
                            "type": "tool_result",
                            "id": call.id,
                            "name": call.name,
                            "content": result.content,
                            "summary": result.summary,
                            "is_error": result.is_error,
                            "images": bool(result.images),
                        }
                    )
                answer = text
                continue

            if stop_reason == "tool_use":
                # 声明要调工具却没给调用：适配器行为异常，明确报错而不是当作正常结束。
                raise ProviderError(
                    _normalized("invalid_request", tr('legacy.34564c43784d'))
                )
            answer = text
            if not self._inserts.empty():
                if text:
                    self.store.append_message(session_id, Message(role='assistant', content=text))
                    self._append_display('assistant', text)
                continue
            break
        else:
            raise ProviderError(
                _normalized("invalid_request", tr('legacy.008906a3e267' ,p1=MAX_TOOL_STEPS))
            )
        if not answer:
            raise ProviderError(_normalized("server", tr('legacy.72f60ab7b3ba')))
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
        model = self._compact_model_now()
        if self.provider_factory is None or model is None:
            return False
        models_section = self._models_section_now()
        cfg = self._compaction_config_now()
        if mid_turn:
            ready = needs_compaction_mid_turn(
                session.messages,
                model,
                session.lastInputTokens or 0,
                len(session.messages),
                models_section,
                cfg,
            )
        else:
            ready = needs_compaction(session, model, models_section, cfg)
        if not ready:
            return False
        result = await compact_session(
            session,
            model,
            self.provider_factory,
            cancel=cancel,
            models_section=models_section,
            cfg=cfg,
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
        model = self._compact_model_now()
        if self.provider_factory is None or model is None:
            return CompactResult("failed", tr('legacy.eb50f4416300'))
        session = self.store.ensure_session(self._session_id)
        result = await compact_session(
            session,
            model,
            self.provider_factory,
            cancel=cancel,
            models_section=self._models_section_now(),
            cfg=self._compaction_config_now(),
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
            self.status_property.set_value(tr('legacy.3e3c8068bb0e'))
            self._append_display("error", message)

        self._ui(apply)
        self.emit({"type": "error", "message": message})


def _normalized(kind: str, message: str) -> NormalizedError:
    return NormalizedError(kind, message)  # type: ignore[arg-type]


def _display_messages(messages: list[Message]) -> list[dict[str, Any]]:
    """历史消息 → 展示条目。先把 `tool_use_id → 工具名` 扫一遍，工具卡才有标题。"""
    names = _tool_names(messages)
    return [
        entry
        for entry in (_display(message, names) for message in messages)
        if entry is not None
    ]


def _tool_names(messages: list[Message]) -> dict[str, str]:
    """`tool_use_id` → 工具名（来自前一条 assistant 消息里的 tool_use 块）。

    tool_result 消息本身只存 `toolUseId`（Deva 的存储格式），不在旁边存工具名；
    展示层要把结果画成「read_file · 12 行」这样的卡片，只能在历史里回查调用方。
    """
    names: dict[str, str] = {}
    for message in messages:
        if isinstance(message.content, str):
            continue
        for part in message.content:
            if getattr(part, "type", "") == "tool_use":
                names[str(getattr(part, "id", ""))] = str(getattr(part, "name", ""))
    return names


def _display(message: Message, names: Optional[dict[str, str]] = None) -> Optional[dict[str, Any]]:
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
        part = tool_results[0]
        name = (names or {}).get(str(getattr(part, "toolUseId", "")))
        entry: dict[str, Any] = {
            "role": "tool",
            "text": part.content,
            "is_error": bool(getattr(part, "isError", False)),
        }
        if name:
            entry["name"] = name
        images = [
            {"mediaType": image.mediaType, "name": image.name, "data": image.data}
            for image in (getattr(part, "images", None) or [])
        ]
        if images:
            entry["images"] = images
        return entry
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
