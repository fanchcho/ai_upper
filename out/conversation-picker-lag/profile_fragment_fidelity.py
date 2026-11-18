"""fragment 搬运是否保留：高亮字符格式、图片资源、表格结构。"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QObject, QUrl, Slot
from PySide6.QtGui import (QGuiApplication, QImage, QTextCursor, QTextDocument,
                           QTextDocumentFragment)
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickTextDocument
from PySide6.QtWidgets import QApplication
from markdown.document import BodyStyle, render_markdown
from markdown.highlight import CodeHighlighter

MD = """```python
if x: pass
```

| a | b |
|---|---|
| 1 | 2 |

![img](my://pic)
"""

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
  TextEdit { id: te; width: 696; readOnly: true; wrapMode: TextEdit.Wrap
    textFormat: TextEdit.RichText
    Component.onCompleted: sink.attach(textDocument) } }''')
engine.rootObjects()[0]; app.processEvents()
qd = sink.doc.textDocument()
style = BodyStyle()

def find_block(doc, text):
    b = doc.begin()
    while b.isValid():
        if b.text() == text:
            return b
        b = b.next()
    return None

img = QImage(10, 10, QImage.Format.Format_RGB32); img.fill(0xFF00FF00)
def resolver(src):
    return img if src.startswith("my://") else None

# A: 直接渲染进 QML 文档（现状）
render_markdown(qd, MD, style, content_width=676.0, image_resolver=resolver)
hl = CodeHighlighter(qd, style); hl.rehighlight()
blk = find_block(qd, "if x: pass")
a_fmt = {blk.text()[f.start:f.start+f.length]: f.format.foreground().color().name()
         for f in blk.layout().formats()}
_res = qd.resource(QTextDocument.ResourceType.ImageResource.value,
                   QUrl("md-image:%d" % id(img)))
a_img = _res is None or _res.isNull()
a_frames = len(list(qd.rootFrame().childFrames()))

# B: scratch（高亮器挂在 scratch）-> fragment
scratch = QTextDocument(); scratch.setTextWidth(696.0)
render_markdown(scratch, MD, style, content_width=676.0, image_resolver=resolver)
hl2 = CodeHighlighter(scratch, style); hl2.rehighlight()
sblk = find_block(scratch, "if x: pass")
b_src_fmt = {sblk.text()[f.start:f.start+f.length]: f.format.foreground().color().name()
             for f in sblk.layout().formats()}

cur = QTextCursor(qd); cur.beginEditBlock()
cur.select(QTextCursor.Document); cur.removeSelectedText()
cur.insertFragment(QTextDocumentFragment(scratch)); cur.endEditBlock()
blk = find_block(qd, "if x: pass")
b_fmt = {blk.text()[f.start:f.start+f.length]: f.format.foreground().color().name()
         for f in blk.layout().formats()}
_res2 = qd.resource(QTextDocument.ResourceType.ImageResource.value,
                    QUrl("md-image:%d" % id(img)))
b_img_missing = _res2 is None or _res2.isNull()
# 检查图片块是否存在
b_img_present = "md-image" in qd.toHtml() or "<img" in qd.toHtml()
b_frames = len(list(qd.rootFrame().childFrames()))
b_tables = qd.toHtml().count("<table")

print(json.dumps({
    "A_direct": {"highlight": a_fmt, "has_table": a_frames, "img_missing": a_img},
    "B_scratch_fmt": b_src_fmt,
    "B_after_copy_fmt": b_fmt,
    "B_highlight_preserved": b_src_fmt == b_fmt,
    "B_table_count": b_tables,
    "B_img_present": b_img_present, "B_img_missing": b_img_missing,
    "B_chars": qd.characterCount(),
}, ensure_ascii=False, indent=2))
