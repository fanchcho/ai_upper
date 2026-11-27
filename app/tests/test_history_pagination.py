"""F86：最后 10 轮初始、更早 10 轮加载、过期 revision 丢弃。"""
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


def test_history_page_ranges(qapp, tmp_path):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "parity"))
    from feature_parity_evidence import build, find_item
    from test_qml_shell import text_stream
    from mvvm.models.chat_models import Message

    w, b, s, t, e, h = build(tmp_path, "dark", text_stream("x"))
    session = s.load_session("s-1"); session.messages = []
    for i in range(30):
        session.messages += [Message(role="user", content=f"TURN_{i} question"), Message(role="assistant", content=f"TURN_{i} answer")]
    s.save("s-1"); b.openSession("s-1"); b._publish()
    for _ in range(30): qapp.processEvents(); time.sleep(.02)
    assert b.historyState()["fromTurn"] == 20
    assert "TURN_29" in b._markdown() and "TURN_0 question" not in b._markdown()
    assert b.historyPage("bad", 0)["ok"] is False
    assert b.historyPage(b.historyState()["revision"], 10)["to"] == 20
    scroll = find_item(w.contentItem(), "bodyScroll")
    scroll.setProperty("contentY", float(scroll.property("contentHeight")) - float(scroll.property("height")))
    qapp.processEvents()
    scroll.setProperty("contentY", 0); qapp.processEvents()
    for _ in range(30): qapp.processEvents(); time.sleep(.02)
    if b.historyState()["fromTurn"] != 10:
        assert b.loadEarlierHistory()["ok"] is True
    assert b.historyState()["fromTurn"] == 10
    assert "TURN_10 question" in b._markdown() and "TURN_9 question" not in b._markdown()
    view = find_item(w.contentItem(), "bodyView")
    for _ in range(30):
        qapp.processEvents(); time.sleep(.02)
        if "TURN_10 question" in (view.property("text") or ""): break
    assert "TURN_10 question" in view.property("text")
    t.stop(); w.close(); e.deleteLater()
