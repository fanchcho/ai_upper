"""F27：会话侧栏宽度真实拖动并落盘。"""
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


def test_sidebar_resize_persists(qapp, tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "parity"))
    from feature_parity_evidence import build, find_item
    from test_qml_shell import text_stream
    from PySide6.QtCore import Qt, QPoint, QPointF
    from PySide6.QtTest import QTest

    w, b, s, t, e, h = build(tmp_path, "dark", text_stream("x"))
    handle = find_item(w.contentItem(), "sidebarResize")
    assert handle is not None
    p = handle.mapToScene(QPointF(handle.width() / 2, 300)).toPoint()
    before = w.property("sidebarWidth")
    QTest.mousePress(w, Qt.LeftButton, Qt.NoModifier, p)
    QTest.mouseMove(w, p + QPoint(80, 0), 20)
    QTest.mouseRelease(w, Qt.LeftButton, Qt.NoModifier, p + QPoint(80, 0))
    qapp.processEvents()
    after = w.property("sidebarWidth")
    assert after >= before + 40, (before, after)
    assert b.sidebarWidth() == int(after)
    b.setSidebarWidth(9999)
    assert b.sidebarWidth() == 480
    t.stop(); w.close(); e.deleteLater()
