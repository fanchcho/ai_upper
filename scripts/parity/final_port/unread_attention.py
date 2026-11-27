import os,sys,json,uuid,threading
from pathlib import Path
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot,find_item
from test_qml_shell import text_stream
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import Qt,QPointF
from PySide6.QtTest import QTest
app=QGuiApplication([]);results=[]
for theme in ['dark','light']:
 w,b,s,t,e,h=build(Path('/tmp/ai-upper-attention-'+uuid.uuid4().hex),theme,text_stream('actual reply'),sessions=('one','two'))
 controller=b._host.interactions
 worker=threading.Thread(target=lambda:controller.request('two','evidence','question','Choose a value',['yes','no']),daemon=True);worker.start()
 assert _pump(app,lambda:'two' in b._attention,5)
 shot(w,Path('out/final-port')/f'attention-{theme}.png')
 rows=b._rows();index=next(i for i,r in enumerate(rows) if r['id']=='two');row=find_item(w.contentItem(),'threadRow'+str(index));pt=row.mapToScene(QPointF(40,20));QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,pt.toPoint());_pump(app,lambda:False,.2)
 pending=b.pendingInteractions();assert pending and b.answerInteraction(pending[0]['id'],'answered','yes');worker.join(2)
 assert _pump(app,lambda:'two' not in b._attention,5)
 # Host completion without _turn_session (scheduled/remote background turn).
 b._host.send({'sessionId':'one','text':'background request'})
 assert _pump(app,lambda:'one' in b._unread,8)
 visible=w.property('sessions');visible=visible.toVariant() if hasattr(visible,'toVariant') else visible
 assert any(r['id']=='one' and r['unread'] for r in visible)
 results.append({'theme':theme,'attention_cleared':True,'background_unread_published':True,'answer':json.loads(controller._path(pending[0]['id']).read_text())['answer']})
 t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.1)
Path('out/final-port/unread-attention.json').write_text(json.dumps(results,indent=2));print('PASS actual pending request, click/read/answer, background host completion and published unread')
