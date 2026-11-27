"""F70：扩展页真实点击导入 .md 技能并刷新列表。"""
from __future__ import annotations
import os
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_import_skill_from_extensions_page(qapp, tmp_path, monkeypatch):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "parity"))
    from feature_parity_evidence import build, find_item
    from test_qml_shell import text_stream
    from PySide6.QtCore import Qt, QPointF
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QFileDialog

    source = tmp_path / "imported.md"
    source.write_text("---\nname: Imported Skill\ndescription: imported\n---\n\nbody\n", encoding="utf-8")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(source), "")))
    w, b, s, t, e, h = build(tmp_path, "dark", text_stream("x"))
    w.setProperty("page", "settings-extensions"); qapp.processEvents()
    button = find_item(w.contentItem(), "extensionsImportSkill")
    assert button is not None
    QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, button.mapToScene(QPointF(button.width()/2, button.height()/2)).toPoint())
    qapp.processEvents()
    folder = s.home / "skills" / "imported-skill"
    assert (folder / "SKILL.md").is_file()
    assert any(r["id"] == "imported-skill" for r in b.extensionRows())
    t.stop(); w.close(); e.deleteLater()
