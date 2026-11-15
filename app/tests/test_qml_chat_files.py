"""QML 入口的附件贴片 / 交付卡：数据投影、通道接线、路径白名单。

这一层要证明的不是「界面上画了东西」，而是：

1. `qml_shell_sessions` 的投影**只从落盘会话与边车取数**：附件行带真实体积、正文里
   不再出现 `[附件文件]` 注入块；交付行带 `os.stat` 的真实体积、文件缺失时 `missing=True`；
2. `ShellBridge` 的四个交付通道与 web 入口同一条不变式——**只认边车登记的路径**，
   传任意路径必须失败（`/etc/passwd` 之类一律拒绝，且不碰磁盘/不起进程）；
3. `send(attachments=...)` 把 QML 传进来的 `QJSValue` / str 路径统一成真实附件，
   落盘里出现图片内容块（「选了文件却没带上」这条曾经真出过）。
"""
from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from helpers_png import png_bytes
from mvvm.models.chat_models import (
    ImagePart,
    Message,
    StoredSession,
    TextPart,
    ToolResultPart,
    ToolUsePart,
)
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.deliverables import delivered_paths
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.settings_service import SettingsService
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.webui.assembly import build_chat_host

from qml_shell import ShellBridge, _coerce_attachment_paths
from qml_shell_sessions import (
    attachment_rows,
    delivery_rows,
    format_bytes,
    message_body,
    preview_text,
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


def text_stream(*chunks):
    events = [
        sse("message_start", {"type": "message_start", "message": {"usage": {"input_tokens": 7}}}),
        sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
    ]
    for chunk in chunks:
        events.append(
            sse("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": chunk}})
        )
    events += [
        sse("content_block_stop", {"type": "content_block_stop", "index": 0}),
        sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 3}}),
        sse("message_stop", {"type": "message_stop"}),
    ]
    return ScriptedTransport(chunks=events)


# ── 纯投影 ──────────────────────────────────────────────────────────────
def _delivered_session(tmp_path, *, missing=False):
    chart = tmp_path / "chart.png"
    chart.write_bytes(png_bytes())
    notes = tmp_path / "notes.md"
    notes.write_text("# 说明\n", encoding="utf-8")
    gone = tmp_path / "gone.txt"
    gone.write_text("x", encoding="utf-8")
    if missing:
        gone.unlink()
    session = StoredSession(
        id="s-1",
        messages=[
            Message(
                role="user",
                content=[
                    ImagePart(mediaType="image/png", data="AAAA", name="photo.png"),
                    TextPart(text="[附件文件] spec.txt\n```\n正文\n```"),
                    TextPart(text="问题正文"),
                ],
            ),
            Message(
                role="assistant",
                content=[
                    TextPart(text="交付如下。"),
                    ToolUsePart(type="tool_use", id="tu-1", name="present_files", input={"paths": [str(chart)]}),
                ],
            ),
            Message(role="user", content=[ToolResultPart(toolUseId="tu-1", content="已交付 1 个文件")]),
        ],
    )
    session.delivered = {"tu-1": [str(chart), str(notes), str(gone)]}
    return session, chart, notes, gone


@pytest.mark.parametrize(
    "size,expected",
    [
        (0, "0 B"),
        (221, "221 B"),
        (1023, "1023 B"),
        (1024, "1 KB"),
        (1536, "2 KB"),          # renderer: Math.round(1.5) → "2 KB"
        (1024 * 1024, "1.0 MB"),
        (1024 * 1024 * 1024, "1.0 GB"),
        (None, ""),
        ("x", ""),
        (-1, ""),
    ],
)
def test_format_bytes_matches_the_renderer(size, expected):
    # 逐档对齐渲染层 `formatSize`（index-feRGkUOb.js:44535）。
    assert format_bytes(size) == expected


