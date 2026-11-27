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
 click('filterBtn');click('filterRole_'+role)
 folders=w.property('filterFoldersAvailable').toVariant();index=next(i for i,x in enumerate(folders) if x['path']=='/fixture/a/shared')
 click('filterFolder_'+str(index))
 rows=w.property('visibleSessions').toVariant();assert [r['id'] for r in rows]==['one'],rows
 shot(w,out/f'filter-{theme}.png')
 QTest.keyClick(w,Qt.Key_Escape);_pump(app,lambda:False,.2)
 click('searchClear');assert len(w.property('visibleSessions'))==3
 results.append(dict(theme=theme,selected=[r['id'] for r in rows],cleared=3,paths=folders))
 t.stop();w.close();e.deleteLater()
(out/'filter.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
