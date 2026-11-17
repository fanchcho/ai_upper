"""宿主 `ChatHost` 的写路径：会话生命周期、事件形状、压缩、待办、受信根。

**为什么存在**：原 `app/tests/test_web_chat_write.py` 经已删除的 `DevaBridge`
（QtWebChannel）调用同一套宿主方法；桥删掉后，那批用例跟着消失，但宿主本身
**仍在生产路径上**——QML 壳的 `send` / `newSession` / `openSession` 走的就是这里的
`send` / `create_session` / `attach`。本文件把「不是通道形状、而是宿主行为」的那部分
覆盖原样接回来，入口改为直接调宿主方法（QML 壳同一条路径）。

不属于本文件的：网络协议解析（`test_anthropic_provider.py` 等）、
压缩算法（`test_compaction.py`）、存储层（`test_chat_session_store.py`）。
传输一律 `ScriptedTransport`（离线 SSE），本文件不访问网络。
"""
from __future__ import annotations

import asyncio
import threading
import time

import pytest

from mvvm.models.chat_models import Message
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.settings_service import SettingsService
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.webui.assembly import build_chat_host
from mvvm.webui.host import BUSY_MESSAGE, to_chat_event

from scripted_transport import ScriptedTransport, sse

MODELS = {
    "activeModelId": "p1:claude-sonnet-5-5",
    "providers": [
        {
            "id": "p1",
            "adapter": "anthropic",
            "apiHost": "https://api.example.com",
            "enabled": True,
            "models": [
                {"id": "claude-sonnet-5-5", "enabled": True},
                {"id": "claude-haiku-5-5", "enabled": True},
            ],
        }
    ],
}


def text_stream(*chunks: str) -> ScriptedTransport:
    """一段正常收尾的文字流（Anthropic SSE）。"""
    events = [
        sse("message_start", {"type": "message_start", "message": {"usage": {"input_tokens": 10}}}),
        sse(
            "content_block_start",
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        ),
    ]
    for piece in chunks:
        events.append(
            sse(
                "content_block_delta",
                {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": piece}},
            )
        )
    events.append(
        sse(
            "message_delta",
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 3}},
        )
    )
    events.append(sse("message_stop", {"type": "message_stop"}))
    return ScriptedTransport(chunks=events)


