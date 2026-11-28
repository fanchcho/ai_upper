"""Real QML mouse events + local RFC8628 endpoint; not Feishu tenant success."""
import json,os,sys,threading,uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qs
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot,find_item
from test_qml_shell import text_stream
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtCore import QPointF,Qt,QObject
from PySide6.QtTest import QTest
mode='pending';requests=[]
class Handler(BaseHTTPRequestHandler):
 def do_POST(self):
  data=parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode());requests.append(data)
  if data['action']==['begin']:result={'verification_uri_complete':'https://accounts.feishu.cn/local-protocol-fixture','device_code':'fixture','expires_in':120,'interval':.05}
  elif mode=='done':result={'client_id':'cli_local_protocol_fixture','client_secret':'local-not-a-real-secret','user_info':{'open_id':'ou_local_owner'}}
  elif mode=='denied':result={'error':'access_denied','error_description':'LOCAL FIXTURE: user rejected creation'}
  else:result={'error':'authorization_pending'}
  raw=json.dumps(result).encode();self.send_response(200);self.end_headers();self.wfile.write(raw)
 def log_message(self,*a):pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
os.environ['AI_UPPER_FEISHU_REGISTRATION']='http://127.0.0.1:'+str(server.server_port)
app=QGuiApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf');results=[]
for theme in ['dark','light']:
 mode='pending';w,b,s,t,e,h=build(Path('/tmp/ai-upper-scan-'+uuid.uuid4().hex),theme,text_stream('unused'))
 def click(name):
  o=find_item(w.contentItem(),name) or w.findChild(QObject,name);assert o,name
  QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,o.mapToScene(QPointF(o.width()/2,o.height()/2)).toPoint());_pump(app,lambda:False,.15)
 click('railBots');api=b.botsService();events=[];api.scanChanged.connect(lambda x:events.append(x))
 click('feishuScan');assert _pump(app,lambda:any(x['status']=='waiting' for x in events),8)
 waiting=next(x for x in events if x['status']=='waiting');assert 'createOnly=true' in waiting['url']
 shot(w,Path('docs/audit/remote-qr-phone')/f'feishu-qr-{theme}.png')
 click('botScanCancel');assert events[-1]['status']=='cancelled'
 mode='denied';click('feishuScan');assert _pump(app,lambda:events[-1]['status']=='denied',8)
 assert 'LOCAL FIXTURE' in events[-1]['error'];denied=events[-1];click('botScanCancel')
 mode='pending';click('feishuScan');assert _pump(app,lambda:events[-1]['status']=='waiting',8)
 mode='done';assert _pump(app,lambda:events[-1]['status']=='done',8)
 rows=json.loads((h/'config.json').read_text())['remote']['bots'];bot=rows[0]
 assert bot['users'][0]['id']=='ou_local_owner'
 assert b._vault.get_secret('remote:'+bot['id']+':appSecret')=='local-not-a-real-secret'
 assert 'local-not-a-real-secret' not in (h/'config.json').read_text()
 _pump(app,lambda:False,.5)
 shot(w,Path('docs/audit/remote-qr-phone')/f'feishu-owner-{theme}.png')
 click('detailInvite');code=api.pairing[bot['id']]['code'];assert len(code)==6
 click('detailCancelInvite');assert bot['id'] not in api.pairing
 click('detailInvite');assert bot['id'] in api.pairing
 shot(w,Path('docs/audit/remote-qr-phone')/f'feishu-owner-{theme}.png')
 click('detailDelete');assert not json.loads((h/'config.json').read_text())['remote']['bots']
 results.append({'theme':theme,'home':str(h),'created':bot,'denied':denied,'cancelled':True,'invite_cancel_and_regenerate':True,'deleted':True})
 api.close();t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.2)
server.shutdown();server.server_close()
Path('docs/audit/remote-qr-phone/feishu-readback.json').write_text(json.dumps({'boundary':'local HTTP registration fixture, NOT real Feishu app creation','results':results,'http_requests':requests},ensure_ascii=False,indent=2))
print('PASS: QML scan/cancel/denied/create/owner-vault-readback/invite/delete in both themes; external tenant creation UNVERIFIED')
