"""F84 code path: synthetic preedit/commit events on the real QML composer.

Environment IME is unavailable in this host (system Qt/plugin ABI mismatch);
this test exercises the production QML TextInput event path and the isComposing guard.
"""
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


def test_qml_input_method_preedit_commit_and_guard(qapp, tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "parity"))
    from feature_parity_evidence import build, find_item, shot
    from test_qml_shell import text_stream
    from PySide6.QtCore import QCoreApplication, Qt
    from PySide6.QtGui import QInputMethodEvent
    from PySide6.QtTest import QTest

    w, b, s, t, e, h = build(tmp_path, "dark", text_stream("x"))
    field = find_item(w.contentItem(), "inputField"); assert field
    field.forceActiveFocus(); qapp.processEvents()
    sent = []
    monkeypatch.setattr(b._host, "send", lambda payload: sent.append(payload) or {"turnId": "x"})
    pre = QInputMethodEvent("ni", [])
    QCoreApplication.sendEvent(field, pre); qapp.processEvents()
    assert field.property("inputMethodComposing") is True
    assert field.property("text") == ""       # preedit must not be committed/persisted
    QTest.keyClick(w, Qt.Key_Return); qapp.processEvents()
    assert sent == []                          # composing Enter must not send
    commit = QInputMethodEvent(); commit.setCommitString("你好")
    QCoreApplication.sendEvent(field, commit); qapp.processEvents()
    assert field.property("inputMethodComposing") is False
    assert field.property("text") == "你好"
    assert int(field.property("cursorPosition")) == 2
    shot(w, Path("out/feature-parity/ime-code-dark.png"))
    t.stop(); w.close(); e.deleteLater()
