import os, sys, time
ROOT = '/home/agent/shared_workspace/ai_upper'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'
os.environ['AI_UPPER_HEADLESS'] = '1'
os.environ['AI_UPPER_HOME'] = '/tmp/fx-qml-home'
os.environ['DEVA_ASSETS_DIR'] = ROOT + '/app/assets'
os.environ['AI_UPPER_QML_PAGE'] = 'delete-confirm'
sys.path.insert(0, ROOT + '/app/src')
os.chdir(ROOT)

from utils.qt_compat import QtWidgets, QtCore, QtQml
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
from qml_shell import (ShellBridge, build_chat_host, app_home, qml_main, _plain_mode,
                       _pump, _start_ticker)
from mvvm.services.settings_service import SettingsService
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.persona_store import PersonaStore
from mvvm.services.skill_store import SkillStore
from mvvm.services.workspace_guard import WorkspaceGuard
from qml_shell_sessions import session_rows
from PySide6.QtTest import QTest

home = app_home()
settings = SettingsService(home); vault = SecretsVault(home); store = ChatSessionStore(home)
personas = PersonaStore(home); personas.ensure_seeded(); guard = WorkspaceGuard()
bridge_box = {}
def emit(payload): bridge_box['bridge'].emit(payload)
host, _ = build_chat_host(settings=settings, vault=vault, store=store, guard=guard, home=home,
                          emit=emit, emit_sessions_changed=lambda: None)
bridge = ShellBridge(host=host, store=store, plain=_plain_mode(), settings=settings,
                     vault=vault, skills=SkillStore(home))
bridge_box['bridge'] = bridge
engine = QtQml.QQmlApplicationEngine()
bridge._engine = engine
engine.rootContext().setContextProperty('shellBridge', bridge)
engine.load(QtCore.QUrl.fromLocalFile(str(qml_main())))
roots = engine.rootObjects()
print('roots', len(roots))
window = roots[0]
bridge.bind_window(window); bridge.initial(); window.setProperty('page', 'delete-confirm')
window.show()
ticker = _start_ticker(bridge)
_pump(app, lambda: False, 0.8)
ctx = window.findChild(QtCore.QObject, 'ctxMenu')
confirm = window.findChild(QtCore.QObject, 'confirmLayer')
print('ctx visible=', ctx.property('visible'), 'geometry=', ctx.property('x'), ctx.property('y'), ctx.property('width'), ctx.property('height'))
texts = []
def walk_items(obj):
    t = obj.property('text')
    if isinstance(t, str) and t.strip():
        texts.append(t)
    for c in obj.childItems():
        walk_items(c)
walk_items(ctx)
print('ctx texts=', texts)
print('ctx item count=', sum(1 for t in texts if t in {'New chat','Rename','Select','Select messages','Archive','Delete conversation'}))
print('confirm visible=', confirm.property('visible'))
print('sessions before=', len(session_rows(store)), 'active=', bridge._active)
QTest.mouseClick(window, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(795, 462), 100)
_pump(app, lambda: False, 0.5)
print('after click at Delete(795,462): confirm visible=', confirm.property('visible'),
      'sessions=', len(session_rows(store)), 'active=', bridge._active)
# Also click at dialog's Cancel text (non-button) for comparison.
QTest.mouseClick(window, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, QtCore.QPoint(695, 462), 100)
_pump(app, lambda: False, 0.3)
print('after click at Cancel(695,462): confirm visible=', confirm.property('visible'))
ticker.stop(); window.close()
