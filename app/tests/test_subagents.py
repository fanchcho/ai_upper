"""F80：五种内置子智能体类型、工具白名单与子会话派发。"""
from __future__ import annotations
import json, os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_subagent_types_and_dispatch(qapp, tmp_path, monkeypatch):
    from test_qml_shell import _bridge, text_stream
    from mvvm.services.members import SUBAGENT_TYPES
    bridge, store, host = _bridge(tmp_path, monkeypatch, text_stream("x"))
    bridge.openSession("s-1")
    vm = host.vm_for("s-1")
    assert set(SUBAGENT_TYPES) == {"General", "Explore", "Research", "Plan", "fork"}
    result = vm.tools.execute("run_subagent", {"agent": "Explore", "prompt": "find files"}, "tu-sub")
    assert result.is_error is False, result
    data = json.loads(result.content)
    child = store.load_session(data["sessionId"])
    assert child.title == "Explore子智能体" and child.parentId == "s-1"
    tools = host.vm_for(data["sessionId"]).tools._tools
    assert "read_file" in tools and "write_file" not in tools and "edit_file" not in tools
    assert vm.tools.execute("run_subagent", {"agent": "unknown", "prompt": "x"}, "tu-bad").is_error is True
