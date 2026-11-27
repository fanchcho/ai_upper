"""宿主控制器：把渲染层的 `window.deva.chat.*` 接到真实回合引擎与落盘服务。

桥（`bridge.py`）只做通道名 → 方法的分发；会话生命周期（turnId ↔ 会话注册表、
事件形状转换、后台线程与界面线程的交接）在这里。

## 为什么不把逻辑塞进 ChatViewModel

`ChatViewModel.emit` 是给界面消费的简化形状（`done{stop,text}`、snake_case 的 `is_error`）；
渲染层要的是 Deva `ChatStreamEvent` 判别联合（camelCase、`done{stopReason,durationMs}`、
外层 `{turnId,sessionId,event}`）。转换只在这里做一次，ViewModel 保持原样（它有自己的单测）。

## turnId

- `chat:send` 同步返回 `{turnId}`，回合本身在后台线程跑（与 Deva `sendMessage` 一致）；
- `chat:abort(turnId)` 按 turnId 找会话再 `cancel()`；未知 turnId 恒 `{ok:true}` 且无副作用；
- `chat:attach-session` 在会话有进行中回合时回该 turnId，否则 `null`。

## 线程

回合在后台线程跑，`emit` 会在那个线程被调用；本模块只把事件交给注入的 `emit` 回调，
真正的跨线程派发由桥负责。这样本模块不依赖 Qt，可以纯 Python 单测。

## 未实现的写路径

附件发送、回合中插入消息、回滚（rewind）、子智能体、群成员、交互卡（ask/plan/mount）
尚未移植：对应通道**不注册**，桥在调用边界显式 reject（`unimplemented: true`），
不会返回假成功。
"""
from __future__ import annotations
from locale_runtime import tr

import asyncio
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from mvvm.services.chat_session_store import ChatSessionStore, derive_title
from mvvm.services.attachments import AttachmentService
from mvvm.services.transport import CancelToken
from mvvm.services.todos import active_todo_list
from mvvm.services.tool_runtime import ToolRuntime
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.view_models.chat_vm import ChatViewModel
from mvvm.webui.bridge import BridgeError, display_messages

# EffortLevel 合法档位（Deva `isEffortLevel`）
EFFORT_LEVELS = ("default", "low", "medium", "high", "xhigh", "max")

# 原版忙碌冲突文案（Deva `chat.ts` startTurn 的 busyError）
BUSY_MESSAGE = 'finish.ui.03c306922c8f'

# 附件读不进时的问题正文回落（Deva startTurn 的 question 回落）
ATTACHMENT_ONLY_QUESTION = "请理解并处理上述附件。"

# 用户自定标题上限（Deva `TITLE_MAX`）
TITLE_MAX = 100


@dataclass
class _Turn:
    """一次进行中的回合：渲染层 turnId 与它所属的会话、ViewModel 与线程。"""

    turn_id: str
    session_id: str
    vm: ChatViewModel
    thread: Optional[threading.Thread] = None
    cancel: Optional[CancelToken] = None
    started_at: int = 0
    aborted: bool = False
    done_sent: bool = False


