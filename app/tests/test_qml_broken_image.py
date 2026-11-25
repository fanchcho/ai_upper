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
        # alt 的宽度是字体度量的函数，不能写死 42：CI runner 没有中日韩字体时
        # 「示意图」会落到 tofu 回退（实测 25.171875px），本机有 Noto CJK 时是
        # 41.953125px；macOS runner 的 CJK 回退实际排 42.9375px，而同字体的
        # QFontMetrics 只报 41.109375px（差 1.83px，字体回退与度量表不完全一致）。
        # 这里用文档默认字体现场量同一串文字，并以 2px 容差吸收平台回退差；
        # 真正锁死的是「alt 完整内联排在 16px 图标槽之后、没有被裁剪或额外加间距」。
        from PySide6.QtGui import QFontMetricsF
        expected_alt = QFontMetricsF(document.defaultFont()).horizontalAdvance("示意图")
        assert end.x() - alt.x() == pytest.approx(expected_alt, abs=2.0)
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
