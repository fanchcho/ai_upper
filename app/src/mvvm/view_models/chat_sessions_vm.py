"""会话列表 ViewModel：左侧栏的会话清单与操作（新建 / 切换 / 改名 / 删除 / 归档）。

数据全部来自 `ChatSessionStore`（磁盘是唯一真相），本类只做「列表 → 展示条目」的
投影与操作后的刷新；不含 Qt，可纯 Python 测试。

Deva 的列表口径（`services/chat-store.ts`、渲染层 `store/chat.tsx`）：
- 只显示未归档、非成员会话；按 `updatedAt` 倒序；
- 重命名与归档不动 `updatedAt`，所以不会把会话顶到最前；
- 新建会话是**惰性**的：这里只发一个安全的新 id，真正建档发生在首条消息落盘时。
"""
from __future__ import annotations
from locale_runtime import tr

import secrets
import time
from typing import Any

from mvvm.core import BaseViewModel, ObservableProperty, PropertyFactory, RelayCommand
from mvvm.services.chat_session_store import ChatSessionStore


def relative_time(updated_ms: int, now_ms: int | None = None) -> str:
    """`updatedAt` → 中文相对时间（列表副标题）。"""
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    delta = max(0, now - int(updated_ms)) // 1000
    if delta < 60:
        return tr('legacy.9e636642d6d4')
    if delta < 3600:
        return tr('legacy.cca145fe6835' ,p0=delta // 60)
    if delta < 86_400:
        return tr('legacy.f43f266bd07f' ,p0=delta // 3600)
    if delta < 86_400 * 30:
        return tr('legacy.9c439091a115' ,p0=delta // 86400)
    return time.strftime("%Y-%m-%d", time.localtime(updated_ms / 1000))


def _entry(meta: Any, active_id: str = "") -> dict[str, Any]:
    return {
        "id": meta.id,
        "title": meta.title or tr('legacy.8200c3d50b95'),
        "subtitle": relative_time(meta.updatedAt),
        "updated_at": meta.updatedAt,
        "active": meta.id == active_id,
    }


class ChatSessionsViewModel(BaseViewModel):
    """左侧会话列表的状态与命令。"""

    def __init__(self, store: ChatSessionStore) -> None:
        self.store = store
        self._active_id = ""
        super().__init__()
        self.refresh()

    # ── 属性 ──────────────────────────────────────────────────────────────
    def _initialize_properties(self) -> None:
        self.sessions_property = PropertyFactory.create([], "sessions")
        self._register_property("sessions", self.sessions_property)

        self.active_id_property = PropertyFactory.create("", "active_id")
        self._register_property("active_id", self.active_id_property)

        self.new_command = RelayCommand(execute=self.new_session)
        self.refresh_command = RelayCommand(execute=self.refresh)

    @property
    def sessions(self) -> list[dict[str, Any]]:
        return list(self.sessions_property.get_value() or [])

    @property
    def active_id(self) -> str:
        return str(self.active_id_property.get_value() or "")

    # ── 读 ────────────────────────────────────────────────────────────────
    def refresh(self) -> int:
        """重读磁盘索引；返回列表条数。"""
        metas = self.store.visible_sessions()
        entries = [_entry(meta, self.active_id) for meta in metas]
        self.sessions_property.set_value(entries)
        return len(entries)

    # ── 命令 ──────────────────────────────────────────────────────────────
    def new_session(self, parameter: Any = None) -> str:
        """发一个新会话 id（惰性建档：首条消息落盘时才真正写文件）。"""
        session_id = self.new_session_id()
        self.set_active(session_id)
        return session_id

    def new_session_id(self) -> str:
        """与 Deva 同形的新 id：`sess_<时间 36 进制>_<随机>`，只含文件名安全字符。"""
        stamp = _base36(time.time() * 1000)
        return f"sess_{stamp}_{secrets.token_hex(3)}"

    def set_active(self, session_id: str) -> None:
        self._active_id = session_id
        self.active_id_property.set_value(session_id)
        self.sessions_property.set_value(
            [{**item, "active": item["id"] == session_id} for item in self.sessions]
        )

    def rename(self, session_id: str, title: str) -> bool:
        title = str(title or "").strip()
        if not title:
            return False
        self.store.rename_session(session_id, title)
        self.refresh()
        return True

    def archive(self, session_id: str, archived: bool = True) -> bool:
        self.store.set_archived(session_id, archived)
        self.refresh()
        return True

    def delete(self, session_id: str) -> bool:
        deleted = self.store.delete_session(session_id)
        if deleted and self._active_id == session_id:
            self._active_id = ""
            self.active_id_property.set_value("")
        self.refresh()
        return deleted


def _base36(value: float) -> str:
    number = int(value)
    if number <= 0:
        return "0"
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out: list[str] = []
    while number:
        number, rem = divmod(number, 36)
        out.append(digits[rem])
    return "".join(reversed(out))


__all__ = ["ChatSessionsViewModel", "relative_time"]
