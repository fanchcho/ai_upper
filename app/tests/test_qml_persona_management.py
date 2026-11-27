"""F52-F56：角色花名册资料卡、编辑、删除、头像、排序。"""
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
        found = _find(child, name)
        if found is not None:
            return found
    return None


def _click(window, item, x=None, y=None):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtTest import QTest
    p = item.mapToScene(QPointF(item.property("width") / 2 if x is None else x,
                                item.property("height") / 2 if y is None else y))
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, p.toPoint(), 100)


def _type(window, field, text):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    _click(window, field)
    field.forceActiveFocus()
    QTest.keyClick(window, Qt.Key_A, Qt.ControlModifier)
    QGuiApplication = __import__("PySide6.QtGui", fromlist=["QGuiApplication"]).QGuiApplication
    QGuiApplication.clipboard().setText(text)
    QTest.keyClick(window, Qt.Key_V, Qt.ControlModifier)


def test_roster_profile_edit_delete_and_reorder(qapp, tmp_path, monkeypatch):
    from qml_shell import _pump
    from test_qml_sidebar_collapse import _build

    window, bridge, _settings, ticker, engine = _build(tmp_path, monkeypatch)
    try:
        from pathlib import Path
        from mvvm.services.persona_store import PersonaStore
        import os as _os
        _os.environ["DEVA_ASSETS_DIR"] = str(Path(__file__).resolve().parents[1] / "assets")
        seed_store = PersonaStore(Path(_os.environ["AI_UPPER_HOME"]) / "deva")
        seed_store.ensure_seeded()
        _pump(qapp, lambda: False, 0.5)
        _click(window, _find(window.contentItem(), "railRoster"))
        _pump(qapp, lambda: False, 0.4)
        assert window.property("page") == "roster"
        rows = bridge.personaRecords()
        assert len(rows) >= 2
        first = rows[0]
        profile = _find(window.contentItem(), "personaProfile_" + first["id"])
        assert profile is not None
        _click(window, profile)
        _pump(qapp, lambda: False, 0.2)
        assert _find(window.contentItem(), "personaRoster").property("mode") == "detail"
        assert _find(window.contentItem(), "personaPromptView") is not None
        # 详情页的 Edit 是 QML Button；直接用同一 QML 函数进入编辑，Save 仍走真实鼠标点击。
        from PySide6.QtQml import QQmlEngine, QQmlExpression
        roster_item = _find(window.contentItem(), "personaRoster")
        QQmlExpression(QQmlEngine.contextForObject(roster_item), roster_item, "openEdit(selected)").evaluate()
        _pump(qapp, lambda: False, 0.3)
        assert roster_item.property("mode") == "edit"
        name = _find(window.contentItem(), "personaName")
        _type(window, name, "Renamed Role")
        _click(window, _find(window.contentItem(), "personaSave"))
        _pump(qapp, lambda: False, 0.4)
        saved = bridge.personaDetail(first["id"])
        assert saved["name"] == "Renamed Role"

        # 新建角色
        QQmlExpression(QQmlEngine.contextForObject(roster_item), roster_item, "openEdit(null)").evaluate()
        _pump(qapp, lambda: False, 0.3)
        _type(window, _find(window.contentItem(), "personaName"), "New Role")
        _type(window, _find(window.contentItem(), "personaPromptEdit"), "New prompt body")
        _click(window, _find(window.contentItem(), "personaSave"))
        _pump(qapp, lambda: False, 0.4)
        assert any(r["name"] == "New Role" for r in bridge.personaRecords())

        # 排序：把第二行上移，读回顺序变化
        ids_before = [r["id"] for r in bridge.personaRecords()]
        assert len(ids_before) >= 2
        _click(window, _find(window.contentItem(), "personaUp_" + ids_before[1]))
        _pump(qapp, lambda: False, 0.3)
        ids_after = [r["id"] for r in bridge.personaRecords()]
        assert ids_after[0] == ids_before[1]

        # 删除新建角色
        new_row = next(r for r in bridge.personaRecords() if r["name"] == "New Role")
        _click(window, _find(window.contentItem(), "personaRow_" + new_row["id"]), 120, 40)
        _pump(qapp, lambda: False, 0.3)
        _click(window, _find(window.contentItem(), "personaDelete"))
        _pump(qapp, lambda: False, 0.3)
        assert not any(r["name"] == "New Role" for r in bridge.personaRecords())
    finally:
        ticker.stop(); window.close(); engine.deleteLater()
