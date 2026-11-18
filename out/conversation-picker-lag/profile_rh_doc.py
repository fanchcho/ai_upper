"""rehighlight 的代价在文档类型上吗？裸文档 vs QML 文档，以及屏蔽信号。"""
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

for turns in (100, 400):
    md = make_md(turns)
    out = {"turns": turns}
    # 裸文档上跑高亮
    bare = QTextDocument(); bare.setTextWidth(696.0)
    hl_bare = CodeHighlighter(bare, style)
    render_markdown(bare, md, style, content_width=676.0)
    t = time.perf_counter(); hl_bare.rehighlight(); out["bare_rehighlight_ms"] = round((time.perf_counter()-t)*1000,1)

    # QML 文档
    scratch = QTextDocument(); scratch.setTextWidth(696.0)
    render_markdown(scratch, md, style, content_width=676.0)
    cur = QTextCursor(qd); cur.beginEditBlock(); cur.select(QTextCursor.Document)
    cur.removeSelectedText(); cur.insertFragment(QTextDocumentFragment(scratch)); cur.endEditBlock()
    hl = CodeHighlighter(qd, style)
    t = time.perf_counter(); hl.rehighlight(); out["qml_rehighlight_ms"] = round((time.perf_counter()-t)*1000,1)

    # QML 文档 + 屏蔽信号
    t = time.perf_counter(); qd.blockSignals(True); hl.rehighlight(); qd.blockSignals(False)
    out["qml_rehighlight_blocked_ms"] = round((time.perf_counter()-t)*1000,1)

    # 只高亮代码块（手动逐块，跳过没代码的块）
    print(json.dumps(out, ensure_ascii=False), flush=True)
