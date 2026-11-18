"""验证 QQuickTextEdit 活动文档慢的原因，并试一条批量替换路径。

A: 裸 QTextDocument 渲染
B: QQuickTextEdit 的 textDocument 渲染（控件可见）
C: 同 B 但控件 visible=false
D: 先渲染到 scratch 文档，再用一次 insertFragment 搬进 QQuickTextEdit 文档
E: 同 D，但用 QTextCursor.insertHtml（整篇一次）
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QTextCursor, QTextDocument, QTextDocumentFragment
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication
from markdown.document import BodyStyle, render_markdown

CODE = "```python\ndef handler(payload):\n    items = payload.get('items') or []\n    return [x * 2 for x in items]\n```"
TABLE = "| 名称 | 数值 |\n|---|---|\n| alpha | 1 |\n| beta | 2 |"

def make_md(turns):
    out = []
    for i in range(turns):
        out.append("第 %d 轮的提问：请把这一轮的结果整理成表格并给出要点。" % i)
        out.append("这是第 %d 轮回复。\n\n%s\n\n要点：\n\n1. 先读 README\n2. 再看依赖\n\n%s" % (i, CODE, TABLE))
    return "\n\n".join(out)

app = QApplication.instance() or QApplication([])
from PySide6.QtCore import QObject, Slot
from PySide6.QtQuick import QQuickTextDocument

class DocSink(QObject):
    def __init__(self):
        super().__init__()
        self.doc = None
        self.te = None
    @Slot(QQuickTextDocument, result=bool)
    def attach(self, quick_document):
        self.doc = quick_document
        return True

sink = DocSink()
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("sink", sink)
engine.loadData(b'''import QtQuick
import QtQuick.Controls
Window { width: 900; height: 700; visible: true
  Flickable { id: sc; width: 780; height: 600; contentHeight: te.implicitHeight; clip: true
    TextEdit { id: te; objectName: "te"; width: 696; readOnly: true; wrapMode: TextEdit.Wrap; textFormat: TextEdit.RichText
      Component.onCompleted: sink.attach(textDocument) }
  }
}''')
win = engine.rootObjects()[0]
app.processEvents()
class TE:
    def __init__(self, win, quick):
        self.win = win; self.quick = quick
    def textDocument(self): return self.quick.textDocument()
    def setVisible(self, v): self.win.setProperty("visible", v)
te = TE(win, sink.doc)
style = BodyStyle()
rows = []

def one(turns):
    md = make_md(turns)
    r = {"turns": turns, "chars": len(md)}
    d = QTextDocument(); t = time.perf_counter()
    render_markdown(d, md, style, content_width=676.0); r["A_bare_ms"] = round((time.perf_counter()-t)*1000, 1)

    qd = te.textDocument()
    t = time.perf_counter(); render_markdown(qd, md, style, content_width=676.0)
    app.processEvents(); r["B_quick_visible_ms"] = round((time.perf_counter()-t)*1000, 1)

    te.setVisible(False); app.processEvents()
    qd = te.textDocument()
    t = time.perf_counter(); render_markdown(qd, md, style, content_width=676.0)
    app.processEvents(); r["C_quick_hidden_ms"] = round((time.perf_counter()-t)*1000, 1)
    te.setVisible(True); app.processEvents()

    # D: scratch -> 一次 insertFragment
    scratch = QTextDocument(); scratch.setTextWidth(696.0)
    t = time.perf_counter()
    render_markdown(scratch, md, style, content_width=676.0)
    render_ms = (time.perf_counter()-t)*1000
    qd = te.textDocument()
    t2 = time.perf_counter()
    cur = QTextCursor(qd); cur.beginEditBlock(); cur.select(QTextCursor.Document); cur.removeSelectedText()
    cur.insertFragment(QTextDocumentFragment(scratch)); cur.endEditBlock()
    app.processEvents()
    frag_ms = (time.perf_counter()-t2)*1000
    r["D_scratch_ms"] = round(render_ms, 1); r["D_fragment_ms"] = round(frag_ms, 1)
    r["D_total_ms"] = round(render_ms + frag_ms, 1)
    r["D_tables_ok"] = qd.rootFrame().childFrames() is not None
    r["D_textlen"] = qd.characterCount()

    # E: 同 D 但 insertHtml
    scratch2 = QTextDocument(); scratch2.setTextWidth(696.0)
    render_markdown(scratch2, md, style, content_width=676.0)
    html = scratch2.toHtml()
    qd = te.textDocument()
    t3 = time.perf_counter()
    cur = QTextCursor(qd); cur.beginEditBlock(); cur.select(QTextCursor.Document); cur.removeSelectedText()
    cur.insertHtml(html); cur.endEditBlock()
    app.processEvents()
    r["E_insertHtml_ms"] = round((time.perf_counter()-t3)*1000, 1)
    r["E_textlen"] = qd.characterCount()
    return r

for turns in (100, 400):
    rows.append(one(turns))
    print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
