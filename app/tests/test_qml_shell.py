"""QML 壳的数据投影与发送链路。

分两块，对应壳里新增的两条依赖：

1. **列表与正文的判据**（`qml_shell_sessions`，纯 Python）：真实会话的行形状、落盘
   消息按顺序拼成 Markdown、流式增量的拼接。壳里只把结果塞进 QML 属性，判据在这里；
2. **发送链路**（`qml_shell.ShellBridge`）：输入区 → `ChatHost.send` → 后台回合 →
   `emit` 入队 → GUI 线程 `tick()` → 正文重渲染，用户消息与回复都要落盘。

传输仍是 `ScriptedTransport`（离线 SSE），本文件不访问网络；真实 provider 的实跑
证据在 `out/qml-shell/run2.log`。
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from mvvm.models.chat_models import Message, StoredSession
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.settings_service import SettingsService
from mvvm.services.skill_store import SkillStore
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.webui.assembly import build_chat_host

from qml_shell_sessions import (
    ASSISTANT_HEADING,
    PREVIEW_MAX,
    USER_HEADING,
    TurnState,
    preview_text,
    session_row,
    session_rows,
    time_label,
    transcript_markdown,
)
from scripted_transport import ScriptedTransport, sse

MODELS = {
    "activeModelId": "p1:claude-sonnet-5-5",
    "providers": [
        {
            "id": "p1",
            "adapter": "anthropic",
            "apiHost": "https://api.example.com",
            "enabled": True,
            "models": [{"id": "claude-sonnet-5-5", "enabled": True}],
        }
    ],
}


def text_stream(*chunks: str) -> ScriptedTransport:
    events = [
        sse("message_start", {"type": "message_start", "message": {"usage": {"input_tokens": 7}}}),
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
            {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 2}},
        )
    )
    events.append(sse("message_stop", {"type": "message_stop"}))
    return ScriptedTransport(chunks=events)


def gated_stream(first: str, gate: threading.Event) -> ScriptedTransport:
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


# ── 列表行 ──────────────────────────────────────────────────────────────
def _session(session_id="s-1", title="", messages=()):
    return StoredSession(id=session_id, title=title, messages=list(messages))


def test_preview_takes_last_message_with_text_and_collapses_lines():
    session = _session(
        messages=[
            Message(role="user", content="第一句"),
            Message(role="assistant", content="多行\n\n  文本\t带空白"),
        ]
    )
    assert preview_text(session) == "多行 文本 带空白"


def test_preview_skips_messages_without_body_text():
    session = _session(
        messages=[
            Message(role="user", content="有正文"),
            Message(role="assistant", content=[{"type": "tool_use", "id": "t1", "name": "x", "input": {}}]),
        ]
    )
    assert preview_text(session) == "有正文"


def test_preview_truncates_long_text_with_ellipsis():
    session = _session(messages=[Message(role="user", content="字" * (PREVIEW_MAX + 5))])
    preview = preview_text(session)
    assert preview == "字" * PREVIEW_MAX + "…"
    assert len(preview) == PREVIEW_MAX + 1


def test_preview_empty_session_is_empty_string():
    assert preview_text(_session()) == ""
    assert preview_text(None) == ""


@pytest.mark.parametrize(
    "delta,expected",
    [
        (0, "刚刚"),
        (59_999, "刚刚"),
        (60_000, "1 分钟前"),
        (3_599_000, "59 分钟前"),
        (3_600_000, "1 小时前"),
        (86_399_000, "23 小时前"),
    ],
)
def test_time_label_relative_buckets(delta, expected):
    now = 1_700_000_000_000
    assert time_label(now - delta, now=now) == expected


@pytest.mark.parametrize(
    "delta,expected",
    [
        (0, "just now"),
        (59_999, "just now"),
        (60_000, "1 min ago"),
        (3_599_000, "59 min ago"),
        (3_600_000, "1 hr ago"),
        (86_399_000, "23 hr ago"),
    ],
)
def test_time_label_english_buckets_match_use_relative_time(delta, expected):
    # 原版 useRelativeTime（ChatFirstShell.tsx:338）的英文词表，逐字相同。
    now = 1_700_000_000_000
    assert time_label(now - delta, now=now, lang="en") == expected


@pytest.mark.parametrize(
    "days,zh,en",
    [(1, "昨天", "yesterday"), (3, "3 天前", "3 days ago")],
)
def test_time_label_day_buckets_count_days(days, zh, en):
    # 原版超过 24 小时按天数写（正好 1 天是 yesterday），没有「绝对日期」这一档。
    now = 1_700_000_000_000
    ms = now - days * 86_400_000
    assert time_label(ms, now=now) == zh
    assert time_label(ms, now=now, lang="en") == en


def test_time_label_garbage_is_empty():
    assert time_label(None) == ""
    assert time_label("not-a-number") == ""


def test_time_label_future_timestamp_clamps_to_just_now():
    now = 1_700_000_000_000
    assert time_label(now + 10_000, now=now) == "刚刚"
    assert time_label(now + 10_000, now=now, lang="en") == "just now"


def test_session_row_uses_meta_title_preview_and_time(tmp_path):
    store = ChatSessionStore(tmp_path)
    store.ensure_session("s-1")
    session = store.load_session("s-1")
    session.title = "标题"
    session.messages.append(Message(role="user", content="预览正文"))
    session.updatedAt = 1_700_000_000_000
    store.save("s-1")

    meta = store.visible_sessions()[0]
    row = session_row(meta, store.load_session("s-1"), now=1_700_000_000_000 + 300_000)
    assert row == {"id": "s-1", "title": "标题", "preview": "预览正文", "time": "5 分钟前"}

    # 英文界面（parity 夹具用 en）走英文词表。
    row_en = session_row(
        meta, store.load_session("s-1"), now=1_700_000_000_000 + 300_000, lang="en"
    )
    assert row_en["time"] == "5 min ago"


def test_session_row_falls_back_to_preview_when_title_is_blank(tmp_path):
    store = ChatSessionStore(tmp_path)
    store.ensure_session("s-1")
    session = store.load_session("s-1")
    session.messages.append(Message(role="user", content="只有预览"))
    store.save("s-1")

    row = session_row(store.visible_sessions()[0], store.load_session("s-1"))
    assert row["title"] == "只有预览"


def test_session_row_untitled_and_empty_session_is_placeholder(tmp_path):
    store = ChatSessionStore(tmp_path)
    store.ensure_session("s-1")
    store.save("s-1")

    row = session_row(store.visible_sessions()[0], store.load_session("s-1"))
    assert row["title"] == "未命名会话"
    assert row["preview"] == ""


def test_session_rows_follow_store_order_and_read_saved_messages(tmp_path):
    store = ChatSessionStore(tmp_path)
    for session_id, title, updated in (("a", "旧的", 1_000), ("b", "新的", 2_000)):
        store.ensure_session(session_id)
        session = store.load_session(session_id)
        session.title = title
        session.updatedAt = updated
        session.messages.append(Message(role="user", content=title + "的正文"))
        store.save(session_id)

    rows = session_rows(store, now=2_000)
    assert [row["id"] for row in rows] == ["b", "a"]
    assert rows[0]["preview"] == "新的的正文"


def test_shot_path_survives_the_builtin_file_a_merged_bundle_reports(monkeypatch, tmp_path):
    """A packaged module's ``__file__`` is "built-in", not a path with parents.

    CI run 44033731069's windows-py38 job died at import time with
    ``File "qml_shell.py", line 55`` / ``File "pathlib.py", line 621, in
    __getitem__``: the shot path was computed at module scope from
    ``Path(__file__).resolve().parents[2]``, and CPython 3.8's Windows
    ``resolve()`` returns a relative path unchanged when it does not exist
    (``Lib/pathlib.py:211``), so ``Path("built-in")`` has one parent and
    ``parents[2]`` raised IndexError. Nothing may be counted from a value that
    is not a file -- the override is the only path a packaged run relies on.
    """
    import qml_shell

    monkeypatch.setattr(qml_shell, "__file__", "built-in")
    monkeypatch.delenv(qml_shell.SHOT_ENV, raising=False)

    shot = qml_shell._shot_path()
    # A writable absolute path outside the source tree, never a relative
    # "built-in/..." that would land beside the process's working directory.
    assert shot.is_absolute()
    assert "built-in" not in shot.parts

    monkeypatch.setenv(qml_shell.SHOT_ENV, str(tmp_path / "shot.png"))
    assert qml_shell._shot_path() == tmp_path / "shot.png"


def test_shot_path_lives_under_the_source_tree_in_a_development_checkout(monkeypatch):
    """Only a real module file has parents worth counting."""
    import qml_shell

    monkeypatch.delenv(qml_shell.SHOT_ENV, raising=False)
    shot = qml_shell._shot_path()
    # <repo>/out/qml-shell/shot.png: app/src/qml_shell.py counted two parents up.
    assert shot == Path(qml_shell.__file__).resolve().parents[2] / "out" / "qml-shell" / "shot.png"


# ── 正文拼接 ────────────────────────────────────────────────────────────
def test_transcript_markdown_keeps_saved_order_and_skips_empty_messages():
    messages = [
        Message(role="user", content="第一问"),
        Message(role="assistant", content=[{"type": "tool_use", "id": "t1", "name": "x", "input": {}}]),
        Message(role="assistant", content="第一答"),
    ]
    markdown = transcript_markdown(messages)
    assert markdown == "%s\n\n第一问\n\n%s\n\n第一答" % (USER_HEADING, ASSISTANT_HEADING)


def test_transcript_markdown_appends_pending_user_and_streaming_tail():
    messages = [Message(role="user", content="历史")]
    markdown = transcript_markdown(messages, pending_user="本轮问题", streaming="增量")
    assert markdown.endswith(
        "%s\n\n历史\n\n%s\n\n本轮问题\n\n%s\n\n增量" % (USER_HEADING, USER_HEADING, ASSISTANT_HEADING)
    )


def test_transcript_markdown_empty_streaming_still_opens_assistant_heading():
    markdown = transcript_markdown([], pending_user="问题", streaming="")
    assert markdown == "%s\n\n问题\n\n%s" % (USER_HEADING, ASSISTANT_HEADING)


def test_transcript_markdown_empty_inputs_give_empty_string():
    assert transcript_markdown([]) == ""
    assert transcript_markdown(None, pending_user="  ", streaming=None) == ""


# ── 流式状态机 ──────────────────────────────────────────────────────────
def test_turn_state_appends_deltas_until_done():
    turn = TurnState("%s\n\n历史" % USER_HEADING, "问题")
    assert turn.markdown() == "%s\n\n历史\n\n%s\n\n问题\n\n%s" % (USER_HEADING, USER_HEADING, ASSISTANT_HEADING)

    assert turn.apply({"type": "text_delta", "text": "你"}) is True
    assert turn.apply({"type": "text_delta", "text": "好"}) is True
    assert turn.stream == "你好"
    assert turn.markdown().endswith("%s\n\n问题\n\n%s\n\n你好" % (USER_HEADING, ASSISTANT_HEADING))

    assert turn.apply({"type": "done", "stopReason": "end_turn"}) is True
    assert turn.finished is True
    assert turn.stop == "end_turn"
    assert turn.error == ""
    # done 之后正文仍是完整的一轮（调用方随后以落盘为准重建）。
    assert turn.markdown().endswith("你好")


def test_turn_state_error_marks_finished_and_keeps_partial_text():
    turn = TurnState("", "问题")
    turn.apply({"type": "text_delta", "text": "半截"})
    assert turn.apply({"type": "error", "message": "连接被中断"}) is True
    assert turn.finished is True
    assert turn.error == "连接被中断"
    assert "半截" in turn.markdown()


def test_turn_state_ignores_unrelated_events():
    turn = TurnState("基础", "问题")
    assert turn.apply({"type": "turn_start"}) is False
    assert turn.apply({}) is False
    assert turn.stream == ""
    assert turn.finished is False


def test_turn_state_without_base_starts_with_this_turn():
    turn = TurnState("", "问题")
    assert turn.markdown() == "%s\n\n问题\n\n%s" % (USER_HEADING, ASSISTANT_HEADING)


# ── 壳的发送链路（ShellBridge → ChatHost → 落盘）────────────────────────
@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication

    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


def _bridge(tmp_path, monkeypatch, transport, *, sessions=()):
    from qml_shell import ShellBridge

    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    settings = SettingsService(home)
    settings.set_config({"models": MODELS})
    vault = SecretsVault(home)
    vault.set_secret("p1", "sk-test")
    store = ChatSessionStore(home)
    for session_id, text in sessions:
        store.ensure_session(session_id)
        session = store.load_session(session_id)
        session.messages.append(Message(role="user", content=text))
        store.save(session_id)

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
    bridge = ShellBridge(host=host, store=store, plain=True, settings=settings, skills=SkillStore(home))
    host._emit = bridge.emit  # 事件改成推到壳的队列（GUI 线程的 tick 再消费）
    # 正文目标：`_render()` 只有拿到文档才重绘；这里给一个只暴露 `textDocument()`
    # 的替身（与 `test_markdown_body` 同口径），不把 QML 环境拖进单测。
    bridge.attach(QuickDocumentStub())
    return bridge, store, host


class QuickDocumentStub:
    """``QQuickTextDocument`` 的最小替身：``BodyDocument.attach`` 只用这个入口。"""

    def __init__(self):
        from PySide6.QtGui import QTextDocument

        self._document = QTextDocument()

    def textDocument(self):  # noqa: N802 - Qt 命名
        return self._document


def _tick_until(bridge, predicate, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        bridge.tick()
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def test_shell_send_streams_into_transcript_and_persists(qapp, tmp_path, monkeypatch, capsys):
    bridge, store, _host = _bridge(
        tmp_path, monkeypatch, text_stream("你", "好"), sessions=[("s-1", "历史问题")]
    )
    assert bridge.openSession("s-1") is True
    base = bridge._markdown()
    assert "历史问题" in base

    assert bridge.send("本轮问题") is True
    before = bridge.rendered
    assert _tick_until(bridge, bridge.turn_finished)
    assert bridge.stop == "end_turn"
    assert bridge.deltas == ["你", "好"]
    assert bridge.rendered - before >= 1, "收到事件后正文必须重渲染"
    assert "本轮问题" in bridge._body.source and "你好" in bridge._body.source

    out = capsys.readouterr().out
    assert "QML SEND" in out and "QML TURN " in out
    assert 'QML STREAM {"text": "你"}' in out
    assert "QML TURN DONE" in out and '"stopReason": "end_turn"' in out

    session = store.load_session("s-1")
    assert [m.role for m in session.messages] == ["user", "user", "assistant"]
    assert session.messages[1].text() == "本轮问题"
    assert session.messages[2].text() == "你好"
    # 回合结束后正文以落盘为准：历史 + 本轮问答都在。
    markdown = bridge._markdown()
    assert "历史问题" in markdown and "本轮问题" in markdown and "你好" in markdown


def test_shell_send_without_active_session_creates_one(qapp, tmp_path, monkeypatch):
    bridge, store, _host = _bridge(tmp_path, monkeypatch, text_stream("收到"))
    assert bridge.send("第一条消息") is True
    assert bridge._active.startswith("qml-")
    created = bridge._active
    assert _tick_until(bridge, bridge.turn_finished)
    assert store.session_path(created).exists()
    assert [m.role for m in store.load_session(created).messages] == ["user", "assistant"]
    assert [row["id"] for row in session_rows(store)] == [created]


def test_shell_send_rejects_blank_and_busy(qapp, tmp_path, monkeypatch, capsys):
    gate = threading.Event()
    bridge, _store, _host = _bridge(
        tmp_path, monkeypatch, gated_stream("开头", gate), sessions=[("s-1", "旧")]
    )
    bridge.openSession("s-1")
    assert bridge.send("   ") is False
    assert capsys.readouterr().out == "", "空文本不该起回合、也不该打印发送日志"

    assert bridge.send("第一句") is True
    assert bridge.send("第二句") is False, "同一会话已有回合在跑时必须拒绝"
    gate.set()
    assert _tick_until(bridge, bridge.turn_finished)


# ── 渲染路径：一次点击只渲染一遍 ──────────────────────────────────────────
def test_open_session_renders_once_and_replaces_the_body(qapp, tmp_path, monkeypatch):
    """点会话行只该渲染一遍正文；旧会话的内容必须整篇被换掉。

    历史回归：``_render`` 曾先在自有文档渲染、又在 ``attach`` 里把同一份正文
    重渲染进 QML 文档，同一份内容付出两倍排版代价（长正文上就是秒级卡顿）。
    """
    bridge, _store, _host = _bridge(
        tmp_path, monkeypatch, text_stream(), sessions=[("s-1", "甲会话的问题"), ("s-2", "乙会话的问题")]
    )
    renders = []
    original = bridge._body.render

    def counted(document=None):
        renders.append(document)
        return original(document)

    bridge._body.render = counted
    assert bridge.openSession("s-1") is True
    assert len(renders) == 1, "attach 不该再重渲染一次"

    target = bridge._document.textDocument()
    assert "甲会话的问题" in target.toPlainText()

    assert bridge.openSession("s-2") is True
    text = target.toPlainText()
    assert "乙会话的问题" in text
    assert "甲会话的问题" not in text, "切会话是整篇替换，不是追加"


def test_open_session_carries_highlight_formats_into_the_qml_document(qapp, tmp_path, monkeypatch):
    """切换会话后，代码块的着色由挂在展示文档上的高亮器重算。

    着色写在 ``QTextLayout`` 上，不能跨文档搬（会把块高打成 0），所以这里同时锁住
    「有颜色」与「行高不为 0」两件事。

    ``_bridge`` 默认 ``plain=True``（无 QML 环境下的纯文本回退），这里要看 Markdown 渲染。
    """
    from markdown.highlight import LIGHT_TOKENS

    bridge, store, _host = _bridge(tmp_path, monkeypatch, text_stream(), sessions=[("s-1", "占位")])
    bridge._plain = False
    bridge._body = type(bridge._body)()
    bridge._body.set_image_resolver(lambda src: None)
    session = store.load_session("s-1")
    session.messages.clear()
    session.messages.append(Message(role="assistant", content="```python\nif x: pass\n```"))
    store.save("s-1")

    assert bridge.openSession("s-1") is True
    target = bridge._document.textDocument()
    block = target.begin()
    while block.isValid() and block.text() != "if x: pass":
        block = block.next()
    assert block.isValid(), "代码行必须在目标文档里"
    target.setTextWidth(696.0)
    target.documentLayout()
    colours = {block.text()[f.start:f.start + f.length]: f.format.foreground().color().name()
               for f in block.layout().formats()}
    assert colours["if"] == LIGHT_TOKENS["keyword"]
    assert target.documentLayout().blockBoundingRect(block).height() > 0, "代码行不能塌成 0 高"


# ── 扩展页（settings-extensions）：行投影与开关写路径 ────────────────────
def test_extension_rows_project_builtin_skills_with_badge_and_note(qapp, tmp_path, monkeypatch):
    """扩展页行形状对齐原版 `SettingsPane.tsx:195-260`。

    QML 的 `extensionsPane` 直接吃这些字段（`badge` 画徽标、`note` 画注记、`builtin`
    决定开关禁用），字段名或语义变了界面就是空白/错画——所以判据锁在数据投影上。
    """
    bridge, _store, _host = _bridge(tmp_path, monkeypatch, text_stream("x"))
    rows = bridge.extensionRows()
    assert [row["id"] for row in rows] == ["create-skill", "create-agent", "create-mcp"]
    for row in rows:
        assert row["enabled"] is True
        assert row["builtin"] is True
        assert row["badge"] == "Skill"
        assert row["note"] == "Built-in"


def test_extension_rows_honor_disk_skill_and_config_enabled(qapp, tmp_path, monkeypatch):
    """磁盘技能排在三条内置之后；`enabled` 取 config 的 `skills.enabled[id]`，不写等于开。"""
    bridge, _store, _host = _bridge(tmp_path, monkeypatch, text_stream("x"))
    folder = tmp_path / "home" / "skills" / "demo"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("---\nname: Demo\n---\nbody\n", encoding="utf-8")

    rows = {row["id"]: row for row in bridge.extensionRows()}
    assert rows["demo"]["enabled"] is True
    assert rows["demo"]["builtin"] is False
    assert rows["demo"]["badge"] == "Skill"
    assert rows["demo"]["note"] == ""

    assert bridge.setSkillEnabled("demo") is False  # 返回落盘后的启用态：关掉了
    assert bridge.extensionRows()[-1]["enabled"] is False
    assert json.loads((tmp_path / "home" / "config.json").read_text())["skills"]["enabled"]["demo"] is False

    assert bridge.setSkillEnabled("demo") is True
    assert bridge.extensionRows()[-1]["enabled"] is True


def test_set_skill_enabled_leaves_builtin_rows_untouched(qapp, tmp_path, monkeypatch):
    """内置技能恒启用：写入口 no-op，不落 `skills.enabled` 键（原版 RESERVED_IDS 语义）。"""
    bridge, _store, _host = _bridge(tmp_path, monkeypatch, text_stream("x"))
    assert bridge.setSkillEnabled("create-skill") is True  # 值仍是「启用」
    assert bridge.extensionRows()[0]["enabled"] is True
    config = tmp_path / "home" / "config.json"
    section = json.loads(config.read_text()).get("skills") or {}
    assert "create-skill" not in (section.get("enabled") or {})


def test_skill_toggle_survives_a_later_settings_write(qapp, tmp_path, monkeypatch):
    """开关落盘后，设置页的其它写入不能把它覆盖掉。

    `SkillStore.set_enabled` 自己读写 `config.json`，而设置页（主题/语言/字号/模型）
    走 `SettingsService` 的内存副本 + 整文件回写。两条写路径并存时，内存副本若还在
    开关之前的状态，下一次设置写入就会把 `skills.enabled` 抹回旧值——这条用例锁住
    开关入口在写完之后让设置服务重新读盘（`reload()`）。
    """
    bridge, _store, _host = _bridge(tmp_path, monkeypatch, text_stream("x"))
    folder = tmp_path / "home" / "skills" / "demo"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text("---\nname: Demo\n---\nbody\n", encoding="utf-8")

    assert bridge.setSkillEnabled("demo") is False  # 关掉
    bridge.setTheme("dark")  # 设置页的另一次写入（走 SettingsService 整文件回写）

    config = json.loads((tmp_path / "home" / "config.json").read_text())
    assert config["theme"] == "dark"
    assert config["skills"]["enabled"]["demo"] is False, "设置写入不能覆盖技能开关"
    assert {row["id"]: row for row in bridge.extensionRows()}["demo"]["enabled"] is False
