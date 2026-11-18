"""策略对比：直接在 QQuickTextEdit 活动文档上渲染 vs 渲染期间屏蔽文档信号。"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QGuiApplication, QTextCursor, QTextDocument
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
        super().__init__(); self.doc = None; self.item = None
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
qd = sink.doc.textDocument()
style = BodyStyle()
rows = []

def run(turns):
    md = make_md(turns)
    r = {"turns": turns, "chars": len(md)}

    t = time.perf_counter(); render_markdown(qd, md, style, content_width=676.0)
    app.processEvents(); r["direct_ms"] = round((time.perf_counter()-t)*1000, 1)

    # 屏蔽文档信号
    t = time.perf_counter()
    qd.blockSignals(True)
    try:
        render_markdown(qd, md, style, content_width=676.0)
    finally:
        qd.blockSignals(False)
    blocked_render = (time.perf_counter()-t)*1000
    r["blocked_render_ms"] = round(blocked_render, 1)
    # 让控件重新认识内容：模拟一次全量 contentsChange
    t2 = time.perf_counter()
    try:
        qd.markContentsDirty(0, qd.characterCount())
        r["markContentsDirty_ok"] = True
    except Exception as exc:
        r["markContentsDirty_ok"] = f"{type(exc).__name__}: {exc}"
    app.processEvents()
    r["notify_ms"] = round((time.perf_counter()-t2)*1000, 1)
    r["blocked_total_ms"] = round((time.perf_counter()-t)*1000, 1)
    r["textlen"] = qd.characterCount()
    rows.append(r); print(json.dumps(r, ensure_ascii=False), flush=True)

for turns in (100, 400):
    run(turns)
