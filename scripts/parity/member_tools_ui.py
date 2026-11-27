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
 def __init__(self):self.parent=0;self.child=0;self.requests=[];self.tools=[]
 async def post(self,url,**kw):
  data=json.loads(kw['body']);self.requests.append(data)
  # Child turn starts with the dispatched task; main starts with @新建成员.
  messages=data['messages'];first=str(messages[0]['content']);wire=None;calls=[]
  if '【主角色派来的任务】' in first:
   if 'LONG_JOB' in json.dumps(messages):await asyncio.sleep(1);wire=text_stream('SHOULD_ABORT')
   else:
    n=self.child;self.child+=1
    if n==0:await asyncio.sleep(.35);calls=[('read_main',{})]
    elif n==1:calls=[('reply_task',{'task':'B','conclusion':'EARLY_B'})]
    elif n==2:calls=[('report_to_main',{'reason':'汇总 A'})]
    else:wire=text_stream('FINAL_A')
  else:
   n=self.parent;self.parent+=1
   if n==0:calls=[('create_member',{'name':'Reviewer','duty':'review'})]
   elif n==1:calls=[('member_send',{'member':'Reviewer','task':'A','message':'WORK_A'}),('member_send',{'member':'Reviewer','task':'B','message':'WORK_B'})]
   elif n==2:calls=[('member_status',{})]
   elif n==3:wire=text_stream('MANAGER_DISPATCHED')
   elif n==4:wire=text_stream('SUMMARY_A')
   elif n==5:calls=[('member_send',{'member':'Reviewer','task':'C','message':'LONG_JOB'})]
   elif n==6:calls=[('member_stop',{'member':'Reviewer'})]
   else:wire=text_stream('STOPPED')
  if calls:self.tools.extend(name for name,_ in calls);wire=tool_stream(calls)
  return await wire.post(url,**kw)
app=QGuiApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf');out=Path('out/final-four');out.mkdir(parents=True,exist_ok=True);results=[]
for theme in ['dark','light']:
 wire=Wire();w,b,s,t,e,h=build(Path('/tmp/ai-upper-member-tools-'+uuid.uuid4().hex),theme,wire)
 def item(n):return find_item(w.contentItem(),n) or w.findChild(QObject,n)
 def click(n):
  o=item(n);assert o,n
  QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,o.mapToScene(QPointF(o.width()/2,o.height()/2)).toPoint());_pump(app,lambda:False,.2)
 def send(text):
  item('inputField').forceActiveFocus();app.clipboard().setText(text);QTest.keyClick(w,Qt.Key_V,Qt.ControlModifier);QTest.keyClick(w,Qt.Key_Return)
 send('@新建成员 create Reviewer and dispatch A and B')
 sid=b._active
 assert _pump(app,lambda:'SUMMARY_A' in s.load_session(sid).model_dump_json() and not b._host.is_busy(sid),12),s.load_session(sid).model_dump_json()
 disk=ChatSessionStore(h);main=disk.load_session(sid);ref=main.members[0];child=disk.load_session(ref['sessionId'])
 assert child.parentId==sid and not ref['openTasks']
 assert 'EARLY_B' in main.model_dump_json() and 'FINAL_A' in main.model_dump_json()
 assert not any(p.isError for m in child.messages for p in (m.content if isinstance(m.content,list) else []) if p.type=='tool_result')
 shot(w,out/f'member-tools-{theme}.png')
 send('Stop the new C task')
 assert _pump(app,lambda:'STOPPED' in s.load_session(sid).model_dump_json() and not b._host.is_busy(ref['sessionId']),10)
 click('backgroundCapsule');shot(w,out/f'member-remove-{theme}.png');click('bgRemove_'+ref['sessionId'])
 final=ChatSessionStore(h).load_session(sid);assert final.members[0]['removedAt'];assert not b.backgroundTasks()
 assert set(wire.tools)=={'create_member','member_send','member_status','member_stop','read_main','reply_task','report_to_main'},wire.tools
 results.append({'theme':theme,'home':str(h),'main':main.model_dump(),'child':child.model_dump(),'removed':final.members[0],'tools':wire.tools,'requests':wire.requests})
 t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.2)
(out/'member-tools.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print('PASS all seven actual tools, busy insertion, early reply, escalation, stop and UI removal; reopened stores')
