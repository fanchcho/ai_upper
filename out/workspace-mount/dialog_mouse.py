import sys,os
from pathlib import Path
sys.path[:0]=['app/src','app/tests']
import pytest
from PySide6.QtGui import QGuiApplication
from test_qml_context_menu import _build_window,_find_item,_click,_pump
app=QGuiApplication([]); mp=pytest.MonkeyPatch()
w,b,s,h,t,e=_build_window(Path(os.environ['AI_UPPER_HOME']),mp);w.setProperty('page','chat');_pump(app);_click(w,_find_item(w.contentItem(),'mountChip'));_pump(app)
from PySide6.QtCore import Qt, QObject
from PySide6.QtTest import QTest
folder=Path(os.environ['AI_UPPER_HOME'])/'aaa-chosen';folder.mkdir()
picker=next(win for win in app.allWindows() if win!=w and win.isVisible())
def find_class(i, prefix):
 if i.metaObject().className().startswith(prefix): return i
 for c in i.childItems():
  found=find_class(c,prefix)
  if found is not None:return found
field=find_class(picker.contentItem(),'TextField_QMLTYPE')
# Actual path-entry Return, row click, and Open button click in the picker window.
field.setProperty('visible',True); field.setProperty('text',str(folder.parent)); field.forceActiveFocus()
QTest.keyClick(picker,Qt.Key_Return);_pump(app,.5)
row=_find_item(picker.contentItem(),'folderDialogDelegate0'); _click(picker,row);_pump(app)
dialog=w.findChild(QObject,'workspaceDialog')
print('selected after real row click',dialog.property('selectedFolder').toLocalFile())
assert dialog.property('selectedFolder').toLocalFile()==str(folder)
def button(i):
 if i.property('text')=='Open' and 'Button' in i.metaObject().className():return i
 for c in i.childItems():
  r=button(c)
  if r is not None:return r
assert picker.grabWindow().save('out/workspace-mount/dialog-selection.png')
_click(picker,button(picker.contentItem()));_pump(app)
assert s.load_session(w.property('activeId')).focusRoot==str(folder)
print('real row click + Open persisted',s.load_session(w.property('activeId')).focusRoot)
t.stop();w.close();e.deleteLater();_pump(app,.05)
