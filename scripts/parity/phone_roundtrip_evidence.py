"""QML clicks -> browser input -> real encrypted WS -> ChatHost -> loopback model -> disk.
Relay and model are explicitly local fixtures, not public/mobile verification.
"""
import atexit,json,os,sys,threading,uuid,subprocess,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,urlunsplit
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot,find_item
from qml_shell import _pump
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.secrets_vault import SecretsVault
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtCore import Qt,QPointF
from PySide6.QtTest import QTest
out=Path('docs/audit/remote-qr-phone');tmp=Path('.tmp/phone-evidence');tmp.mkdir(parents=True,exist_ok=True)
requests=[]
class Model(BaseHTTPRequestHandler):
 def do_POST(self):
  data=json.loads(self.rfile.read(int(self.headers['Content-Length'])));requests.append({'path':self.path,'messages':data['messages']})
  events=[('message_start',{'type':'message_start','message':{'usage':{'input_tokens':7}}}),('content_block_start',{'type':'content_block_start','index':0,'content_block':{'type':'text','text':''}}),('content_block_delta',{'type':'content_block_delta','index':0,'delta':{'type':'text_delta','text':'LOCAL_MODEL_REPLY'}}),('message_delta',{'type':'message_delta','delta':{'stop_reason':'end_turn'},'usage':{'output_tokens':2}}),('message_stop',{'type':'message_stop'})]
  raw=''.join('event: '+name+'\ndata: '+json.dumps(body)+'\n\n' for name,body in events).encode();self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def log_message(self,*a):pass
model=ThreadingHTTPServer(('127.0.0.1',0),Model);threading.Thread(target=model.serve_forever,daemon=True).start()
env=os.environ.copy();env['PATH']=str(Path('.tmp/wm/usr/bin').resolve())+':'+str(Path('.tmp/icon-dpi/runtime/usr/bin').resolve())+':'+env['PATH'];env['LD_LIBRARY_PATH']=':'.join(str(Path(p).resolve()) for p in ['.tmp/extensions-complete/runtime/usr/lib/aarch64-linux-gnu','.tmp/icon-dpi/runtime/usr/lib/aarch64-linux-gnu','.tmp/wm/usr/lib/aarch64-linux-gnu']);env['NODE_PATH']='/home/agent/shared_workspace/deva/node_modules';env['TMPDIR']=str(tmp.resolve())
portfile=tmp/'relay-port';portfile.unlink(missing_ok=True)
relay=subprocess.Popen(['node','scripts/parity/phone_relay_fixture.cjs'],env=env,stdout=open(tmp/'relay.stdout','w'),stderr=subprocess.STDOUT)
atexit.register(lambda: relay.terminate() if relay.poll() is None else None)
for _ in range(100):
 if portfile.exists():break
 time.sleep(.05)
