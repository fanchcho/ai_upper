"""Actual QML events -> model protocol fixture -> production tool runtime and persisted stores."""
import asyncio,json,sys,uuid
from pathlib import Path
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot,find_item
from test_qml_shell import text_stream
from scripted_transport import ScriptedTransport,sse
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtCore import Qt,QPointF,QObject
from PySide6.QtTest import QTest
from mvvm.services.chat_session_store import ChatSessionStore

def tool_stream(calls):
 chunks=[sse('message_start',{'type':'message_start','message':{'usage':{'input_tokens':5}}})]
 for i,(name,args) in enumerate(calls):
  chunks.extend([sse('content_block_start',{'type':'content_block_start','index':i,'content_block':{'type':'tool_use','id':uuid.uuid4().hex,'name':name,'input':{}}}),sse('content_block_delta',{'type':'content_block_delta','index':i,'delta':{'type':'input_json_delta','partial_json':json.dumps(args)}}),sse('content_block_stop',{'type':'content_block_stop','index':i})])
 chunks.extend([sse('message_delta',{'type':'message_delta','delta':{'stop_reason':'tool_use'},'usage':{'output_tokens':5}}),sse('message_stop',{'type':'message_stop'})]);return ScriptedTransport(chunks=chunks)
class Wire:
 def __init__(self):self.parent=0;self.requests=[]
 async def post(self,url,**kw):
  data=json.loads(kw['body']);self.requests.append(data);serialized=json.dumps(data['messages'])
  if 'TASK_SEED' in serialized:
   if 'LONG_JOB' in serialized:await asyncio.sleep(1);wire=text_stream('SHOULD_ABORT')
   else:wire=text_stream('TASK_ANSWER')
  else:
   n=self.parent;self.parent+=1
   if n==0:wire=tool_stream([('member_send',{'member':'Daily','task':'Question','message':'Answer this'})])
   elif n==1:wire=text_stream('DISPATCHED')
   elif n==2:wire=tool_stream([('member_send',{'member':'Daily','task':'Stop test','message':'LONG_JOB'})])
   elif n==3:wire=tool_stream([('member_stop',{'member':'Daily'})])
   else:wire=text_stream('STOPPED')
  return await wire.post(url,**kw)
app=QGuiApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf');out=Path('out/remaining-three');out.mkdir(parents=True,exist_ok=True);results=[]
for theme in ['dark','light']:
 wire=Wire();w,b,s,t,e,h=build(Path('/tmp/ai-upper-task-fallback-'+uuid.uuid4().hex),theme,wire)
 from mvvm.models.chat_models import Message
 from datetime import datetime,timedelta,timezone
 api=b.tasksService();assert not api.create('Daily','TASK_SEED','once',(datetime.now(timezone.utc)+timedelta(days=1)).replace(tzinfo=None).isoformat(),'UTC','general')
 rows=api.read();rows[0]['ownerSessionId']=b._active;api.write(rows);before=(h/'tasks.json').read_bytes()
 task=rows[0];child=s.load_session(task['sessionId']);child.messages.append(Message(role='user',content='TASK_SEED'));s.save(child.id)
 field=find_item(w.contentItem(),'inputField')
 def send(text):
  field.forceActiveFocus();app.clipboard().setText(text);QTest.keyClick(w,Qt.Key_V,Qt.ControlModifier);QTest.keyClick(w,Qt.Key_Return)
 send('Ask Daily about its results')
 assert _pump(app,lambda:'Daily：TASK_ANSWER' in s.load_session(b._active).model_dump_json(),10)
 shot(w,out/f'task-answer-{theme}.png')
 send('Stop the next task question')
 assert _pump(app,lambda:'STOPPED' in s.load_session(b._active).model_dump_json() and not b._host.is_busy(child.id),10)
 shot(w,out/f'task-stop-{theme}.png')
 disk=ChatSessionStore(h);main=disk.load_session(b._active);child=disk.load_session(child.id)
 assert 'TASK_ANSWER' in main.model_dump_json() and 'LONG_JOB' in child.model_dump_json() and 'SHOULD_ABORT' not in child.model_dump_json()
 assert (h/'tasks.json').read_bytes()==before
 assert not main.members
 results.append({'theme':theme,'main':main.model_dump(),'taskSession':child.model_dump(),'task':json.loads(before),'requests':wire.requests})
 api.timer.stop();t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.2)
(out/'task-fallback.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print('PASS actual member_send/member_stop task fallback, reopened sessions, task schedule unchanged, dark/light keyboard input')
