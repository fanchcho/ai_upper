"""附件与工作区文件通道：`fs:*` 九条 + `chat:attachment-image` + 发送时的附件读入。

这里测的是**渲染层真实走的那条链**：桥的 `fs:*` 入口登记白名单 → `chat:send` 的
`build_attachment_part` 读到同一份白名单 → 内容块随用户消息落盘 → 历史重建给出贴片。

第一条用例专门钉住一个曾经真实存在的缺陷：桥和宿主各自 `new` 一份 `AttachmentService`，
白名单各存一份，界面选中的文件在发送时被判「未授权」——两个实例必须同一个。
"""
from __future__ import annotations

import base64
import json
import time

import pytest

from mvvm.models.chat_models import ImagePart, Message, TextPart
from mvvm.services.attachments import (
    ATTACH_FOLDER_PREFIX,
    ATTACH_PATH_PREFIX,
    ATTACH_TEXT_PREFIX,
    AttachmentService,
    paste_name,
)
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.persona_store import PersonaStore
from mvvm.services.provider_setup import ModelGateway
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.settings_service import SettingsService
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.webui.assembly import build_chat_host
from mvvm.webui.bridge import DevaBridge, attachment_image, display_messages

from scripted_transport import ScriptedTransport, sse

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

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


def _stream() -> ScriptedTransport:
    events = [
        sse("message_start", {"type": "message_start", "message": {"usage": {"input_tokens": 1}}}),
        sse(
            "content_block_start",
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        ),
        sse("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "好"}}),
        sse("content_block_stop", {"type": "content_block_stop", "index": 0}),
        sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn"}}),
        sse("message_stop", {"type": "message_stop"}),
    ]
    return ScriptedTransport(events)


@pytest.fixture()
def rig(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    home = tmp_path / "deva-home"
    workspace = tmp_path / "work"
    workspace.mkdir()
    settings = SettingsService(home)
    settings.set_config({"models": MODELS})
    vault = SecretsVault(home)
    vault.set_secret("p1", "sk-test")
    store = ChatSessionStore(home)
    guard = WorkspaceGuard([workspace])
    host, gateway = build_chat_host(
        settings=settings,
        vault=vault,
        store=store,
        guard=guard,
        home=home,
        emit=lambda payload: None,
        emit_sessions_changed=lambda: None,
        transport=_stream(),
    )
    bridge = DevaBridge(settings=settings, personas=PersonaStore(home), store=store, home=home)
    bridge.vault = vault
    bridge.chat_host = host
    bridge.model_gateway = gateway

    class Rig:
        pass

    r = Rig()
    r.bridge, r.host, r.store, r.guard = bridge, host, store, guard
    r.home, r.workspace, r.attachments = home, workspace, host.attachments
    r.call = lambda channel, *args: bridge._handlers[channel](*args)
    return r


# ── 白名单必须只有一份 ────────────────────────────────────────────────────
def test_bridge_and_host_share_one_attachment_service(rig):
    """桥的 fs:* 与宿主的 send 必须读写同一份白名单。

    曾经各 new 一份：`fs:pick-attachments` 登记到桥的实例，发送时宿主读自己的实例，
    结果「界面上选好了，发出去是已忽略未授权文件」。
    """
    assert rig.bridge.attachments is rig.host.attachments


def test_attachment_service_is_shared_even_before_host_is_wired(tmp_path):
    """宿主还没接线时桥用自己那份；接线后立刻切到宿主那份（同一个白名单）。"""
    home = tmp_path / "home"
    bridge = DevaBridge(
        settings=SettingsService(home),
        personas=PersonaStore(home),
        store=ChatSessionStore(home),
        home=home,
    )
    own = bridge.attachments
    assert isinstance(own, AttachmentService)

    class Host:
        attachments = AttachmentService(home, WorkspaceGuard())

    bridge.chat_host = Host()
    assert bridge.attachments is Host.attachments
    assert bridge.attachments is not own


# ── fs:pick-attachments / open-folder / reveal-folder ─────────────────────
def test_pick_attachments_requires_a_dialog_and_never_fakes_success(tmp_path):
    """没注入原生选择框时必须显式报错——不能回空数组假装「用户取消了」。"""
    service = AttachmentService(tmp_path, WorkspaceGuard())
    with pytest.raises(RuntimeError, match="未接线"):
        service.pick_attachments()


def test_pick_attachments_matches_original_shape(rig, tmp_path):
    picked = rig.workspace / "笔记.md"
    picked.write_text("附件正文", encoding="utf-8")
    big = tmp_path / "big.png"
    big.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024 + 1))
    rig.attachments.set_file_dialogs(pick_files=lambda: [str(picked), str(big)])

    out = rig.call("fs:pick-attachments")

    assert out[0] == {
        "path": str(picked),
        "name": "笔记.md",
        "ext": ".md",
        "size": len("附件正文".encode("utf-8")),
        "kind": "text",
        "supported": True,
    }
    # 超限的图片按「只给位置」处理（原版 inspect 的 byPath 分支），不是丢弃
    assert out[1]["kind"] == "file" and out[1]["supported"] is True
    assert str(picked) in rig.attachments.allowed
    assert str(big) in rig.attachments.allowed_files


