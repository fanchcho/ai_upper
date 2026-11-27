"""F11：Esc 收回收起状态下的会话浮出列表。"""
from __future__ import annotations
import os
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_escape_closes_side_peek(qapp, tmp_path):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "parity"))
    from feature_parity_evidence import build, find_item
    from test_qml_shell import text_stream
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    w, b, s, t, e, h = build(tmp_path, "dark", text_stream("x"))
    w.setProperty("sideCollapsed", True)
    w.setProperty("sidePeek", True)
    field = find_item(w.contentItem(), "inputField")
    assert field is not None
    field.forceActiveFocus(); qapp.processEvents()
    QTest.keyClick(w, Qt.Key_Escape)
    qapp.processEvents()
    assert w.property("sidePeek") is False
    t.stop(); w.close(); e.deleteLater()
