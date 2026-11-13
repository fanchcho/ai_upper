"""会话 ViewModel：左侧列表的增删改查，与聊天 ViewModel 的切换协作。

Deva 的列表语义（`services/chat-store.ts` + 渲染层 `store/chat.tsx`）：
- 新建会话以「首条消息落盘」为建档时机（惰性建档），不在点「新建」时就落盘；
- 列表按 `updatedAt` 倒序，重命名/归档不改 `updatedAt`；
- 归档项不出现在列表里；删除后若当前会话被删，界面要切到最近一条或回到空态。
"""
from __future__ import annotations

import time

from mvvm.models.chat_models import Message
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.view_models.chat_sessions_vm import ChatSessionsViewModel


def make_store(tmp_path) -> ChatSessionStore:
    return ChatSessionStore(tmp_path / "home")


def seed(store: ChatSessionStore, session_id: str, title: str, *, age_ms: int = 0):
    session = store.ensure_session(session_id)
    session.messages.append(Message(role="user", content=title))
    session.title = title
    store.save(session_id)
    if age_ms:
        session.updatedAt = int(time.time() * 1000) - age_ms
        store.save(session_id)
    return session


def test_initial_list_shows_visible_sessions_newest_first(tmp_path):
    store = make_store(tmp_path)
    seed(store, "a", "甲", age_ms=10_000)
    seed(store, "b", "乙")
    vm = ChatSessionsViewModel(store)
    assert [item["title"] for item in vm.sessions] == ["乙", "甲"]
    assert vm.sessions[0]["id"] == "b"
    assert vm.sessions[0]["active"] is False


def test_archived_sessions_are_hidden(tmp_path):
    store = make_store(tmp_path)
    seed(store, "a", "甲")
    seed(store, "b", "乙")
    vm = ChatSessionsViewModel(store)
    vm.archive("a")
    assert [item["id"] for item in vm.sessions] == ["b"]
    # 取消归档后回到列表（排序按 updatedAt，不因归档往返被顶到最前）
    vm.archive("a", archived=False)
    assert {item["id"] for item in vm.sessions} == {"a", "b"}


def test_rename_keeps_position(tmp_path):
    """重命名不该把会话顶到最前（与 Deva 的 updatedAt 语义一致）。"""
    store = make_store(tmp_path)
    seed(store, "a", "甲", age_ms=10_000)
    seed(store, "b", "乙")
    vm = ChatSessionsViewModel(store)
    vm.rename("a", "甲（改名）")
    assert [item["id"] for item in vm.sessions] == ["b", "a"]
    assert vm.sessions[1]["title"] == "甲（改名）"


def test_delete_removes_from_list_and_disk(tmp_path):
    store = make_store(tmp_path)
    seed(store, "a", "甲")
    seed(store, "b", "乙")
    vm = ChatSessionsViewModel(store)
    assert vm.delete("a") is True
    assert [item["id"] for item in vm.sessions] == ["b"]
    assert not store.session_path("a").exists()
    assert vm.delete("a") is False  # 再删一次：明确返回 False，不抛错


def test_active_session_is_marked(tmp_path):
    store = make_store(tmp_path)
    seed(store, "a", "甲")
    seed(store, "b", "乙")
    vm = ChatSessionsViewModel(store)
    vm.set_active("a")
    flags = {item["id"]: item["active"] for item in vm.sessions}
    assert flags == {"a": True, "b": False}
    assert vm.active_id == "a"


def test_refresh_picks_up_sessions_written_elsewhere(tmp_path):
    """别的入口（新建会话的首条消息）落盘后，列表刷新就能看到。"""
    store = make_store(tmp_path)
    vm = ChatSessionsViewModel(store)
    assert vm.sessions == []
    seed(store, "late", "新来的")
    assert vm.refresh() == 1
    assert vm.sessions[0]["id"] == "late"


def test_subtitle_shows_relative_time_and_empty_hint(tmp_path):
    store = make_store(tmp_path)
    seed(store, "a", "甲")
    vm = ChatSessionsViewModel(store)
    item = vm.sessions[0]
    assert item["subtitle"] in ("刚刚", "1 分钟前", "刚刚更新")
    vm.set_active("a")
    assert vm.sessions[0]["active"] is True


def test_new_session_id_is_unique_and_filename_safe(tmp_path):
    store = make_store(tmp_path)
    vm = ChatSessionsViewModel(store)
    first = vm.new_session_id()
    second = vm.new_session_id()
    assert first != second
    assert all(ch.isalnum() or ch in "_-" for ch in first)