def test_open_folder_trusts_the_directory(rig):
    folder = rig.workspace / "sub"
    folder.mkdir()
    rig.attachments.set_file_dialogs(open_folder=lambda: str(folder))
    assert rig.call("fs:open-folder") == {"path": str(folder), "name": "sub"}
    assert rig.guard.is_inside_root(folder)


def test_open_folder_cancel_returns_null(rig):
    rig.attachments.set_file_dialogs(open_folder=lambda: None)
    assert rig.call("fs:open-folder") is None


def test_reveal_folder_only_accepts_trusted_directories(rig, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    assert rig.call("fs:reveal-folder", str(outside)) == {"ok": False}
    assert rig.call("fs:reveal-folder", "x") == {"ok": False}

    opened: list[str] = []
    rig.attachments.set_file_dialogs(open_path=lambda p: (opened.append(p), "")[1])
    assert rig.call("fs:reveal-folder", str(rig.workspace)) == {"ok": True}
    assert opened == [str(rig.workspace)]


def test_reveal_folder_reports_opener_failure(rig):
    rig.attachments.set_file_dialogs(open_path=lambda p: "找不到文件管理器")
    assert rig.call("fs:reveal-folder", str(rig.workspace)) == {"ok": False}


# ── fs:paste-attachment / dropped-entries ─────────────────────────────────
def test_paste_attachment_writes_under_paste_dir_and_dedupes(rig, tmp_path):
    payload = {"name": "截图.png", "mime": "image/png", "size": len(PNG), "data": list(PNG)}
    first = rig.call("fs:paste-attachment", payload)
    second = rig.call("fs:paste-attachment", payload)
    assert first == second  # sha256 去重：同一份字节只落一次盘
    assert first["kind"] == "image" and first["supported"] is True
    assert first["path"].startswith(str(rig.attachments.paste_dir))
    with open(first["path"], "rb") as handle:
        assert handle.read() == PNG


def test_paste_attachment_without_data_is_judged_without_writing(rig):
    out = rig.call("fs:paste-attachment", {"name": "a.exe", "mime": "", "size": 0, "data": None})
    assert out["supported"] is False
    assert out["reason"] == "暂不支持的文件类型"


def test_paste_name_sanitises_and_falls_back(monkeypatch):
    assert paste_name("a/b:c*.png", "image/png") == "b_c_.png"
    assert paste_name("image.png", "image/png").startswith("粘贴-")
    monkeypatch.setattr("time.strftime", lambda fmt, tm: "20261114-010203")
    assert paste_name("", "image/png") == "粘贴-20261114-010203.png"


def test_dropped_entries_register_folders_as_roots(rig, tmp_path):
    folder = tmp_path / "dropped"
    folder.mkdir()
    note = rig.workspace / "n.md"
    note.write_text("hi", encoding="utf-8")
    out = rig.call("fs:dropped-entries", [str(folder), str(note), 7, ""])
    assert out[0] == {"folder": {"path": str(folder), "name": "dropped"}}
    assert out[1]["file"]["name"] == "n.md"
    assert out[2] is None and out[3] is None
    assert rig.guard.is_inside_root(folder)


# ── fs:read-dir / read-file / write-file ──────────────────────────────────
def test_read_dir_is_guarded_sorted_and_skips_symlinks(rig, tmp_path):
    (rig.workspace / "b.txt").write_text("b", encoding="utf-8")
    (rig.workspace / "a_dir").mkdir()
    (tmp_path / "outside.txt").write_text("x", encoding="utf-8")
    (rig.workspace / "link").symlink_to(tmp_path / "outside.txt")

    entries = rig.call("fs:read-dir", str(rig.workspace))
    assert [e["name"] for e in entries] == ["a_dir", "b.txt"]
    assert [e["type"] for e in entries] == ["dir", "file"]

    with pytest.raises(PermissionError, match="拒绝访问"):
        rig.call("fs:read-dir", str(tmp_path))


def test_read_file_reports_too_large_and_binary(rig):
    big = rig.workspace / "big.txt"
    big.write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    assert rig.call("fs:read-file", str(big))["tooLarge"] is True

    binary = rig.workspace / "b.bin"
    binary.write_bytes(b"abc\x00def")
    assert rig.call("fs:read-file", str(binary))["binary"] is True

    text = rig.workspace / "t.txt"
    text.write_text("中文", encoding="utf-8")
    assert rig.call("fs:read-file", str(text)) == {
        "path": str(text), "content": "中文",
    }


def test_write_file_does_not_create_parent_directories(rig):
    target = rig.workspace / "deep" / "a.txt"
    with pytest.raises(FileNotFoundError):
        rig.call("fs:write-file", str(target), "x")
    plain = rig.workspace / "ok.txt"
    assert rig.call("fs:write-file", str(plain), "内容") == {"ok": True}
    assert plain.read_text(encoding="utf-8") == "内容"


# ── 发送：附件读入正文前面的内容块 ────────────────────────────────────────
def test_send_reads_picked_attachment_into_content_parts(rig):
    """选中 → 发送：图片进 ImagePart、文本按前缀注入，顺序在提问正文之前。"""
    image = rig.workspace / "shot.png"
    image.write_bytes(PNG)
    note = rig.workspace / "readme.md"
    note.write_text("说明正文", encoding="utf-8")
    rig.attachments.set_file_dialogs(pick_files=lambda: [str(image), str(note)])
    rig.call("fs:pick-attachments")

    rig.call("chat:send", {"sessionId": "s1", "text": "看图", "attachments": [str(image), str(note)]})
    assert _wait_idle(rig, "s1")

    message = rig.store.load_session("s1").messages[0]
    kinds = [part.type for part in message.content]
    assert kinds == ["image", "text", "text"]
    assert message.content[0].mediaType == "image/png"
    assert message.content[1].text.startswith(ATTACH_TEXT_PREFIX + "readme.md")
    assert message.content[2].text == "看图"


def test_send_unpicked_attachment_is_a_note_not_a_part(rig):
    """未授权路径不产出内容块，只在提问正文后括号里说明（原版 note 语义）。"""
    sneaky = rig.workspace / "secret.txt"
    sneaky.write_text("不该被读", encoding="utf-8")
    rig.call("chat:send", {"sessionId": "s2", "text": "看", "attachments": [str(sneaky)]})
    assert _wait_idle(rig, "s2")
    message = rig.store.load_session("s2").messages[0]
    assert [part.type for part in message.content] == ["text"]
    assert "已忽略未授权文件：secret.txt" in message.content[-1].text
    assert "不该被读" not in message.content[-1].text


def test_send_attachment_only_uses_fallback_question(rig):
    from mvvm.webui.host import ATTACHMENT_ONLY_QUESTION

    image = rig.workspace / "only.png"
    image.write_bytes(PNG)
    rig.attachments.set_file_dialogs(pick_files=lambda: [str(image)])
    rig.call("fs:pick-attachments")
    rig.call("chat:send", {"sessionId": "s3", "text": "   ", "attachments": [str(image)]})
    assert _wait_idle(rig, "s3")
    message = rig.store.load_session("s3").messages[0]
    assert message.content[-1].text == ATTACHMENT_ONLY_QUESTION


def test_send_folder_attachment_marks_position_only(rig, tmp_path):
    folder = tmp_path / "proj"
    folder.mkdir()
    rig.call("fs:dropped-entries", [str(folder)])
    rig.call("chat:send", {"sessionId": "s4", "text": "看这个目录", "attachments": [str(folder)]})
    assert _wait_idle(rig, "s4")
    text = rig.store.load_session("s4").messages[0].content[0].text
    assert text.startswith(ATTACH_FOLDER_PREFIX + str(folder))
    assert "内容未展开" in text


def test_send_path_only_attachment_for_oversized_file(rig):
    big = rig.workspace / "big.pdf"
    big.write_bytes(b"%PDF" + b"0" * (20 * 1024 * 1024 + 1))
    rig.attachments.set_file_dialogs(pick_files=lambda: [str(big)])
    rig.call("fs:pick-attachments")
    rig.call("chat:send", {"sessionId": "s5", "text": "这份 PDF", "attachments": [str(big)]})
    assert _wait_idle(rig, "s5")
    text = rig.store.load_session("s5").messages[0].content[0].text
    assert text.startswith(ATTACH_PATH_PREFIX + str(big))
    assert "内容没有直接放进消息" in text


# ── 历史重建：贴片 + 按 ref 取图 ──────────────────────────────────────────
def test_display_messages_rebuilds_attachment_chips():
    messages = [
        Message(
            role="user",
            content=[
                ImagePart(mediaType="image/png", data=base64.b64encode(PNG).decode("ascii"), name="a.png"),
                TextPart(text=f"{ATTACH_TEXT_PREFIX}notes.md\n```\nhello\n```"),
                TextPart(text=f"{ATTACH_FOLDER_PREFIX}/tmp/proj\n（位置）"),
                TextPart(text=f"{ATTACH_PATH_PREFIX}/tmp/x.docx\n（位置）"),
                TextPart(text="提问"),
            ],
        )
    ]
    displayed = display_messages(messages)
    chips = displayed[0]["attachments"]
    assert [chip["kind"] for chip in chips] == ["image", "text", "folder", "file"]
    assert chips[0]["name"] == "a.png" and chips[0]["size"] == len(PNG)
    assert chips[0]["ref"].startswith("0:0:")
    assert chips[1]["size"] == len("hello")
    assert chips[2]["path"] == "/tmp/proj"
    assert chips[3]["name"] == "x.docx"
    assert displayed[0]["text"] == "提问"


def test_attachment_image_resolves_original_and_thumbnail():
    data = base64.b64encode(PNG).decode("ascii")
    message = Message(role="user", content=[ImagePart(mediaType="image/png", data=data, name="a.png")])
    session = type("S", (), {"messages": [message]})()

    displayed = display_messages([message])
    ref = displayed[0]["attachments"][0]["ref"]
    full = attachment_image(session, ref, True)
    assert full == f"data:image/png;base64,{data}"
    assert attachment_image(session, ref, False).startswith("data:")


def test_attachment_image_rejects_stale_or_malformed_refs():
    data = base64.b64encode(PNG).decode("ascii")
    message = Message(role="user", content=[ImagePart(mediaType="image/png", data=data, name="a.png")])
    session = type("S", (), {"messages": [message]})()
    ref = display_messages([message])[0]["attachments"][0]["ref"]

    assert attachment_image(session, "0:0:deadbeef") is None  # 指纹不符（删轮后错位）
    assert attachment_image(session, 42) is None
    assert attachment_image(session, "not-a-ref") is None
    assert attachment_image(session, "9:0:abc") is None  # 下标越界
    assert attachment_image(session, "0:1:abc") is None  # 块下标越界
    assert attachment_image(session, ref, "yes") == attachment_image(session, ref, False)


def test_attachment_image_on_missing_session_is_null(rig):
    """`chat:attachment-image` 拿到不存在的会话 → null（原版 handler 的同一分支）。"""
    assert rig.call("chat:attachment-image", "missing", "0:0:abc", True) is None


def test_chat_attachment_image_channel_reads_from_store(rig):
    image = rig.workspace / "shot.png"
    image.write_bytes(PNG)
    rig.attachments.set_file_dialogs(pick_files=lambda: [str(image)])
    rig.call("fs:pick-attachments")
    rig.call("chat:send", {"sessionId": "s6", "text": "图", "attachments": [str(image)]})
    assert _wait_idle(rig, "s6")

    listed = rig.call("chat:load-session", "s6")
    ref = listed[0]["attachments"][0]["ref"]
    assert rig.call("chat:attachment-image", "s6", ref, True).startswith("data:image/png;base64,")
    assert rig.call("chat:attachment-image", "missing", ref, True) is None


def _wait_idle(rig, session_id: str, timeout: float = 10.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not rig.host.is_busy(session_id):
            return True
        time.sleep(0.02)
    return False


# ── fs:attachment-image（输入框里的图片贴片）──────────────────────────────
def test_attachment_image_channel_returns_data_url_only_for_allowed_images(rig, tmp_path):
    """缩略图/原图都走 `fs:attachment-image`：未授权或非图片一律 null，不抛错。"""
    image = rig.workspace / "shot.png"
    image.write_bytes(PNG)
    rig.attachments.set_file_dialogs(pick_files=lambda: [str(image)])
    rig.call("fs:pick-attachments")  # 登记进 allowed

    full = rig.call("fs:attachment-image", str(image), True)
    assert full.startswith("data:image/png;base64,")
    assert rig.call("fs:attachment-image", str(image)).startswith("data:image/")

    note = rig.workspace / "readme.md"
    note.write_text("正文", encoding="utf-8")
    assert rig.call("fs:attachment-image", str(note), True) is None  # 非图片
    outside = tmp_path / "outside.png"
    outside.write_bytes(PNG)
    assert rig.call("fs:attachment-image", str(outside), True) is None  # 未授权
    assert rig.call("fs:attachment-image", 42, True) is None
    assert rig.call("fs:attachment-image", "", True) is None
