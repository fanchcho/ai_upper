import sys,json,uuid
from pathlib import Path
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot,find_item
from test_qml_shell import text_stream
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtCore import Qt,QPointF
from PySide6.QtTest import QTest
app=QGuiApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf');out=Path('out/remaining-three');results=[]
for theme in ['dark','light']:
 w,b,s,t,e,h=build(Path('/tmp/ai-upper-feishu-config-'+uuid.uuid4().hex),theme,text_stream('unused'))
 def click(n):
  o=find_item(w.contentItem(),n);assert o,n
  QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,o.mapToScene(QPointF(o.width()/2,o.height()/2)).toPoint());_pump(app,lambda:False,.25)
 click('railBots');click('feishuConnect')
 assert not b.botsService().list()
 shot(w,out/f'feishu-missing-{theme}.png')
 results.append({'theme':theme,'reason':'未验证：飞书 App ID 或 App Secret 未配置','config':json.loads((h/'config.json').read_text()),'bots':b.botsService().list()})
 for name,text in [('feishuId','cli_invalid_parity'),('feishuSecret','invalid-not-a-credential')]:
  click(name);app.clipboard().setText(text);QTest.keyClick(w,Qt.Key_V,Qt.ControlModifier)
 click('feishuDomain');QTest.keyClick(w,Qt.Key_End);QTest.keyClick(w,Qt.Key_Return)
 click('feishuConnect');api=b.botsService();assert len(api.list())==1
 bot=api.list()[0];assert bot['settings']=={'appId':'cli_invalid_parity','domain':'lark'}
 assert _pump(app,lambda:api.states.get(bot['id'],'').startswith(('未验证','error')),25),api.states
 reason=api.states[bot['id']];assert 'connected' not in reason
 disk=json.loads((h/'config.json').read_text());row=disk['remote']['bots'][0]
 assert row['settings']==bot['settings'] and row['users']==[]
 assert 'invalid-not-a-credential' not in (h/'config.json').read_text()
 from mvvm.services.secrets_vault import SecretsVault
 assert SecretsVault(h).get_secret('remote:'+bot['id']+':appSecret')=='invalid-not-a-credential'
 shot(w,out/f'feishu-error-{theme}.png');click('feishuPair_'+bot['id']);shot(w,out/f'feishu-pair-{theme}.png')
 assert len(api.pairing[bot['id']]['code'])==6
 results.append({'theme':theme,'reason':reason,'config':disk,'secret_readback':True,'pair_code_issued':True,'paired':False})
 api.close();t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.1)
(out/'feishu-config.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print('PASS actual keyboard config, QML connect, reopened disk/vault readback, real endpoint failure, pair code click; no external pairing/send success claimed');print(json.dumps([r['reason'] for r in results],ensure_ascii=False))
