"""F76：本机用户头像真实选择/清除并读写盘。"""
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


def test_profile_avatar_pick_and_clear(qapp, tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "parity"))
    from feature_parity_evidence import build, find_item
    from test_qml_shell import text_stream
    from PySide6.QtCore import Qt, QPointF
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QFileDialog

    image = tmp_path / "avatar.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"fixture")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(image), "")))
    w, b, s, t, e, h = build(tmp_path, "dark", text_stream("x"))
    def item(name): return find_item(w.contentItem(), name) or w.findChild(__import__("PySide6.QtCore", fromlist=["QObject"]).QObject, name)
    def click(name):
        o = item(name); assert o is not None, name
        QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, o.mapToScene(QPointF(o.width()/2, o.height()/2)).toPoint())
        qapp.processEvents()
    click("meBtn"); click("profileChoose")
    path = s.home / "profile" / "avatar.png"
    assert path.is_file() and path.read_bytes().startswith(b"\x89PNG")
    assert b.userProfile()["image"].startswith("data:image/png;base64,")
    click("profileClear")
    assert not path.exists() and b.userProfile()["image"] == ""
    t.stop(); w.close(); e.deleteLater()
