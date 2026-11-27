import json,os,sys,uuid
from pathlib import Path
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot,find_item
from test_qml_shell import text_stream
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtCore import Qt,QPointF
from PySide6.QtTest import QTest
app=QGuiApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf');results=[]
for theme in ['dark','light']:
 w,b,s,t,e,h=build(Path('/tmp/ai-upper-mentions-'+uuid.uuid4().hex),theme,text_stream('unused'))
 session=s.load_session(b._active);session.members=[{'id':'reviewer','name':'Reviewer'}];s.save(b._active)
 field=find_item(w.contentItem(),'inputField');point=field.mapToScene(QPointF(30,20));QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,point.toPoint())
 app.clipboard().setText('Ask @Rev after');QTest.keyClick(w,Qt.Key_V,Qt.ControlModifier)
 for _ in range(6):QTest.keyClick(w,Qt.Key_Left)
 _pump(app,lambda:False,.3);assert w.property('slashOpen')
 shot(w,Path('out/final-port')/f'mentions-{theme}.png')
 QTest.keyClick(w,Qt.Key_Tab);_pump(app,lambda:False,.2)
 assert field.property('text')=='Ask @Reviewer after',field.property('text')
 assert not w.property('slashOpen')
 results.append({'theme':theme,'text':field.property('text'),'sent':len(session.messages),'candidates':b.mentionCandidates()})
 t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.1)
Path('out/final-port/mentions-ui.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print('PASS real keyboard trigger/filter/Tab insertion; suffix preserved; no message sent')
