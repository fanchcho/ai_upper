import os,sys
from pathlib import Path
sys.path[:0]=['app/src','app/tests']
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QPoint,Qt
from PySide6.QtTest import QTest
from pytest import MonkeyPatch
from test_qml_settings_provider import _build_window,_pump,_find_item,_click
app=QGuiApplication([])
w,b,s,v,t,e=_build_window(Path(os.environ['AI_UPPER_HOME']),MonkeyPatch())
b.setTheme(sys.argv[1]);_pump(app,.2)
_click(w,_find_item(w.contentItem(),'providerDelete'));_pump(app,.3)
QTest.mouseMove(w,QPoint(100,100));_pump(app,.3)
w.grabWindow().save('out/feature-review/provider-confirm-'+sys.argv[1]+'.png')
print('STATE',[(n,w.property(n)) for n in ['sidePeek','sideCollapsed','page','settingsOpen']])
QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(100,100),100);_pump(app,.3)
print('RESULT',_find_item(w.contentItem(),'providerDeleteLayer').property('visible'))
print('AFTER',[(n,w.property(n)) for n in ['sidePeek','sideCollapsed','page','settingsOpen']])
assert not _find_item(w.contentItem(),'providerDeleteLayer').property('visible')
w.grabWindow().save('out/feature-review/provider-dismissed-'+sys.argv[1]+'.png')
t.stop();w.close();e.deleteLater()
