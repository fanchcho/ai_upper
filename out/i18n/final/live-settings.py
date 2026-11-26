"""Verify the settings object survives language changes on the same open panel."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'app/src'), str(ROOT/'app/tests')]
from PySide6.QtGui import QGuiApplication
from pytest import MonkeyPatch
from test_qml_window_controls import _build_window, _pump, _find_item
from test_native_i18n import _texts
app = QGuiApplication.instance() or QGuiApplication([])
import tempfile
base = Path(tempfile.mkdtemp(prefix='live-i18n-', dir=ROOT/'.tmp'))
base.mkdir(parents=True, exist_ok=True)
patch = MonkeyPatch()
w, b, ticker, engine = _build_window(base, patch, sessions=[('untitled','')])
try:
    w.setProperty('page', 'settings-general')
    _pump(app)
    panel = _find_item(w.contentItem(), 'settingsModal')
    for locale, title, send, session_title in [('zh-CN','通用','发送','未命名会话'), ('en','General','Send','Untitled conversation'), ('zh-CN','通用','发送','未命名会话')]:
        assert b.setLanguage(locale)
        _pump(app)
        assert _find_item(w.contentItem(), 'settingsModal') is panel
        texts = _texts(w.contentItem())
        assert title in texts and send in texts and session_title in texts
        print(locale, 'same settings object; navigation, send and session title updated: PASS', flush=True)
finally:
    ticker.stop()
    w.close()
    engine.deleteLater()
    patch.undo()
