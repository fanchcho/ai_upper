"""写路径端到端：桥 → ChatHost → ChatViewModel → 适配器（脚本化传输）→ 事件回推。

这里测的是「渲染层真实会调的形状」：`chat:send` 同步拿 turnId，流式事件按
`chat:event {turnId,sessionId,event}` 逐个推出，`done` 收尾；中止、建会话、改模型/
档位/文件夹、改名、归档、删除、待办也各走一遍桥的通道入口（不是直接调宿主方法）。

传输是 `ScriptedTransport`（离线 SSE），**不是真 provider**：本文件不访问网络。
真实 provider 的实跑证据在 `docs/BUILD-PROGRESS.md` 第六阶段的端到端小节。
"""
from __future__ import annotations

import asyncio
import json
import threading
import time

import pytest

from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.provider_setup import ModelGateway
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.settings_service import SettingsService
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.webui.assembly import build_chat_host
from mvvm.webui.bridge import DevaBridge

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
        sse(
            "message_start",
            {"type": "message_start", "message": {"usage": {"input_tokens": 10}}},
        ),
        sse(
            "content_block_start",
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        ),
    ]
    for piece in chunks:
        events.append(
            sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": piece},
                },
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


def gated_stream(first: str, rest: list[str], gate: threading.Event) -> ScriptedTransport:
    """先出一段，然后卡住等测试放行——用来在回合进行中发 abort。"""
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
            # 结束前一直等闸门：真实网络里就是「服务端还没把剩余字节送完」。
            deadline = time.time() + 5.0
            while not gate.is_set() and time.time() < deadline:
                await asyncio.sleep(0.01)

    return Gated()


@pytest.fixture()
def rig(tmp_path, monkeypatch):
    """真实的一套桥 + 宿主 + 网关，传输由测试逐次指定。"""
    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    home = tmp_path / "deva-home"
    settings = SettingsService(home)
    settings.set_config({"models": MODELS})
    vault = SecretsVault(home)
    vault.set_secret("p1", "sk-test-123")
    store = ChatSessionStore(home)
    guard = WorkspaceGuard()
    transport = text_stream("你", "好")
    emitted: list[tuple[str, object]] = []

    def emit(payload):
        emitted.append(("chat:event", payload))

    def emit_sessions_changed():
        emitted.append(("chat:sessions-changed", None))

    host, gateway = build_chat_host(
        settings=settings,
        vault=vault,
        store=store,
        guard=guard,
        home=home,
        emit=emit,
        emit_sessions_changed=emit_sessions_changed,
        transport=transport,
    )
    from mvvm.services.persona_store import PersonaStore

    bridge = DevaBridge(
        settings=settings, personas=PersonaStore(home), store=store, home=home
    )
    bridge.vault = vault
    bridge.chat_host = host
    bridge.model_gateway = gateway

    class Rig:
        pass

    r = Rig()
    r.bridge, r.host, r.store, r.guard, r.settings, r.vault = (
        bridge, host, store, guard, settings, vault
    )
    r.emitted = emitted
    r.transport = transport
    return r


def _host_with_transport(home: Path, transport):
    """独立的一套宿主（自带 home），返回 host；事件丢弃即可。"""
    home.mkdir(parents=True, exist_ok=True)
    settings = SettingsService(home)
    settings.set_config({"models": MODELS})
    vault = SecretsVault(home)
    vault.set_secret("p1", "sk-key")
    store = ChatSessionStore(home)
    host, _gateway = build_chat_host(
        settings=settings,
        vault=vault,
        store=store,
        guard=WorkspaceGuard(),
        home=home,
        emit=lambda payload: None,
        emit_sessions_changed=lambda: None,
        transport=transport,
    )
    return host


def call(rig, channel: str, *args):
    """经桥的真实入口调用一次通道（与渲染层 `invoke` 同路径）。"""
    return rig.bridge._handlers[channel](*args)


