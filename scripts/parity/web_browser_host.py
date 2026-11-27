import sys,uuid,json
from pathlib import Path
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,find_item
from test_qml_shell import text_stream
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QTimer,Qt,QPointF
from PySide6.QtTest import QTest
app=QGuiApplication([]);w,b,s,t,e,h=build(Path('/tmp/ai-upper-web-browser-'+uuid.uuid4().hex),'dark',text_stream('unused'))
api=b.botsService();url=api.webPairTicket();Path('.tmp/remaining-three/browser-url.json').write_text(json.dumps({'url':url,'home':str(h)}))
def tick():
 server=next(iter(api.workers.values()))
 Path('.tmp/remaining-three/browser-state.json').write_text(json.dumps({'devices':[{k:v for k,v in state.items() if k in ('device','visible','proven')} for state in server.connections.values()]}))
 revoke=Path('.tmp/remaining-three/browser-revoke')
 if revoke.exists():
  revoke.unlink();bot=api.list()[0];did=bot['users'][0]['id']
  def click(name):
   o=find_item(w.contentItem(),name);assert o,name
   QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,o.mapToScene(QPointF(o.width()/2,o.height()/2)).toPoint())
  click('railBots');app.processEvents();click('botUser_'+did);app.processEvents()
  disk=json.loads((h/'config.json').read_text());assert not disk['remote']['bots'][0]['users']
  from mvvm.services.secrets_vault import SecretsVault
  assert SecretsVault(h).get_secret('remote:'+bot['id']+':dev:'+did) is None
  Path('.tmp/remaining-three/browser-revoked.json').write_text(json.dumps({'mouseClicked':True,'deviceRemoved':True,'keyDeleted':True}))
 if Path('.tmp/remaining-three/browser-done').exists():app.quit()
timer=QTimer();timer.setInterval(100);timer.timeout.connect(tick);timer.start();app.exec();api.close()
