"""三种 attach 实现的端到端耗时，以及 setDocument 自身是否触发全量重高亮。"""
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

def timed(fn):
    t = time.perf_counter(); fn(); return round((time.perf_counter()-t)*1000, 1)

for turns in (100, 400):
    md = make_md(turns)
    out = {"turns": turns, "chars": len(md)}

    # 现状（两遍渲染 + attach 内再全量 rehighlight）
    body_owned = QTextDocument(); body_owned.setTextWidth(696.0)
    hl_owned = CodeHighlighter(body_owned, style)
    def current():
        render_markdown(body_owned, md, style, content_width=676.0)
        hl_owned.rehighlight()
        hl_owned.setDocument(qd)
        render_markdown(qd, md, style, content_width=676.0)
        hl_owned.rehighlight()
    out["current_ms"] = timed(current)
    app.processEvents()

    # 用单独的文档承载 scratch 与高亮器（避免污染 qd）
    scratch = QTextDocument(); scratch.setTextWidth(696.0)
    hl_scratch = CodeHighlighter(scratch, style)

    # setDocument 本身（高亮器从 scratch 换到 qd，qd 已有大内容）是否触发全量重高亮
    def move_hl():
        hl_scratch.setDocument(qd)
    out["setDocument_to_big_target_ms"] = timed(move_hl)
    out["setDocument_then_back_ms"] = timed(lambda: hl_scratch.setDocument(scratch))
    app.processEvents()

    # V1: 高亮器留在自有文档（scratch），scratch 渲染(含高亮) + fragment 搬运，目标侧无高亮器
    def v1():
        hl_scratch.setDocument(scratch)
        render_markdown(scratch, md, style, content_width=676.0)
        hl_scratch.rehighlight()
        cur = QTextCursor(qd); cur.beginEditBlock()
        cur.select(QTextCursor.Document); cur.removeSelectedText()
        cur.insertFragment(QTextDocumentFragment(scratch)); cur.endEditBlock()
    out["v1_hl_stays_on_scratch_ms"] = timed(v1)
    app.processEvents()

    # V2: 先把高亮器挂到目标，再搬运（不显式 rehighlight）
    hl2 = CodeHighlighter(qd, style)
    def v2():
        render_markdown(scratch, md, style, content_width=676.0)
        cur = QTextCursor(qd); cur.beginEditBlock()
        cur.select(QTextCursor.Document); cur.removeSelectedText()
        cur.insertFragment(QTextDocumentFragment(scratch)); cur.endEditBlock()
    out["v2_hl_on_target_ms"] = timed(v2)
    app.processEvents()

    out["target_chars"] = qd.characterCount()
    print(json.dumps(out, ensure_ascii=False), flush=True)
