import os,sys,json,time
from pathlib import Path
sys.path[:0]=['app/src','app/tests']
from PySide6.QtGui import QGuiApplication,QWheelEvent
from PySide6.QtCore import QPoint,QPointF,QObject,Qt,QFile,QCollator,QLocale
from PySide6.QtTest import QTest
from pytest import MonkeyPatch
from test_qml_settings_provider import _build_window,_pump
Path(os.environ['XDG_DATA_HOME']).mkdir(parents=True,exist_ok=True)
app=QGuiApplication([])
home=Path(os.environ['AI_UPPER_HOME']);home.mkdir(parents=True,exist_ok=True)
w,b,s,v,t,e=_build_window(home,MonkeyPatch(),'chat')
fixture=s.home
def wheel(x,y):
 point=QPointF(x,y)
 event=QWheelEvent(point,QPointF(w.mapToGlobal(point.toPoint())),QPoint(),QPoint(0,-10000),Qt.NoButton,Qt.NoModifier,Qt.ScrollUpdate,False)
 app.sendEvent(w,event);_pump(app,.4)
for name in ['alpha','beta']:
 p=fixture/'skills'/name;p.mkdir(parents=True);(p/'SKILL.md').write_text(f'---\nname: {name}\n---\n# {name}\n\n'+('Detailed instructions.\n\n'*70))
from mvvm.services.plugin_identity import shared_store
os.environ['DEVA_ASSETS_DIR']=str(Path('app/assets').resolve())
shared_store().ensure_seeded()
p=fixture/'deva'/'personas';p.mkdir(parents=True,exist_ok=True)
for name in ['reviewer','writer','tester','designer','analyst']:(p/(name+'.md')).write_text(f'---\nname: {name}\n---\nPersona\n')
server=Path('.tmp/extensions-calibration/server.py').resolve()
server.parent.mkdir(parents=True,exist_ok=True)
server.write_text("import json,sys\nTOOLS=[{'name':'echo','description':'Echo input'}, {'name':'read_file','description':'Read a file from the workspace and return the complete contents with line numbers for review.'}, {'name':'list_files','description':'List workspace files'}]\nfor line in sys.stdin:\n r=json.loads(line)\n if 'id' not in r: continue\n result={'protocolVersion':'2025-06-18','capabilities':{},'serverInfo':{'name':'layout-fixture','version':'1'}} if r['method']=='initialize' else {'tools':[dict(t,inputSchema={'type':'object'}) for t in TOOLS]} if r['method']=='tools/list' else {}\n print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':result}),flush=True)\n")
(fixture/'mcp.json').write_text(json.dumps({'mcpServers':{'echo':{'name':'Echo','transport':'stdio','command':sys.executable,'args':[str(server)]},'fail':{'name':'Failure','transport':'stdio','command':'/missing-test-command'},'idle':{'name':'Off','transport':'http','url':'http://127.0.0.1:9'}}}))
s.set_config({'theme':sys.argv[1],'locale':'en','skills':{'enabled':{'beta':False},'roles':{'alpha':['reviewer','writer','tester','designer','analyst']}},'mcp':{'enabled':{'echo':True,'fail':True,'idle':False}}});b._apply_theme();w.setProperty('page','settings-extensions');_pump(app,2)
out=Path('out/extensions-typeahead');theme=sys.argv[1]
def shot(name):
 assert w.grabWindow().save(str(out/(theme+'-'+name+'.png')))
 def walk(item):
  yield item
  for child in item.childItems():yield from walk(child)
 data=[]
 for o in walk(w.contentItem()):
  if o.property('visible') and (o.property('text') or o.objectName()):
   pt=o.mapToScene(QPointF(0,0));row={'name':o.objectName(),'text':str(o.property('text') or '')[:60],'x':pt.x(),'y':pt.y(),'w':o.width(),'h':o.height()}
   data.append(row)
 (out/(theme+'-'+name+'-geometry.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2))
deadline=time.monotonic()+12
while b._extension_runtime().view('echo')['status']!='connected' and time.monotonic()<deadline: _pump(app,.2)
_pump(app,.3)
print('INITIAL runtime',b._extension_runtime().view('echo'),flush=True)
def visual(item):
 yield item
 for child in item.childItems():yield from visual(child)
notes=[str(o.property('text')) for o in visual(w.contentItem()) if o.property('visible') and o.property('text') in ('Connected','Connection failed')]
shot('state-check')
print('VISIBLE list states',notes,flush=True);assert 'Connected' in notes and 'Connection failed' in notes
shot('list')
(out/(theme+'-fixture.json')).write_text(json.dumps({'registry':json.loads((fixture/'mcp.json').read_text()),'config':json.loads((fixture/'config.json').read_text()),'rows':b.extensionRows()},ensure_ascii=False,indent=2))

from types import SimpleNamespace
from mvvm.services.extension_settings import ExtensionSettings
# Test double only at the OS keyring boundary; real vault/service/bridge/QML unchanged.
store={}
v._backend='keyring'
v._keyring=SimpleNamespace(set_password=lambda service,key,value: store.__setitem__(key,value),get_password=lambda service,key: store.get(key),delete_password=lambda service,key: store.pop(key,None))
service=ExtensionSettings(s,v)
service.update('mcp','echo',{'env':[{'key':'TOKEN','secret':True}], 'enabled':False})
b._check_extensions();_pump(app,.4)
w.setProperty('page','chat');_pump(app,.2);w.setProperty('page','settings-extensions');_pump(app,.3)
QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(580,487));_pump(app,.3);wheel(700,550)
w.requestActivate();_pump(app,.2)
field=next(o for o in visual(w.contentItem()) if o.property('visible') and o.property('placeholderText')=='Enter secret value (stored encrypted)')
field.forceActiveFocus()
for ch in 'fixture':QTest.keyClick(w,ord(ch.upper()))
_pump(app,.8)
assert store.get('mcp:echo:TOKEN')=='FIXTURE'
assert any(o.property('visible') and o.property('text')=='Saved' for o in visual(w.contentItem()))
shot('secret-double-saved');print('DOUBLE: real QTest input -> timer -> bridge -> vault -> fake keyring; Saved visible',flush=True)
w.setProperty('page','chat');_pump(app,.2);w.setProperty('page','settings-extensions');_pump(app,.3)
QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(580,487));_pump(app,.3);wheel(700,550)
assert any(o.property('visible') and o.property('text')=='Configured' for o in visual(w.contentItem()))
shot('secret-double-configured');print('DOUBLE: reopened detail Configured visible; NOT an OS credential success',flush=True)
b._ext_runtime.close();b._ext_timer.stop();t.stop();w.close();e.deleteLater();_pump(app,.1)
