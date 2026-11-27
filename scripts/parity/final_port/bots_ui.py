"""Actual QML config-management roundtrip. Does not claim external bot connectivity."""
import json,os,sys,uuid
from pathlib import Path
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot,find_item
from test_qml_shell import text_stream
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtCore import QPointF,Qt,QObject
from PySide6.QtTest import QTest
app=QGuiApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf');results=[]
for theme in ['dark','light']:
 w,b,s,t,e,h=build(Path('/tmp/ai-upper-bots-'+uuid.uuid4().hex),theme,text_stream('unused'))
 # A stored config fixture, not a substitute for a connected remote channel.
 bot={'id':'bot-fixture','name':'配置管理验证','platform':'telegram','enabled':False,'replyMode':'final','createdAt':1,
      'scope':{'mode':'all','personas':[],'sessions':[]},'users':[],'bindings':{},'settings':{}}
 b._settings.set_config({'remote':{'bots':[bot]}})
 def click(name):
  o=find_item(w.contentItem(),name) or w.findChild(QObject,name);assert o is not None,name
  pt=o.mapToScene(QPointF(o.width()/2,o.height()/2));QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,pt.toPoint());_pump(app,lambda:False,.2)
 def row():return json.loads((h/'config.json').read_text())['remote']['bots'][0]
 click('railBots');click('botSearch');app.clipboard().setText('telegram');QTest.keyClick(w,Qt.Key_V,Qt.ControlModifier);_pump(app,lambda:False,.2);assert find_item(w.contentItem(),'botReply_bot-fixture') is not None;click('botReply_bot-fixture');assert row()['replyMode']=='stream'
 click('botScope_bot-fixture');assert row()['scope']['sessions']==[b._active]
 click('botToggle_bot-fixture');assert row()['enabled'] is False
 shot(w,Path('docs/audit/parity-close')/f'bots-{theme}.png')
 results.append({'theme':theme,'home':str(h),'config':row(),'enable':'blocked: missing real credentials; not connected'})
 click('botDelete_bot-fixture');assert json.loads((h/'config.json').read_text())['remote']['bots']==[]
 b.botsService().close();t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.1)
Path('out/final-port/bots-ui.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print('PASS configuration list/reply/scope/delete; external connection UNVERIFIED (no credentials)')
