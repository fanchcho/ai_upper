import sys,json,threading,time,uuid
from pathlib import Path
from datetime import datetime,timedelta,timezone
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot,find_item
from test_qml_shell import text_stream
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtCore import Qt,QPointF,QObject
from PySide6.QtTest import QTest
calls=[]
class Server(BaseHTTPRequestHandler):
 def do_POST(self):
  data=json.loads(self.rfile.read(int(self.headers['Content-Length'])));calls.append(data)
  mode=data['state'].splitlines()[0]
  if mode=='timeout':time.sleep(16)
  try:
   raw=json.dumps({'answers':{'execute':{'noul':.9 if mode=='allowed' else .1}}}).encode();self.send_response(200);self.end_headers();self.wfile.write(raw)
  except BrokenPipeError:pass
 def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Server);threading.Thread(target=server.serve_forever,daemon=True).start()
app=QGuiApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf');out=Path('out/final-four');out.mkdir(parents=True,exist_ok=True);results=[]
for theme in ['dark','light']:
 w,b,s,t,e,h=build(Path('/tmp/ai-upper-decision-'+uuid.uuid4().hex),theme,text_stream('EXECUTED'))
 def item(name):return find_item(w.contentItem(),name) or w.findChild(QObject,name)
 def click(name):
  o=item(name);assert o,name
  QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,o.mapToScene(QPointF(o.width()/2,o.height()/2)).toPoint());_pump(app,lambda:False,.15)
 def text(name,value):
  click(name);QTest.keyClick(w,Qt.Key_A,Qt.ControlModifier);app.clipboard().setText(value);QTest.keyClick(w,Qt.Key_V,Qt.ControlModifier)
 def rows():return json.loads((h/'tasks.json').read_text())['tasks']
 click('railTasks')
 click('taskDecisionConfig')
 text('decisionConfigName','Loopback Jev');text('decisionConfigHost','http://127.0.0.1:'+str(server.server_port));text('decisionConfigKey','fixture');text('decisionConfigThreshold','0.65')
 shot(w,out/f'decision-provider-{theme}.png');click('decisionConfigSave')
 providers=json.loads((h/'config.json').read_text())['models']['providers'];provider=next(p for p in providers if p.get('purpose')=='decision')
 assert provider['threshold']==.65 and provider['adapter']=='jev' and b._vault.get_secret(provider['id'])=='fixture'
 text('taskTitle','Manual denied');text('taskPrompt','denied');text('taskWhen',(datetime.now(timezone.utc)+timedelta(hours=1)).replace(tzinfo=None).isoformat(timespec='seconds'));click('taskCreate')
 row=next(r for r in rows() if r['title']=='Manual denied');identity=row['id'];click('taskEdit_'+identity)
 if not item('taskDecision').property('checked'):click('taskDecision')
 click('taskCreate');before=next(r for r in rows() if r['id']==identity)
 click('taskRun_'+identity)
 assert _pump(app,lambda:bool(next(r for r in rows() if r['id']==identity).get('runs')),8)
 result=next(r for r in rows() if r['id']==identity)
 assert result['lastDecision']['status']=='denied' and result['status']=='active' and result['nextRunAt']==before['nextRunAt']
 assert not s.load_session(result['sessionId']).messages
 shot(w,out/f'decision-manual-{theme}.png');results.append(result)
 b.tasksService().timer.stop();t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.1)
(out/'decision-manual.json').write_text(json.dumps({'results':results,'http_requests':calls},ensure_ascii=False,indent=2));print('PASS real click run-now -> HTTP decision denied; scheduled time retained; no model execution');server.shutdown()
