"""未读红点：回合在非当前会话结束时标未读，打开该会话即清除。

判据来源（只读）：deva `redesign/Rail.tsx:1124-1156`（头像右上角红点，
`unread`/`attention` 仅在非当前、非归档会话显示）与 `redesign.css:1041-1051`
（10px、--danger、外圈 2px --bg-panel）。
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


def test_background_turn_marks_unread_and_open_clears(qapp, tmp_path, monkeypatch):
    from test_qml_shell import _bridge, text_stream

    bridge, store, _host = _bridge(
        tmp_path, monkeypatch, text_stream("回"), sessions=[("s-1", "一"), ("s-2", "二")]
    )
    assert bridge.openSession("s-1") is True
    assert bridge.send("问题") is True
    # 回合进行中切到另一个会话：s-1 的 done 落在后台。
    assert bridge.openSession("s-2") is True
    from test_qml_shell import _tick_until
    assert _tick_until(bridge, lambda: "s-1" in bridge._unread, 10)
    rows = {row["id"]: row for row in bridge._rows()}
    assert rows["s-1"]["unread"] is True
    assert rows["s-2"]["unread"] is False
    # 打开 s-1 清除未读。
    assert bridge.openSession("s-1") is True
    assert {row["id"]: row for row in bridge._rows()}["s-1"]["unread"] is False


def test_unread_dot_visible_in_qml_and_click_clears(qapp, tmp_path, monkeypatch):
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt, QPointF
    from qml_shell import _pump
    from test_qml_sidebar_collapse import _build

    window, bridge, _settings, ticker, engine = _build(tmp_path, monkeypatch)
    try:
        # 模拟两个会话 + 后台回合：直接走 bridge 的真实状态机。
        store = bridge._store
        store.ensure_session("s-1"); store.ensure_session("s-2")
        bridge._publish()
        _pump(qapp, lambda: False, 0.3)
        bridge._active = "s-1"
        bridge.send("问题")
        bridge._active = "s-2"
        bridge._publish()
        _pump(qapp, lambda: "s-1" in bridge._unread, 10)
        bridge._publish()
        _pump(qapp, lambda: False, 0.3)
        dot = _find_item(window.contentItem(), "threadUnread")
        assert dot is not None and dot.property("visible") is True
        # 点 s-1 行：未读清除、红点消失。
        ids = [row["id"] for row in bridge._rows()]
        index = ids.index("s-1")
        row = _find_item(window.contentItem(), "threadRow" + str(index))
        assert row is not None
        pt = row.mapToScene(QPointF(40, 20))
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, pt.toPoint())
        _pump(qapp, lambda: False, 0.4)
        assert {row["id"]: row for row in bridge._rows()}["s-1"]["unread"] is False
    finally:
        ticker.stop(); window.close(); engine.deleteLater()
