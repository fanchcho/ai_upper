"""F38/F40：输入框上方 Todo 胶囊与待插入队列。"""
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


def _find(root, name):
    try:
        if root.objectName() == name:
            return root
    except Exception:
        pass
    for child in root.childItems():
        got = _find(child, name)
        if got is not None:
            return got
    return None


def test_todo_capsule_reads_real_session_and_opens_list(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    from qml_shell import _pump
    from test_qml_sidebar_collapse import _build

    window, bridge, _settings, ticker, engine = _build(tmp_path, monkeypatch)
    try:
        store = bridge._store
        session = store.load_session("s-1")
        session.todos = [{"listId": "L1", "title": "证据待办", "at": 1, "items": [
            {"content": "第一步", "status": "completed"},
            {"content": "第二步", "status": "in_progress"},
        ]}]
        store.save("s-1")
        assert bridge.openSession("s-1") is True
        bridge._publish(); _pump(qapp, lambda: False, 0.5)
        capsule = _find(window.contentItem(), "todoCapsule")
        assert capsule is not None and capsule.property("visible") is True
        text = capsule.findChild(type(capsule.children()[0])) if False else None
        # 通过可见 Text 的文本断言：胶囊本体有 1 个 Text 子项。
        labels = [c.property("text") for c in capsule.childItems() if hasattr(c, "property") and c.property("text") is not None]
        assert any("证据待办" in str(v) for v in labels), labels
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                         capsule.mapToScene(QPointF(20, 13)).toPoint())
        _pump(qapp, lambda: False, 0.3)
        listing = _find(window.contentItem(), "todoCapsuleList")
        assert listing is not None and listing.property("visible") is True
    finally:
        ticker.stop(); window.close(); engine.deleteLater()


def test_insert_queue_is_visible_and_flushed_after_turn(qapp, tmp_path, monkeypatch):
    import threading
    from test_qml_shell import _bridge, gated_stream, _tick_until

    gate = threading.Event()
    bridge, store, _host = _bridge(tmp_path, monkeypatch, gated_stream("开头", gate), sessions=[("s-1", "一")])
    bridge.openSession("s-1")
    bridge.send("第一轮")
    assert bridge.insertMessage("插话") is True
    assert bridge.pendingInserts() == ["插话"]
    gate.set()
    assert _tick_until(bridge, lambda: len(store.load_session("s-1").messages) >= 4, 10)
    assert bridge.pendingInserts() == []