class ChatHost:
    """一条渲染层会话 ↔ 一个 ChatViewModel 的宿主。

    - `emit(payload)`：推送 `chat:event` 的 payload（`{turnId, sessionId, event}`）；
    - `emit_sessions_changed()`：推送 `chat:sessions-changed`（无 payload）。

    两者都由桥注入；宿主自己不碰 Qt。
    """

    def __init__(
        self,
        *,
        store: ChatSessionStore,
        guard: WorkspaceGuard,
        home: Path,
        emit: Callable[[dict[str, Any]], None],
        emit_sessions_changed: Callable[[], None],
        tool_factory: Optional[Callable[[str], ToolRuntime]] = None,
        vm_factory: Optional[Callable[[str], ChatViewModel]] = None,
        attachments: Optional[AttachmentService] = None,
    ) -> None:
        self.store = store
        self.guard = guard
        self.home = Path(home)
        # 附件服务与守卫共用同一个实例：受信根、白名单才是同一份。
        self.attachments = attachments or AttachmentService(self.home, guard)
        self._emit = emit
        self._emit_sessions_changed = emit_sessions_changed
        # ViewModel 的装配来自外部（模型网关等依赖在应用层，宿主不认识）。
        # 没给工厂时用「无 provider」的 ViewModel：回合会以「尚未配置」错误收场，但落盘链路真实。
        self._vm_factory = vm_factory or self._default_vm
        self._tool_factory = tool_factory or (
            lambda session_id: ToolRuntime(self.guard, None, home=self.home, session_id=session_id)
        )
        self._vms: dict[str, ChatViewModel] = {}
        self._turns: dict[str, _Turn] = {}  # turnId → 回合
        self._session_turn: dict[str, str] = {}  # sessionId → 进行中 turnId
        self._turns_lock = threading.Lock()
        from mvvm.services.members import Members
        self._members = Members(self)


    # ── 装配 ──────────────────────────────────────────────────────────────
    def _default_vm(self, session_id: str) -> ChatViewModel:
        """无外部工厂时的最小 ViewModel：provider 为 None，回合以「未配置」错误收场。"""
        vm = ChatViewModel(self.store, None, self._tool_factory(session_id), session_id=session_id)
        vm.open_session(session_id)
        return vm

    def vm_for(self, session_id: str) -> ChatViewModel:
        """按会话取（或建）ViewModel，并把事件接上推送。"""
        vm = self._vms.get(session_id)
        if vm is not None:
            return vm
        vm = self._vm_factory(session_id)
        vm.emit = lambda event, sid=session_id: self._on_vm_event(sid, event)
        vm.open_session(session_id)
        self._members.install(vm, self.store.load_session(session_id))
        self._vms[session_id] = vm
        return vm

    def drain(self) -> int:
        """GUI 线程周期性调用：执行回合线程攒下的状态写入（`ChatViewModel._ui` 队列）。

        不 drain 的话 `busy` / `status` / `streaming` 这些可观察属性永远停在旧值，
        宿主看到的「忙不忙」也会失真。返回本次执行了几条。
        """
        count = 0
        for vm in list(self._vms.values()):
            count += vm.drain()
        self._members.drain()
        return count

    def _on_vm_event(self, session_id: str, event: dict[str, Any]) -> None:
        """把 ViewModel 的简化事件转成渲染层契约形状再推。"""
        with self._turns_lock:
            turn = self._turns.get(self._session_turn.get(session_id, ""))
        turn_id = turn.turn_id if turn is not None else ""
        payload = to_chat_event(turn_id, session_id, event)
        if payload is None:
            return
        if payload["event"]["type"] == "done":
            if turn is not None:
                if turn.done_sent:
                    return
                turn.done_sent = True
                payload["event"]["durationMs"] = max(
                    0, int(time.time() * 1000) - turn.started_at
                )
            if payload["event"]["stopReason"] == "aborted":
                self.store.save(session_id)
            self._emit_sessions_changed()
        self._emit(payload)

    # ── chat:send ─────────────────────────────────────────────────────────
    def send(self, request: Any) -> dict[str, str]:
        """`chat:send`：落盘用户消息 → 推 turn_start → 后台起回合 → 立即返回 turnId。"""
        if not isinstance(request, dict):
            raise BridgeError(tr('legacy.a728e87a8a99'))
        session_id = _as_str(request.get("sessionId"))
        if not session_id:
            raise BridgeError(tr('legacy.264bbac62499'))
        text = _as_str(request.get("text"))
        if self.is_busy(session_id):
            raise BridgeError(tr(BUSY_MESSAGE))

        session = self.store.ensure_session(
            session_id,
            persona_id=_optional_str(request.get("personaId")),
            focus_root=_optional_str(request.get("focusRoot")),
            model=_optional_str(request.get("modelRef")),
        )
        effort = request.get("effort")
        if isinstance(effort, str) and effort in EFFORT_LEVELS:
            session.effort = effort

        attachments = request.get("attachments")
        # 附件：逐条读成内容块（排在提问正文之前），读不进的转成 note 拼在正文后的括号里。
        # 语义逐条对齐 Deva `chat.ts` sendMessage（buildAttachmentPart 的三种前缀标记）。
        parts: list[Any] = self._members.mentions(session, text)
        notes: list[str] = []
        adapter = _adapter_of(request.get("model"))
        if isinstance(attachments, list):
            for path in attachments:
                if not isinstance(path, str) or not path:
                    continue
                built = self.attachments.build_attachment_part(path, adapter)
                if built.part is not None:
                    parts.append(built.part)
                if built.note:
                    notes.append(built.note)
        question = text.strip() or (ATTACHMENT_ONLY_QUESTION if parts else "")
        if notes:
            # note 是「读不进消息」的说明，拼在提问正文后的括号里（原版 questionText 同形状）。
            question = f"{question}\n（{'；'.join(notes)}）"
        if not question.strip():
            raise BridgeError(tr('legacy.455eb564fc42'))
        # Enabled, role-scoped skill invocation is resolved at the host boundary.
        import re
        from mvvm.services.skill_store import SkillStore
        from mvvm.models.chat_models import TextPart
        names = {m.lower() for m in re.findall(r'(?:^|\s)/([^\s/]+)', text)}
        if names:
            seen = {'compact', 'rewind'}
            for skill in SkillStore(self.home).list_skills():
                name = skill['name'].lower()
                if name in seen: continue
                if not skill.get('enabled') or (skill.get('roles') is not None and (session.personaId or 'general') not in skill['roles']): continue
                seen.add(name)
                if name in names:
                    parts.append(TextPart(text='<skill name="' + skill['name'] + '">\n' + skill['instructions'] + '\n</skill>'))
        if session.restoreNote:
            from mvvm.models.chat_models import TextPart
            parts.append(TextPart(text=session.restoreNote))
            session.restoreNote = None
        vm = self.vm_for(session_id)
        # ViewModel 的 run_turn 自己落盘用户消息并写标题；这里只为 turn_start 准备展示形态。
        turn_id = uuid.uuid4().hex
        turn = _Turn(
            turn_id=turn_id,
            session_id=session_id,
            vm=vm,
            cancel=CancelToken(),
            started_at=int(time.time() * 1000),
        )
        with self._turns_lock:
            self._turns[turn_id] = turn
            self._session_turn[session_id] = turn_id

        if session.archived:
            self.store.set_archived(session.id, False)
        # 本轮用户消息的完整形状：附件块 → 待办说明块 → 提问正文（与 ViewModel 落盘的顺序一致）。
        # turn_start 展示形态在起线程**之前**算好：线程会立刻改写历史，事后再算容易把上一轮的
        # assistant 段也算进来；先算则与「本轮第一事件」的语义严格对齐。
        note_parts = self._turn_notes(session)
        user_display = _pending_user_display(
            session.messages, [*note_parts, *parts], question
        )
        self._emit(
            {"turnId": turn_id, "sessionId": session_id, "event": {"type": "turn_start", "user": user_display}}
        )

        from mvvm.services.rewind import Rewind
        Rewind(self.home, session_id).begin(session)
        thread = vm.start_turn(
            text, cancel=turn.cancel, parts=parts or None, question=question
        )
        turn.thread = thread
        self._watch(turn)
        return {"turnId": turn_id}

    def _turn_notes(self, session: Any) -> list[Any]:
        """本轮随用户消息带出的系统说明块（待办取消告知 / 遗留清单提醒）。

        只用于算 `turn_start` 的展示形状：真正的落盘与「用一次即清」在 ViewModel 里做，
        这里读的是同一份边车，不写状态。
        """
        from mvvm.models.chat_models import TextPart
        from mvvm.services.todos import todo_reminder_text

        out: list[Any] = []
        if session.todoCancelNote:
            out.append(TextPart(text=session.todoCancelNote))
        reminder = todo_reminder_text(session.todos, session.todoCancelled)
        if reminder:
            out.append(TextPart(text=reminder))
        return out

    def _watch(self, turn: _Turn) -> None:
        """回合线程结束后清注册表并推 done 的收尾（ViewModel 已推过 done，这里只清状态）。"""

        def join() -> None:
            thread = turn.thread
            if thread is not None:
                thread.join()
            # ViewModel 在异常分支不推 done（它只推 error）；渲染层靠 done 收尾，
            # 缺了就会一直显示「正在输出」。这里按错误语义补一条，绝不静默留白。
            if not turn.done_sent:
                turn.done_sent = True
                self._emit(
                    {
                        "turnId": turn.turn_id,
                        "sessionId": turn.session_id,
                        "event": {
                            "type": "done",
                            "stopReason": "error",
                            "durationMs": max(0, int(time.time() * 1000) - turn.started_at),
                        },
                    }
                )
            self._members.finished(turn.session_id)
            with self._turns_lock:
                self._turns.pop(turn.turn_id, None)
                if self._session_turn.get(turn.session_id) == turn.turn_id:
                    self._session_turn.pop(turn.session_id, None)

        threading.Thread(target=join, name=f"chat-watch-{turn.turn_id[:8]}", daemon=True).start()

    def is_busy(self, session_id: str) -> bool:
        with self._turns_lock:
            turn = self._turns.get(self._session_turn.get(session_id, ""))
        if turn is None:
            return False
        if turn.vm.busy:
            return True
        return turn.thread is not None and turn.thread.is_alive()

    # ── chat:abort ────────────────────────────────────────────────────────
    def shutdown(self) -> None:
        with self._turns_lock:
            turns = list(self._turns)
        for turn_id in turns:
            self.abort(turn_id)
        for vm in list(self._vms.values()):
            vm.tools.close()

    def abort(self, turn_id: Any) -> dict[str, bool]:
        """`chat:abort`：按 turnId 取消对应回合；未知 turnId 无副作用（原版恒回 ok:true）。"""
        key = _as_str(turn_id)
        with self._turns_lock:
            turn = self._turns.get(key)
        if turn is not None:
            turn.aborted = True
            # 直接作用于本轮自己的取消标记：`vm.cancel()` 只在 `vm.busy` 为真时生效，而 busy
            # 由 UI 线程 drain 才更新；走标记可以立即止损。
            if turn.cancel is not None:
                turn.cancel.cancel()
            turn.vm.cancel()
        return {"ok": True}

    # ── 会话与写路径 ──────────────────────────────────────────────────────
    def create_session(self, request: Any) -> dict[str, bool]:
        """`chat:create-session`：立即落盘，空对话跨重启存活。"""
        payload = request if isinstance(request, dict) else {}
        session_id = _as_str(payload.get("sessionId"))
        if not session_id:
            raise BridgeError(tr('legacy.b2e079b9ad36'))
        session = self.store.ensure_session(
            session_id,
            persona_id=_optional_str(payload.get("personaId")),
            focus_root=_optional_str(payload.get("focusRoot")),
            model=_optional_str(payload.get("modelRef")),
        )
        self.store.save(session.id)
        self.vm_for(session.id)
        self._emit_sessions_changed()
        return {"ok": True}

    def set_model(self, request: Any) -> dict[str, bool]:
        payload = request if isinstance(request, dict) else {}
        session_id = _as_str(payload.get("sessionId"))
        ok = self.store.set_model(session_id, _optional_str(payload.get("modelRef")))
        return {"ok": ok}

    def set_effort(self, request: Any) -> dict[str, bool]:
        """原版：会话不存在或档位非法 → 不动，仍回 `{ok:true}`。"""
        payload = request if isinstance(request, dict) else {}
        session_id = _as_str(payload.get("sessionId"))
        effort = payload.get("effort")
        if session_id and isinstance(effort, str) and effort in EFFORT_LEVELS:
            self.store.set_effort(session_id, effort)
        return {"ok": True}

    def set_focus(self, request: Any) -> dict[str, bool]:
        payload = request if isinstance(request, dict) else {}
        session_id = _as_str(payload.get("sessionId"))
        if session_id:
            self.store.set_focus(session_id, _optional_str(payload.get("focusRoot")))
        return {"ok": True}

    def rename_session(self, request: Any) -> Optional[dict[str, str]]:
        """`chat:rename-session`：空标题恢复自动标题；未建档返回 null。"""
        payload = request if isinstance(request, dict) else {}
        session_id = _as_str(payload.get("sessionId"))
        session = self.store.load_session(session_id) if session_id else None
        if session is None:
            return None
        title = " ".join(_as_str(payload.get("title")).split())[:TITLE_MAX]
        if not title:
            first = next((m for m in display_messages(session.messages) if m.get("role") == "user"
                          and not m.get("notify")), None)
            if first is not None:
                title = derive_title(_as_str(first.get("text"))) or derive_title(
                    " ".join(str(a.get("name", "")) for a in first.get("attachments") or [])
                )
        self.store.rename_session(session.id, title)
        self._emit_sessions_changed()
        return {"title": title}

    def set_archived(self, request: Any) -> dict[str, bool]:
        """`chat:set-archived`：忙碌会话拒绝归档（渲染层据此复原清单）。"""
        payload = request if isinstance(request, dict) else {}
        session_id = _as_str(payload.get("sessionId"))
        if not session_id:
            return {"ok": False}
        if self.is_busy(session_id):
            return {"ok": False}
        if self.store.load_session(session_id) is None:
            return {"ok": False}
        self.store.set_archived(session_id, payload.get("archived") is True)
        self._emit_sessions_changed()
        return {"ok": True}

    def delete_session(self, session_id: Any, workspace_root: Any = None) -> dict[str, bool]:
        """`chat:delete-session`：先中止该会话的进行中回合，再删文件。恒回 ok:true。"""
        del workspace_root
        key = _as_str(session_id)
        if key:
            with self._turns_lock:
                turn_id = self._session_turn.get(key)
            if turn_id:
                self.abort(turn_id)
            self._vms.pop(key, None)
            self.store.delete_session(key)
            self._emit_sessions_changed()
        return {"ok": True}

    def reset(self, session_id: Any, workspace_root: Any = None) -> dict[str, bool]:
        """`chat:reset`：清空消息与回合边车，刷新 updatedAt；会话不存在也回 ok:true。"""
        del workspace_root
        key = _as_str(session_id)
        if key and self.store.reset_messages(key):
            self._emit_sessions_changed()
        return {"ok": True}

    def delete_turns(self, session_id: Any, workspace_root: Any = None, turns: Any = None) -> list[dict[str, Any]]:
        """`chat:delete-turns`：按轮删消息，返回重建后的 DisplayMessage[]。"""
        del workspace_root
        key = _as_str(session_id)
        indices = [t for t in turns if isinstance(t, int)] if isinstance(turns, list) else []
        messages = self.store.delete_turns(key, indices) if key else None
        if messages is None:
            return []
        self._emit({"turnId": "", "sessionId": key, "event": {"type": "todos", "state": self.todos(key)["active"]}})
        return display_messages(messages)

    def rewind(self, session_id, action, turn=0, mode='both'):
        from mvvm.services.rewind import Rewind
        from mvvm.services.chat_session_store import is_genuine_user_turn
        import copy
        session = self.store.load_session(session_id)
        if session is None or self.is_busy(session_id):
            raise ValueError('会话不存在或正在运行')
        service = Rewind(self.home, session_id)
        starts = [i for i, message in enumerate(session.messages) if is_genuine_user_turn(message)]
        if not hasattr(self, '_rewind_undo'): self._rewind_undo = {}
        if action == 'list':
            return {'turns':[{'turn':i, 'text':str(session.messages[start].content)[:100]} for i,start in enumerate(starts)], 'canUndo':session_id in self._rewind_undo}
        if action == 'undo':
            saved = self._rewind_undo.get(session_id)
            if not saved: raise ValueError('没有可撤销的回滚')
            service.undo(saved['files'])
            session.__dict__.update(copy.deepcopy(saved['state'].__dict__))
            service.save(saved['journal'])
            del self._rewind_undo[session_id]
        else:
            if type(turn) is not int or turn < 0 or turn >= len(starts): raise ValueError('无效回合')
            if action == 'preview':
                plan = service.preview(turn)
                return {'files':[{k:v for k,v in row.items() if k not in ('pre','post')} for row in plan['files']], 'commands':plan['commands']}
            if action != 'apply' or mode not in ('both', 'code', 'conversation'): raise ValueError('无效回滚操作')
            saved = {'state':copy.deepcopy(session), 'journal':service.read(), 'files':[]}
            if mode in ('both', 'code'):
                saved['files'] = service.apply(turn)
                journal = service.read()
                restored = {r['path']:r['post'] for r in saved['files']}
                for row in journal['records']:
                    if row.get('path') in restored: row['post'] = restored[row['path']]
                service.save(journal)
                if mode == 'code' and restored:
                    session.restoreNote = '用户已恢复文件：' + ', '.join(restored)

            if mode in ('both', 'conversation'):
                self.store.delete_turns(session_id, list(range(turn,len(starts))))
                journal = service.read(); journal['records'] = [r for r in journal['records'] if r['turn'] < turn]; service.save(journal)
            self._rewind_undo[session_id] = saved
        self.store.save(session_id)
        self._emit_sessions_changed()
        return {'ok':True}

    def todos(self, session_id: Any) -> dict[str, Any]:
        """`chat:todos`：只读当前清单。"""
        key = _as_str(session_id)
        session = self.store.load_session(key) if key else None
        if session is None:
            return {"active": None}
        return {"active": active_todo_list(session.todos, session.todoCancelled)}

    def cancel_todos(self, session_id: Any) -> dict[str, Any]:
        """`chat:todo-cancel`：不忙时才受理；返回最新状态。"""
        key = _as_str(session_id)
        session = self.store.load_session(key) if key else None
        if session is None:
            return {"active": None}
        if not self.is_busy(key):
            self.vm_for(key).cancel_todos()
            session = self.store.load_session(key) or session
        return {"active": active_todo_list(session.todos, session.todoCancelled)}

    # ── chat:compact ──────────────────────────────────────────────────────
    def compact(self, request: Any) -> dict[str, str]:
        """`chat:compact`：立即返回 turnId，压缩在后台跑（原版同语义）。

        `compacting` / `compacted` 由 ViewModel 推；这里在收尾时补 `done{stopReason:'end_turn'}`，
        与原版 `finally` 里的那条一致（渲染层据 done 收起进行中状态）。
        """
        payload = request if isinstance(request, dict) else {}
        session_id = _as_str(payload.get("sessionId"))
        if not session_id:
            raise BridgeError(tr('legacy.105260295be9'))
        if self.store.load_session(session_id) is None:
            raise BridgeError(tr('legacy.c93accfa32ee' ,p1=session_id))
        if self.is_busy(session_id):
            raise BridgeError(tr(BUSY_MESSAGE))
        vm = self.vm_for(session_id)
        turn_id = uuid.uuid4().hex
        turn = _Turn(
            turn_id=turn_id,
            session_id=session_id,
            vm=vm,
            started_at=int(time.time() * 1000),
        )
        with self._turns_lock:
            self._turns[turn_id] = turn
            self._session_turn[session_id] = turn_id

        def run() -> None:
            try:
                asyncio.run(vm.compact_now())
            except Exception as exc:  # noqa: BLE001 - 回合边界：异常必须变成界面可见的错误
                self._emit(
                    {
                        "turnId": turn_id,
                        "sessionId": session_id,
                        "event": {"type": "error", "kind": "server", "message": tr('finish.ui.0397d985c3b2', p1=exc)},
                    }
                )
            finally:
                if not turn.done_sent:
                    turn.done_sent = True
                    self._emit(
                        {
                            "turnId": turn_id,
                            "sessionId": session_id,
                            "event": {
                                "type": "done",
                                "stopReason": "end_turn",
                                "durationMs": max(0, int(time.time() * 1000) - turn.started_at),
                            },
                        }
                    )
                with self._turns_lock:
                    self._turns.pop(turn_id, None)
                    if self._session_turn.get(session_id) == turn_id:
                        self._session_turn.pop(session_id, None)
                self._emit_sessions_changed()

        thread = threading.Thread(target=run, name="chat-compact", daemon=True)
        turn.thread = thread
        thread.start()
        return {"turnId": turn_id}

    # ── attach-session ────────────────────────────────────────────────────
    def attach(self, session_id: Any) -> dict[str, Any]:
        """`chat:attach-session`：历史 + 进行中回合（同一时刻取出）。"""
        key = _as_str(session_id)
        session = self.store.load_session(key) if key else None
        messages = display_messages(session.messages) if session is not None else []
        with self._turns_lock:
            turn_id = self._session_turn.get(key)
            turn = self._turns.get(turn_id) if turn_id else None
        return {
            "messages": messages,
            "turnId": turn.turn_id if turn is not None else None,
            "startedAt": turn.started_at if turn is not None else None,
        }


