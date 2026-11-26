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
for name in ['reviewer','writer']:(p/(name+'.md')).write_text(f'---\nname: {name}\n---\nPersona\n')
server=Path('.tmp/extensions-complete/shared-server.py').resolve()
server.write_text("""import json,sys
for line in sys.stdin:
 r=json.loads(line)
 if 'id' not in r:continue
 result={'protocolVersion':'2025-06-18','capabilities':{},'serverInfo':{'name':'test','version':'1'}} if r['method']=='initialize' else {'tools':[{'name':'echo','description':'Echo input','inputSchema':{'type':'object'}}]} if r['method']=='tools/list' else {}
 print(json.dumps({'jsonrpc':'2.0','id':r['id'],'result':result}),flush=True)
""")
(fixture/'mcp.json').write_text(json.dumps({'mcpServers':{'echo':{'name':'Echo','transport':'stdio','command':sys.executable,'args':[str(server)]},'fail':{'name':'Failure','transport':'stdio','command':'/missing-test-command'},'idle':{'name':'Off','transport':'http','url':'http://127.0.0.1:9'}}}))
s.set_config({'theme':sys.argv[1],'locale':'en','skills':{'enabled':{'beta':False},'roles':{'alpha':['reviewer','writer']}},'mcp':{'enabled':{'echo':True,'fail':True,'idle':False}}});b._apply_theme();w.setProperty('page','settings-extensions');_pump(app,2)
out=Path('out/extensions-exact');theme=sys.argv[1]
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
QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(580,487));_pump(app,.5);shot('mcp-detail')
scroll=[o for o in w.findChildren(QObject,'extensionDetailScroll') if o.property('visible')][-1].property('contentItem')
before=scroll.property('contentY');wheel(700,550);after=scroll.property('contentY')
print('MCP detail wheel',before,'->',after,'height',scroll.property('contentHeight'),'view',scroll.property('height'),flush=True);assert 0 < after <= scroll.property('contentHeight')-scroll.property('height')+1;shot('mcp-bottom')
w.setProperty('page','chat');_pump(app,.2);w.setProperty('page','settings-extensions');_pump(app,.3)
QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(580,397));_pump(app,.3);shot('skill-detail')
QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(600,343));_pump(app,.2);shot('roles-popup')
label=[o for o in visual(w.contentItem()) if o.property('visible') and o.property('text')=='writer'][-1]
point=label.mapToScene(QPointF(label.width()/2,label.height()/2));QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,point.toPoint());_pump(app,.2)
assert json.loads((fixture/'config.json').read_text())['skills']['roles']['alpha']==['reviewer']
label=[o for o in visual(w.contentItem()) if o.property('visible') and o.property('text')=='writer'][-1]
point=label.mapToScene(QPointF(label.width()/2,label.height()/2));QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,point.toPoint());_pump(app,.2)
assert json.loads((fixture/'config.json').read_text())['skills']['roles']['alpha']==['reviewer','writer']
print('ROLES dropdown mouse click persisted [reviewer,writer] -> [reviewer] -> [reviewer,writer]',flush=True)
QTest.keyClick(w,Qt.Key_Escape);_pump(app,.2)
scroll=[o for o in w.findChildren(QObject,'extensionInstructionsScroll') if o.property('visible')][-1]
before=scroll.property('contentY');shot('pre-scroll');wheel(700,550);after=scroll.property('contentY')
print('INSTRUCTIONS wheel contentY',before,'->',after,'height',scroll.property('contentHeight'),'view',scroll.property('height'),flush=True);assert after>before;shot('skill-bottom')
# Retry through the visible error detail, after correcting the real registry.
w.setProperty('page','chat');_pump(app,.2);w.setProperty('page','settings-extensions');_pump(app,.3)
QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(580,532));_pump(app,.3);shot('mcp-error')
b._ext_timer.stop()
registry=json.loads((fixture/'mcp.json').read_text());registry['mcpServers']['fail'].update(command=sys.executable,args=[str(server)])
(fixture/'mcp.json').write_text(json.dumps(registry))
retry=[o for o in visual(w.contentItem()) if o.property('visible') and o.property('text')=='Retry'][-1]
point=retry.mapToScene(QPointF(retry.width()/2,retry.height()/2))
QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,point.toPoint())
deadline=time.monotonic()+12
while b._extension_runtime().view('fail')['status']!='connected' and time.monotonic()<deadline:_pump(app,.2)
assert b._extension_runtime().view('fail')['status']=='connected';_pump(app,.3);shot('mcp-retry')
print('UI RETRY failed -> corrected command -> connected tools=',len(b._extension_runtime().view('fail')['tools']),flush=True)
b._ext_timer.start()
# Real keyboard input: secret autosave and masked retained draft.
from mvvm.services.extension_settings import ExtensionSettings
ExtensionSettings(s,v).update('mcp','echo',{'env':[{'key':'TOKEN','secret':True}]})
w.setProperty('page','chat');_pump(app,.2);w.setProperty('page','settings-extensions');_pump(app,.3)
QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(580,487));_pump(app,.3);wheel(700,550)
field=[o for o in visual(w.contentItem()) if o.property('visible') and o.property('placeholderText')=='Enter secret value (stored encrypted)'][-1]
point=field.mapToScene(QPointF(field.width()/2,field.height()/2));QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,point.toPoint())
w.requestActivate();_pump(app,.2);field.forceActiveFocus()
for c in 'FIXTURESECRET':QTest.keyClick(w,ord(c.upper()))
_pump(app,1)
assert v.get_secret('mcp:echo:TOKEN')=='FIXTURESECRET'
assert field.property('text')=='FIXTURESECRET'
assert 'FIXTURESECRET' not in (fixture/'mcp.json').read_text()
assert any(o.property('visible') and o.property('text')=='Saved' for o in visual(w.contentItem()))
shot('secret-saved');print('SECRET keyboard -> 600ms autosave -> encrypted vault verified, draft masked/retained, registry no plaintext',flush=True)
# External directory creation must emit and become visible without reopening.
w.setProperty('page','chat');_pump(app,.2);w.setProperty('page','settings-extensions');_pump(app,.3)
events=[];b.extensionsChanged.connect(lambda:events.append(time.time()))
p=fixture/'skills'/'external-added';p.mkdir();(p/'SKILL.md').write_text('---\nname: external-added\n---\nExternal content')
_pump(app,1.3);assert any(x['id']=='external-added' for x in b.extensionRows());assert events;assert any(o.property('visible') and o.property('text')=='external-added' for o in visual(w.contentItem()));shot('external-added')
print('EXTERNAL skill auto-discovered broadcasts=',len(events),flush=True)
for i in range(30):
 p=fixture/'skills'/f'long-{i:02}';p.mkdir();(p/'SKILL.md').write_text(f'---\nname: long-{i:02}\n---\nBody')
