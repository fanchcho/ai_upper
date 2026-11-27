"""F47：剪贴板文件 URL 粘贴为附件（真实 QClipboard + QTest Ctrl+V）。"""
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


def test_clipboard_file_url_pastes_attachment(qapp, tmp_path):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "parity"))
    from feature_parity_evidence import build, find_item
    from test_qml_shell import text_stream
    from PySide6.QtCore import Qt, QMimeData, QUrl
    from PySide6.QtTest import QTest

    w, b, s, t, e, h = build(tmp_path, "dark", text_stream("x"))
    source = tmp_path / "clip.txt"; source.write_text("clipboard file\n")
    mime = QMimeData(); mime.setUrls([QUrl.fromLocalFile(str(source))])
    qapp.clipboard().setMimeData(mime)
    field = find_item(w.contentItem(), "inputField"); assert field
    field.forceActiveFocus(); qapp.processEvents()
    QTest.keyClick(w, Qt.Key_V, Qt.ControlModifier); qapp.processEvents()
    assert str(source) in w.property("pendingFiles").toVariant()
    t.stop(); w.close(); e.deleteLater()
