"""验证 scratch 渲染 + insertFragment 搬运的保真度（表格/边框/图片/字符数/HTML 等价）。"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QObject, Qt, Slot, QUrl
from PySide6.QtGui import QGuiApplication, QImage, QTextCursor, QTextDocument, QTextDocumentFragment
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickTextDocument
from PySide6.QtWidgets import QApplication
from markdown.document import BodyStyle, render_markdown

MD = """## 标题一

普通段落，含 `inline code` 与 [链接](https://example.com)。

> 引用一行

- 项目一
- 项目二

1. 有序一
2. 有序二

```python
def handler(payload):
    return [x * 2 for x in payload]
```

| 名称 | 数值 |
|---|---|
| alpha | 1 |
| beta | 2 |

---

![图](/tmp/does-not-exist.png)

结尾段落。
"""

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
    TextEdit { id: te; width: 696; readOnly: true; wrapMode: TextEdit.Wrap
      textFormat: TextEdit.RichText
      Component.onCompleted: sink.attach(textDocument) } } }''')
engine.rootObjects()[0]
app.processEvents()
style = BodyStyle()

def stats(doc):
    frames = []
    fr = doc.rootFrame()
    for f in fr.childFrames():
        frames.append({"pos": f.firstPosition(), "tables": len(list(f.childFrames()))})
    tables = 0
    blk = doc.begin()
    while blk.isValid():
        if blk.textFormats() and any(True for _ in blk.textFormats()):
            pass
        blk = blk.next()
    return {"chars": doc.characterCount(), "blocks": doc.blockCount(),
            "html_len": len(doc.toHtml()), "child_frames": len(list(fr.childFrames()))}

def count_tables(doc):
    n = 0
    stack = list(doc.rootFrame().childFrames())
    while stack:
        f = stack.pop()
        if f.frameFormat().objectIndex() >= 0 or hasattr(f, "toTable"):
            pass
        for c in f.childFrames():
            stack.append(c)
    # 用光标扫描
    cur = QTextCursor(doc)
    cur.movePosition(QTextCursor.Start)
    while True:
        cur.movePosition(QTextCursor.NextBlock)
        if cur.isNull() or cur.atEnd():
            break
    tb = doc.begin()
    while tb.isValid():
        for tf in tb.textFormats():
            pass
        tb = tb.next()
    return n

# A: 直接渲染进 QML 文档
qd = sink.doc.textDocument()
render_markdown(qd, MD, style, content_width=676.0)
a_stats = stats(qd)
a_html = qd.toHtml()

# B: scratch 渲染 + insertFragment
scratch = QTextDocument(); scratch.setTextWidth(696.0)
render_markdown(scratch, MD, style, content_width=676.0)
b_stats = stats(scratch)
qd2 = sink.doc.textDocument()
cur = QTextCursor(qd2)
cur.beginEditBlock(); cur.select(QTextCursor.Document); cur.removeSelectedText()
cur.insertFragment(QTextDocumentFragment(scratch)); cur.endEditBlock()
b_in_doc = stats(qd2)
b_html = qd2.toHtml()

# C: scratch 渲染 + insertHtml
qd3 = sink.doc.textDocument()
html = scratch.toHtml()
cur = QTextCursor(qd3)
cur.beginEditBlock(); cur.select(QTextCursor.Document); cur.removeSelectedText()
cur.insertHtml(html); cur.endEditBlock()
c_in_doc = stats(qd3)
c_html = qd3.toHtml()

def norm(h):
    import re
    h = re.sub(r"<head>.*?</head>", "", h, flags=re.S)
    return re.sub(r"\s+", " ", h).strip()

print(json.dumps({
    "A_direct_in_qml": a_stats,
    "B_scratch": b_stats, "B_after_fragment": b_in_doc,
    "C_after_html": c_in_doc,
    "B_html_equals_A": norm(b_html) == norm(a_html),
    "C_html_equals_A": norm(c_html) == norm(a_html),
    "frame_format_objectindex": [f.frameFormat().objectIndex() for f in qd.rootFrame().childFrames()],
}, ensure_ascii=False, indent=2))
