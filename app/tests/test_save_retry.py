"""F87：真实写失败（路径变目录）后的可见错误与重试落盘。"""
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


def test_save_failure_then_retry(qapp, tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "parity"))
    from feature_parity_evidence import build, find_item
    from test_qml_shell import text_stream
    from PySide6.QtCore import Qt, QPointF
    from PySide6.QtTest import QTest

    w, b, s, t, e, h = build(tmp_path, "dark", text_stream("x"))
    b.openSession("s-1")
    path = s.session_path("s-1")
    path.unlink(); path.mkdir()
    assert b.retrySave() is False
    assert b.saveError and "IsADirectory" in b.saveError or "directory" in b.saveError.lower()
    path.rmdir()
    button = find_item(w.contentItem(), "saveRetry"); assert button
    QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint())
    qapp.processEvents()
    assert b.saveError == ""
    assert path.is_file()
    t.stop(); w.close(); e.deleteLater()
