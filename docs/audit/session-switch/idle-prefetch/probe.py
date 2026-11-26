import os, sys, json, time, statistics, math, threading, resource, hashlib
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
app=MeasuredApplication([]); mp=MonkeyPatch()
# Suppress automatic first-session open: every cold sample is a first open.
from qml_shell import ShellBridge
mp.setattr(ShellBridge, 'initial', lambda self: self._publish())
startup=time.perf_counter()
w,b,s,h,t,e=fixture._build_window(Path(os.environ['AI_UPPER_HOME']),mp)
w.setProperty('page','chat'); fixture._pump(app,.3)

first_frame=w.grabWindow()
startup_ms=(time.perf_counter()-startup)*1000
from PySide6 import QtCore, QtGui, QtQml
from markdown.body import BodyDocument
from markdown.cache import Display
from markdown.prepare import prepare_document
from qml_shell_sessions import transcript_markdown
from qml_shell import _load_image
from concurrent.futures import ThreadPoolExecutor
import markdown.viewport as vp

class Prefetch(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.last_input=time.perf_counter(); self.epoch=0; self.stages=[]; self.input_delays=[]; self.click_events=[]
        self.completed=[]; self.cancelled=0; self.active=None; self.future=None
        self.executor=ThreadPoolExecutor(max_workers=1)
        self.timer=QtCore.QTimer(self);self.timer.setInterval(10);self.timer.timeout.connect(self.tick)
        self.queue=[f'parity-{i:03d}' for i in range(4)]
        app.installEventFilter(self);self.timer.start()
    def eventFilter(self,obj,event):
        if event.type() in (QEvent.MouseButtonPress,QEvent.MouseButtonRelease,QEvent.KeyPress,QEvent.Wheel,QEvent.TouchBegin):
            self.last_input=time.perf_counter();self.epoch+=1
            if self.future is not None:self.future.cancel()
        return False
    def record(self,label,fn):
        start=time.perf_counter();fn();self.stages.append(dict(stage=label,ms=(time.perf_counter()-start)*1000))
    def tick(self):
        if time.perf_counter()-self.last_input<1.0:return
        if self.future is None:
            if not self.queue:self.timer.stop();return
            self.sid=self.queue.pop(0);self.source=transcript_markdown(s.load_session(self.sid).messages)
            self.generation=self.epoch
            self.future=self.executor.submit(prepare_document,self.source,b._plain,b._body.style,b._body.content_width,_load_image)
            return
        if not self.future.done():return
        if self.generation!=self.epoch:
            self.cancelled+=1;self.future=None;return
        fragment,images=self.future.result();self.future=None
        # Same TextEdit width/font options, separate invisible item. Never swap
        # the visible body during prefetch.
        component=QtQml.QQmlComponent(e)
        component.setData(b'import QtQuick; TextEdit { visible: false; textFormat: TextEdit.RichText; wrapMode: TextEdit.Wrap }',QtCore.QUrl())
        item=component.create();item.setParentItem(w.contentItem());item.setWidth(b._document.parent().width())
        quick=item.property('textDocument');target=quick.textDocument()
        target.setDefaultFont(b._document.textDocument().defaultFont())
        target.setDefaultTextOption(b._document.textDocument().defaultTextOption())
        body=BodyDocument(style=b._body.style,content_width=b._body.content_width)
        body._source=self.source;body._plain=b._plain
        real_grids=vp.attach_table_grids;real_code=vp.attach_code_viewports
        vp.attach_table_grids=lambda *args:[];vp.attach_code_viewports=lambda *args:[]
        scheduled=time.perf_counter()+.001
        def click():
            self.input_delays.append(max(0,(time.perf_counter()-scheduled)*1000))
            tick=time.perf_counter()
            QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,QPoint(600,70),0)
            self.click_events.append((time.perf_counter()-tick)*1000)
        if os.environ.get('PROBE_INPUT')=='1':QtCore.QTimer.singleShot(1,click)
        else:QtCore.QTimer.singleShot(1,lambda:self.input_delays.append(max(0,(time.perf_counter()-scheduled)*1000)))
        try:self.record('fragment_commit_highlight',lambda:body.attach(quick,fragment=fragment,images=images))
        finally:vp.attach_table_grids=real_grids;vp.attach_code_viewports=real_code
        def overlays():
            if self.generation!=self.epoch:
                self.cancelled+=1;item.deleteLater();return
            self.record('code_viewports',lambda:setattr(body,'_viewports',real_code(quick,target,QtGui.QColor(body.palette.code_bg))))
            self.record('table_grids',lambda:setattr(body,'_grids',real_grids(quick,target,QtGui.QColor(body.palette.border))))
            # Probe owns the hidden TextEdit; do not transfer its document ownership.
            self.completed.append((self.sid,item,body,target,component))
        QtCore.QTimer.singleShot(0,overlays)

mode=sys.argv[2] if len(sys.argv)>2 else 'prefetch'
probe=Prefetch() if mode=='prefetch' else None
app.tracking=True;app.longest=0
start=time.perf_counter()
while time.perf_counter()-start<4:
    app.processEvents();time.sleep(.001)
app.tracking=False
result=dict(startup_first_frame_ms=startup_ms,max_gui_event_ms=app.longest,
            stages=probe.stages if probe else [],timer_delay_ms=probe.input_delays if probe else [],
            cancelled=probe.cancelled if probe else 0,click_dispatch_ms=probe.click_events if probe else [],completed=len(probe.completed) if probe else 0,rss_peak_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
assert w.property('activeId')==''
after=w.grabWindow();after.save(sys.argv[1]+'.png');first_frame.save(sys.argv[1]+'-initial.png')
Path(sys.argv[1]+'.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
if probe:
    probe.timer.stop();probe.executor.shutdown(wait=True,cancel_futures=True)
    app.removeEventFilter(probe)
    for _,item,body,target,component in probe.completed:
        body.highlighter.setDocument(None);item.deleteLater()
t.stop();w.close();e.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);mp.undo()