relay_port=int(portfile.read_text());app=QGuiApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf');results=[]
for theme in ('dark','light'):
 w,b,s,t,e,h=build(Path('/tmp/ai-upper-phone-'+uuid.uuid4().hex),theme,None)
 models=b._settings.get('models');models['providers'][0]['apiHost']='http://127.0.0.1:'+str(model.server_port);b._settings.set_config({'models':models})
 def click(name):
  item=find_item(w.contentItem(),name);assert item,name
  QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint());_pump(app,lambda:False,.25)
 click('railBots');api=b.botsService();api.webPairTicket();rows=api.list();bot=rows[0];bot['settings']={'port':0,'relayUrl':'http://127.0.0.1:'+str(relay_port)};api.save(rows);click('phoneEntry')
 for via in ('lan','relay'):
  for name in ('result.json','revoked','repair-url','repaired'):(tmp/name).unlink(missing_ok=True)
  click('phoneLan' if via=='lan' else 'phoneRelay');pane=find_item(w.contentItem(),'phoneQr').parentItem().parentItem().parentItem()
  ticket=pane.property('ticket');assert ticket.get('url'),ticket
  server=api.workers[bot['id']];cancel_id=server.ticket['id'];click('phoneCancel');assert cancel_id not in server.tickets
  click('phoneLink');sticky_id=server.ticket['id'];copied=QGuiApplication.clipboard().text();assert '#d=' in copied
  click('phoneCancel');assert server.tickets[sticky_id]['sticky']
  click('phoneLan' if via=='lan' else 'phoneRelay');ticket=pane.property('ticket')
  url=ticket['url']
  if via=='lan':
   parsed=urlsplit(url);url=urlunsplit((parsed.scheme,'127.0.0.1:'+str(api.workers[bot['id']].lan.port()),parsed.path,parsed.query,parsed.fragment))
  shot(w,out/f'phone-qr-{theme}-{via}.png')
  browser=subprocess.Popen(['xvfb-run','-a',str(Path('.tmp/extensions-complete/browser/node_modules/electron/dist/electron').resolve()),'--no-sandbox','--disable-gpu','scripts/parity/phone_browser_evidence.cjs',url,theme,via,str(out/'phone-browser')],env=env,stdout=open(out/f'browser-{theme}-{via}.log','w'),stderr=subprocess.STDOUT)
  assert _pump(app,lambda:(tmp/'result.json').exists() or browser.poll() is not None,45),(theme,via,'timeout')
  assert (tmp/'result.json').exists(),(browser.returncode,(out/f'browser-{theme}-{via}.log').read_text())
  result=json.loads((tmp/'result.json').read_text());sid=result['sid'];did=result['device']
  reopened=ChatSessionStore(h);session=reopened.load_session(sid);assert session
  messages=[m.text() for m in session.messages];assert 'PHONE_'+via+'_'+theme in messages and 'LOCAL_MODEL_REPLY' in messages,messages
  users=json.loads((h/'config.json').read_text())['remote']['bots'][0]['users'];assert len(users)==1 and users[0]['via']==via
  assert any(d['id']==did and d['online'] for d in api.phoneState()['devices'])
  shot(w,out/f'phone-device-{theme}-{via}.png')
  click('phoneRevoke_'+did);assert _pump(app,lambda:(tmp/'revoked').exists(),15)
  assert not json.loads((h/'config.json').read_text())['remote']['bots'][0]['users']
  assert SecretsVault(h).get_secret('remote:'+bot['id']+':dev:'+did) is None
  click('phoneLan' if via=='lan' else 'phoneRelay');repair_url=pane.property('ticket')['url']
  if via=='lan':
   parsed=urlsplit(repair_url);repair_url=urlunsplit((parsed.scheme,'127.0.0.1:'+str(server.lan.port()),parsed.path,parsed.query,parsed.fragment))
  (tmp/'repair-url').write_text(repair_url)
  assert _pump(app,lambda:(tmp/'repaired').exists() or browser.poll() is not None,20)
  assert (tmp/'repaired').exists(),(out/f'browser-{theme}-{via}.log').read_text()
  repaired=(tmp/'repaired').read_text();assert repaired!=did
  click('phoneRevoke_'+repaired);assert _pump(app,lambda:browser.poll() is not None,15)
  assert browser.returncode==0,(out/f'browser-{theme}-{via}.log').read_text()
  assert not json.loads((h/'config.json').read_text())['remote']['bots'][0]['users']
  result['fresh_qr_after_revoke']=repaired
  results.append({'theme':theme,'via':via,'home':str(h),'session':sid,'messages_reopened':messages,'device_before_revoke':users[0],'browser':result,'revoked_disk_and_key':True})
 api.close();t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.2)
model.shutdown();model.server_close();relay.terminate();relay.wait(5)
(out/'phone-readback.json').write_text(json.dumps({'boundary':'localhost relay and model fixtures; real sockets/ChatHost/store/browser events; no physical phone or public relay','results':results,'model_http_requests':requests,'relay_envelopes':json.loads((tmp/'relay-log.json').read_text())},ensure_ascii=False,indent=2))
print('PASS LAN + relay x dark/light: real browser input, encrypted ingress, real ChatHost HTTP model, egress, reload, reopened disk, device revoke/key removal')
