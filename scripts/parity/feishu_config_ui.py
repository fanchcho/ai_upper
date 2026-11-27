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
 t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.1)
(out/'feishu-config.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print('PASS actual connect click with absent credentials refuses creation; no network success claimed; dark/light screenshots')
