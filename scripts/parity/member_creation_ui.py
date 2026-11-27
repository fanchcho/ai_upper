import json,sys,uuid
from pathlib import Path
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot,find_item
from test_qml_shell import text_stream
from scripted_transport import ScriptedTransport,sse
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtCore import Qt,QPointF
from PySide6.QtTest import QTest
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.plugin_identity import shared_store
class ModelWire:
 def __init__(self):self.calls=[]
 async def post(self,url,**kwargs):
  data=json.loads(kwargs['body']);self.calls.append(data)
  serialized=json.dumps(data.get('messages'))
  calls=[p.get('name') for m in data.get('messages',[]) for p in (m.get('content',[]) if isinstance(m.get('content'),list) else []) if p.get('type')=='tool_use']
  if 'member_send' in calls: wire=text_stream('DISPATCHED')
  elif 'MEMBER_JOB' in serialized: wire=text_stream('MEMBER_RESULT')
  else:
   name='member_send' if 'create_member' in calls else 'create_member'
   args={'member':'Reviewer','message':'MEMBER_JOB'} if name=='member_send' else {'name':'Reviewer','duty':'Review code'}
   wire=ScriptedTransport(chunks=[sse('message_start',{'type':'message_start','message':{'usage':{'input_tokens':5}}}),sse('content_block_start',{'type':'content_block_start','index':0,'content_block':{'type':'tool_use','id':'dispatch-'+uuid.uuid4().hex,'name':name,'input':{}}}),sse('content_block_delta',{'type':'content_block_delta','index':0,'delta':{'type':'input_json_delta','partial_json':json.dumps(args)}}),sse('content_block_stop',{'type':'content_block_stop','index':0}),sse('message_delta',{'type':'message_delta','delta':{'stop_reason':'tool_use'},'usage':{'output_tokens':5}}),sse('message_stop',{'type':'message_stop'})])
  return await wire.post(url,**kwargs)
app=QGuiApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf')
out=Path('out/final-four');out.mkdir(parents=True,exist_ok=True);results=[]
for theme in ['dark','light']:
 wire=ModelWire();w,b,s,t,e,h=build(Path('/tmp/ai-upper-members-'+uuid.uuid4().hex),theme,wire)

 field=find_item(w.contentItem(),'inputField');field.forceActiveFocus()
 app.clipboard().setText('@新建');QTest.keyClick(w,Qt.Key_V,Qt.ControlModifier);_pump(app,lambda:False,.3)
 menu=find_item(w.contentItem(),'slashMenuRoot');shot(w,out/f'member-candidate-{theme}.png')
 QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,menu.mapToScene(QPointF(20,40)).toPoint())
 app.clipboard().setText('create Reviewer then review');QTest.keyClick(w,Qt.Key_V,Qt.ControlModifier);QTest.keyClick(w,Qt.Key_Return)
 sid=b._active
 ok = _pump(app,lambda:'Reviewer：MEMBER_RESULT' in s.load_session(sid).model_dump_json(),8)
 if not ok: print('DEBUG',s.load_session(sid).model_dump_json(),json.dumps(wire.calls,ensure_ascii=False),b._host._members.pending,b._host._members.reports,flush=True)
 assert ok
 disk=ChatSessionStore(h);main=disk.load_session(sid);member=main.members[0];child=disk.load_session(member['sessionId'])
 assert child.parentId==sid and 'MEMBER_JOB' in child.model_dump_json() and 'MEMBER_RESULT' in child.model_dump_json()
 assert 'Reviewer：MEMBER_RESULT' in main.model_dump_json()
 shot(w,out/f'member-result-{theme}.png')
 results.append({'theme':theme,'home':str(h),'member':member,'child':child.model_dump(),'main':main.model_dump(),'model_requests':len(wire.calls)})
 t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.1)
(out/'members.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print('PASS mouse selection -> role auto creation -> real member_send tool -> child turn -> reopened main and child stores')