def test_message_body_drops_attachment_injection_blocks():
    message = Message(
        role="user",
        content=[
            TextPart(text="[附件文件] spec.txt\n```\n正文\n```"),
            TextPart(text="[附件文件夹] /tmp/ws\n（位置）"),
            TextPart(text="真正的提问"),
        ],
    )
    assert message_body(message) == "真正的提问"
    assert message_body(Message(role="user", content="纯文本")) == "纯文本"
    assert message_body(Message(role="user", content=[TextPart(text="[附件文件] a.txt")])) == ""


def test_transcript_markdown_still_shows_attachment_chips_without_the_raw_block():
    session, _chart, _notes, _gone = _delivered_session_light()
    markdown = transcript_markdown(session.messages)
    assert "- 附件文件：spec.txt（6 B）" in markdown, "注入块还原成贴片行，体积按正文实算"
    assert "[附件文件] spec.txt" not in markdown, "注入块不能原样出现在正文"
    assert "问题正文" in markdown
    assert "data:image/png;base64,AAAA" in markdown, "图片附件内联成 Markdown 图"


def _delivered_session_light():
    session = StoredSession(
        id="s-1",
        messages=[
            Message(
                role="user",
                content=[
                    ImagePart(mediaType="image/png", data="AAAA", name="photo.png"),
                    TextPart(text="[附件文件] spec.txt\n```\n正文\n```"),
                    TextPart(text="问题正文"),
                ],
            )
        ],
    )
    return session, None, None, None


def test_preview_ignores_attachment_only_messages():
    session = StoredSession(
        id="s-1",
        messages=[
            Message(role="user", content="有正文"),
            Message(role="user", content=[TextPart(text="[附件文件] a.txt\n```\nx\n```")]),
        ],
    )
    assert preview_text(session) == "有正文"


def test_attachment_rows_carry_real_sizes_and_image_data(tmp_path):
    session, _chart, _notes, _gone = _delivered_session(tmp_path)
    rows = attachment_rows(session)
    by_name = {row["name"]: row for row in rows}
    assert set(by_name) == {"photo.png", "spec.txt"}
    # base64 解码后的字节数（AAAA = 3 字节），不是 base64 串长度。
    assert by_name["photo.png"]["size"] == 3
    assert by_name["photo.png"]["sizeText"] == "3 B"
    assert by_name["photo.png"]["thumb"] == "data:image/png;base64,AAAA"
    assert by_name["photo.png"]["partIndex"] == 0
    assert by_name["spec.txt"]["size"] == len("正文".encode("utf-8"))
    assert by_name["spec.txt"]["thumb"] == ""
    assert attachment_rows(None) == []


def test_delivery_rows_use_sidecar_only_and_report_missing(tmp_path):
    session, chart, notes, gone = _delivered_session(tmp_path, missing=True)
    rows = delivery_rows(session)
    by_name = {row["name"]: row for row in rows}
    assert set(by_name) == {"chart.png", "notes.md", "gone.txt"}
    assert by_name["chart.png"]["size"] == chart.stat().st_size
    assert by_name["chart.png"]["sizeText"] == "%d B" % chart.stat().st_size
    assert by_name["chart.png"]["dir"] == str(tmp_path)
    assert by_name["chart.png"]["openable"] is True
    assert by_name["chart.png"]["missing"] is False
    assert by_name["gone.txt"]["missing"] is True
    assert by_name["gone.txt"]["size"] is None
    assert by_name["gone.txt"]["sizeText"] == ""
    assert all(row["toolUseId"] == "tu-1" for row in rows)
    assert delivery_rows(None) == []


def test_delivery_rows_ignore_paths_that_are_not_in_the_sidecar(tmp_path):
    """正文里提到的路径不算数：边车没有就不许出现在交付卡上。"""
    session, _chart, _notes, _gone = _delivered_session(tmp_path)
    session.delivered = {}  # 模拟边车缺失（旧会话）
    assert delivery_rows(session) == []
    # 只认 present_files 调用 id；别的工具调用即使有边车条目也不上线。
    session.delivered = {"tu-other": [str(tmp_path / "notes.md")]}
    assert delivery_rows(session) == []


