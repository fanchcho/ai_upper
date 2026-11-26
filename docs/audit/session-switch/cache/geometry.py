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

def seed(store, count=24):
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

import markdown.prepare as prep
import markdown.viewport as vp
from markdown.viewport import _iter_tables, _is_code_table
from utils.qt_compat import QtCore, QtGui
specs=[]
def geometry(document):
    layout = document.documentLayout()
    overlays = []
    for table in _iter_tables(document.rootFrame()):
        if _is_code_table(table):
            continue
        rows = table.rows()
        columns = table.columns()
        if rows <= 0 or columns <= 0:
            continue
        first = layout.blockBoundingRect(table.cellAt(0, 0).firstCursorPosition().block())
        if rows > 1:
            second = layout.blockBoundingRect(table.cellAt(1, 0).firstCursorPosition().block())
            row_height = second.y() - first.y()
        else:
            row_height = first.height()
        if row_height <= 1:
            continue
        top = first.y()
        bottom = layout.blockBoundingRect(
            table.cellAt(rows - 1, 0).firstCursorPosition().block()).y() + row_height
        left = first.x()
        col_lines = []
        right = left
        for column in range(columns):
            block_rect = layout.blockBoundingRect(
                table.cellAt(0, column).firstCursorPosition().block())
            col_lines.append(block_rect.x())
            right = max(right, block_rect.x() + block_rect.width())
        if right - left <= 1 or bottom - top <= 1:
            continue
        # Remove the engine-drawn frame only in the QML document copy.
        stripped = QtGui.QTextTableFormat(table.format())
        stripped.setBorder(0.0)
        table.setFormat(stripped)
        row_lines = [top + index * row_height for index in range(rows + 1)]
        col_lines.append(right)
        rect = QtCore.QRectF(left, top, right - left, bottom - top)
        overlays.append((rect, row_lines, col_lines))
    return overlays

original_prepare=prep.prepare_document
def prepared(source, plain, style, width, resolver):
    fragment,images=original_prepare(source,plain,style,width,resolver)
    document=QtGui.QTextDocument()
    document.setDocumentMargin(0)
    document.setTextWidth(width)
    QtGui.QTextCursor(document).insertFragment(fragment)
    specs[:]=geometry(document)
    return QtGui.QTextDocumentFragment(document),images
prep.prepare_document=prepared
def grids(quick_document, document, color):
    return [vp.TableGridOverlay(quick_document.parent(),r,rows,cols,color) for r,rows,cols in specs]
vp.attach_table_grids=grids

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
for position, i in enumerate((list(range(1,24))+[0])*2):
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
    rows.append(dict(path="cold" if position<24 else "hot",id=i,dispatch_ms=dispatch,max_gui_ms=app.longest,frame_ms=elapsed,phases=phases.copy(),calls=counts.copy()))
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
