"""F38：回合中插话进入模型边界队列，撤回取回原文。"""
from __future__ import annotations
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_insert_and_withdraw(qapp, monkeypatch, tmp_path):
    from test_qml_shell import _bridge, text_stream
    bridge, _store, host = _bridge(tmp_path, monkeypatch, text_stream("x"))
    bridge.openSession("s-1")
    monkeypatch.setattr(host, "is_busy", lambda sid: True)
    assert bridge.insertMessage("插话内容") is True
    assert bridge.pendingInserts() == ["插话内容"]
    assert bridge.withdrawInserts() == ["插话内容"]
    assert bridge.pendingInserts() == []
    assert bridge.insertMessage("   ") is False
