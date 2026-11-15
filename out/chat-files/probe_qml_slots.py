"""QML 桥实测：回形针真弹 QFileDialog、附件随消息落盘、交付卡三个按钮的真实返回。

不 mock 选择框：用 QTimer 在 200ms 后抓住真正弹出的 `QFileDialog`，selectFile + accept。
打开 / 定位在本机没有桌面会话，因此只记录将要执行的平台命令（`_desktop_open` /
`_spawn_detached` 的入参），不实际弹文件管理器——这一点在报告里如实标注。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(ROOT / "app" / "tests"))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DEVA_SECRETS_BACKEND", "file")

HOME = Path(os.environ.get("CHAT_FILES_SLOTS_HOME", "/tmp/chat-files-slots-home"))
WS = HOME / "ws"
WS.mkdir(parents=True, exist_ok=True)

from utils.qt_compat import QtCore, QtWidgets  # noqa: E402

from mvvm.models.chat_models import ImagePart, Message, TextPart  # noqa: E402
from mvvm.services import deliverables as service  # noqa: E402
from mvvm.services.chat_session_store import ChatSessionStore  # noqa: E402
from mvvm.services.secrets_vault import SecretsVault  # noqa: E402
from mvvm.services.settings_service import SettingsService  # noqa: E402
from mvvm.services.workspace_guard import WorkspaceGuard  # noqa: E402
from mvvm.webui.assembly import build_chat_host  # noqa: E402
from qml_shell import ShellBridge  # noqa: E402
from scripted_transport import ScriptedTransport, sse  # noqa: E402

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


from test_qml_shell import text_stream  # 与单测同一份 SSE 剧本


class DocStub:
    def __init__(self):
        from PySide6.QtGui import QTextDocument

        self._doc = QTextDocument()

    def textDocument(self):  # noqa: N802
        return self._doc


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    settings = SettingsService(HOME)
    settings.set_config({"models": MODELS})
    vault = SecretsVault(HOME)
    vault.set_secret("p1", "sk-test")
    store = ChatSessionStore(HOME)
    store.ensure_session("slot-probe")
    image = WS / "截图-2026-11-16.png"

    host, _gateway = build_chat_host(
        settings=settings,
        vault=vault,
        store=store,
        guard=WorkspaceGuard(),
        home=HOME,
        emit=lambda payload: None,
        emit_sessions_changed=lambda: None,
        transport=text_stream("收到附件"),
    )
    bridge = ShellBridge(host=host, store=store, plain=True)
    host._emit = bridge.emit
    bridge.attach(DocStub())
    assert bridge.openSession("slot-probe") is True

    # ── 1. 回形针：真弹 QFileDialog，并在弹出的对话框里选中图片 ────────────
    seen: dict = {"ticks": 0}
    shot_path = Path(__file__).resolve().parent / "qml-file-dialog.png"

    def pick_inside_dialog() -> None:
        """真对话框里选文件：把 fileNameEdit 填成绝对路径，再 accept。"""
        seen["ticks"] += 1
        widget = app.activeModalWidget()
        if not isinstance(widget, QtWidgets.QFileDialog):
            candidates = [w for w in app.allWidgets() if isinstance(w, QtWidgets.QFileDialog)]
            widget = candidates[-1] if candidates else None
        if widget is None:
            if seen["ticks"] < 40:
                QtCore.QTimer.singleShot(80, pick_inside_dialog)
            return
        seen["dialog"] = type(widget).__name__
        seen["modal"] = widget.isModal()
        widget.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, True)
        widget.setDirectory(str(WS))
        if seen.get("filled") is None:
            seen["filled"] = False
        if not seen["filled"]:
            for edit in widget.findChildren(QtWidgets.QLineEdit):
                if edit.objectName() == "fileNameEdit":
                    edit.setText(str(image))
                    seen["filled"] = True
            widget.grab().save(str(shot_path), "PNG")
            QtCore.QTimer.singleShot(200, pick_inside_dialog)
            return
        seen["selected"] = widget.selectedFiles()
        widget.accept()

    QtCore.QTimer.singleShot(100, pick_inside_dialog)
    picked = bridge.pickAttachments()
    print("== pickAttachments() ==")
    print("   真的弹出了对话框 =", seen.get("dialog"), " modal=", seen.get("modal"),
          " selectedFiles=", seen.get("selected"))
    print("   对话框截图 =", shot_path)
    print("   返回 =", json.dumps(picked, ensure_ascii=False))

    # ── 2. 附件随消息发送并落盘 ───────────────────────────────────────────
    ok = bridge.sendWithAttachments("这张图里的文件能给我吗", picked)
    deadline = time.time() + 15
    while time.time() < deadline and not bridge.turn_finished():
        bridge.tick()
        time.sleep(0.02)
    session = store.load_session("slot-probe")
    last_user = [m for m in session.messages if m.role == "user"][-1]
    kinds = [getattr(part, "type", "") for part in last_user.content]
    print("== sendWithAttachments() ==")
    print("   send 返回 =", ok, " turn stop =", bridge.stop)
    print("   落盘用户消息块类型 =", kinds)
    print("   附件贴片（QML 属性源）=", json.dumps(bridge.attachmentChips(), ensure_ascii=False)[:200])

    # ── 3. 交付卡：真实体积 / 打开 / 定位 / 复制路径 ──────────────────────
    delivered = str(WS / "季度报告.md")
    forged = str(WS / "需求说明.pdf")  # 真实存在但不在边车里
    sid = "chat-files"
    if store.load_session(sid) is None:
        print("   [warn] 没有 chat-files 会话，跳过交付卡实测")
        return 0
    bridge.openSession(sid)
    print("== deliveryItems() ==")
    for row in bridge.deliveryItems():
        print("   ", json.dumps({k: row[k] for k in ("name", "size", "sizeText", "openable", "missing")}, ensure_ascii=False))

    opened, revealed = [], []
    real_open, real_reveal = service._open_with_desktop, service._reveal_in_file_manager
    service._open_with_desktop = lambda path: opened.append(path) or True
    service._reveal_in_file_manager = lambda path: revealed.append(path) or True
    try:
        import qml_shell

        qml_shell.open_item = service.open_item
        qml_shell.reveal = service.reveal
        print("== 交付卡按钮 ==")
        print("   open(边车路径)   =", bridge.openDeliverable("tu_present_chat_files", delivered), "→", opened)
        print("   open(伪造路径)   =", bridge.openDeliverable("tu_present_chat_files", forged), "→", opened)
        print("   reveal(边车路径) =", bridge.revealDeliverable("tu_present_chat_files", delivered), "→", revealed)
        print("   reveal(/etc/passwd) =", bridge.revealDeliverable("tu_present_chat_files", "/etc/passwd"))
        print("   copy(边车路径)   =", bridge.copyDeliverablePath(delivered))
        print("   剪贴板内容       =", QtWidgets.QApplication.clipboard().text())
        print("   copy(伪造路径)   =", bridge.copyDeliverablePath(forged))
        print("   剪贴板内容(拒绝后不变) =", QtWidgets.QApplication.clipboard().text())
    finally:
        service._open_with_desktop, service._reveal_in_file_manager = real_open, real_reveal
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
