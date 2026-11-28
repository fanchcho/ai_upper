"""F79：真实 bash QProcess 终端，输入命令并读回 stdout。"""
from __future__ import annotations
import os, time
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_terminal_real_command(qapp, tmp_path):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "parity"))
    from feature_parity_evidence import build, find_item
    from test_qml_shell import text_stream
    from PySide6.QtCore import Qt, QPointF
    from PySide6.QtTest import QTest

    w, b, s, t, e, h = build(tmp_path, "dark", text_stream("x"))
    button = find_item(w.contentItem(), "terminalOpen"); assert button
    QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint())
    assert b.startTerminal() is True
    chunks = []
    b.terminalOutput.connect(chunks.append)
    assert b.terminalInput("echo TERM_OK") is True
    deadline = time.time() + 5
    while time.time() < deadline and "TERM_OK" not in "".join(chunks):
        qapp.processEvents(); time.sleep(0.05)
    assert "TERM_OK" in "".join(chunks)
    b.stopTerminal(); t.stop(); w.close(); e.deleteLater()
