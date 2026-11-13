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


# ── 拆分存盘（压缩后）────────────────────────────────────────────────────────────
def _compacted_messages() -> list[Message]:
    """一条已压缩的对话：摘要 + 三轮问答。模型视图从摘要起，前面两轮（含摘要）拆出去。"""
    return [
        Message(role="user", content="第一问"),
        Message(role="assistant", content="第一答"),
        Message(role="user", content="第二问"),
        Message(role="assistant", content="第二答"),
        Message(role="user", content="⟦deva:compaction⟧\n摘要：前两轮谈过甲和乙"),
        Message(role="user", content="第三问"),
        Message(role="assistant", content="第三答"),
    ]


def test_save_splits_prefix_into_chunk_and_stitches_back(store):
    session = store.ensure_session("split")
    session.messages = _compacted_messages()
    store.save("split")

    # 模型视图从摘要（下标 4）起：摘要及其之前的内容拆进 .jsonl，主文件只留它之后的部分。
    main = json.loads((store.chats_dir / "split.json").read_text(encoding="utf-8"))
    assert [m["content"] for m in main["messages"]] == ["⟦deva:compaction⟧\n摘要：前两轮谈过甲和乙", "第三问", "第三答"]
    assert main["compacted"]["count"] == 4
    chunk = store.chats_dir / main["compacted"]["file"]
    assert chunk.exists()
    assert [json.loads(line)["content"] for line in chunk.read_text(encoding="utf-8").splitlines()] == [
        "第一问",
        "第一答",
        "第二问",
        "第二答",
    ]
    assert main["compacted"]["file"].startswith("split.compacted-")

    # 换一个 Store 实例（模拟重启）读回完整记录
    reopened = ChatSessionStore(store.home)
    restored = reopened.load_session("split")
    assert [m.text() for m in restored.messages] == ["第一问", "第一答", "第二问", "第二答", "⟦deva:compaction⟧\n摘要：前两轮谈过甲和乙", "第三问", "第三答"]


def test_save_appends_to_existing_chunk_when_prefix_intact(store):
    """切点前移时只追加新压掉的那几条，不换文件；前缀被改动才换新文件。"""
    session = store.ensure_session("append")
    session.messages = _compacted_messages()
    store.save("append")
    first = session.compacted
    assert first is not None
    assert first.count == 4

    # 续聊两条：切点不变，拆分文件不动
    session.messages.append(Message(role="user", content="第四问"))
    session.messages.append(Message(role="assistant", content="第四答"))
    store.save("append")
    assert session.compacted.file == first.file
    assert session.compacted.count == 4

    # 第二次压缩：在保留段之前再插一条摘要（正常由压缩器做，这里直接构造）。
    # 切点前移到 5（把第一份摘要也压掉），前缀对象原样还在 → 只往旧文件追加一行。
    session.messages.insert(5, Message(role="user", content="⟦deva:compaction⟧\n第二份摘要"))
    store.save("append")
    assert session.compacted.file == first.file
    assert session.compacted.count == 5
    chunk_lines = (store.chats_dir / first.file).read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["content"] for line in chunk_lines] == [
        "第一问", "第一答", "第二问", "第二答", "⟦deva:compaction⟧\n摘要：前两轮谈过甲和乙",
    ]

    # 改动已拆出去的那段（修补消息）：旧文件不再可信 → 换新文件整份重写，旧文件删掉
    session.messages[2] = Message(role="user", content="第二问（修补）")
    store.save("append")
    assert session.compacted.file != first.file
    assert not (store.chats_dir / first.file).exists()
    assert len(list(store.chats_dir.glob("append.compacted-*.jsonl"))) == 1


def test_save_rewrites_chunk_when_prefix_changed(store):
    """删掉了前缀里的一条消息：旧拆分文件不再可信，换新文件整份写。"""
    session = store.ensure_session("rewrite")
    session.messages = _compacted_messages()
    store.save("rewrite")
    old_file = session.compacted.file

    del session.messages[0]  # 删掉「第一问」
    store.save("rewrite")
    assert session.compacted.file != old_file
    assert not (store.chats_dir / old_file).exists()

    restored = ChatSessionStore(store.home).load_session("rewrite")
    assert [m.text() for m in restored.messages][0] == "第一答"


def test_save_rejoins_main_file_when_compaction_reverted(store):
    """压缩被撤销（摘要没了）：不再拆分，主文件写全量，旧拆分文件删掉。"""
    session = store.ensure_session("revert")
    session.messages = _compacted_messages()
    store.save("revert")
    chunk = session.compacted.file

    for index, message in enumerate(session.messages):
        if str(message.content).startswith("⟦deva:compaction⟧"):
            del session.messages[index]
            break
    store.save("revert")
    assert session.compacted is None
    assert not (store.chats_dir / chunk).exists()
    main = json.loads((store.chats_dir / "revert.json").read_text(encoding="utf-8"))
    assert len(main["messages"]) == 6


def test_missing_chunk_does_not_delete_other_chunks(store):
    """拆分文件读不出来时保留磁盘上的文件（可能只是暂时被占用），下次还能读回。"""
    main = {
        "id": "keep",
        "title": "",
        "createdAt": 1,
        "updatedAt": 2,
        "messages": [{"role": "assistant", "content": "后段"}],
        "compacted": {"count": 2, "file": "keep.compacted-broken.jsonl"},
    }
    (store.chats_dir / "keep.json").write_text(json.dumps(main), encoding="utf-8")
    # 文件存在但内容坏掉
    (store.chats_dir / "keep.compacted-broken.jsonl").write_text("not json\n", encoding="utf-8")
    store.load_session("keep")
    assert (store.chats_dir / "keep.compacted-broken.jsonl").exists()


def test_base36_matches_js_toString_36():
    from mvvm.services.chat_session_store import base36

    assert base36(0) == "0"
    assert base36(1) == "1"
    assert base36(35) == "z"
    assert base36(36) == "10"
    assert base36(1296) == "100"
