import json,os,sys,uuid
from pathlib import Path
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot,find_item
from test_qml_shell import text_stream
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import Qt,QPointF
from PySide6.QtTest import QTest
from mvvm.models.chat_models import Message
from mvvm.services.model_view import COMPACT_MARKER
from mvvm.services.chat_session_store import ChatSessionStore
app=QGuiApplication([]);results=[]
for theme in ['dark','light']:
 w,b,s,t,e,h=build(Path('/tmp/ai-upper-compact-'+uuid.uuid4().hex),theme,text_stream('Summary of earlier context.'))
 config=b._settings.models_section()
 for provider in config['providers']:
  for model in provider['models']:
   if isinstance(model,dict):model['contextWindow']=20000
 b._settings.set_config({'models':config})
 session=s.load_session(b._active)
 for i in range(50):
  session.messages.extend([Message(role='user',content='旧内容'*300+str(i)),Message(role='assistant',content='答复内容'*300+str(i))])
 s.save(session.id)
 field=find_item(w.contentItem(),'inputField');field.forceActiveFocus();QTest.keyClick(w,Qt.Key_Slash);_pump(app,lambda:False,.3)
 menu=find_item(w.contentItem(),'slashMenuRoot');point=menu.mapToScene(QPointF(25,40));assert point.y()>0
 shot(w,Path('out/final-port')/f'compact-{theme}.png')
 QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,point.toPoint())
 assert _pump(app,lambda:any(str(m.content).startswith(COMPACT_MARKER) for m in s.load_session(session.id).messages),15)
 assert _pump(app,lambda:not b._host.is_busy(session.id),5)
 disk=ChatSessionStore(h).load_session(session.id)
 assert any(str(m.content).startswith(COMPACT_MARKER) for m in disk.messages)
 results.append({'theme':theme,'home':str(h),'messages':len(disk.messages),'compacted':disk.compacted.model_dump() if disk.compacted else None})
 t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.1)
Path('out/final-port/compact-ui.json').write_text(json.dumps(results,indent=2));print('PASS real click -> unmodified ChatHost.compact -> persisted compaction summary; model transport fixture only')
