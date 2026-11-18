"""fragment 搬运时，高亮器挂在目标文档上与否的代价对比。"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QGuiApplication, QTextCursor, QTextDocument, QTextDocumentFragment
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

def transfer(target, scratch):
    cur = QTextCursor(target); cur.beginEditBlock()
    cur.select(QTextCursor.Document); cur.removeSelectedText()
    cur.insertFragment(QTextDocumentFragment(scratch)); cur.endEditBlock()

for turns in (100, 400):
    md = make_md(turns)
    scratch = QTextDocument(); scratch.setTextWidth(696.0)
    out = {"turns": turns}

    # 高亮在一份独立（裸）文档上：便宜
    t = time.perf_counter(); render_markdown(scratch, md, style, content_width=676.0)
    out["scratch_render_ms"] = round((time.perf_counter()-t)*1000, 1)
    hl_scratch = CodeHighlighter(scratch, style)
    t = time.perf_counter(); hl_scratch.rehighlight()
    out["scratch_rehighlight_ms"] = round((time.perf_counter()-t)*1000, 1)

    # 情况1：目标文档没有高亮器
    hl_scratch.setDocument(QTextDocument())     # 摘掉，避免影响
    t = time.perf_counter(); transfer(qd, scratch); app.processEvents()
    out["transfer_no_hl_on_target_ms"] = round((time.perf_counter()-t)*1000, 1)

    # 情况2：高亮器挂在目标文档上
    hl_target = CodeHighlighter(qd, style)
    t = time.perf_counter(); transfer(qd, scratch); app.processEvents()
    out["transfer_with_hl_on_target_ms"] = round((time.perf_counter()-t)*1000, 1)
    print(json.dumps(out, ensure_ascii=False), flush=True)