# ── 通道与白名单 ────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application


def _rig(tmp_path, monkeypatch, *, session=None, transport=None):
    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    settings = SettingsService(home)
    settings.set_config({"models": MODELS})
    vault = SecretsVault(home)
    vault.set_secret("p1", "sk-test")
    store = ChatSessionStore(home)
    stored = session or StoredSession(id="s-1")
    store.ensure_session(stored.id)
    current = store.load_session(stored.id)
    current.messages = list(stored.messages)
    current.delivered = stored.delivered
    store.save(stored.id)

    host, _gateway = build_chat_host(
        settings=settings,
        vault=vault,
        store=store,
        guard=WorkspaceGuard(),
        home=home,
        emit=lambda payload: None,
        emit_sessions_changed=lambda: None,
        transport=transport or text_stream("好"),
    )
    bridge = ShellBridge(host=host, store=store, plain=True, settings=settings, vault=vault)
    host._emit = bridge.emit
    bridge.openSession(stored.id)
    return bridge, store, host, home


def test_qml_bridge_shares_the_host_attachment_service(qapp, tmp_path, monkeypatch):
    """回形针登记的白名单必须就是 `ChatHost.send` 读附件时用的那一份。

    各 new 一份的话，「选好了 → 发出去是已忽略未授权文件」（web 入口踩过同一个坑）。
    """
    bridge, _store, host, _home = _rig(tmp_path, monkeypatch)
    assert bridge._attachments is host.attachments


def test_qml_deliverable_channels_return_real_sizes(qapp, tmp_path, monkeypatch):
    session, chart, notes, _gone = _delivered_session(tmp_path)
    bridge, _store, _host, _home = _rig(tmp_path, monkeypatch, session=session)
    rows = bridge.deliveryItems()
    assert {row["name"] for row in rows} == {"chart.png", "notes.md", "gone.txt"}
    assert next(row for row in rows if row["name"] == "chart.png")["size"] == chart.stat().st_size
    assert next(row for row in rows if row["name"] == "notes.md")["size"] == notes.stat().st_size
    # attachmentChips 与 _publish 的同一份投影。
    assert {row["name"] for row in bridge.attachmentChips()} == {"photo.png", "spec.txt"}


def test_qml_copy_path_only_accepts_sidecar_paths(qapp, tmp_path, monkeypatch, capsys):
    session, chart, _notes, _gone = _delivered_session(tmp_path)
    bridge, _store, _host, _home = _rig(tmp_path, monkeypatch, session=session)

    assert bridge.copyDeliverablePath(str(chart)) is True
    from PySide6.QtGui import QGuiApplication

    assert QGuiApplication.clipboard().text() == str(chart)
    err = capsys.readouterr().err
    assert "QML COPY REJECTED" not in err

    for bad in ("/etc/passwd", "", str(tmp_path / "evil.png")):
        assert bridge.copyDeliverablePath(bad) is False
    assert "QML COPY REJECTED" in capsys.readouterr().err


def test_qml_open_and_reveal_reject_paths_outside_the_sidecar(qapp, tmp_path, monkeypatch):
    """越权入参：任意路径必须失败，且不能起进程、不能碰磁盘。"""
    session, chart, _notes, _gone = _delivered_session(tmp_path)
    bridge, _store, _host, _home = _rig(tmp_path, monkeypatch, session=session)
    spawned = []
    monkeypatch.setattr("mvvm.services.deliverables._spawn", lambda argv: spawned.append(argv) or True)
    monkeypatch.setattr("mvvm.services.deliverables._desktop_open", lambda path: False)

    assert bridge.openDeliverable("tu-1", "/etc/passwd") is False
    assert bridge.revealDeliverable("tu-1", "/etc/passwd") is False
    assert bridge.openDeliverable("tu-missing", str(chart)) is False
    assert spawned == [], "被拒绝的请求不许起任何进程"

    # 边车内的路径仍然可用。
    assert bridge.openDeliverable("tu-1", str(chart)) is True
    # 目录不在边车（边车登记的是文件）→ 定位也必须拒绝。
    assert bridge.revealDeliverable("tu-1", str(chart.parent)) is False
    assert bridge.revealDeliverable("tu-1", str(chart)) is True
    assert spawned, "合法请求要真的落到后端命令"


