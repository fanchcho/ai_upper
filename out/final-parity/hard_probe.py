import os,sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'app/src'),str(ROOT/'app/tests')];os.environ['QT_QPA_PLATFORM']='offscreen'
import pytest
from PySide6 import QtCore as C,QtGui as G
from test_qml_context_menu import _build_window,_find_item,_pump
app=G.QGuiApplication([]);mp=pytest.MonkeyPatch();w,b,store,home,ticker,engine=_build_window(Path(os.environ['AI_UPPER_HOME']),mp)
try:
 w.setProperty('page','search-results');_pump(app,.4);ls=_find_item(w.contentItem(),'sessionList');print('SEARCH_RESULTS count',ls.property('count'));assert ls.property('count')==10
 w.setProperty('page','focus-composer');_pump(app,.4);co=_find_item(w.contentItem(),'composer');p=co.mapToScene(C.QPointF(0,0));x,y=int(p.x()),int(p.y());ww,hh=int(co.width()),int(co.height());im=w.grabWindow()
 colors={label:im.pixelColor(xx,yy).name() for label,xx,yy in [('top',x+ww//2,y),('bottom',x+ww//2,y+hh-1),('left',x,y+hh//2),('right',x+ww-1,y+hh//2)]};print('FOCUS',x,y,ww,hh,colors);assert all(c=='#5b5bd6' for c in colors.values())
finally:ticker.stop();w.close();engine.deleteLater();mp.undo()
