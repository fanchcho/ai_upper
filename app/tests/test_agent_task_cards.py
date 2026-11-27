"""F81：propose_agent/create_task 名片决定、角色与任务真实落盘。"""
from __future__ import annotations
import json, os
from datetime import datetime, timedelta
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_cards_resolve_to_persona_and_task(qapp, tmp_path, monkeypatch):
    from test_qml_shell import _bridge, text_stream
    from mvvm.models.chat_models import Message, ToolUsePart
    bridge, store, host = _bridge(tmp_path, monkeypatch, text_stream("x"))
    host.create_session({"sessionId": "s-1", "personaId": "general"})
    bridge.openSession("s-1")
    session = store.load_session("s-1")
    when = (datetime.now() + timedelta(hours=1)).replace(microsecond=0).isoformat()
    session.messages = [Message(role="assistant", content=[
        ToolUsePart(type="tool_use", id="p1", name="propose_agent", input={"name": "Card Persona", "description": "d", "prompt": "p"}),
        ToolUsePart(type="tool_use", id="t1", name="create_task", input={"title": "Card Task", "prompt": "do it", "schedule": {"kind": "once", "at": when, "tz": "Asia/Shanghai"}}),
    ])]
    store.save("s-1"); bridge._publish()
    assert bridge.proposalCards()[0]["status"] == "pending"
    result = bridge.resolveProposal("p1", "accepted")
    assert result["ok"] is True and result["personaId"]
    assert bridge.proposalCards()[0]["status"] == "accepted"
    result = bridge.resolveAutotask("t1", "create", json.dumps({"title": "Card Task", "prompt": "do it", "schedule": {"kind": "once", "at": when, "tz": "Asia/Shanghai"}}))
    assert result["ok"] is True, result
    assert bridge.autotaskCards()[0]["status"] == "created"
    assert (tmp_path / "home" / "tasks.json").exists() or any((tmp_path).rglob("tasks.json"))
    reread = store.load_session("s-1")
    assert reread.proposals["p1"] == "accepted"
    assert reread.autotasks["t1"]["status"] == "created"
