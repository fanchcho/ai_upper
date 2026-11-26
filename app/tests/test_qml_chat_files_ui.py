"""QML 入口的附件贴片 / 交付卡：数据层判据 + 壳槽位的路径安全 + 回形针真实选文件。

这条链路与 web 入口共用同一份服务（`transcript_parts` / `deliverables` / `attachments`），
所以这里只测「QML 侧有没有接对」：

1. **数据层**（`qml_shell_sessions`）：附件贴片带真实体积与缩略图 data URI；交付卡的每一行
   带真实文件名 / 体积 / 是否已不存在 / 能否打开；路径只认 `present_files` 的边车。
2. **回形针**：`pickAttachments()` 真的走 `QFileDialog.getOpenFileNames`（这里替身记录调用），
   选中的文件登记白名单后回给界面；取消返回空列表。
3. **发送**：`sendWithAttachments()` 把路径原样透传给 `ChatHost.send`，图片落成 `image` 内容块。
4. **交付卡按钮**：`openDeliverable` / `revealDeliverable` / `copyDeliverablePath` 只接受边车里
   登记过的路径，任意路径一律拒绝（不弹系统进程、不进剪贴板）。
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from mvvm.models.chat_models import (
    ImagePart,
    Message,
    StoredSession,
    TextPart,
    ToolResultPart,
    ToolUsePart,
)
from mvvm.services.tool_results import record_delivered

from qml_shell_sessions import (
    attachment_rows,
    delivery_rows,
    delivery_tool_use_ids,
    format_bytes,
    transcript_markdown,
)
from test_qml_shell import _bridge, text_stream

PNG_4X4 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAIAAAAmkwkpAAAAEElEQVR4nGP4z8AARwzEcQCukw/x0F8jngAAAABJRU5ErkJggg=="
)


# ── 夹具 ──────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def qapp():
    """与 `test_qml_shell` 同口径：不需要真窗口，但槽位里的剪贴板要一个 GUI 应用。"""
    from PySide6.QtGui import QGuiApplication

    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


@pytest.fixture()
def workspace(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    (root / "report.md").write_text("# 报告\n正文\n" * 40, encoding="utf-8")
    (root / "build.py").write_text("print('hi')\n", encoding="utf-8")
    (root / "shot.png").write_bytes(PNG_4X4)
    return root


def _session_with_files(root: Path, *, tool_id: str = "tu_present_1") -> StoredSession:
    """一条真实形状的会话：user[image, text] → assistant[text, present_files]。"""
    png = root / "shot.png"
    b64 = base64.b64encode(png.read_bytes()).decode("ascii")
    session = StoredSession(id="s-files", title="带附件的消息")
    session.messages = [
        Message(
            role="user",
            content=[
                ImagePart(type="image", mediaType="image/png", name="shot.png", data=b64),
                TextPart(text="这两份文件请整理成季度报告"),
            ],
        ),
        Message(
            role="assistant",
            content=[
                TextPart(text="已生成报告。"),
                ToolUsePart(
                    id=tool_id,
                    name="present_files",
                    input={"paths": [str(root / "report.md")]},
                ),
                ToolResultPart(toolUseId=tool_id, content="delivered", isError=False),
            ],
        ),
    ]
    return session


def _with_sidecar(session: StoredSession, root: Path, tool_id: str = "tu_present_1") -> StoredSession:
    class _Result:
        delivered = [str(root / "report.md"), str(root / "build.py")]

    session.delivered = record_delivered(session.delivered, tool_id, _Result())
    return session


# ── 1. 数据层：体积文案 ───────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("size", "expected"),
    [
        (None, ""),
        (-1, ""),
        (0, "0 B"),
        (221, "221 B"),
        (1023, "1023 B"),
        (1024, "1 KB"),
        (1536, "2 KB"),
        (1024 * 1024, "1.0 MB"),
        (int(1.5 * 1024 * 1024), "1.5 MB"),
        (7 * 1024 * 1024 * 1024, "7.0 GB"),
        ("512", "512 B"),
        ("oops", ""),
    ],
)
def test_format_bytes_matches_the_renderer_scale(size, expected):
    assert format_bytes(size) == expected


# ── 2. 数据层：正文里的附件行 ─────────────────────────────────────────────
def test_transcript_markdown_inlines_images_and_lists_documents_before_the_question(workspace):
    session = _session_with_files(workspace)
    markdown = transcript_markdown(session.messages)
    assert "![shot.png](data:image/png;base64," in markdown
    # 附件行排在提问正文之前（与原版贴片顺序一致）。
    assert markdown.index("![shot.png]") < markdown.index("这两份文件请整理成季度报告")
    assert "已生成报告。" in markdown


def test_transcript_markdown_keeps_a_message_that_has_only_an_attachment(workspace):
    b64 = base64.b64encode((workspace / "shot.png").read_bytes()).decode("ascii")
    messages = [
        Message(
            role="user",
            content=[ImagePart(type="image", mediaType="image/png", name="shot.png", data=b64)],
        )
    ]
    markdown = transcript_markdown(messages)
    assert "## 你" in markdown
    assert "![shot.png](data:image/png;base64," in markdown


# ── 3. 数据层：附件贴片（真实体积 + 缩略图）───────────────────────────────
def test_attachment_rows_carry_real_size_text_and_a_thumbnail(workspace):
    session = _session_with_files(workspace)
    rows = attachment_rows(session)
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "shot.png"
    assert row["kind"] == "image"
    assert row["size"] == len((workspace / "shot.png").read_bytes())
    assert row["sizeText"] == format_bytes(row["size"])
    assert row["thumb"].startswith("data:image/png;base64,")
    assert row["index"] == 0


def test_attachment_rows_are_empty_without_a_session():
    assert attachment_rows(None) == []


# ── 4. 数据层：交付卡行 ───────────────────────────────────────────────────
def test_delivery_rows_read_the_sidecar_and_report_real_file_facts(workspace):
    session = _with_sidecar(_session_with_files(workspace), workspace)
    rows = delivery_rows(session)
    assert [row["name"] for row in rows] == ["report.md", "build.py"]
    report = rows[0]
    assert report["size"] == (workspace / "report.md").stat().st_size
    assert report["sizeText"] == format_bytes(report["size"])
    assert report["dir"] == str(workspace)
    assert report["openable"] is True
    assert report["missing"] is False
    assert report["toolUseId"] == "tu_present_1"
    # 脚本类不在打开白名单里：按钮只能是禁用态。
    assert rows[1]["openable"] is False


def test_delivery_rows_mark_a_file_that_was_moved_away(workspace):
    session = _with_sidecar(_session_with_files(workspace), workspace)
    (workspace / "build.py").unlink()
    rows = delivery_rows(session)
    assert rows[1]["missing"] is True
    assert rows[1]["size"] is None
    assert rows[1]["sizeText"] == ""


def test_delivery_rows_ignore_messages_without_a_sidecar(workspace):
    """历史里提到了文件、但边车没登记（旧会话）→ 不出交付卡，避免把历史字符串当路径。"""
    session = _session_with_files(workspace)
    assert delivery_rows(session) == []
    assert delivery_tool_use_ids(session.messages) == ["tu_present_1"]


def test_delivery_tool_use_ids_only_accept_present_files_and_dedupe():
    messages = [
        Message(
            role="assistant",
            content=[
                ToolUsePart(id="tu_a", name="present_files", input={"paths": ["/tmp/a"]}),
                ToolUsePart(id="tu_b", name="read_file", input={"path": "/tmp/b"}),
                ToolUsePart(id="tu_a", name="present_files", input={"paths": ["/tmp/a"]}),
            ],
        )
    ]
    assert delivery_tool_use_ids(messages) == ["tu_a"]


def test_delivery_rows_dedupe_repeated_paths_and_drop_relative_entries():
    session = StoredSession(id="s")
    session.delivered = {
        "tu_1": ["/tmp/once.md", "relative.md"],
        "tu_2": ["/tmp/once.md", "/tmp/twice.md"],
    }
    session.messages = [
        Message(
            role="assistant",
            content=[
                ToolUsePart(id="tu_1", name="present_files", input={"paths": []}),
                ToolUsePart(id="tu_2", name="present_files", input={"paths": []}),
            ],
        )
    ]
    assert [row["path"] for row in delivery_rows(session)] == ["/tmp/once.md", "/tmp/twice.md"]


# ── 5. 回形针：真弹选择框 + 白名单 ────────────────────────────────────────
def test_pick_attachments_goes_through_the_real_file_dialog(qapp, tmp_path, monkeypatch, capsys):
    bridge, _store, _host = _bridge(tmp_path, monkeypatch, text_stream("ok"), sessions=[("s-1", "旧")])
    assert bridge.setLanguage("zh-CN")
    picked = tmp_path / "home" / "shot.png"
    picked.write_bytes(PNG_4X4)
    calls = []

    from utils.qt_compat import QtWidgets

    def fake_dialog(parent, caption, directory, filters, *args, **kwargs):
        calls.append({"caption": caption, "filters": filters})
        return [str(picked)], filters

    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileNames", fake_dialog)
    result = bridge.pickAttachments()
    assert calls, "回形针必须真的弹系统选择框"
    assert "支持的文件" in calls[0]["filters"]
    assert str(picked) in result
    out = capsys.readouterr()
    assert "QML PICK" in out.out
    # 日志里是 `json.dumps(paths)`，Windows 路径的反斜杠会被转义成 `\\`；
    # 直接比对原始路径在 Windows 上必然不命中，所以按同一序列化口径断言。
    assert json.dumps([str(picked)], ensure_ascii=False) in out.out


def test_pick_attachments_cancelled_returns_empty_and_logs_nothing(qapp, tmp_path, monkeypatch, capsys):
    bridge, _store, _host = _bridge(tmp_path, monkeypatch, text_stream("ok"), sessions=[("s-1", "旧")])
    from utils.qt_compat import QtWidgets

    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getOpenFileNames", lambda *a, **k: ([], "")
    )
    assert bridge.pickAttachments() == []
    assert "QML PICK" in capsys.readouterr().out


# ── 6. 发送：附件随消息落盘 ──────────────────────────────────────────────
def test_send_with_attachments_persists_the_image_content_part(qapp, tmp_path, monkeypatch, capsys):
    bridge, store, _host = _bridge(
        tmp_path, monkeypatch, text_stream("收到"), sessions=[("s-1", "旧")]
    )
    png = tmp_path / "home" / "shot.png"
    png.write_bytes(PNG_4X4)
    from utils.qt_compat import QtWidgets

    monkeypatch.setattr(
        QtWidgets.QFileDialog, "getOpenFileNames", lambda *a, **k: ([str(png)], "")
    )
    assert bridge.openSession("s-1") is True
    assert bridge.pickAttachments() == [str(png)]

    assert bridge.sendWithAttachments("这张图里的文件能给我吗", [str(png)]) is True
    from test_qml_shell import _tick_until

    assert _tick_until(bridge, bridge.turn_finished)
    session = store.load_session("s-1")
    user_message = session.messages[-2]
    kinds = [getattr(part, "type", "") for part in user_message.content]
    assert "image" in kinds, "附件必须落成 image 内容块，而不是只留一个路径字符串"
    assert user_message.text() == "这张图里的文件能给我吗"

    out = capsys.readouterr().out
    assert "QML SEND" in out
    payload = json.loads(out.split("QML SEND ", 1)[1].splitlines()[0])
    assert payload["attachments"] == [str(png)]

    rows = bridge.attachmentChips()
    assert [row["name"] for row in rows] == ["shot.png"]
    assert rows[0]["size"] == len(PNG_4X4)


def test_send_with_attachments_rejects_an_empty_message_without_files(qapp, tmp_path, monkeypatch):
    bridge, _store, _host = _bridge(tmp_path, monkeypatch, text_stream("ok"), sessions=[("s-1", "旧")])
    bridge.openSession("s-1")
    assert bridge.sendWithAttachments("   ", []) is False


# ── 7. 交付卡按钮：只认边车路径 ──────────────────────────────────────────
def _bridge_with_delivery(qapp, tmp_path, monkeypatch, workspace):
    bridge, store, _host = _bridge(tmp_path, monkeypatch, text_stream("ok"), sessions=[("s-1", "旧")])
    store.ensure_session("s-1")
    session = store.load_session("s-1")
    session.messages = _session_with_files(workspace).messages
    store.save("s-1")
    session = store.load_session("s-1")
    session.delivered = {"tu_present_1": [str(workspace / "report.md")]}
    store.save("s-1")
    bridge.openSession("s-1")
    return bridge, store


def test_delivery_rows_reach_the_qml_properties(qapp, tmp_path, monkeypatch, workspace):
    bridge, _store = _bridge_with_delivery(qapp, tmp_path, monkeypatch, workspace)
    rows = bridge.deliveryItems()
    assert [row["name"] for row in rows] == ["report.md"]
    assert rows[0]["sizeText"] == format_bytes((workspace / "report.md").stat().st_size)


def test_open_and_reveal_only_accept_paths_from_the_sidecar(qapp, tmp_path, monkeypatch, workspace):
    bridge, _store = _bridge_with_delivery(qapp, tmp_path, monkeypatch, workspace)
    from mvvm.services import deliverables as service

    opened, revealed = [], []
    # 替身保留服务层的口径：序号为 -1（路径不在边车里）时返回失败。
    monkeypatch.setattr(
        service,
        "open_item",
        lambda session, tool_id, index: opened.append(index) or {"ok": index >= 0},
    )
    monkeypatch.setattr(
        service,
        "reveal",
        lambda session, tool_id, index: revealed.append(index) or {"ok": index >= 0},
    )
    import qml_shell

    monkeypatch.setattr(qml_shell, "open_item", service.open_item)
    monkeypatch.setattr(qml_shell, "reveal", service.reveal)

    delivered = str(workspace / "report.md")
    forged = str(workspace / "build.py")  # 真实存在，但不在边车里
    assert bridge.openDeliverable("tu_present_1", delivered) is True
    assert opened == [0]
    assert bridge.openDeliverable("tu_present_1", forged) is False
    assert opened[-1] == -1, "任意路径取不到序号，服务层据此拒绝"

    assert bridge.revealDeliverable("tu_present_1", delivered) is True
    assert bridge.revealDeliverable("tu_other", delivered) is False
    assert bridge.revealDeliverable("tu_present_1", "/etc/passwd") is False
    assert revealed == [0, -1, -1]


def test_copy_path_only_accepts_paths_from_the_sidecar(qapp, tmp_path, monkeypatch, workspace, capsys):
    bridge, _store = _bridge_with_delivery(qapp, tmp_path, monkeypatch, workspace)
    from utils.qt_compat import QtGui

    clipboard = QtGui.QGuiApplication.clipboard()
    clipboard.setText("sentinel")
    delivered = str(workspace / "report.md")
    assert bridge.copyDeliverablePath(delivered) is True
    assert clipboard.text() == delivered

    forged = str(workspace / "build.py")
    assert bridge.copyDeliverablePath(forged) is False
    assert clipboard.text() == delivered, "被拒绝的路径不许改剪贴板"
    assert "QML COPY REJECTED" in capsys.readouterr().err


def test_copy_path_rejects_non_string_and_sessions_without_a_sidecar(qapp, tmp_path, monkeypatch, capsys):
    bridge, _store, _host = _bridge(tmp_path, monkeypatch, text_stream("ok"), sessions=[("s-1", "旧")])
    bridge.openSession("s-1")
    assert bridge.copyDeliverablePath("/etc/passwd") is False
    assert "QML COPY REJECTED" in capsys.readouterr().err