# ── 事件形状转换 ──────────────────────────────────────────────────────────
def to_chat_event(turn_id: str, session_id: str, event: dict[str, Any]) -> Optional[dict[str, Any]]:
    """ChatViewModel 的简化事件 → Deva `ChatEventPayload {turnId, sessionId, event}`。

    返回 None 表示该事件在渲染层没有对应物（当前没有这类事件，保留扩展位）。

    形状差异逐条对位（见 `docs/audit/contracts-chat.md` 的 `chat:event`）：
    - `done{stop}` → `done{stopReason}`（渲染层 `appendTerminalNotice(ev.stopReason)`）；
    - `tool_result.is_error` → `isError`（渲染层按 camelCase 判定工具卡状态）；
    - `tool_call` 的 `id` 来自 `ChatViewModel`（它推 `{type,id,name,input}`），渲染层按这个 id
      把随后的 `tool_result` 回填到同一张工具卡上。
    """
    kind = event.get("type")
    if not isinstance(kind, str):
        return None
    body: dict[str, Any]
    if kind == "user":
        # ViewModel 在落盘后推 user；turn_start 已由宿主在起回合前推过，这里不再重复。
        return None
    if kind == "done":
        body = {"type": "done", "stopReason": _stop_reason(event.get("stop"))}
    elif kind == "tool_result":
        body = {
            "type": "tool_result",
            "id": _as_str(event.get("id")),
            "name": _as_str(event.get("name")),
            "summary": _as_str(event.get("summary")),
            "isError": bool(event.get("is_error")),
        }
    elif kind == "tool_call":
        body = {
            "type": "tool_call",
            "id": _as_str(event.get("id")),
            "name": _as_str(event.get("name")),
            "args": event.get("input") if isinstance(event.get("input"), dict) else {},
        }
    elif kind == "error":
        body = {"type": "error", "kind": "server", "message": _as_str(event.get("message"))}
    else:
        # text_delta / thinking_delta / todos / todo_done / compacting / compacted 形状一致。
        body = dict(event)
    return {"turnId": turn_id, "sessionId": session_id, "event": body}


