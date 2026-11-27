"""F85：Git 面板真实键鼠保存身份、触发 AI 信息（无模型时 unverified）。"""
from __future__ import annotations
import os, subprocess, time, sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_git_panel_identity_and_unverified_generation(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import Qt, QPointF, QObject
    from PySide6.QtQml import QQmlExpression, QQmlEngine
    from PySide6.QtTest import QTest
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "parity"))
    from feature_parity_evidence import build, find_item
    from test_qml_shell import text_stream

    w, b, s, t, e, h = build(tmp_path, "dark", text_stream("x"))
    repo = h / "repo"; repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    (repo / "a.txt").write_text("one\n")
    session = s.load_session("s-1"); session.focusRoot = str(repo); s.save("s-1")
    b.openSession("s-1"); b._publish()
    panel = w.findChild(QObject, "gitPanel")
    QQmlExpression(QQmlEngine.contextForObject(panel), panel, "open()").evaluate()
    time.sleep(0.2)
    def item(name): return find_item(w.contentItem(), name) or w.findChild(QObject, name)
    def click(name):
        o = item(name); assert o is not None, name
        QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, o.mapToScene(QPointF(o.width()/2, o.height()/2)).toPoint())
        time.sleep(0.1)
    def type_into(name, value):
        o = item(name); click(name); o.forceActiveFocus(); QTest.keyClick(w, Qt.Key_A, Qt.ControlModifier)
        qapp.clipboard().setText(value); QTest.keyClick(w, Qt.Key_V, Qt.ControlModifier)
    type_into("gitIdentityName", "Panel User"); type_into("gitIdentityEmail", "panel@example.com")
    click("gitSetConfig")
    assert subprocess.check_output(["git", "-C", str(repo), "config", "--local", "--get", "user.name"]).decode().strip() == "Panel User"
    click("gitGenerateMessage")
    deadline = time.time() + 5
    notice = ""
    while time.time() < deadline:
        qapp.processEvents(); time.sleep(0.05)
        n = item("gitNotice")
        notice = n.property("text") if n is not None else ""
        if notice: break
    assert "unverified" in notice or "未配置" in notice or "no-model" in notice, notice
    t.stop(); w.close(); e.deleteLater()