def test_qml_delivery_items_empty_without_a_session(qapp, tmp_path, monkeypatch):
    bridge, _store, _host, _home = _rig(tmp_path, monkeypatch)
    bridge._active = ""
    assert bridge.deliveryItems() == []
    assert bridge.attachmentChips() == []
    assert bridge.copyDeliverablePath("/etc/passwd") is False


# ── 发送带附件 ──────────────────────────────────────────────────────────
def test_coerce_attachment_paths_accepts_qjsvalue_and_rejects_junk():
    class FakeJSValue:
        def __init__(self, value):
            self._value = value

        def toString(self):
            return self._value

    assert _coerce_attachment_paths(["/tmp/a.png", FakeJSValue("/tmp/b.png")]) == ["/tmp/a.png", "/tmp/b.png"]
    assert _coerce_attachment_paths(None) == []
    assert _coerce_attachment_paths("/tmp/a.png") == []
    assert _coerce_attachment_paths([None, 3, "", "/tmp/c.png"]) == ["/tmp/c.png"]


def test_send_with_attachment_lands_as_an_image_part(qapp, tmp_path, monkeypatch):
    from datetime import datetime

    transport = text_stream("收到")
    session = StoredSession(id="s-1")
    bridge, store, host, home = _rig(tmp_path, monkeypatch, session=session, transport=transport)
    photo = home / "ws" / "photo.png"
    photo.parent.mkdir(parents=True, exist_ok=True)
    photo.write_bytes(png_bytes())
    # 回形针的真实登记动作（白名单只认这里加进去的路径）。
    assert host.attachments.inspect(str(photo), photo.stat().st_size)["supported"] is True

    assert bridge.sendWithAttachments("看这张图", [str(photo)]) is True
    deadline = time.time() + 10.0
    while time.time() < deadline and not bridge.turn_finished():
        bridge.tick()
        time.sleep(0.02)
    assert bridge.turn_finished()

    saved = store.load_session("s-1")
    user = next(m for m in saved.messages if m.role == "user")
    kinds = [getattr(part, "type", "") for part in user.content]
    assert "image" in kinds
    assert any(getattr(part, "text", "") == "看这张图" for part in user.content)
    image = next(part for part in user.content if getattr(part, "type", "") == "image")
    assert image.mediaType == "image/png"
    assert image.name == "photo.png"
    # 附件贴片按落盘会话现算，发送后立即可见。
    rows = bridge.attachmentChips()
    assert [row["name"] for row in rows] == ["photo.png"]


def test_send_rejects_unpicked_attachment_but_still_sends_text(qapp, tmp_path, monkeypatch, capsys):
    """没经过回形针登记（不在白名单）的路径不能变成附件；提问正文照常发送。"""
    bridge, store, _host, _home = _rig(tmp_path, monkeypatch, session=StoredSession(id="s-1"))
    session = store.load_session("s-1")
    session.messages = []
    store.save("s-1")
    assert bridge.sendWithAttachments("只有正文", ["/etc/passwd"]) is True
    deadline = time.time() + 10.0
    while time.time() < deadline and not bridge.turn_finished():
        bridge.tick()
        time.sleep(0.02)
    saved = store.load_session("s-1")
    user = next(m for m in saved.messages if m.role == "user")
    kinds = [getattr(part, "type", "") for part in user.content]
    assert "image" not in kinds and "document" not in kinds
    text = "".join(getattr(part, "text", "") for part in user.content)
    assert "只有正文" in text
    assert "已忽略未授权文件" in text or "passwd" not in text
