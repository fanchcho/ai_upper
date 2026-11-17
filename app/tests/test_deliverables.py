"""交付卡（`present_files`）：边车写入 + 四个操作 + 路径白名单。

三条主线：

1. **写边车**：工具结果里的 `delivered` 必须按 `toolUseId` 落进 `StoredSession.delivered`
   并写盘（重启后仍在）。此前 `ToolResult.delivered` 有值但没人消费，会话里也没有这个键。
2. **四个操作**：`inspect` / `thumbnail` / `open` / `reveal` 的返回结构照原版
   `shared/deliverables.ts` 契约（`{path,name,dir,size,openable}`、`{ok}`、data URI / null）。
3. **路径安全**：路径只能来自边车。调用方给任意路径 / 伪造 toolUseId / 越界序号都必须拿不到
   文件；`open` 只放行 `OPENABLE` 白名单（`.py` / `.sh` 一律拒绝）。

这里只测服务层。界面侧真正调这四个操作的是 QML 壳的四个槽
（`openDeliverable` / `revealDeliverable` / `copyDeliverablePath` / `deliveryItems`），
它们「只认边车路径」的断言在 `app/tests/test_qml_chat_files.py`；随 WebEngine 承载窗口
删除的 `DevaBridge` 通道层不再是产品代码。
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[1] / "src"

from mvvm.models.chat_models import Message, TextPart
from mvvm.services import deliverables as deliverables_service
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.deliverables import (
    OPENABLE,
    delivered_path,
    delivered_paths,
    inspect,
    is_openable,
    open_command,
    open_item,
    reveal,
    reveal_command,
    thumbnail,
)
from mvvm.services.provider_gateway import Done, GenerateRequest, TextDelta, ToolCall
from mvvm.services.tool_results import record_delivered
from mvvm.services.tool_runtime import ToolResult, ToolRuntime
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.view_models.chat_vm import ChatViewModel

# 4×4 红色 PNG（有真实像素，缩略图不会解成空图）。
PNG_4X4 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAIAAAAmkwkpAAAAEElEQVR4nGP4z8AARwzEcQCukw/x0F8jngAAAABJRU5ErkJggg=="
)


# ── 夹具 ──────────────────────────────────────────────────────────────────
@pytest.fixture()
def workspace(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    (root / "report.md").write_text("# 报告\n正文\n", encoding="utf-8")
    (root / "chart.png").write_bytes(PNG_4X4)
    (root / "build.sh").write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    (root / "tool.py").write_text("print('hi')\n", encoding="utf-8")
    return root


class PresentOnceProvider:
    """首轮回一次 `present_files` 调用，拿到 tool_result 后回一句正文结束。

    与 `FakeProvider` 的区别：内置剧本固定是 `read_file`，这里要的是一次真实的
    `present_files`（`ToolResult.delivered` 只有它会产生）。
    """

    name = "present-once"

    def __init__(self, paths, tool_use_id="tu_present_1"):
        self._paths = list(paths)
        self._tool_use_id = tool_use_id
        self.requests = []

    async def stream(self, request: GenerateRequest):
        self.requests.append(request)
        if _has_tool_result(request.messages):
            yield TextDelta("报告已生成，见下方交付卡。")
            yield Done("end_turn")
            return
        yield TextDelta("我把报告整理好了。")
        yield ToolCall(id=self._tool_use_id, name="present_files", input={"paths": self._paths})
        yield Done("tool_use")


def _has_tool_result(messages) -> bool:
    for message in messages:
        if isinstance(message.content, str):
            continue
        for part in message.content:
            if getattr(part, "type", "") == "tool_result":
                return True
    return False


# ── 1. 写边车 ─────────────────────────────────────────────────────────────
def test_tool_delivery_is_written_to_the_session_sidecar_and_persisted(tmp_path, workspace):
    """`present_files` 成功后：边车按 toolUseId 记绝对路径，重启（新 Store）读得回来。"""
    home = tmp_path / "home"
    store = ChatSessionStore(home)
    tools = ToolRuntime(WorkspaceGuard([workspace]), workspace)
    provider = PresentOnceProvider(["report.md", "chart.png"], tool_use_id="tu_present_1")
    vm = ChatViewModel(store, provider, tools, model="fake-model")
    vm.open_session("s1")
    vm.input_text_property.set_value("把报告给我")

    vm.send()
    assert vm.wait_idle(5.0)
    assert vm.error == "", vm.error
    assert vm.tool_results[0].delivered == [
        str(workspace / "report.md"),
        str(workspace / "chart.png"),
    ]

    # 磁盘上的边车
    raw = json.loads((home / "data" / "chats" / "s1.json").read_text(encoding="utf-8"))
    assert raw["delivered"] == {
        "tu_present_1": [str(workspace / "report.md"), str(workspace / "chart.png")]
    }
    # messages 里仍是模型原样发出的参数（相对路径），不被改写
    tool_use = [
        part
        for message in raw["messages"]
        if not isinstance(message["content"], str)
        for part in message["content"]
        if part["type"] == "tool_use"
    ][0]
    assert tool_use["input"] == {"paths": ["report.md", "chart.png"]}

    reread = ChatSessionStore(home).load_session("s1")
    assert delivered_paths(reread, "tu_present_1") == [
        str(workspace / "report.md"),
        str(workspace / "chart.png"),
    ]


def test_failed_present_files_leaves_no_sidecar(tmp_path, workspace):
    """交付失败（一个路径不对 → 整体失败）不写边车；界面不该画出不存在的文件。"""
    home = tmp_path / "home"
    store = ChatSessionStore(home)
    tools = ToolRuntime(WorkspaceGuard([workspace]), workspace)
    provider = PresentOnceProvider(["report.md", "nope.md"])
    vm = ChatViewModel(store, provider, tools, model="fake-model")
    vm.open_session("s2")
    vm.input_text_property.set_value("交付")

    vm.send()
    assert vm.wait_idle(5.0)
    raw = json.loads((home / "data" / "chats" / "s2.json").read_text(encoding="utf-8"))
    assert "delivered" not in raw


def test_record_delivered_is_pure_and_ignores_empty_results():
    """辅助函数不改入参；没有交付时原样返回（None 仍是 None）。"""
    before = {"old": ["/tmp/a"]}
    assert record_delivered(before, "t2", ToolResult("ok", False)) is before
    after = record_delivered(before, "t3", ToolResult("ok", False, delivered=["/tmp/b"]))
    assert after == {"old": ["/tmp/a"], "t3": ["/tmp/b"]}
    assert before == {"old": ["/tmp/a"]}


def test_delete_turns_prunes_the_delivery_sidecar(tmp_path, workspace):
    """删轮时按存活 tool_use 修剪边车（Deva `deleteTurns` 的 prune）；全删则清空。"""
    store = ChatSessionStore(tmp_path / "home")
    store.ensure_session("s3")
    store.append_message("s3", Message(role="user", content="第一轮"))
    session = store.load_session("s3")
    session.messages.append(
        Message(role="assistant", content=[TextPart(text="交付中")])
    )
    from mvvm.models.chat_models import ToolUsePart

    session.messages[-1].content.append(
        ToolUsePart(id="tu_keep", name="present_files", input={"paths": ["a.txt"]})
    )
    session.delivered = {"tu_keep": [str(workspace / "report.md")], "tu_gone": ["/tmp/x"]}
    store.save("s3")

    store.delete_turns("s3", [0])
    trimmed = store.load_session("s3")
    assert trimmed.delivered is None


# ── 2. 四条通道的服务层 ───────────────────────────────────────────────────
def _session_with(workspace, paths):
    class Session:
        delivered = {"tu": list(paths)}

    return Session()


def test_inspect_reports_real_name_size_dir_and_openable(workspace):
    session = _session_with(
        workspace, [str(workspace / "report.md"), str(workspace / "build.sh")]
    )
    rows = inspect(session, "tu")
    assert [row["name"] for row in rows] == ["report.md", "build.sh"]
    assert rows[0]["dir"] == str(workspace)
    assert rows[0]["size"] == (workspace / "report.md").stat().st_size
    assert rows[0]["openable"] is True
    # 脚本类可在交付卡上看到，但不许用默认应用打开
    assert rows[1]["openable"] is False


def test_inspect_reports_missing_file_as_null_size(workspace):
    missing = workspace / "gone.md"
    rows = inspect(_session_with(workspace, [str(missing)]), "tu")
    assert rows[0]["size"] is None
    assert rows[0]["openable"] is True


def test_inspect_unknown_tool_use_id_is_empty(workspace):
    session = _session_with(workspace, [str(workspace / "report.md")])
    assert inspect(session, "tu_other") == []
    assert inspect(session, "") == []
    assert inspect(_session_with(workspace, []), "tu") == []


def test_thumbnail_scales_an_image_to_a_data_url(workspace):
    url = thumbnail(_session_with(workspace, [str(workspace / "chart.png")]), "tu", 0)
    assert isinstance(url, str) and url.startswith("data:image/png;base64,")
    assert len(url) > 40


def _thumbnail_in_subprocess(app_class, path, qt_env="offscreen"):
    """在干净子进程里按指定应用类跑一次缩略图，返回输出（'NONE' 或 data URI 前缀）。

    必须子进程：Qt 的应用实例是进程全局的，本进程里早先的用例可能已经建过
    `QApplication`，进程内的结果会随执行顺序变——那样断言的是顺序而不是行为。
    `app_class` 写全名（`QtGui.QGuiApplication` / `QtWidgets.QApplication`）。
    """
    module, name = app_class.split(".")
    script = (
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "from PySide6 import QtGui, QtWidgets\n"
        "cls = %s.%s\n"
        "app = cls.instance() or cls([])\n"
        "from mvvm.services.deliverables import thumbnail\n"
        "class S:\n"
        "    delivered = {'tu': [%r]}\n"
        "url = thumbnail(S(), 'tu', 0)\n"
        "print(url[:40] if url else 'NONE')\n"
    ) % (str(_SRC), module, name, str(path))
    env = dict(os.environ, QT_QPA_PLATFORM=qt_env)
    out = subprocess.run(
        [sys.executable, "-c", script], env=env, capture_output=True, text=True, timeout=120
    )
    assert out.returncode == 0, out.stderr[-2000:]
    return out.stdout.strip()


def test_thumbnail_of_a_non_image_is_none_without_a_widget_app(workspace):
    """只有 `QGuiApplication` 时（QML 入口）回落不执行，返回 None 而不是崩进程。

    `QFileIconProvider` 在 QGuiApplication 上 `icon(...)` 会段错误（实测 PySide6 6.11.2 /
    offscreen：`Segmentation fault`，`core dumped`），所以服务层先探进程类型。渲染层对
    null 缩略图有占位图，显示占位好过崩。
    """
    assert _thumbnail_in_subprocess("QtGui.QGuiApplication", workspace / "report.md") == "NONE"


def test_thumbnail_falls_back_to_a_file_icon_under_a_real_qapplication(workspace):
    """真 `QApplication` 下非图片回落文件类型图标（QML 壳建的就是 QApplication）。"""
    assert _thumbnail_in_subprocess("QtWidgets.QApplication", workspace / "report.md").startswith(
        "data:image/"
    )


def test_thumbnail_of_a_missing_file_is_none(workspace):
    assert thumbnail(_session_with(workspace, [str(workspace / "gone.png")]), "tu", 0) is None


def test_open_only_allows_the_openable_whitelist(workspace, monkeypatch):
    opened = []
    monkeypatch.setattr(deliverables_service, "_desktop_open", lambda p: opened.append(p) or True)
    session = _session_with(
        workspace,
        [str(workspace / "report.md"), str(workspace / "build.sh"), str(workspace / "tool.py")],
    )
    assert open_item(session, "tu", 0) == {"ok": True}
    assert open_item(session, "tu", 1) == {"ok": False}
    assert open_item(session, "tu", 2) == {"ok": False}
    assert opened == [str(workspace / "report.md")]


def test_open_rejects_missing_files_and_bad_indices(workspace, monkeypatch):
    monkeypatch.setattr(deliverables_service, "_desktop_open", lambda p: True)
    session = _session_with(workspace, [str(workspace / "gone.md")])
    assert open_item(session, "tu", 0) == {"ok": False}
    assert open_item(session, "tu", 1) == {"ok": False}
    assert open_item(session, "tu", -1) == {"ok": False}
    assert open_item(session, "tu", True) == {"ok": False}
    assert open_item(session, "tu", "0") == {"ok": False}


def test_reveal_spawns_the_platform_command_without_a_shell(workspace, monkeypatch):
    spawned = []
    monkeypatch.setattr(deliverables_service, "_spawn", lambda argv: spawned.append(argv) or True)
    result = reveal(_session_with(workspace, [str(workspace / "report.md")]), "tu", 0)
    assert result == {"ok": True}
    assert spawned == [["xdg-open", str(workspace)]]


def test_reveal_refuses_missing_files(workspace, monkeypatch):
    spawned = []
    monkeypatch.setattr(deliverables_service, "_spawn", lambda argv: spawned.append(argv) or True)
    assert reveal(_session_with(workspace, [str(workspace / "gone.md")]), "tu", 0) == {"ok": False}
    assert spawned == []


def test_reveal_command_is_per_platform_and_keeps_metacharacters_literal(monkeypatch):
    """路径里带引号 / 分号也只当一个参数：命令用列表传，不经 shell。"""
    weird = '/tmp/a b"c;rm -rf ~/x.md'
    monkeypatch.setattr(deliverables_service.sys, "platform", "linux")
    assert reveal_command(weird) == ["xdg-open", '/tmp/a b"c;rm -rf ~']
    monkeypatch.setattr(deliverables_service.sys, "platform", "darwin")
    assert reveal_command(weird) == ["open", "-R", weird]
    monkeypatch.setattr(deliverables_service.sys, "platform", "win32")
    assert reveal_command(weird)[0] == "explorer"
    assert reveal_command(weird)[1].startswith("/select,")


def test_open_command_is_per_platform_and_never_joins_arguments(monkeypatch):
    """QDesktopServices 不可用时的回落：同样是列表参数，路径整个作为一个 argv。"""
    weird = '/tmp/a b"c;rm -rf ~/x.md'
    monkeypatch.setattr(deliverables_service.sys, "platform", "linux")
    assert open_command(weird) == ["xdg-open", weird]
    monkeypatch.setattr(deliverables_service.sys, "platform", "darwin")
    assert open_command(weird) == ["open", weird]
    monkeypatch.setattr(deliverables_service.sys, "platform", "win32")
    assert open_command(weird) == ["cmd", "/c", "start", "", weird]


def test_open_falls_back_when_desktop_services_refuse(workspace, monkeypatch):
    """offscreen 平台插件不支持 openDocument 时，回落平台打开器（否则按钮点了没反应）。"""
    spawned = []
    monkeypatch.setattr(deliverables_service, "_desktop_open", lambda p: False)
    monkeypatch.setattr(deliverables_service, "_spawn", lambda argv: spawned.append(argv) or True)
    result = open_item(_session_with(workspace, [str(workspace / "report.md")]), "tu", 0)
    assert result == {"ok": True}
    assert spawned == [["xdg-open", str(workspace / "report.md")]]


def test_open_reports_failure_when_both_paths_fail(workspace, monkeypatch):
    monkeypatch.setattr(deliverables_service, "_desktop_open", lambda p: False)
    monkeypatch.setattr(deliverables_service, "_spawn", lambda argv: False)
    result = open_item(_session_with(workspace, [str(workspace / "report.md")]), "tu", 0)
    assert result == {"ok": False}


# ── 3. 路径安全：只能来自边车 ─────────────────────────────────────────────
def test_relative_and_non_string_entries_are_dropped():
    class Session:
        delivered = {"tu": ["relative/path.md", 123, None, "/abs/ok.md"]}

    assert delivered_paths(Session(), "tu") == ["/abs/ok.md"]


def test_no_sidecar_means_no_paths_even_if_messages_mention_files(workspace):
    """旧会话（边车写入之前）里的 tool_use 参数**不**当路径用。

    原版会回落到 `tool_use.input.paths` 的绝对路径；这里刻意不做——那是模型原样发出的
    字符串，未经工具解析。宁可没有卡片，也不开一个任意路径口子。
    """
    from mvvm.models.chat_models import ToolUsePart

    class Session:
        delivered = None
        messages = [
            Message(
                role="assistant",
                content=[
                    ToolUsePart(
                        id="tu_old",
                        name="present_files",
                        input={"paths": [str(workspace / "report.md")]},
                    )
                ],
            )
        ]

    assert delivered_paths(Session(), "tu_old") == []
    assert inspect(Session(), "tu_old") == []
    assert open_item(Session(), "tu_old", 0) == {"ok": False}
    assert thumbnail(Session(), "tu_old", 0) is None


def test_tool_use_id_cannot_smuggle_a_path(workspace):
    """toolUseId 是普通字符串键；拿一个路径当 id 也查不到任何东西。"""
    session = _session_with(workspace, [str(workspace / "report.md")])
    assert delivered_paths(session, str(workspace / "report.md")) == []
    assert inspect(session, str(workspace / "build.sh")) == []


def test_delivered_path_requires_a_non_negative_integer_index(workspace):
    session = _session_with(workspace, [str(workspace / "report.md")])
    assert delivered_path(session, "tu", 0) == str(workspace / "report.md")
    for bad in (None, "0", 1.0, True, -1, 2):
        assert delivered_path(session, "tu", bad) is None


def test_openable_whitelist_matches_the_original_set():
    """白名单逐项照抄原版（少一项会让正常文件打不开，多一项会放行脚本）。"""
    assert OPENABLE == frozenset(
        {
            ".html", ".htm", ".md", ".markdown", ".txt", ".log", ".csv", ".tsv", ".json",
            ".xml", ".yaml", ".yml",
            ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".odt", ".ods",
            ".odp", ".rtf", ".epub",
            ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico", ".tif",
            ".tiff", ".avif", ".heic",
            ".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v",
            ".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".opus",
            ".zip",
        }
    )
    assert is_openable("/tmp/REPORT.MD") is True
    for blocked in ("/tmp/x.py", "/tmp/x.sh", "/tmp/x.exe", "/tmp/x.bat", "/tmp/x.js", "/tmp/x"):
        assert is_openable(blocked) is False


# ── 4. 会话落盘 → 服务取数（无会话、无 toolUseId 的边界）─────────────────────
def _seed_session(store: ChatSessionStore, workspace, delivered):
    """落一条带交付边车的会话（含 tool_use，删轮修剪也能对上）。"""
    from mvvm.models.chat_models import ToolUsePart

    store.ensure_session("dl")
    store.append_message("dl", Message(role="user", content="把文件给我"))
    store.append_message(
        "dl",
        Message(
            role="assistant",
            content=[ToolUsePart(id="tu1", name="present_files", input={"paths": ["report.md"]})],
        ),
    )
    session = store.load_session("dl")
    session.delivered = delivered
    store.save("dl")
    return session


def test_seeded_session_round_trips_through_the_store(tmp_path, workspace):
    """`_seed_session` 的落盘能原样读回：边车与 `present_files` 调用都在。"""
    store = ChatSessionStore(tmp_path / "home")
    session = _seed_session(store, workspace, {"tu1": [str(workspace / "report.md")]})
    reloaded = store.load_session("dl")
    assert reloaded.delivered == {"tu1": [str(workspace / "report.md")]}
    assert delivered_paths(reloaded, "tu1") == [str(workspace / "report.md")]
    assert inspect(reloaded, "tu1")[0]["size"] == (workspace / "report.md").stat().st_size


def test_operations_on_a_session_without_a_sidecar_return_nothing(tmp_path, workspace):
    """没有边车 / 边车里没有这条 toolUseId：四个操作一律给空结果，不抛错。"""
    store = ChatSessionStore(tmp_path / "home")
    store.ensure_session("empty")
    session = store.load_session("empty")
    assert getattr(session, "delivered", None) in (None, {})
    assert inspect(session, "tu1") == []
    assert delivered_paths(session, "tu1") == []
    assert thumbnail(session, "tu1", 0) is None
    assert open_item(session, "tu1", 0) == {"ok": False}
    assert reveal(session, "tu1", 0) == {"ok": False}
