import os,sys,json
from pathlib import Path
sys.path[:0]=['scripts/parity','app/src','app/tests']
from feature_parity_evidence import *
from test_qml_shell import text_stream
from qml_shell import _pump
from PySide6.QtCore import QPointF
app=QGuiApplication([])
rows=[]
for theme in ['dark','light']:
 tmp=Path(os.environ['AI_UPPER_HOME'])/theme
 w,b,s,t,e,h=build(tmp,theme,text_stream('ok'),sessions=('s-1','s-2'))
 field=find_item(w.contentItem(),'inputField')
 def click(x,y):
  QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(x,y));_pump(app,lambda:False,.25)
 def rowclick(i):
  item=find_item(w.contentItem(),'threadRow'+str(i));pt=item.mapToScene(QPointF(40,20));click(round(pt.x()),round(pt.y()))
 def type_text(text):
  for ch in text: QTest.keyClick(w,ch)
 # Select rows through the actual sidebar and type through the focused editor.
 rowclick(0)
 first=w.property('activeId')
 p=field.mapToScene(QPointF(30,25));click(round(p.x()),round(p.y()))
 type_text('draft one');_pump(app,lambda:False,.1)
 rowclick(1)
 second=w.property('activeId')
 assert first and second and first!=second,(first,second)
 empty=field.property('text')
 click(round(p.x()),round(p.y()));type_text('draft two')
 rowclick(0)
 restored=field.property('text')
 shot(w,Path('out/feature-review')/f'drafts-{theme}.png')
 rows.append(dict(theme=theme,first=first,second=second,second_initial=empty,restored=restored))
 t.stop();w.close();e.deleteLater()
Path('out/feature-review/drafts.json').write_text(json.dumps(rows,indent=2))
assert all(r['second_initial']=='' and r['restored']=='draft one' for r in rows),rows
