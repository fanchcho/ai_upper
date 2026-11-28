"""Real horizontal/vertical wheel events on independent overflowing code blocks."""
import os
from pathlib import Path
import pytest
from test_qml_context_menu import _build_window, _find_item, _pump


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication
    yield QGuiApplication.instance() or QGuiApplication([])


def test_code_scroll_is_local_and_vertical_wheel_still_scrolls_body(qapp, tmp_path, monkeypatch):
    from PySide6 import QtCore as C, QtGui as G
    from PySide6.QtTest import QTest
    window, bridge, store, home, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        window.setProperty("page", "chat")
        view = _find_item(window.contentItem(), "bodyView")
        scroller = _find_item(window.contentItem(), "bodyScroll")
        line = "START " + "wide_code_" * 100 + " END"
        bridge._body.set_markdown("```text\n" + line + "\n```\n\n```text\n" + line + "\n```\n\n" + "paragraph\n\n" * 60)
        bridge._body.attach(view.property("textDocument"))
        scroller.setProperty("contentY", 0)
        _pump(qapp, .3)
        first, second = bridge._body._viewports
        assert first.contentWidth > 7000
        assert first.contentX == second.contentX == 0
        evidence = os.environ.get("CODE_SCROLL_EVIDENCE")
        if evidence:
            Path(evidence).mkdir(parents=True, exist_ok=True)
            window.grabWindow().save(str(Path(evidence) / "code-start.png"))
        point = first.mapToScene(C.QPointF(40, first.height()/2))
        def wheel(x, y):
            # QTest supplies native timestamps/device and maps global position;
            # a zero-timestamp QWheelEvent breaks Flickable velocity on macOS.
            QTest.wheelEvent(window, point, C.QPoint(x, y))
            _pump(qapp,.2)
        before_y = scroller.property("contentY")
        wheel(-120, 0)
        assert first.contentX == 120
        assert second.contentX == 0
        assert scroller.property("contentY") == before_y
        wheel(-10000, 0)
        assert first.contentX == pytest.approx(first.contentWidth-first.width())
        assert second.contentX == 0
        if evidence:
            window.grabWindow().save(str(Path(evidence) / "code-end.png"))
        document = view.property("textDocument").textDocument()
        tail = view.positionToRectangle(document.toPlainText().index("END"))
        tail_x = tail.x()-first.x()-first.contentX
        assert 0 < tail_x < first.width()
        print(f"CODE width={first.contentWidth} viewport={first.width()} contentX=0->120->{first.contentX} tail_local_x={tail_x} second_contentX={second.contentX} bodyY={before_y}->{scroller.property('contentY')}")
        wheel(0,-120)
        assert scroller.property("contentY") > before_y
        print(f"VERTICAL bodyY={before_y}->{scroller.property('contentY')} code_contentX={first.contentX}")
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()
