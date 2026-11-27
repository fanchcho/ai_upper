"""F32：exit_plan 工具真实阻塞、卡片点击决定、plans 边车写盘。"""
from __future__ import annotations
import os, threading, time
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_plan_request_card_approve(qapp, tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "parity"))
    from feature_parity_evidence import build, find_item
    from test_qml_shell import text_stream
    from mvvm.services.plugin_interactions import Interactions
    from PySide6.QtCore import Qt, QPointF
    from PySide6.QtTest import QTest

    w, b, s, t, e, h = build(tmp_path, "dark", text_stream("x"))
    b.openSession("s-1")
    controller = Interactions(h / "interactions", timeout=30)
    b._host.interactions = controller
    vm = b._host.vm_for("s-1"); vm.tools.interactions = controller
    result = {}
    def run():
        result["value"] = vm.tools.execute("exit_plan", {"plan": "1. 做 A\n2. 做 B"}, "tu-plan")
    th = threading.Thread(target=run); th.start()
    deadline = time.time() + 3
    while time.time() < deadline and not controller.pending("s-1"):
        qapp.processEvents(); time.sleep(0.05)
    b._publish(); qapp.processEvents()
    cards = b.planCards(); assert cards and cards[0]["id"] == "tu-plan"
    button = find_item(w.contentItem(), "planApprove_tu-plan"); assert button
    assert b.answerPlan("tu-plan", "approve", "") is True
    th.join(5)
    assert "已批准" in result["value"].content
    reread = s.load_session("s-1")
    assert reread.plans["tu-plan"]["decision"] == "approve"
    t.stop(); w.close(); e.deleteLater()
