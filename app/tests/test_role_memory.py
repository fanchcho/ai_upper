"""F56：角色记忆 v2 真实写盘/读回。"""
from __future__ import annotations
import json, os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_role_memory_roundtrip(tmp_path, monkeypatch):
    from test_qml_shell import _bridge, text_stream
    bridge, _store, _host = _bridge(tmp_path, monkeypatch, text_stream("x"))
    from mvvm.services.plugin_identity import identity_home
    from pathlib import Path
    home = identity_home()
    result = bridge.roleMemorySave("general", json.dumps({"title": "偏好", "body": "用中文回答", "type": "user"}))
    assert result["ok"] is True
    path = home / "personas" / "memory" / "general.json"
    data = json.loads(path.read_text())
    assert data["entries"][0]["title"] == "偏好"
    rows = bridge.roleMemories("general")
    assert rows and rows[0]["body"] == "用中文回答"
    entry_id = rows[0]["id"]
    assert bridge.roleMemoryDelete("general", entry_id)["ok"] is True
    assert bridge.roleMemories("general") == []
