"""对比：撤销栈开关 / edit block 批处理 / 目标文档类型 对渲染耗时的影响。"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QGuiApplication, QTextDocument
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickTextDocument
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

class Sink(QObject):
    def __init__(self):
        super().__init__(); self.doc = None
    @Slot(QQuickTextDocument, result=bool)
    def attach(self, qd):
        self.doc = qd; return True

app = QApplication.instance() or QApplication([])
sink = Sink()
engine = QQmlApplicationEngine()
engine.rootContext().setContextProperty("sink", sink)
engine.loadData(b'''import QtQuick
Window { width: 900; height: 700; visible: true
  Flickable { width: 780; height: 600; contentHeight: te.implicitHeight; clip: true
    TextEdit { id: te; objectName: "te"; width: 696; readOnly: true; wrapMode: TextEdit.Wrap
      textFormat: TextEdit.RichText
      Component.onCompleted: sink.attach(textDocument) } } }''')
engine.rootObjects()[0]
app.processEvents()
quick = sink.doc.textDocument()
style = BodyStyle()
rows = []

def t(fn):
    s = time.perf_counter(); r = fn(); return (time.perf_counter()-s)*1000, r

for turns in (100, 400):
    md = make_md(turns)
    r = {"turns": turns, "chars": len(md)}

    d = QTextDocument()
    r["bare_undo_on_ms"] = round(t(lambda: render_markdown(d, md, style, content_width=676.0))[0], 1)

    d = QTextDocument(); d.setUndoRedoEnabled(False)
    r["bare_undo_off_ms"] = round(t(lambda: render_markdown(d, md, style, content_width=676.0))[0], 1)

    # 清空一个已有大文档的代价
    d = QTextDocument(); d.setUndoRedoEnabled(False)
    render_markdown(d, md, style, content_width=676.0)
    r["bare_clear_big_ms"] = round(t(lambda: d.clear())[0], 1)

    q = quick
    r["quick_undo_on_ms"] = round(t(lambda: render_markdown(q, md, style, content_width=676.0))[0], 1)
    app.processEvents()

    q.setUndoRedoEnabled(False)
    s = time.perf_counter(); render_markdown(q, md, style, content_width=676.0)
    r["quick_undo_off_ms"] = round((time.perf_counter()-s)*1000, 1)
    app.processEvents()

    # 短内容覆盖大文档（切换会话时的清理代价）
    short = make_md(1)
    s = time.perf_counter(); render_markdown(q, short, style, content_width=676.0)
    r["quick_overwrite_big_with_short_ms"] = round((time.perf_counter()-s)*1000, 1)
    app.processEvents()

    q.setUndoRedoEnabled(False)
    s = time.perf_counter(); render_markdown(q, md, style, content_width=676.0)  # 先放回去
    app.processEvents()
    s = time.perf_counter(); render_markdown(q, short, style, content_width=676.0)
    r["quick_overwrite_undo_off_ms"] = round((time.perf_counter()-s)*1000, 1)
    app.processEvents()

    rows.append(r); print(json.dumps(r, ensure_ascii=False), flush=True)
