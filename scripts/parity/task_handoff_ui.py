import json,sys,uuid
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot,find_item
from test_qml_shell import text_stream
from scripted_transport import ScriptedTransport,sse
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtCore import Qt,QPointF,QObject
from PySide6.QtTest import QTest
from mvvm.services.chat_session_store import ChatSessionStore
class Wire:
 def __init__(self):self.wakes=0
 async def post(self,url,**kwargs):
  data=json.loads(kwargs['body']);body=json.dumps(data['messages'],ensure_ascii=False)
  if '<定时任务交接>' in body:self.wakes+=1;wire=text_stream('MAIN_AWAKE')
  elif 'tool_result' in body:wire=text_stream('DELIVERED_FULL_BODY')
  else:
   args={'needs_action':'WAKE_TASK' in body,'summary':'summary','content':'Action details'}
   wire=ScriptedTransport(chunks=[sse('message_start',{'type':'message_start','message':{'usage':{'input_tokens':5}}}),sse('content_block_start',{'type':'content_block_start','index':0,'content_block':{'type':'tool_use','id':uuid.uuid4().hex,'name':'deliver_result','input':{}}}),sse('content_block_delta',{'type':'content_block_delta','index':0,'delta':{'type':'input_json_delta','partial_json':json.dumps(args)}}),sse('content_block_stop',{'type':'content_block_stop','index':0}),sse('message_delta',{'type':'message_delta','delta':{'stop_reason':'tool_use'},'usage':{'output_tokens':5}}),sse('message_stop',{'type':'message_stop'})])
  return await wire.post(url,**kwargs)
app=QGuiApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf')
out=Path('out/member-task-close');out.mkdir(parents=True,exist_ok=True);results=[]
for theme in ['dark','light']:
 for needs in [False,True]:
  wire=Wire();w,b,s,t,e,h=build(Path('/tmp/ai-upper-handoff-'+uuid.uuid4().hex),theme,wire)
  from mvvm.services.plugin_identity import shared_store
  shared_store().ensure_seeded();b._publish();main_id=b._active
  def item(name):return find_item(w.contentItem(),name) or w.findChild(QObject,name)
  def click(name):
   o=item(name);assert o is not None,name
   QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,o.mapToScene(QPointF(o.width()/2,o.height()/2)).toPoint());_pump(app,lambda:False,.15)
  def text(name,value):
   click(name);QTest.keyClick(w,Qt.Key_A,Qt.ControlModifier);app.clipboard().setText(value);QTest.keyClick(w,Qt.Key_V,Qt.ControlModifier)
  def choose(name,index):
   o=item(name);o.forceActiveFocus();QTest.keyClick(w,Qt.Key_Home)
   for _ in range(index):QTest.keyClick(w,Qt.Key_Down)
   QTest.keyClick(w,Qt.Key_Tab)
  def rows():return json.loads((h/'tasks.json').read_text())['tasks']
  click('railTasks');text('taskTitle','Initial');text('taskPrompt','initial')
  text('taskWhen',(datetime.now(timezone.utc)+timedelta(hours=1)).replace(tzinfo=None).isoformat(timespec='seconds'));click('taskCreate')
  identity=rows()[0]['id'];click('taskEdit_'+identity)
  text('taskTitle','Edited task');text('taskPrompt','WAKE_TASK' if needs else 'INFORM_TASK');choose('taskKind',1);text('taskWhen','*/5 * * * *');text('taskTimezone','Asia/Shanghai');text('taskModel','p1:claude-sonnet-5-5');click('taskEnabled');choose('taskOwner',next(i for i,row in enumerate(item('taskOwner').property('model')) if row['id']==main_id))
  shot(w,out/f'task-edit-{theme}-{needs}.png');click('taskCreate')
  edited=rows()[0];assert edited['title']=='Edited task' and edited['status']=='paused' and edited['schedule']=={'kind':'recurring','tz':'Asia/Shanghai','cron':'*/5 * * * *'},edited
  assert edited['auth']['modelRef']=='p1:claude-sonnet-5-5' and edited['ownerSessionId']==main_id,edited
  click('taskEdit_'+identity);choose('taskKind',0);text('taskTimezone','UTC');text('taskWhen',(datetime.now(timezone.utc)+timedelta(seconds=8)).replace(tzinfo=None).isoformat(timespec='seconds'));click('taskEnabled');click('taskCreate')
  marker='MAIN_AWAKE' if needs else 'Edited task：DELIVERED_FULL_BODY'
  assert _pump(app,lambda:marker in s.load_session(main_id).model_dump_json(),20),(rows(),s.load_session(main_id).model_dump_json())
  disk=ChatSessionStore(h);assert marker in disk.load_session(main_id).model_dump_json()
  assert wire.wakes==(1 if needs else 0)
  finished=rows()[0];assert finished['runs'][0]['handoff']['needsAction']==needs
  if not needs:assert finished['remoteDelivery']['status']=='unverified'
  shot(w,out/f'task-result-{theme}-{needs}.png')
  results.append({'theme':theme,'needsAction':needs,'edited':edited,'finished':finished,'wakes':wire.wakes,'main':disk.load_session(main_id).model_dump()})
  b.tasksService().timer.stop();t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.1)
(out/'tasks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print('PASS edited fields disk readback; timed execution; inform zero main turns; action exactly one main turn; remote unverified reason retained')
