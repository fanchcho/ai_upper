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
 click('railBots');click('webPairTicket')
 rows=json.loads((h/'config.json').read_text())['remote']['bots'];web=next(r for r in rows if r['platform']=='web')
 s.ensure_session('s-2');s.save('s-2')
 click('botDetail_'+web['id']);click('scopeMode_sessions');click('scopeChoice_s-1');click('scopeChoice_s-2');click('scopeSave')
 def webrow():return next(r for r in json.loads((h/'config.json').read_text())['remote']['bots'] if r['id']==web['id'])
 assert set(webrow()['scope']['sessions'])=={'s-1','s-2'}
 b.personaSave(json.dumps({'id':'detail-a','name':'Detail A','prompt':'A'}));b.personaSave(json.dumps({'id':'detail-b','name':'Detail B','prompt':'B'}))
 click('scopeMode_personas')
 choices=b.botsService().scopeChoices('personas');assert len(choices)>1
 for p in choices[:2]:click('scopeChoice_'+p['id'])
 click('scopeSave');assert len(webrow()['scope']['personas'])==2
 click('detailReply');assert webrow()['replyMode']=='stream'
 shot(w,Path('docs/audit/bot-detail')/f'detail-{theme}.png')
 results.append({'theme':theme,'web':webrow(),'created_from_actual_click':True})
 click('detailDelete');assert not any(r['id']==web['id'] for r in json.loads((h/'config.json').read_text())['remote']['bots'])
 b.botsService().close();t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.1)
Path('docs/audit/bot-detail/readback.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print('PASS configuration list/reply/scope/delete; external connection UNVERIFIED (no credentials)')
