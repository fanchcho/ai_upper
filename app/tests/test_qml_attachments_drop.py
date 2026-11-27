"""拖放与粘贴附件：原版 `fs:dropped-entries` / `fs:paste-attachment` 的 QML 对位。

判据来源（只读）：deva `redesign/Composer.tsx:576-596` 在 window 上监听 dragover/drop，
`Composer.tsx:508,567` 处理剪贴板图片；`services/attachments.ts:201-233` 是通道实现。
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication

    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


def _find_item(root, name):
    try:
        if root.objectName() == name:
            return root
    except Exception:
        pass
    for child in root.childItems():
        found = _find_item(child, name)
        if found is not None:
            return found
    return None


def test_dropped_files_and_folders_are_registered(tmp_path, monkeypatch):
    from test_qml_shell import _bridge, text_stream

    bridge, _store, _host = _bridge(tmp_path, monkeypatch, text_stream("x"))
    file_path = tmp_path / "drop-note.txt"
    file_path.write_text("拖放内容", encoding="utf-8")
    folder = tmp_path / "drop-folder"
    folder.mkdir()
    rows = bridge.acceptDroppedFiles([file_path.as_uri(), folder.as_uri()])
    assert [r["kind"] for r in rows] == ["text", "folder"]
    assert rows[0]["supported"] is True and rows[0]["size"] == len("拖放内容".encode())
    assert rows[1]["path"] == str(folder.resolve())
    assert rows[0]["path"] in bridge._attachments.allowed


def test_clipboard_image_becomes_a_png_attachment(qapp, tmp_path, monkeypatch):
    from PySide6.QtGui import QColor, QImage

    from test_qml_shell import _bridge, text_stream

    bridge, _store, _host = _bridge(tmp_path, monkeypatch, text_stream("x"))
    image = QImage(8, 6, QImage.Format_ARGB32)
    image.fill(QColor("#5b5bd6"))
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.clipboard().setImage(image)
    rows = bridge.attachClipboardImage()
    assert len(rows) == 1 and rows[0]["kind"] == "image" and rows[0]["supported"] is True
    from pathlib import Path
    assert Path(rows[0]["path"]).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_qml_drop_area_and_paste_key_append_pending_files(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QObject
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    from qml_shell import _pump
    from test_qml_sidebar_collapse import _build

    window, bridge, _settings, ticker, engine = _build(tmp_path, monkeypatch)
    try:
        area = _find_item(window.contentItem(), "dropArea")
        assert area is not None
        assert area.property("width") == 1280 and area.property("height") == 820
        note = tmp_path / "拖放 文件.txt"
        note.write_text("drop", encoding="utf-8")
        # 真实 QDragEnterEvent + QDropEvent 投递到窗口：QML DropArea 收到后走 onDropped。
        from PySide6.QtCore import QMimeData, QPoint, QUrl, QPointF, QCoreApplication
        from PySide6.QtGui import QDragEnterEvent, QDropEvent
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(note))])
        QCoreApplication.sendEvent(window, QDragEnterEvent(
            QPoint(400, 400), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
        QCoreApplication.sendEvent(window, QDropEvent(
            QPointF(400, 400), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
        _pump(qapp, lambda: False, 0.4)
        pending0 = window.property("pendingFiles")
        if hasattr(pending0, "toVariant"):
            pending0 = pending0.toVariant()
        assert pending0 == [str(note.resolve())]

        # 真实 Ctrl+V：剪贴板图片进入待发列表。
        image = QImage(6, 6, QImage.Format_ARGB32)
        image.fill(QColor("#ffffff"))
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setImage(image)
        field = _find_item(window.contentItem(), "inputField")
        field.forceActiveFocus()
        QTest.keyClick(window, Qt.Key_V, Qt.ControlModifier)
        _pump(qapp, lambda: False, 0.3)
        pending = window.property("pendingFiles")
        if hasattr(pending, "toVariant"):
            pending = pending.toVariant()
        assert len(pending) == 2 and pending[-1].endswith("pasted.png")
    finally:
        ticker.stop(); window.close(); engine.deleteLater()
