import os, sys
from pathlib import Path
sys.path[:0] = ['app/src','app/tests']
import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QObject
from test_qml_context_menu import _build_window, _pump
app=QGuiApplication([])
mp=pytest.MonkeyPatch()
root=Path(os.environ['AI_UPPER_HOME']); root.mkdir(parents=True,exist_ok=True)
w,b,s,h,t,e=_build_window(root,mp)
w.setProperty('page','chat'); w.setWidth(1200); w.setHeight(800)
rows=[dict(path=f'/Users/fanchunchun/ekko_workspace/app/charles/work/{i}/Patch.java',name='Patch.java',dir='/Users/fanchunchun/ekko_workspace/app/charles/work',sizeText='5.9 MB',missing=False,openable=False,toolUseId='t') for i in range(24)]
w.setProperty('deliveries',rows)
_pump(app,.5)
scroll=w.findChild(QObject,'bodyScroll')
for y in range(0,480,17):
 scroll.setProperty('contentY',y); _pump(app,.02)
_pump(app,.2)
assert w.grabWindow().save('out/workspace-mount/'+sys.argv[1]+'.png')
print('rows',len(rows),'scroll',scroll.property('height'),scroll.property('contentHeight'),'backend',os.environ.get('QT_QUICK_BACKEND'))
t.stop(); w.close(); e.deleteLater(); _pump(app,.05)
