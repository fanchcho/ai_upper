import os,sys,json,time
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['QT_QUICK_BACKEND']='software'
sys.path[:0]=['app/src','app/tests']
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import Qt,QPoint,QObject,QCoreApplication,QEvent
from PySide6.QtTest import QTest
from pytest import MonkeyPatch
from test_qml_context_menu import _build_window,_find_item,_center,_pump,_as_list
app=QGuiApplication([]);mp=MonkeyPatch();w,b,s,h,t,e=_build_window(Path(os.environ['AI_UPPER_HOME']),mp)
w.setProperty('page','chat');_pump(app,.1)
# Hold a long image-rich document while independently scaling sidebar metadata.
png='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII='
b._body.set_markdown(('Long body **bold**\n\n![pixel]('+png+')\n\n```python\nreturn 42\n```\n\n')*200);b._body.attach(b._document)
results=[]
def click(name):
 item=_find_item(w.contentItem(),name);assert item is not None,name
 x,y=_center(item);start=time.perf_counter();QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(round(x),round(y)),0);app.processEvents();im=w.grabWindow();assert not im.isNull();return (time.perf_counter()-start)*1000
lst=w.findChild(QObject,'sessionList')
for n in [120,1000,10000,100000,300000]:
 rows=[dict(id=f's-{i}',title=f'Session {i}',time='now',persona='general',personaName='Deva') for i in range(n)]
 w.setProperty('sessions',rows);w.setProperty('selectMode',True);w.setProperty('selectedSessions',[]);lst.setProperty('contentY',0);_pump(app,.1)
 samples=[]
 for repeat in range(3):
  for action in ['selectionAll','threadRow1','threadRow1','selectionAll']:
   samples.append(dict(action=action,ms=click(action)))
  samples.append(dict(action='select_before_scroll',ms=click('selectionAll')))
  assert len(_as_list(w.property('selectedSessions')))==n
  start=time.perf_counter();lst.setProperty('contentY',(n-15)*54);app.processEvents();w.grabWindow();samples.append(dict(action='scroll',ms=(time.perf_counter()-start)*1000));w.grabWindow().save(sys.argv[1]+f'-selected-{n}.png');lst.setProperty('contentY',0);_pump(app,.02)
  samples.append(dict(action='clear_after_scroll',ms=click('selectionAll')))
  assert len(_as_list(w.property('selectedSessions')))==0
 results.append(dict(n=n,samples=samples));print(n,max(x['ms'] for x in samples),flush=True)
w.grabWindow().save(sys.argv[1]+'.png');Path(sys.argv[1]+'.json').write_text(json.dumps(results,indent=2))
t.stop();w.close();e.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
