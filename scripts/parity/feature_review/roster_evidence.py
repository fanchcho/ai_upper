import os,sys,json
from pathlib import Path
sys.path[:0]=['scripts/parity','app/src','app/tests']
from feature_parity_evidence import build,find_item,shot
from qml_shell import _pump
from test_qml_shell import text_stream
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtCore import QPointF,Qt
from PySide6.QtTest import QTest
app=QGuiApplication([])
QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf')
base=Path(os.environ['AI_UPPER_HOME']);out=Path('out/parity-close');results=[]
for theme in ['dark','light']:
 w,b,store,t,e,home=build(base/theme,theme,text_stream('ok'),sessions=('one','two','three'))
 from mvvm.services.plugin_identity import shared_store
 shared_store().ensure_seeded()
 roles=b.quickStartPersonas();role=roles[0]['id']
 for sid,folder in [('one','/fixture/a/shared'),('two','/fixture/b/shared'),('three','')]:
  session=store.load_session(sid);session.personaId=role;session.focusRoot=folder;store.save(sid)
 b._publish();_pump(app,lambda:False,.3)
 def click(name):
  item=find_item(w.contentItem(),name)
  if item is None:
   from PySide6.QtCore import QObject
   item=w.findChild(QObject,name)
  assert item is not None,name
  pt=item.mapToScene(QPointF(item.width()/2,item.height()/2));QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,pt.toPoint());_pump(app,lambda:False,.25)
 click('railRoster')
 assert w.property('page')=='roster'
 field=find_item(w.contentItem(),'rosterSearch')
 pt=field.mapToScene(QPointF(20,15));QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,pt.toPoint())
 # Paste through the real text input because persona names may be non-ASCII.
 app.clipboard().setText(roles[0]['name']);QTest.keyClick(w,Qt.Key_V,Qt.ControlModifier);_pump(app,lambda:False,.3)
 shot(w,out/f'roster-{theme}.png')
 click('rosterStart_'+role)
 assert w.property('page')=='chat'
 sid=w.property('activeId');assert store.load_session(sid).personaId==role
 saved=json.loads(store.session_path(sid).read_text())
 results.append(dict(theme=theme,session=sid,persona=role,file=str(store.session_path(sid)),saved=saved))
 t.stop();w.close();e.deleteLater()
(out/'roster.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
