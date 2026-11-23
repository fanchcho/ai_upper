"""The native broken-image resource must actually render in QML, before bare alt."""
import os
from pathlib import Path
import pytest
from test_qml_context_menu import _build_window, _find_item, _pump


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication
    yield QGuiApplication.instance() or QGuiApplication([])


def test_broken_image_paints_icon_and_keeps_alt_inline(qapp, tmp_path, monkeypatch):
    from PySide6 import QtCore as C
    window, bridge, store, home, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        window.setProperty("page", "chat")
        view = _find_item(window.contentItem(), "bodyView")
        bridge._body.set_markdown("![示意图](data:image/png;base64,iVBORw0KGgo=)")
        bridge._body.attach(view.property("textDocument"))
        _pump(qapp, .3)
        document = view.property("textDocument").textDocument()
        assert document.toPlainText().strip() == "\ufffc示意图"
        icon = view.positionToRectangle(0)
        alt = view.positionToRectangle(1)
        end = view.positionToRectangle(4)
        assert alt.x() - icon.x() == 16
        assert end.x() - alt.x() == pytest.approx(42, abs=1/16)  # Qt 1/64px advances
        point = view.mapToScene(C.QPointF(icon.x(), icon.y()))
        shot = window.grabWindow()
        green = 0
        for y in range(int(point.y()), int(point.y()) + 32):
            for x in range(int(point.x()), int(point.x()) + 16):
                color = shot.pixelColor(x, y)
                green += color.green() > color.red()+18 and color.green() > color.blue()+10
        assert green >= 30  # proves icon pixels, not only a document resource entry
        print(f"BROKEN_IMAGE slot={alt.x()-icon.x()}x16 alt_width={end.x()-alt.x()} total_width={end.x()-icon.x()} green_pixels={green} icon_position=({point.x()},{point.y()})")
        evidence = os.environ.get("BROKEN_IMAGE_EVIDENCE")
        if evidence:
            Path(evidence).mkdir(parents=True, exist_ok=True)
            shot.save(str(Path(evidence) / "broken-image.png"))
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()
