"""F41：成员/后台任务列表、打开、取消的真实状态。"""
from __future__ import annotations
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication
    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


def test_background_tasks_roundtrip(qapp, tmp_path, monkeypatch):
    from test_qml_shell import _bridge, text_stream
    bridge, store, host = _bridge(tmp_path, monkeypatch, text_stream("x"), sessions=[("s-1", "主")])
    bridge.openSession("s-1")
    session = store.load_session("s-1")
    child_id = "member-child"
    host.create_session({"sessionId": child_id, "personaId": "general"})
    session.members = [{"id": child_id, "sessionId": child_id, "name": "Reviewer", "personaId": "general"}]
    store.save("s-1")
    rows = bridge.backgroundTasks()
    assert len(rows) == 1 and rows[0]["name"] == "Reviewer"
    assert bridge.openBackground(child_id) is True
    assert bridge._active == child_id
    assert bridge.openBackground("missing") is False
