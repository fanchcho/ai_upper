"""输入框 `/` 指令联想：真实键盘输入 `/` 打开，Enter 执行 compact。

判据来源（只读）：deva `redesign/Composer.tsx:382-420`（slashCommands 内建 /compact、
/rewind + 技能；:671-700 键盘选择）；本移植版只接可用的 /compact，/rewind 无后端不列出。
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication

    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


def _find_item(root, name):
    try:
        if root.objectName() == name:
            return root
    except Exception:
        pass
    for child in root.childItems():
        found = _find_item(child, name)
        if found is not None:
            return found
    return None


def test_slash_menu_opens_on_slash_and_enter_runs_compact(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from qml_shell import _pump
    from test_qml_sidebar_collapse import _build

    window, bridge, _settings, ticker, engine = _build(tmp_path, monkeypatch)
    try:
        calls = []
        bridge._host.compact = lambda request: calls.append(request) or {"turnId": "compact-test"}
        field = _find_item(window.contentItem(), "inputField")
        field.forceActiveFocus()
        QTest.keyClick(window, Qt.Key_Slash)
        _pump(qapp, lambda: False, 0.3)
        assert window.property("slashOpen") is True
        menu = _find_item(window.contentItem(), "slashMenuRoot")
        assert menu is not None and menu.property("visible") is True
        # 再输入 c：仍匹配 compact。
        QTest.keyClick(window, Qt.Key_C)
        _pump(qapp, lambda: False, 0.2)
        assert window.property("slashOpen") is True
        QTest.keyClick(window, Qt.Key_Return)
        _pump(qapp, lambda: False, 0.4)
        assert calls == [{"sessionId": bridge._active}]
        assert field.property("text") == ""
        assert window.property("slashOpen") is False
    finally:
        ticker.stop(); window.close(); engine.deleteLater()
