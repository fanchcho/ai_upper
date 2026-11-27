import json,os,sys,time,uuid
from pathlib import Path
from datetime import datetime,timezone,timedelta
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot,find_item
from test_qml_shell import text_stream
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtCore import QPointF,Qt,QObject
from PySide6.QtTest import QTest
app=QGuiApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf');results=[]
for theme in ['dark','light']:
 w,b,s,t,e,h=build(Path('/tmp/ai-upper-tasks-'+uuid.uuid4().hex),theme,text_stream('task reply'))
 from mvvm.services.plugin_identity import shared_store
 shared_store().ensure_seeded();b._publish()
 def item(name):
  return find_item(w.contentItem(),name) or w.findChild(QObject,name)
 def click(name):
  o=item(name);assert o is not None,name
  pt=o.mapToScene(QPointF(o.width()/2,o.height()/2));QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,pt.toPoint());_pump(app,lambda:False,.25)
 def type_text(name,text):
  click(name);QTest.keyClick(w,Qt.Key_A,Qt.ControlModifier)
  app.clipboard().setText(text);QTest.keyClick(w,Qt.Key_V,Qt.ControlModifier);_pump(app,lambda:False,.1)
 click('railTasks');type_text('taskTitle','Task evidence');type_text('taskPrompt','scheduled fixture request')
 type_text('taskWhen',(datetime.now(timezone.utc)+timedelta(seconds=12)).replace(tzinfo=None).isoformat(timespec='seconds'))
 click('taskCreate');rows=json.loads((h/'tasks.json').read_text())['tasks'];assert len(rows)==1,rows
 identity=rows[0]['id'];click('taskPause_'+identity);assert json.loads((h/'tasks.json').read_text())['tasks'][0]['status']=='paused'
 click('taskPause_'+identity);assert json.loads((h/'tasks.json').read_text())['tasks'][0]['status']=='active'
 assert _pump(app,lambda:len(json.loads((h/'tasks.json').read_text())['tasks'][0]['runs'])==1,20),'timer did not run'
 row=json.loads((h/'tasks.json').read_text())['tasks'][0];assert row['runs'][0]['status']=='done',row
 session=s.load_session(row['sessionId']);assert len(session.messages)>=2
 shot(w,Path('out/final-port')/f'tasks-{theme}.png')
 click('taskOpen_'+identity);assert b._active==identity
 click('railTasks');click('taskDelete_'+identity);assert json.loads((h/'tasks.json').read_text())['tasks']==[]
 results.append({'theme':theme,'home':str(h),'created':row,'message_count':len(session.messages),'deleted':True})
 b.tasksService().timer.stop();t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.1)
Path('out/final-port/tasks-ui.json').write_text(json.dumps(results,indent=2));print('PASS real create/pause/resume/automatic timer/host turn/persisted history/open/delete in both themes')
