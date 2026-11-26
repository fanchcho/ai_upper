"""Real mouse drill-down must not leave a modal/window alive after closing."""
import json
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from test_qml_settings_provider import qapp, _build_window, _pump


def test_extension_drilldown_toggle_and_close(qapp, tmp_path, monkeypatch):
    w,b,s,v,t,e = _build_window(tmp_path,monkeypatch,'chat')
    try:
        folder=s.home/'skills'/'alpha';folder.mkdir(parents=True)
        (folder/'SKILL.md').write_text('---\nname: alpha\n---\n# Instructions\n')
        w.setProperty('page','settings-extensions');_pump(qapp,.5)
        QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(945,397));_pump(qapp,.2)
        assert s.get('skills')['enabled']['alpha'] is False
        QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(580,397));_pump(qapp,.2)
        assert json.loads(b.extensionAction('detail','skill','alpha','{}'))['item']['enabled'] is False
        QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(500,212));_pump(qapp,.2)
        w.setProperty('page','chat');_pump(qapp,.2)
    finally:
        t.stop();w.close();e.deleteLater();_pump(qapp,.1)
    assert not any(win.isVisible() for win in qapp.allWindows())
