"""会话持久化：Deva 文件格式的读写、索引自愈、重启读回。

这些测试只碰临时目录，不读真实的 `~/.deva`；「重启」用换一个 Store 实例模拟，
并被 test_store_reads_back_after_restart 固定成一条端到端断言。
"""
from __future__ import annotations

import json

import pytest

from mvvm.models.chat_models import Message, StoredSession, TextPart
from mvvm.services.chat_session_store import (
    INDEX_FILE,
    ChatSessionStore,
    derive_title,
    safe_id,
)


@pytest.fixture()
def store(tmp_path):
    return ChatSessionStore(tmp_path)


def test_derive_title_matches_deva_rules():
    assert derive_title("  你好   世界  ") == "你好 世界"
    assert derive_title("x" * 30) == "x" * 30
    assert derive_title("x" * 31) == "x" * 30 + "…"
    assert derive_title("   ") == ""


def test_safe_id_strips_path_characters():
    assert safe_id("../../etc/passwd") == "etcpasswd"
    assert safe_id("abc-123_X") == "abc-123_X"
    with pytest.raises(ValueError):
        safe_id("../..")


def test_create_append_and_read_back(store):
    store.ensure_session("s1")
    store.append_message("s1", Message(role="user", content=[TextPart(text="你好，介绍一下自己")]))

    # 同一实例内读回
    session = store.load_session("s1")
    assert session is not None
    assert [m.text() for m in session.messages] == ["你好，介绍一下自己"]
    assert session.title == "你好，介绍一下自己"

    # 目录里真的有一对话一文件 + 索引
    assert (store.chats_dir / "s1.json").is_file()
    index = json.loads((store.chats_dir / INDEX_FILE).read_text(encoding="utf-8"))
    assert [m["id"] for m in index] == ["s1"]
    assert "messages" not in index[0]  # 索引只存元信息


def test_store_reads_back_after_restart(store, tmp_path):
    store.ensure_session("s1")
    store.append_message("s1", Message(role="user", content="重启前说的话"))
    store.append_message("s1", Message(role="assistant", content="重启前的回答"))

    # 「重启」= 全新 Store 实例指向同一目录（内存缓存与索引缓存都丢了）
    restarted = ChatSessionStore(tmp_path)
    session = restarted.load_session("s1")
    assert session is not None
    assert [m.text() for m in session.messages] == ["重启前说的话", "重启前的回答"]
    assert restarted.list_sessions()[0].id == "s1"


def test_ensure_session_is_idempotent_and_memory_first(store):
    first = store.ensure_session("s2")
    assert first.messages == []
    # Deva 语义：新建只进内存与索引，首次 save 才落盘
    assert not (store.chats_dir / "s2.json").exists()
    second = store.ensure_session("s2")
    assert second is first
    assert store.list_sessions()[0].title == ""


def test_index_is_rebuilt_from_session_files_when_missing(store):
    store.ensure_session("a")
    store.append_message("a", Message(role="user", content="A"))
    store.ensure_session("b")
    store.append_message("b", Message(role="user", content="B"))
    (store.chats_dir / INDEX_FILE).unlink()

    rebuilt = ChatSessionStore(store._home)  # 新实例没有索引缓存
    ids = sorted(m.id for m in rebuilt.list_sessions())
    assert ids == ["a", "b"]


def test_corrupt_index_falls_back_to_scan(store):
    store.ensure_session("a")
    store.append_message("a", Message(role="user", content="A"))
    (store.chats_dir / INDEX_FILE).write_text("{not json", encoding="utf-8")

    rebuilt = ChatSessionStore(store._home)
    assert [m.id for m in rebuilt.list_sessions()] == ["a"]


def test_corrupt_session_file_is_skipped_not_fatal(store):
    store.ensure_session("good")
    store.append_message("good", Message(role="user", content="ok"))
    (store.chats_dir / "bad.json").write_text("oops", encoding="utf-8")
    (store.chats_dir / INDEX_FILE).unlink()

    rebuilt = ChatSessionStore(store._home)
    assert [m.id for m in rebuilt.list_sessions()] == ["good"]


def test_list_sessions_orders_by_updated_at_and_hides_archived(store):
    store.ensure_session("old")
    store.append_message("old", Message(role="user", content="旧"))
    store.ensure_session("new")
    store.append_message("new", Message(role="user", content="新"))
    # 手工把 old 的 updatedAt 调大，验证排序看字段而不是插入顺序
    session = store.load_session("old")
    session.updatedAt = session.updatedAt + 10_000
    store.save("old")

    assert [m.id for m in store.list_sessions()] == ["old", "new"]
    store.set_archived("old", True)
    assert [m.id for m in store.visible_sessions()] == ["new"]


