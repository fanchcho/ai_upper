"""候选方案（都在真实 QQuickTextEdit 活动文档上，400 轮正文）：
M0 现状：render_markdown 直接写活动文档 + rehighlight
M1 渲染期间 textWidth=-1（禁换行布局），结束后恢复并强制重排一次
M2 M1 + blockSignals
M3 scratch 渲染(含高亮) -> insertFragment -> 手工把 layout 格式搬到目标块
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import (QGuiApplication, QTextCursor, QTextDocument, QTextDocumentFragment,
                           QTextLayout)
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickTextDocument
from PySide6.QtWidgets import QApplication
from markdown.document import BodyStyle, render_markdown
from markdown.highlight import CodeHighlighter

CODE = "```python\ndef handler(payload):\n    items = payload.get('items') or []\n    return [x * 2 for x in items]\n```"
TABLE = "| 名称 | 数值 |\n|---|---|\n| alpha | 1 |\n| beta | 2 |"

def make_md(turns):
    out = []
    for i in range(turns):
        out.append("第 %d 轮的提问：请把这一轮的结果整理成表格并给出要点。" % i)
        out.append("这是第 %d 轮回复。\n\n%s\n\n要点：\n\n1. 先读 README\n2. 再看依赖\n\n%s" % (i, CODE, TABLE))
    return "\n\n".join(out)

class Sink(QObject):
    def __init__(self):
        super().__init__(); self.doc = None
    @Slot(QQuickTextDocument, result=bool)
    def attach(self, qd):
        self.doc = qd; return True

app = QApplication.instance() or QApplication([])
sink = Sink(); engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("sink", sink)
engine.loadData(b'''import QtQuick
Window { width: 900; height: 700; visible: true
  Flickable { width: 780; height: 600; contentHeight: te.implicitHeight; clip: true
    TextEdit { id: te; width: 696; readOnly: true; wrapMode: TextEdit.Wrap
      textFormat: TextEdit.RichText
      Component.onCompleted: sink.attach(textDocument) } } }''')
engine.rootObjects()[0]; app.processEvents()
qd = sink.doc.textDocument()
style = BodyStyle()

def code_formats(doc, text="if x: pass"):
    b = doc.begin()
    while b.isValid() and b.text() != text:
        b = b.next()
    if not b.isValid():
        return None
    lay = b.layout()
    if lay is None:
        return {"layout": None}
    return {text[f.start:f.start+f.length]: f.format.foreground().color().name()
            for f in lay.formats()}

for turns in (100, 400):
    md = make_md(turns)
    out = {"turns": turns, "chars": len(md)}
    hl = CodeHighlighter(qd, style)

    def m0():
        render_markdown(qd, md, style, content_width=676.0)
        hl.rehighlight()
    t = time.perf_counter(); m0(); app.processEvents()
    out["M0_current_ms"] = round((time.perf_counter()-t)*1000, 1)
    out["M0_highlight"] = code_formats(qd)

    def m1():
        w = qd.textWidth()
        qd.setTextWidth(-1)
        try:
            render_markdown(qd, md, style, content_width=676.0)
        finally:
            qd.setTextWidth(w if w > 0 else 696.0)
        qd.documentLayout()
        hl.rehighlight()
    t = time.perf_counter(); m1(); app.processEvents()
    out["M1_nowrap_ms"] = round((time.perf_counter()-t)*1000, 1)
    out["M1_highlight"] = code_formats(qd)

    def m1b():
        w = qd.textWidth()
        qd.setTextWidth(-1)
        try:
            qd.blockSignals(True)
            render_markdown(qd, md, style, content_width=676.0)
        finally:
            qd.blockSignals(False)
            qd.setTextWidth(w if w > 0 else 696.0)
        qd.documentLayout()
        hl.rehighlight()
    t = time.perf_counter(); m1b(); app.processEvents()
    out["M1b_nowrap_blocked_ms"] = round((time.perf_counter()-t)*1000, 1)

    scratch = QTextDocument(); scratch.setTextWidth(696.0)
    hl_s = CodeHighlighter(scratch, style)
    def m3():
        render_markdown(scratch, md, style, content_width=676.0)
        hl_s.rehighlight()
        cur = QTextCursor(qd); cur.beginEditBlock()
        cur.select(QTextCursor.Document); cur.removeSelectedText()
        cur.insertFragment(QTextDocumentFragment(scratch)); cur.endEditBlock()
        # 手工搬 layout 格式
        sb, tb = scratch.begin(), qd.begin()
        moved = 0
        while sb.isValid() and tb.isValid():
            slay = sb.layout()
            if slay is not None and slay.formats():
                tlay = tb.layout()
                if tlay is not None:
                    tlay.setFormats(list(slay.formats()))
                    moved += 1
            sb, tb = sb.next(), tb.next()
        return moved
    t = time.perf_counter(); moved = m3(); app.processEvents()
    out["M3_fragment_layoutcopy_ms"] = round((time.perf_counter()-t)*1000, 1)
    out["M3_blocks_with_formats_moved"] = moved
    out["M3_highlight"] = code_formats(qd)
    print(json.dumps(out, ensure_ascii=False, default=str), flush=True)
