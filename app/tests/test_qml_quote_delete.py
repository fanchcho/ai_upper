"""F34/F35/F36：正文右键引用选中，以及删除最后一轮真实写盘。"""
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


def test_quote_and_delete_last_turn(qapp, tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "parity"))
    from feature_parity_evidence import build, find_item
    from test_qml_shell import text_stream
    from mvvm.models.chat_models import Message
    from PySide6.QtCore import Qt, QPointF
    from PySide6.QtTest import QTest

    w, b, s, t, e, h = build(tmp_path, "dark", text_stream("x"))
    session = s.load_session("s-1")
    session.messages = [Message(role="user", content="第一轮问题"), Message(role="assistant", content="第一轮回答"),
                        Message(role="user", content="第二轮问题"), Message(role="assistant", content="第二轮回答")]
    s.save("s-1"); b.openSession("s-1"); b._publish(); qapp.processEvents()
    body = find_item(w.contentItem(), "bodyView"); assert body
    body.selectAll(); qapp.processEvents()
    QTest.mouseClick(w, Qt.RightButton, Qt.NoModifier, body.mapToScene(QPointF(100, 60)).toPoint())
    qapp.processEvents()
    quote = find_item(w.contentItem(), "editMenuQuote")
    assert quote is not None
    QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, quote.mapToScene(QPointF(quote.width()/2, quote.height()/2)).toPoint())
    qapp.processEvents()
    assert w.property("quoteText") != ""
    assert b.deleteLastTurn() is True
    reread = s.load_session("s-1")
    assert [m.role for m in reread.messages] == ["user", "assistant"]
    t.stop(); w.close(); e.deleteLater()
