import json,os,sys,uuid
from pathlib import Path
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot,find_item
from test_qml_shell import text_stream
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtCore import Qt,QPointF,QPoint
from PySide6.QtTest import QTest
from mvvm.models.chat_models import Message
from mvvm.services.rewind import Rewind
from mvvm.services.tool_runtime import ToolRuntime
app=QGuiApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf'); results=[]
out=Path('out/member-task-close');out.mkdir(parents=True,exist_ok=True)
for theme in ['dark','light']:
 w,b,s,t,e,h=build(Path('/tmp/ai-upper-rewind-'+uuid.uuid4().hex),theme,text_stream('done'))
 target=h/'sample.txt';target.write_text('BEFORE\n')
 session=s.load_session(b._active)
 Rewind(h,session.id).begin(session)
 session.messages.append(Message(role='user',content='change sample'));s.save(session.id)
 b._host.guard.trust_root(h)
 runtime=ToolRuntime(b._host.guard,h,home=h,session_id=session.id)
 result=runtime.execute('write_file',{'path':str(target),'content':'AFTER\n'},'evidence-write')
 assert not result.is_error, result
 assert target.read_text()=='AFTER\n'
 field=find_item(w.contentItem(),'inputField');field.forceActiveFocus();[QTest.keyClick(w,ord(c.upper())) for c in '/rewind'];_pump(app,lambda:False,.3)
 menu=find_item(w.contentItem(),'slashMenuRoot')
 QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,menu.mapToScene(QPointF(25,40)).toPoint());_pump(app,lambda:False,.3)
 def click(name):
  item=find_item(w.contentItem(),name);assert item is not None,name
  QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,item.mapToScene(QPointF(item.width()/2,item.height()/2)).toPoint());_pump(app,lambda:False,.2)
 click('rewindTurn_0');shot(w,out/f'rewind-{theme}.png')
 click('rewindApply');assert target.read_text()=='BEFORE\n'
 click('rewindUndo');assert target.read_text()=='AFTER\n'
 target.write_text('EXTERNAL\n');click('rewindApply');assert target.read_text()=='EXTERNAL\n'
 error=find_item(w.contentItem(),'rewindResult').property('text');assert 'conflict' in error,error
 click('rewindUndo');click('rewindTurn_0')
 click('rewindForce_0');shot(w,out/f'rewind-force-{theme}.png');click('rewindApply')
 assert target.read_text()=='BEFORE\n'
 click('rewindUndo');assert target.read_text()=='EXTERNAL\n'
 # 105 actual tool writes, one per genuine user turn; old payloads released.
 journal=Rewind(h,'retention');counted=s.ensure_session('retention')
 rt=ToolRuntime(b._host.guard,h,home=h,session_id='retention')
 for n in range(105):
  journal.begin(counted);counted.messages.append(Message(role='user',content=str(n)))
  assert not rt.execute('write_file',{'path':str(target),'content':str(n)},'cap-'+str(n)).is_error
 data=journal.read();assert len({r['turn'] for r in data['records'] if isinstance(r.get('pre'),str)})==100
 assert sum(bool(r.get('released')) for r in data['records'])==5
 results.append({'retention':100,'released':5})

 results.append({'theme':theme,'home':str(h),'restored':'BEFORE','undone':'AFTER','conflict':error,'disk':'EXTERNAL'})
 click('rewindClose')
 skill=h/'skills'/'example';skill.mkdir(parents=True)
 (skill/'SKILL.md').write_text('---\nname: example\ndescription: Skill execution evidence\n---\nSKILL_EXECUTION_MARKER')
 field.forceActiveFocus()
 for c in '/example': QTest.keyClick(w,ord(c.upper()))
 _pump(app,lambda:False,.3)
 menu=find_item(w.contentItem(),'slashMenuRoot');shot(w,out/f'skill-{theme}.png')
 QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,menu.mapToScene(QPointF(25,40)).toPoint());_pump(app,lambda:False,.2)
 assert field.property('text')=='/example '
 QTest.keyClick(w,Qt.Key_Return)
 assert _pump(app,lambda:len(s.load_session(session.id).messages)>2 and not b._host.is_busy(session.id),10)
 from mvvm.services.chat_session_store import ChatSessionStore
 disk=ChatSessionStore(h).load_session(session.id)
 assert 'SKILL_EXECUTION_MARKER' in disk.model_dump_json()
 results[-1]['skill_host_disk']=True
 t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.1)
for theme in ['dark','light']:
 w,b,s,t,e,h=build(Path('/tmp/ai-upper-scroll-'+uuid.uuid4().hex),theme,text_stream('unused'))
 session=s.load_session(b._active)
 for n in range(150):session.messages.append(Message(role='user',content='scroll row '+str(n)))
 s.save(session.id)
 field=find_item(w.contentItem(),'inputField');field.forceActiveFocus()
 for c in '/rewind':QTest.keyClick(w,ord(c.upper()))
 _pump(app,lambda:False,.3)
 menu=find_item(w.contentItem(),'slashMenuRoot');QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,menu.mapToScene(QPointF(20,40)).toPoint());_pump(app,lambda:False,.3)
 flick=find_item(w.contentItem(),'rewindScroll')
 QTest.wheelEvent(w,QPointF(700,500),QPoint(0,-3600));_pump(app,lambda:False,.5)
 assert flick.property('contentY')>0,(flick.property('contentY'),flick.property('contentHeight'))
 results.append({'theme':theme,'scrollY':flick.property('contentY'),'turns':150});shot(w,out/f'rewind-scroll-{theme}.png')
 t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.1)
out.joinpath('rewind.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print('PASS',json.dumps(results,ensure_ascii=False))
