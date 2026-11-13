"""真实 Qt（offscreen）界面冒烟：输入 → 点发送 → 绑定刷新。

与 `app/tests/test_deva_app.py` 的区别：那边用假 Qt 测装配与绑定，这里用真实
PySide6 跑一遍控件与信号，确认 `bind_property` / `bind_command` 在真 Qt 上确实生效。

跑法：QT_QPA_PLATFORM=offscreen PYTHONPATH=app/src .venv/bin/python scripts/deva_qt_smoke.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from utils.qt_compat import QtWidgets

from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.fake_provider import FakeProvider
from mvvm.services.tool_runtime import ToolRuntime
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.view_models.chat_vm import ChatViewModel
from mvvm.views.chat_window import ChatWindow


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv[:1])
    base = Path(tempfile.mkdtemp(prefix="deva-qt-smoke-"))
    try:
        workspace = base / "workspace"
        workspace.mkdir()
        (workspace / "notes.txt").write_text("真实 Qt 冒烟\n", encoding="utf-8")
        store = ChatSessionStore(base / "home")
        vm = ChatViewModel(store, FakeProvider(), ToolRuntime(WorkspaceGuard([workspace]), workspace))
        vm.open_session("qt-smoke")

        window = ChatWindow(vm)
        window.show()
        app.processEvents()

        window._input.setPlainText("看一下 notes.txt")
        app.processEvents()
        print("input_text in VM:", repr(vm.input_text_property.get_value()))
        print("can_send:", vm.can_send())

        window._send_button.click()
        app.processEvents()

        print("status label:", window._status.text())
        print("transcript widget head:", window._transcript.toPlainText().splitlines()[:2])
        print("assistant in widget:", "真实 Qt 冒烟" in window._transcript.toPlainText())
        print("input cleared:", window._input.toPlainText() == "")

        ok = (
            "真实 Qt 冒烟" in window._transcript.toPlainText()
            and window._status.text() == "就绪"
            and window._input.toPlainText() == ""
        )
        window.close()
        print("QT SMOKE PASS" if ok else "QT SMOKE FAIL")
        return 0 if ok else 1
    finally:
        app.quit()
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
