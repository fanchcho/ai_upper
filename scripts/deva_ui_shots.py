"""真实 Qt（offscreen）主窗口截图：会话列表 / 聊天 / 工具卡与图片 / 待办胶囊 / 设置页。

跑法（仓库根目录）：
    QT_QPA_PLATFORM=offscreen PYTHONPATH=app/src .venv/bin/python scripts/deva_ui_shots.py out/ui

输出若干 PNG，并打印每个界面里能读到的关键文案，供人工核对。脚本只读工程代码、不碰网络：
前两张用假 provider 让「回复」立即出现；工具卡与待办那组用一个脚本化 provider 回放
read_file / todo_write 的真实调用，走完整回合（工具真执行、结果真落盘）。
"""
from __future__ import annotations

import base64
import shutil
import struct
import sys
import tempfile
import zlib
from pathlib import Path
from typing import Any

from utils.qt_compat import QtWidgets

from mvvm.models.chat_models import Message
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.fake_provider import FakeProvider
from mvvm.services.provider_gateway import Done, Provider, TextDelta, ToolCall
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.settings_service import SettingsService
from mvvm.services.tool_runtime import ToolRuntime
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.view_models.chat_sessions_vm import ChatSessionsViewModel
from mvvm.view_models.chat_vm import ChatViewModel
from mvvm.view_models.settings_vm import SettingsViewModel
from mvvm.views.deva_main_window import DevaMainWindow

MODELS = {
    "activeModelId": "p1:claude-sonnet-5-5",
    "activeEffort": "high",
    "providers": [
        {
            "id": "p1",
            "name": "Anthropic",
            "adapter": "anthropic",
            "apiHost": "https://api.anthropic.com",
            "enabled": True,
            "models": [
                {"id": "claude-sonnet-5-5", "enabled": True, "contextWindow": 200_000},
                {"id": "claude-haiku-5-5", "enabled": False},
            ],
        },
        {
            "id": "custom-1700000000000",
            "name": "本地 Ollama",
            "adapter": "openai",
            "apiHost": "http://127.0.0.1:11434",
            "enabled": True,
            "models": [{"id": "qwen3:8b", "enabled": True}],
        },
    ],
}


def png_bytes() -> bytes:
    """1×1 红色 PNG：截图里的图片卡要有一个真能被 QImage 解码的文件。"""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b"")
    )


class ScriptedProvider(Provider):
    """按脚本回放事件：第一次回工具调用，第二次回正文。"""

    name = "scripted"

    def __init__(self, scripts: list[list[Any]]) -> None:
        self._scripts = list(scripts)

    async def stream(self, request):  # type: ignore[override]
        script = self._scripts.pop(0) if self._scripts else [TextDelta("完成。"), Done("end_turn")]
        for event in script:
            yield event


def seed_store(home: Path) -> ChatSessionStore:
    """两条有内容的会话：截图里能看到列表层次与聊天记录。"""
    store = ChatSessionStore(home)
    store.ensure_session("sess_alpha")
    store.append_message("sess_alpha", Message(role="user", content="帮我把工作区里的笔记过一遍"))
    store.rename_session("sess_alpha", "读一下工作区笔记")
    store.ensure_session("sess_beta")
    store.append_message("sess_beta", Message(role="user", content="总结上午的会议"))
    store.rename_session("sess_beta", "会议纪要整理")
    return store