def test_rename_keeps_updated_at(store):
    store.ensure_session("s")
    store.append_message("s", Message(role="user", content="原标题"))
    before = store.load_session("s").updatedAt
    store.rename_session("s", "新标题")
    after = store.load_session("s")
    assert after.title == "新标题"
    assert after.updatedAt == before


def test_delete_removes_file_and_index_entry(store):
    store.ensure_session("s")
    store.append_message("s", Message(role="user", content="x"))
    chunk = store.chats_dir / "s.compacted-abc.jsonl"
    chunk.write_text("", encoding="utf-8")

    assert store.delete_session("s") is True
    assert not (store.chats_dir / "s.json").exists()
    assert not chunk.exists()
    assert store.list_sessions() == []
    assert store.delete_session("s") is False


def test_reads_deva_legacy_fields_and_preserves_unknown(store):
    """Deva 历史文件里有 bucket 等已废弃字段：读进来不报错，写回去也不丢。"""
    raw = {
        "id": "legacy",
        "title": "旧对话",
        "createdAt": 1,
        "updatedAt": 2,
        "messages": [{"role": "user", "content": "hi"}],
        "bucket": "project-1",
        "focusRoot": "/tmp/work",
        "archived": False,
    }
    (store.chats_dir / "legacy.json").write_text(json.dumps(raw), encoding="utf-8")
    session = store.load_session("legacy")
    assert session.focusRoot == "/tmp/work"
    assert session.model_extra["bucket"] == "project-1"

    store.append_message("legacy", Message(role="assistant", content="hello"))
    written = json.loads((store.chats_dir / "legacy.json").read_text(encoding="utf-8"))
    assert written["bucket"] == "project-1"
    assert [m["role"] for m in written["messages"]] == ["user", "assistant"]


def test_compacted_chunks_are_stitched_back(store):
    """压缩拆分存盘：主文件只存后段，前段在 .compacted-*.jsonl 里，载入时拼回。"""
    main = {
        "id": "c1",
        "title": "压缩过的对话",
        "createdAt": 1,
        "updatedAt": 2,
        "messages": [{"role": "assistant", "content": "后段"}],
        "compacted": {"count": 1, "file": "c1.compacted-x.jsonl"},
        "notices": [{"after": 2, "kind": "notice", "code": "truncated"}],
    }
    (store.chats_dir / "c1.json").write_text(json.dumps(main), encoding="utf-8")
    (store.chats_dir / "c1.compacted-x.jsonl").write_text(
        json.dumps({"role": "user", "content": "前段"}) + "\n", encoding="utf-8"
    )
    session = store.load_session("c1")
    assert [m.text() for m in session.messages] == ["前段", "后段"]
    assert session.compacted is None  # 内存里已拼回完整记录


def test_missing_compacted_chunk_shifts_notices_and_keeps_loading(store):
    main = {
        "id": "c2",
        "title": "",
        "createdAt": 1,
        "updatedAt": 2,
        "messages": [{"role": "assistant", "content": "后段"}],
        "compacted": {"count": 3, "file": "c2.compacted-gone.jsonl"},
        "notices": [
            {"after": 1, "kind": "notice", "code": "truncated"},
            {"after": 4, "kind": "error", "message": "失败"},
        ],
    }
    (store.chats_dir / "c2.json").write_text(json.dumps(main), encoding="utf-8")
    session = store.load_session("c2")
    assert [m.text() for m in session.messages] == ["后段"]
    assert [n.after for n in session.notices] == [1]  # 4 - 3 = 1，1 - 3 < 0 被丢弃


def test_save_without_loaded_session_raises(store):
    with pytest.raises(KeyError):
        store.save("never-loaded")


def test_round_trip_preserves_tool_parts(tmp_path):
    store = ChatSessionStore(tmp_path)
    store.ensure_session("t")
    store.append_message(
        "t",
        Message(
            role="assistant",
            content=[
                TextPart(text="查一下"),
                {
                    "type": "tool_use",
                    "id": "call_1",
                    "name": "read_file",
                    "input": {"path": "a.txt"},
                },
            ],
        ),
    )
    session = StoredSession.model_validate_json(
        (store.chats_dir / "t.json").read_text(encoding="utf-8")
    )
    assert session.messages[0].content[1].name == "read_file"
