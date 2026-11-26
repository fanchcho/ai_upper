import os, sys, json, time, statistics, math, threading, resource
from pathlib import Path
os.environ['QT_QPA_PLATFORM']='offscreen'
os.environ['QT_QUICK_BACKEND']='software'
sys.path[:0]=['app/src','app/tests']
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QPoint, Qt, QCoreApplication, QEvent
from PySide6.QtTest import QTest
from pytest import MonkeyPatch
import test_qml_context_menu as fixture
from mvvm.models.chat_models import Message

def seed(store, count=96):
    for i in range(count):
        s=store.ensure_session(f'parity-{i:03d}')
        s.title=f'Session {i:03d}'
        s.messages=[Message(role='assistant',content=f'Session {i:03d} turn {j}\n\nA paragraph with **bold** and a [link](https://example.com).\n\n```python\ndef square(x):\n    return x * x\n```\n\n| Name | Value |\n| --- | --- |\n| item | 42 |') for j in range(30)]
        s.updatedAt=1700000000000-i*1000
        store.save(s.id)
fixture._seed_sessions=seed
class MeasuredApplication(QGuiApplication):
    tracking = False
    longest = 0.0
    gui_ident = threading.get_ident()
    def notify(self, receiver, event):
        start = time.perf_counter()
        try:
            return super().notify(receiver, event)
        finally:
            if self.tracking and threading.get_ident() == self.gui_ident:
                self.longest = max(self.longest, (time.perf_counter()-start)*1000)
app=MeasuredApplication([]); mp=MonkeyPatch()
# Suppress automatic first-session open: every cold sample is a first open.
from qml_shell import ShellBridge
mp.setattr(ShellBridge, 'initial', lambda self: self._publish())
w,b,s,h,t,e=fixture._build_window(Path(os.environ['AI_UPPER_HOME']),mp)
w.setProperty('page','chat'); fixture._pump(app,.3)
list_signals=[]
w.sessionsChanged.connect(lambda: list_signals.append(1))
phases={}; counts={}
for obj,name in [(b,'_render'),(b,'_publish'),(b,'_rows'),(b._body,'set_markdown'),(b._body,'attach'),(s,'load_session')]:
    original=getattr(obj,name)
    def wrapped(*args,_name=name,_original=original,**kw):
        start=time.perf_counter()
        try: return _original(*args,**kw)
        finally:
            phases[_name]=phases.get(_name,0)+(time.perf_counter()-start)*1000
            counts[_name]=counts.get(_name,0)+1
    setattr(obj,name,wrapped)
rows=[]
lst=w.findChild(__import__('PySide6.QtCore',fromlist=['QObject']).QObject,'sessionList')
for position, i in enumerate((list(range(1,96))+[0])):
    lst.setProperty('contentY',max(0,min(i*54,float(lst.property('contentHeight'))-float(lst.property('height')))))
    fixture._pump(app,.03)
    item=fixture._find_item(w.contentItem(),f'threadRow{i}')
    assert item is not None,i
    x,y=fixture._center(item)
    phases.clear(); counts.clear()
    rendered_before=b.rendered
    app.longest=0.0; app.tracking=True
    start=time.perf_counter()
    QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(round(x),round(y)),0)
    dispatch=(time.perf_counter()-start)*1000
    deadline=time.perf_counter()+10
    gaps=[]
    while b.rendered == rendered_before:
        tick=time.perf_counter(); app.processEvents(); gaps.append((time.perf_counter()-tick)*1000)
        assert time.perf_counter()<deadline
        time.sleep(.001)
    app.processEvents(); image=w.grabWindow()
    elapsed=(time.perf_counter()-start)*1000
    app.tracking=False
    assert not image.isNull()
    assert w.property('activeId')==f'parity-{i:03d}',(i,w.property('activeId'))
    assert f'Session {i:03d} turn 29' in b._document.textDocument().toPlainText()
    assert w.property('activeTitle')==f'Session {i:03d}'
    cache = b._display_cache
    assert len(cache.entries) <= cache.max_entries and cache.bytes <= cache.max_bytes
    rows.append(dict(rss_peak_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,path="cold" if position<24 else "hot",id=i,dispatch_ms=dispatch,max_gui_ms=app.longest,frame_ms=elapsed,phases=phases.copy(),calls=counts.copy()))
    if position == 23:
        image.save(sys.argv[1]+'-cold.png')
image.save(sys.argv[1]+'.png')
values=sorted(r['frame_ms'] for r in rows)
result=dict(n=len(rows),median_ms=statistics.median(values),p95_ms=values[math.ceil(.95*len(values))-1],samples=rows)
cache=getattr(b,'_display_cache',None)
result['cache']=dict(hits=cache.hits,misses=cache.misses,entries=len(cache.entries),charged_bytes=cache.bytes) if cache else None
result['session_list_signals']=len(list_signals)
result['rss_peak_kib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
Path(sys.argv[1]+'.json').write_text(json.dumps(result,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='samples'}),flush=True)
t.stop(); w.close(); e.deleteLater(); QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete); mp.undo()