_pump(app,1);shot('long-list')
scroll=[o for o in w.findChildren(QObject,'extensionListScroll') if o.property('visible')][-1];before=scroll.property('contentY');wheel(700,550);after=scroll.property('contentY')
assert 0 < after <= scroll.property('contentHeight')-scroll.property('height')+1;shot('list-bottom');print('LIST wheel contentY',before,'->',after,'height',scroll.property('contentHeight'),flush=True)
# Service uses QFile.moveToTrash; exercise actual move and readback, then restore.
from mvvm.services.extension_settings import ExtensionSettings
service=ExtensionSettings(s,v)
p=fixture/'skills'/'000-trash-test';p.mkdir();(p/'SKILL.md').write_text('---\nname: 000-trash-test\n---\nRecoverable')
trash_paths=[];original_remove=ExtensionSettings.remove
def observe_remove(self,kind,key):
 result=original_remove(self,kind,key);trash_paths.append(result);return result
ExtensionSettings.remove=observe_remove
w.setProperty('page','chat');_pump(app,.2);w.setProperty('page','settings-extensions');_pump(app,.6)
QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(580,397));_pump(app,.2)
QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(853,215));_pump(app,.2);shot('delete-confirm')
buttons=[o for o in w.findChildren(QObject) if o.property('text')=='OK' and o.property('visible')]
assert buttons
button=buttons[-1];point=button.mapToScene(QPointF(button.width()/2,button.height()/2))
print('DELETE button local-scene',point,'UI click',640,481,flush=True)
QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(640,481));_pump(app,.8);shot('delete-result')
assert trash_paths and not p.exists()
trash=Path(trash_paths[-1]);assert 'Recoverable' in (trash/'SKILL.md').read_text()
trash.rename(p);assert (p/'SKILL.md').exists();print('TRASH UI-confirmed moved/read/restored',trash,p,flush=True)
print('MCP',b._extension_runtime().view('echo'),b._extension_runtime().view('fail'),flush=True)
b._ext_runtime.close();b._ext_timer.stop();t.stop();w.close();e.deleteLater();_pump(app,.1)