def gated_stream(first: str, gate: threading.Event) -> ScriptedTransport:
    """先出一段，再卡住等放行——用来在回合进行中发 abort。"""
    chunks = [
        sse("message_start", {"type": "message_start", "message": {"usage": {"input_tokens": 5}}}),
        sse(
            "content_block_start",
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        ),
        sse(
            "content_block_delta",
            {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": first}},
        ),
    ]

    class Gated(ScriptedTransport):
        async def _body(self):
            for chunk in chunks:
                yield chunk
            deadline = time.time() + 10.0
            while not gate.is_set() and time.time() < deadline:
                await asyncio.sleep(0.01)

    return Gated()


def wait_for(predicate, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


class Rig:
    """一整套真实服务 + 宿主；`emitted` 收宿主推出来的每个事件。"""

    def __init__(self, home, transport):
        self.home = home
        home.mkdir(parents=True, exist_ok=True)
        self.settings = SettingsService(home)
        self.settings.set_config({"models": MODELS})
        self.vault = SecretsVault(home)
        self.vault.set_secret("p1", "sk-test-123")
        self.store = ChatSessionStore(home)
        self.guard = WorkspaceGuard()
        self.emitted: list[tuple[str, object]] = []
        self.host, self.gateway = build_chat_host(
            settings=self.settings,
            vault=self.vault,
            store=self.store,
            guard=self.guard,
            home=home,
            emit=lambda payload: self.emitted.append(("chat:event", payload)),
            emit_sessions_changed=lambda: self.emitted.append(("chat:sessions-changed", None)),
            transport=transport,
        )

    def events(self, kind: str | None = None):
        out = [payload["event"] for channel, payload in self.emitted if channel == "chat:event"]
        return out if kind is None else [event for event in out if event["type"] == kind]

    def sessions_changed(self) -> int:
        return sum(1 for channel, _ in self.emitted if channel == "chat:sessions-changed")


@pytest.fixture()
def rig(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    return Rig(tmp_path / "home", text_stream("你", "好"))


# ── send：流式正文、事件形状、落盘 ────────────────────────────────────────
def test_send_streams_text_and_finishes_with_done(rig):
    result = rig.host.send({"sessionId": "h-1", "text": "你好"})
    assert isinstance(result, dict) and result["turnId"]

    assert wait_for(lambda: any(e["type"] == "done" for e in rig.events()))
    assert wait_for(lambda: not rig.host.is_busy("h-1"))

    kinds = [event["type"] for event in rig.events()]
    assert kinds[0] == "turn_start", "turn_start 必须是本轮第一个事件"
    turn_start = rig.events("turn_start")[0]
    assert turn_start["user"]["role"] == "user"
    assert turn_start["user"]["text"] == "你好"
    assert [event["text"] for event in rig.events("text_delta")] == ["你", "好"]
    done = rig.events("done")[-1]
    assert done["stopReason"] == "end_turn"
    assert isinstance(done["durationMs"], int) and done["durationMs"] >= 0

    # 每条事件都带同一个回合/会话标识（界面据此分派到对应运行时）。
    payloads = [payload for channel, payload in rig.emitted if channel == "chat:event"]
    assert {p["sessionId"] for p in payloads} == {"h-1"}
    assert {p["turnId"] for p in payloads} == {result["turnId"]}

    session = rig.store.load_session("h-1")
    assert session is not None and rig.store.session_path("h-1").exists()
    assert [m.role for m in session.messages] == ["user", "assistant"]
    assert "你好" in str(session.messages[0].content)
    assert session.title == "你好"


def test_send_raises_busy_message_when_turn_running(tmp_path, monkeypatch):
    """同一会话已有一轮在跑时，第二次发送必须被拒绝、文案与原版一致。"""
    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    gate = threading.Event()
    rig = Rig(tmp_path / "busy-home", gated_stream("开头", gate))
    first = rig.host.send({"sessionId": "h-busy", "text": "第一句"})
    assert first["turnId"]
    assert wait_for(lambda: rig.host.is_busy("h-busy"))
    with pytest.raises(Exception) as excinfo:
        rig.host.send({"sessionId": "h-busy", "text": "第二句"})
    assert BUSY_MESSAGE in str(excinfo.value)
    gate.set()
    assert wait_for(lambda: not rig.host.is_busy("h-busy"))


def test_send_without_text_is_rejected_before_anything_is_persisted(rig):
    with pytest.raises(Exception) as excinfo:
        rig.host.send({"sessionId": "h-empty", "text": "   "})
    assert "没有可发送的内容" in str(excinfo.value)
    assert rig.store.load_session("h-empty") is None or not rig.store.load_session("h-empty").messages


# ── abort ────────────────────────────────────────────────────────────────
def test_abort_stops_the_turn_and_reports_aborted(tmp_path, monkeypatch):
    """中止必须在回合进行中生效，并以 `stopReason:'aborted'` 收尾。"""
    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    gate = threading.Event()
    rig = Rig(tmp_path / "abort-home", gated_stream("半截", gate))
    turn = rig.host.send({"sessionId": "h-abort", "text": "说长一点"})

    def saw_delta() -> bool:
        rig.host.drain()
        return any(event["type"] == "text_delta" for event in rig.events())

    assert wait_for(saw_delta)
    assert rig.host.abort(turn["turnId"]) == {"ok": True}
    gate.set()
    assert wait_for(lambda: any(event["type"] == "done" for event in rig.events()))
    assert wait_for(lambda: not rig.host.is_busy("h-abort"))

    done = rig.events("done")[-1]
    assert done["stopReason"] == "aborted"
    # 半截正文已落盘：重开后看得出这一轮被打断。
    session = rig.store.load_session("h-abort")
    assert any("半截" in str(m.content) for m in session.messages if m.role == "assistant")


def test_abort_unknown_turn_is_ok_without_side_effects(rig):
    assert rig.host.abort("nope") == {"ok": True}
    assert rig.events() == []


# ── 会话生命周期 ──────────────────────────────────────────────────────────
def test_create_session_persists_empty_session(rig):
    assert rig.host.create_session({"sessionId": "empty-1", "personaId": "p-1"}) == {"ok": True}
    # 空对话也落盘：跨重启存活（原版 createSession 后立即 saveProject）。
    assert rig.store.session_path("empty-1").exists()
    assert rig.sessions_changed() >= 1


def test_create_session_requires_an_id(rig):
    with pytest.raises(Exception) as excinfo:
        rig.host.create_session({})
    assert "sessionId" in str(excinfo.value)


def test_set_model_and_effort_and_focus_write_session(rig):
    rig.host.create_session({"sessionId": "w-1"})
    assert rig.host.set_model({"sessionId": "w-1", "modelRef": "p1:claude-haiku-5-5"}) == {"ok": True}
    assert rig.host.set_effort({"sessionId": "w-1", "effort": "high"}) == {"ok": True}
    assert rig.host.set_focus({"sessionId": "w-1", "focusRoot": "/tmp/project"}) == {"ok": True}

    session = rig.store.load_session("w-1")
    assert session.model == "p1:claude-haiku-5-5"
    assert session.effort == "high"
    assert session.focusRoot == "/tmp/project"


def test_set_model_on_missing_session_reports_false(rig):
    assert rig.host.set_model({"sessionId": "nope", "modelRef": "p1:claude-haiku-5-5"}) == {"ok": False}


def test_set_effort_illegal_level_is_still_ok(rig):
    """原版语义：非法档位不动会话，但仍回 ok（界面不该因此弹错）。"""
    rig.host.create_session({"sessionId": "w-2"})
    assert rig.host.set_effort({"sessionId": "w-2", "effort": "ultra"}) == {"ok": True}
    assert rig.store.load_session("w-2").effort is None


def test_rename_session_returns_trimmed_title(rig):
    rig.host.create_session({"sessionId": "r-1"})
    assert rig.host.rename_session({"sessionId": "r-1", "title": "  多   空格  标题  "}) == {
        "title": "多 空格 标题"
    }
    assert rig.store.load_session("r-1").title == "多 空格 标题"


def test_rename_missing_session_returns_null(rig):
    assert rig.host.rename_session({"sessionId": "nope", "title": "x"}) is None


def test_set_archived_toggles_and_hides_from_visible_list(rig):
    rig.host.create_session({"sessionId": "a-1"})
    assert rig.host.set_archived({"sessionId": "a-1", "archived": True}) == {"ok": True}
    assert "a-1" not in {meta.id for meta in rig.store.visible_sessions()}
    assert rig.host.set_archived({"sessionId": "a-1", "archived": False}) == {"ok": True}
    assert "a-1" in {meta.id for meta in rig.store.visible_sessions()}


def test_set_archived_refuses_unknown_session(rig):
    assert rig.host.set_archived({"sessionId": "nope", "archived": True}) == {"ok": False}


def test_delete_session_removes_file_and_returns_ok(rig):
    rig.host.create_session({"sessionId": "d-1"})
    assert rig.store.session_path("d-1").exists()
    assert rig.host.delete_session("d-1") == {"ok": True}
    assert not rig.store.session_path("d-1").exists()


def test_reset_clears_messages(rig):
    rig.host.create_session({"sessionId": "rs-1"})
    rig.store.append_message("rs-1", Message(role="user", content="旧内容"))
    assert rig.host.reset("rs-1") == {"ok": True}
    assert rig.store.load_session("rs-1").messages == []


def test_delete_turns_returns_display_messages(rig):
    rig.host.create_session({"sessionId": "dt-1"})
    for role, text in (("user", "第一轮"), ("assistant", "答一"), ("user", "第二轮"), ("assistant", "答二")):
        rig.store.append_message("dt-1", Message(role=role, content=text))
    remaining = rig.host.delete_turns("dt-1", None, [1])
    assert [m["text"] for m in remaining if m["role"] == "user"] == ["第一轮"]
    # 删轮之后宿主会推一条 todos 状态（界面据此刷新清单）。
    assert any(event["type"] == "todos" for event in rig.events())


def test_attach_reports_history_and_no_running_turn(rig):
    rig.host.create_session({"sessionId": "at-1"})
    assert rig.host.attach("at-1") == {"messages": [], "turnId": None, "startedAt": None}


def test_attach_reports_the_running_turn(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    gate = threading.Event()
    rig = Rig(tmp_path / "attach-home", gated_stream("开头", gate))
    turn = rig.host.send({"sessionId": "at-2", "text": "跑着"})
    assert wait_for(lambda: rig.host.is_busy("at-2"))
    attached = rig.host.attach("at-2")
    assert attached["turnId"] == turn["turnId"]
    assert isinstance(attached["startedAt"], int)
    gate.set()
    assert wait_for(lambda: not rig.host.is_busy("at-2"))


# ── 待办 ─────────────────────────────────────────────────────────────────
def _seed_todos(rig, session_id: str, list_id: str = "L1") -> None:
    rig.store.ensure_session(session_id)
    session = rig.store.load_session(session_id)
    session.todos = [
        {
            "listId": list_id,
            "title": "收尾清单",
            "at": 1,
            "items": [
                {"content": "写台账", "status": "pending"},
                {"content": "跑测试", "status": "in_progress"},
            ],
        }
    ]
    session.messages.append(Message(role="user", content="开始"))
    rig.store.save(session_id)


def test_todos_on_missing_session_is_empty(rig):
    assert rig.host.todos("nope") == {"active": None}
    assert rig.host.cancel_todos("nope") == {"active": None}


def test_todos_returns_active_list_shape(rig):
    _seed_todos(rig, "td-1")
    active = rig.host.todos("td-1")["active"]
    assert active["id"] == "L1"
    assert active["title"] == "收尾清单"
    assert [item["content"] for item in active["items"]] == ["写台账", "跑测试"]


def test_todo_cancel_marks_list_and_hides_it(rig):
    _seed_todos(rig, "td-2")
    assert rig.host.todos("td-2")["active"] is not None
    assert rig.host.cancel_todos("td-2") == {"active": None}
    assert rig.store.load_session("td-2").todoCancelled == ["L1"]


# ── 压缩：通道链路与事件收尾（算法本身在 test_compaction.py）──────────────
def test_compact_returns_turn_id_and_finishes_with_done(rig):
    rig.host.create_session({"sessionId": "cp-1"})
    result = rig.host.compact({"sessionId": "cp-1"})
    assert isinstance(result, dict) and result["turnId"]
    assert wait_for(lambda: any(e["type"] == "compacted" for e in rig.events()))
    assert wait_for(lambda: any(e["type"] == "done" for e in rig.events()))
    assert wait_for(lambda: not rig.host.is_busy("cp-1"))

    compacted = [e for e in rig.events() if e["type"] == "compacted"][-1]
    assert compacted["scope"] == "manual"
    assert compacted["status"] in {"none", "compacted", "failed"}
    assert rig.events("done")[-1]["stopReason"] == "end_turn"


def test_compact_on_missing_session_raises(rig):
    with pytest.raises(Exception) as excinfo:
        rig.host.compact({"sessionId": "nope"})
    assert "会话不存在" in str(excinfo.value)


def test_compact_without_session_id_raises(rig):
    with pytest.raises(Exception) as excinfo:
        rig.host.compact({})
    assert "sessionId" in str(excinfo.value)


# ── 事件形状转换 ──────────────────────────────────────────────────────────
def test_tool_call_events_carry_ids_matching_results():
    call_event = to_chat_event(
        "t", "s", {"type": "tool_call", "id": "toolu_9", "name": "read_file", "input": {"path": "a"}}
    )
    result_event = to_chat_event(
        "t",
        "s",
        {"type": "tool_result", "id": "toolu_9", "name": "read_file", "summary": "读到 1 行", "is_error": False},
    )
    assert call_event["event"] == {"type": "tool_call", "id": "toolu_9", "name": "read_file", "args": {"path": "a"}}
    assert result_event["event"] == {
        "type": "tool_result",
        "id": "toolu_9",
        "name": "read_file",
        "summary": "读到 1 行",
        "isError": False,
    }