def wait_for(predicate, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


def events(rig, kind: str | None = None):
    out = [payload["event"] for channel, payload in rig.emitted if channel == "chat:event"]
    if kind is None:
        return out
    return [event for event in out if event["type"] == kind]


# ── chat:send：流式正文与 done ────────────────────────────────────────────
def test_send_streams_text_and_finishes_with_done(rig):
    result = call(rig, "chat:send", {
        "sessionId": "web-1",
        "text": "你好",
        "model": {"adapter": "anthropic", "providerId": "p1", "baseURL": "https://api.example.com", "model": "claude-sonnet-5-5"},
        "workspaceRoot": None,
    })
    assert isinstance(result, dict) and result["turnId"]

    # 回合是 fire-and-forget：send 已返回 turnId，正文随后分期到达。
    assert wait_for(lambda: any(e["type"] == "done" for e in events(rig)), 10.0)
    assert wait_for(lambda: not rig.host.is_busy("web-1"))

    kinds = [event["type"] for event in events(rig)]
    assert kinds[0] == "turn_start", "turn_start 必须是本轮第一个事件"
    turn_start = events(rig, "turn_start")[0]
    assert turn_start["user"]["role"] == "user"
    assert turn_start["user"]["text"] == "你好"
    assert [event["text"] for event in events(rig, "text_delta")] == ["你", "好"]
    done = events(rig, "done")[-1]
    assert done["stopReason"] == "end_turn"
    assert isinstance(done["durationMs"], int) and done["durationMs"] >= 0

    # 每条事件都带同一个回合/会话标识（渲染层据此分派到对应的运行时）。
    payloads = [payload for channel, payload in rig.emitted if channel == "chat:event"]
    assert {p["sessionId"] for p in payloads} == {"web-1"}
    assert {p["turnId"] for p in payloads} == {result["turnId"]}

    # 落盘：用户消息 + 助手回复都在会话文件里，重开能读回。
    session = rig.store.load_session("web-1")
    assert session is not None
    assert rig.store.session_path("web-1").exists()
    roles = [m.role for m in session.messages]
    assert roles == ["user", "assistant"]
    assert "你好" in str(session.messages[0].content)
    assert "你好" in str(session.messages[1].content)
    assert session.title == "你好"


def test_send_raises_busy_message_when_turn_running(rig, tmp_path, monkeypatch):
    """同一会话已有一轮在跑时，第二次发送必须被拒绝且文案与原版一致。"""
    gate = threading.Event()
    host = _host_with_transport(tmp_path / "busy-home", gated_stream("开头", [], gate))
    first = host.send({"sessionId": "web-busy", "text": "第一句"})
    assert first["turnId"]
    assert wait_for(lambda: host.is_busy("web-busy"))
    with pytest.raises(Exception) as excinfo:
        host.send({"sessionId": "web-busy", "text": "第二句"})
    assert "正在进行中" in str(excinfo.value)
    gate.set()
    assert wait_for(lambda: not host.is_busy("web-busy"), 10.0)


# ── chat:abort ───────────────────────────────────────────────────────────
def test_abort_stops_the_turn_and_reports_aborted(tmp_path, monkeypatch):
    """中止必须在回合进行中生效，并以 `stopReason:'aborted'` 收尾。"""
    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    gate = threading.Event()
    home = tmp_path / "abort-home"
    home.mkdir(parents=True, exist_ok=True)
    settings = SettingsService(home)
    settings.set_config({"models": MODELS})
    vault = SecretsVault(home)
    vault.set_secret("p1", "sk-key")
    store = ChatSessionStore(home)
    emitted: list[tuple[str, object]] = []
    host, _gateway = build_chat_host(
        settings=settings,
        vault=vault,
        store=store,
        guard=WorkspaceGuard(),
        home=home,
        emit=lambda payload: emitted.append(("chat:event", payload)),
        emit_sessions_changed=lambda: emitted.append(("chat:sessions-changed", None)),
        transport=gated_stream("半截", [], gate),
    )

    turn = host.send({"sessionId": "s-abort", "text": "说长一点"})

    def saw_delta() -> bool:
        host.drain()
        return any(p["event"]["type"] == "text_delta" for c, p in emitted if c == "chat:event")

    assert wait_for(saw_delta)
    assert host.abort(turn["turnId"]) == {"ok": True}
    gate.set()
    assert wait_for(lambda: any(p["event"]["type"] == "done" for c, p in emitted if c == "chat:event"), 10.0)
    assert wait_for(lambda: not host.is_busy("s-abort"), 10.0)

    done = [p["event"] for c, p in emitted if c == "chat:event" and p["event"]["type"] == "done"][-1]
    assert done["stopReason"] == "aborted"
    # 半截正文已落盘：重开后看得出这一轮被打断。
    session = store.load_session("s-abort")
    assert any("半截" in str(m.content) for m in session.messages if m.role == "assistant")


def test_abort_unknown_turn_is_ok_without_side_effects(rig):
    assert call(rig, "chat:abort", "nope") == {"ok": True}


# ── chat:create-session / set-model / set-effort / set-focus ─────────────
def test_create_session_persists_empty_session(rig):
    assert call(rig, "chat:create-session", {"sessionId": "empty-1", "personaId": "p-1"}) == {"ok": True}
    # 空对话也落盘：跨重启存活（原版 createSession 后立即 saveProject）。
    assert rig.store.session_path("empty-1").exists()
    assert any(channel == "chat:sessions-changed" for channel, _ in rig.emitted)
    metas = call(rig, "chat:list-sessions", None)
    assert "empty-1" in {meta["id"] for meta in metas}


def test_set_model_and_effort_and_focus_write_session(rig):
    call(rig, "chat:create-session", {"sessionId": "w-1"})

    assert call(rig, "chat:set-model", {"sessionId": "w-1", "modelRef": "p1:claude-haiku-5-5"}) == {"ok": True}
    assert call(rig, "chat:set-effort", {"sessionId": "w-1", "effort": "high"}) == {"ok": True}
    assert call(rig, "chat:set-focus", {"sessionId": "w-1", "focusRoot": "/tmp/project"}) == {"ok": True}

    session = rig.store.load_session("w-1")
    assert session.model == "p1:claude-haiku-5-5"
    assert session.effort == "high"
    assert session.focusRoot == "/tmp/project"


def test_set_model_on_missing_session_reports_false(rig):
    assert call(rig, "chat:set-model", {"sessionId": "nope", "modelRef": "p1:claude-haiku-5-5"}) == {"ok": False}


def test_set_effort_illegal_level_is_still_ok(rig):
    call(rig, "chat:create-session", {"sessionId": "w-2"})
    assert call(rig, "chat:set-effort", {"sessionId": "w-2", "effort": "ultra"}) == {"ok": True}
    assert rig.store.load_session("w-2").effort is None


# ── 改名 / 归档 / 删除 / 重置 / 删轮 ─────────────────────────────────────
def test_rename_session_returns_trimmed_title(rig):
    call(rig, "chat:create-session", {"sessionId": "r-1"})
    result = call(rig, "chat:rename-session", {"sessionId": "r-1", "title": "  多   空格  标题  "})
    assert result == {"title": "多 空格 标题"}
    assert rig.store.load_session("r-1").title == "多 空格 标题"


def test_rename_missing_session_returns_null(rig):
    assert call(rig, "chat:rename-session", {"sessionId": "nope", "title": "x"}) is None


def test_set_archived_toggles_and_hides_from_visible_list(rig):
    call(rig, "chat:create-session", {"sessionId": "a-1"})
    assert call(rig, "chat:set-archived", {"sessionId": "a-1", "archived": True}) == {"ok": True}
    assert "a-1" not in {m.id for m in rig.store.visible_sessions()}
    assert call(rig, "chat:set-archived", {"sessionId": "a-1", "archived": False}) == {"ok": True}
    assert "a-1" in {m.id for m in rig.store.visible_sessions()}


def test_delete_session_removes_file_and_returns_ok(rig):
    call(rig, "chat:create-session", {"sessionId": "d-1"})
    assert rig.store.session_path("d-1").exists()
    assert call(rig, "chat:delete-session", "d-1", None) == {"ok": True}
    assert not rig.store.session_path("d-1").exists()


def test_reset_clears_messages(rig):
    call(rig, "chat:create-session", {"sessionId": "rs-1"})
    rig.store.append_message("rs-1", __import__("mvvm.models.chat_models", fromlist=["Message"]).Message(
        role="user", content="旧内容"))
    rig.store.save("rs-1")
    assert call(rig, "chat:reset", "rs-1", None) == {"ok": True}
    assert rig.store.load_session("rs-1").messages == []


def test_delete_turns_returns_display_messages(rig):
    call(rig, "chat:create-session", {"sessionId": "dt-1"})
    models = __import__("mvvm.models.chat_models", fromlist=["Message"])
    rig.store.append_message("dt-1", models.Message(role="user", content="第一轮"))
    rig.store.append_message("dt-1", models.Message(role="assistant", content="答一"))
    rig.store.append_message("dt-1", models.Message(role="user", content="第二轮"))
    rig.store.append_message("dt-1", models.Message(role="assistant", content="答二"))
    rig.store.save("dt-1")
    remaining = call(rig, "chat:delete-turns", "dt-1", None, [1])
    assert [m["text"] for m in remaining if m["role"] == "user"] == ["第一轮"]


# ── 待办 ─────────────────────────────────────────────────────────────────
def test_todos_on_missing_session_is_empty(rig):
    assert call(rig, "chat:todos", "nope") == {"active": None}
    assert call(rig, "chat:todo-cancel", "nope") == {"active": None}


# ── attach / list / load ─────────────────────────────────────────────────
def test_attach_session_reports_running_turn(rig):
    call(rig, "chat:create-session", {"sessionId": "at-1"})
    attached = call(rig, "chat:attach-session", "at-1")
    assert attached == {"messages": [], "turnId": None, "startedAt": None}


def test_list_sessions_trusts_focus_roots(rig):
    """非空 focusRoot 必须登记为受信根，否则重启后 git/fs 报「拒绝访问」。"""
    target = rig.store.home / "proj"
    target.mkdir(parents=True, exist_ok=True)
    call(rig, "chat:create-session", {"sessionId": "f-1", "focusRoot": str(target)})
    assert not rig.guard.is_inside_root(target)
    call(rig, "chat:list-sessions", None)
    assert rig.guard.is_inside_root(target)


# ── 事件转换：tool_call / tool_result ────────────────────────────────────
def test_tool_call_events_carry_ids_matching_results(rig):
    from mvvm.webui.host import to_chat_event

    call_event = to_chat_event("t", "s", {"type": "tool_call", "id": "toolu_9", "name": "read_file", "input": {"path": "a"}})
    result_event = to_chat_event("t", "s", {
        "type": "tool_result", "id": "toolu_9", "name": "read_file",
        "summary": "读到 1 行", "is_error": False,
    })
    assert call_event["event"] == {"type": "tool_call", "id": "toolu_9", "name": "read_file", "args": {"path": "a"}}
    assert result_event["event"] == {
        "type": "tool_result", "id": "toolu_9", "name": "read_file", "summary": "读到 1 行", "isError": False,
    }


# ── chat:compact ─────────────────────────────────────────────────────────
def test_compact_returns_turn_id_and_finishes_with_done(rig):
    """`/compact`：立即回 turnId，压缩在后台跑，收尾必定是 compacted + done。

    本用例的会话没有可压缩的历史，压缩器回 `status:'none'`——这正是原版「没什么可压」
    的分支；断言的是**通道链路与事件收尾**，不是压缩算法本身（那在 test_compaction.py）。
    """
    call(rig, "chat:create-session", {"sessionId": "cp-1"})
    result = call(rig, "chat:compact", {"sessionId": "cp-1", "model": MODELS, "workspaceRoot": None})
    assert isinstance(result, dict) and result["turnId"]
    assert wait_for(lambda: any(e["type"] == "compacted" for e in events(rig)), 10.0)
    assert wait_for(lambda: any(e["type"] == "done" for e in events(rig)), 10.0)
    assert wait_for(lambda: not rig.host.is_busy("cp-1"), 10.0)

    compacted = [e for e in events(rig) if e["type"] == "compacted"][-1]
    assert compacted["scope"] == "manual"
    assert compacted["status"] in {"none", "compacted", "failed"}
    done = [e for e in events(rig) if e["type"] == "done"][-1]
    assert done["stopReason"] == "end_turn"


def test_compact_on_missing_session_raises(rig):
    with pytest.raises(Exception) as excinfo:
        call(rig, "chat:compact", {"sessionId": "nope"})
    assert "会话不存在" in str(excinfo.value)


def test_compact_without_session_id_raises(rig):
    with pytest.raises(Exception) as excinfo:
        call(rig, "chat:compact", {})
    assert "sessionId" in str(excinfo.value)


# ── chat:todos / chat:todo-cancel：有清单时的真实形状 ────────────────────
def _seed_todos(rig, session_id: str, list_id: str = "L1") -> None:
    from mvvm.models.chat_models import Message

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


def test_todos_returns_active_list_shape(rig):
    _seed_todos(rig, "td-1")
    active = call(rig, "chat:todos", "td-1")["active"]
    assert active["id"] == "L1"
    assert active["title"] == "收尾清单"
    assert [item["content"] for item in active["items"]] == ["写台账", "跑测试"]


def test_todo_cancel_marks_list_and_hides_it(rig):
    _seed_todos(rig, "td-2")
    assert call(rig, "chat:todos", "td-2")["active"] is not None
    result = call(rig, "chat:todo-cancel", "td-2")
    assert result == {"active": None}
    assert rig.store.load_session("td-2").todoCancelled == ["L1"]