# ViewModel 的回合结束原因 → Deva 的 StopReason
_STOP_REASONS = {
    "end_turn": "end_turn",
    "aborted": "aborted",
    "error": "error",
    "max_steps": "max_steps",
}


def _stop_reason(value: Any) -> str:
    text = _as_str(value)
    return _STOP_REASONS.get(text, text or "end_turn")


def _adapter_of(model: Any) -> str:
    """`chat:send` 入参里的适配器名；缺省按 anthropic（原版 model.adapter 必填）。"""
    if isinstance(model, dict):
        adapter = model.get("adapter")
        if isinstance(adapter, str) and adapter:
            return adapter
    return "anthropic"


def _pending_user_display(
    stored: list[Any], parts: list[Any], question: str
) -> dict[str, Any]:
    """本轮用户消息的展示形态（turn_start.user）。

    与历史重建走**同一个函数**：把「附件内容块 + 提问正文」拼成临时的 user 消息，
    再用 `display_messages` 转换，`index_base` 取它在整份记录里的下标——这样图片 ref
    与重开历史时算出的 ref 完全一致（原版 `emitTurnStart` 也复用了 `toDisplayMessages`）。
    """
    from mvvm.models.chat_models import Message, TextPart

    synthetic = Message(role="user", content=[*parts, TextPart(text=question)])
    displayed = display_messages([synthetic], index_base=len(stored))
    if displayed and displayed[0].get("role") == "user":
        return displayed[0]
    return {"role": "user", "text": question, "attachments": []}


def _as_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _optional_str(value: Any) -> Optional[str]:
    return value if isinstance(value, str) and value else None


__all__ = [
    "ATTACHMENT_ONLY_QUESTION",
    "BUSY_MESSAGE",
    "ChatHost",
    "EFFORT_LEVELS",
    "TITLE_MAX",
    "to_chat_event",
]