def save(widget, path: Path) -> bool:
    ok = widget.grab().save(str(path))
    print("saved:", path, ok, widget.size().toTuple())
    return bool(ok)


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1] if len(argv) > 1 else "out/ui").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    base = Path(tempfile.mkdtemp(prefix="deva-ui-shots-"))
    ok = True
    try:
        home = base / "home"
        workspace = base / "workspace"
        workspace.mkdir()
        (workspace / "notes.txt").write_text("会议纪要：上线时间定在周五\n", encoding="utf-8")
        (workspace / "diagram.png").write_bytes(png_bytes())

        store = seed_store(home)
        settings = SettingsService(home)
        settings.set_config({"models": MODELS})
        vault = SecretsVault(home)
        guard = WorkspaceGuard([workspace])

        chat = ChatViewModel(store, FakeProvider(), ToolRuntime(guard, workspace))
        chat.open_session("sess_alpha")
        sessions = ChatSessionsViewModel(store)
        sessions.set_active("sess_alpha")
        window = DevaMainWindow(chat, sessions, SettingsViewModel(settings, vault))
        window.show()
        app.processEvents()

        # 1) 聊天态：发一条消息，等回合结束并把事件落到控件上。
        window.chat_pane()._input.setPlainText("看一下 notes.txt")
        window.chat_pane()._send_button.click()
        assert chat.wait_idle(10.0)
        app.processEvents()
        print("status:", window.status_text)
        print("transcript head:", window.chat_pane()._transcript.toPlainText().splitlines()[:3])
        print("session count:", window.session_pane().list_widget().count())
        ok &= save(window._window, out_dir / "01-chat.png")

        # 2) 设置页：服务商列表态。
        window.session_pane().buttons()["settings"].click()
        app.processEvents()
        print("settings page:", window.settings_pane().page())
        ok &= save(window._window, out_dir / "02-settings-list.png")

        # 3) 设置页：服务商详情态（模型列表 + 密钥状态）。
        pane = window.settings_pane()
        pane.widgets()["provider_list"].setCurrentRow(0)
        pane.widgets()["open_provider"].click()
        app.processEvents()
        print("provider page:", pane.page(), pane.current_provider_id())
        print("key status:", pane.widgets()["key_status"].text())
        print("models:", pane.widgets()["model_list"].count())
        ok &= save(window._window, out_dir / "03-settings-provider.png")

        # 4) 工具卡 + 内联图片 + 待办胶囊：脚本化 provider 回放 read_file / todo_write。
        window.session_pane().buttons()["new"].click()
        app.processEvents()
        tool_session = chat.session_id
        scripted = ScriptedProvider(
            [
                [
                    TextDelta("先看图，再列个清单。"),
                    ToolCall(id="call_img", name="read_file", input={"path": "diagram.png"}),
                    ToolCall(
                        id="call_todo",
                        name="todo_write",
                        input={
                            "title": "整理工作区",
                            "todos": [
                                {"content": "看图片", "status": "completed"},
                                {"content": "读笔记", "status": "in_progress"},
                                {"content": "写总结", "status": "pending"},
                            ],
                        },
                    ),
                    Done("tool_use"),
                ],
                [TextDelta("图片已查看，清单已建立。"), Done("end_turn")],
            ]
        )
        chat.provider = scripted
        chat.input_text_property.set_value("看一下 diagram.png 并建立清单")
        chat.send()
        assert chat.wait_idle(10.0)
        app.processEvents()
        print("explain tool session:", tool_session)
        rendered = window.chat_pane()._transcript.toHtml()
        print("tool card present:", "<table" in rendered)
        # 真 QTextDocument 没有「列出全部资源」的接口：按占位 URL 取回来验是否已注册成功。
        from utils.qt_compat import QtCore, QtGui

        probe = window.chat_pane()._transcript.document().resource(
            QtGui.QTextDocument.ResourceType.ImageResource, QtCore.QUrl("deva-image:0")
        )
        print("image resource registered:", probe is not None and not probe.isNull())
        print("todo pill:", window.chat_pane().todo_widgets()["pill"].text())
        ok &= save(window._window, out_dir / "04-tool-card-and-todo.png")

        # 5) 待办展开态。
        window.chat_pane().todo_widgets()["toggle"].click()
        app.processEvents()
        print("todo details:", window.chat_pane().todo_widgets()["details"].text().splitlines())
        ok &= save(window._window, out_dir / "05-todo-expanded.png")

        window.close()
        app.processEvents()
        print("UI SHOTS PASS" if ok else "UI SHOTS FAIL")
        return 0 if ok else 1
    finally:
        app.quit()
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
