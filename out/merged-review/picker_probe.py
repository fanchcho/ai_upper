from pathlib import Path
import sys, os, tempfile, json
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'app/src'),str(ROOT/'app/tests')]
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QPointF
from PySide6.QtQml import QQmlEngine
from test_qml_model_picker import _build_chat_window,_find_item,_click,_pump,_texts
app=QGuiApplication.instance() or QGuiApplication([])
with tempfile.TemporaryDirectory(dir='/tmp',prefix='ai-upper-picker-probe-') as tmp, pytest.MonkeyPatch.context() as mp:
 w,b,store,home,ticker,engine=_build_chat_window(Path(tmp),mp)
 try:
  b._settings.set_config({'models':{'activeModelId':'anthropic:deepseek-v4.1-flash','providers':[{'id':'anthropic','name':'Anthropic','enabled':True,'models':[{'id':'deepseek-v4.1-flash','name':'deepseek-v4.1-flash','enabled':True}]}]}})
  b.initial();_pump(app,.4);_click(w,_find_item(w.contentItem(),'modelChip'));_pump(app,.4)
  picker=_find_item(w.contentItem(),'modelPicker'); panel=_find_item(picker,'pickerPanel');origin=panel.mapToScene(QPointF(0,0))
  row=_find_item(picker,'modelRow0_0');shadow=QQmlEngine.contextForObject(panel).contextProperty('panelShadow')
  image=w.grabWindow(); borders={k:image.pixelColor(x,y).name() for k,(x,y) in {'top':(700,658),'bottom':(700,803),'left':(428,720),'right':(1207,720)}.items()}
  print(json.dumps({'texts':_texts(picker),'activeRef':picker.property('activeRef'),'panel':[origin.x(),origin.y(),panel.width(),panel.height()],'rowHeight':row.height(),'border':borders,'shadow':{k:shadow.property(k) for k in ('blur','offsetY')}},ensure_ascii=False))
  assert _texts(_find_item(picker,'modelList'))==['Anthropic','deepseek-v4.1-flash']
  assert picker.property('activeRef')=='anthropic:deepseek-v4.1-flash'
  assert all(v=='#5b5bd6' for v in borders.values())
 finally:
  ticker.stop();w.close();engine.deleteLater()
