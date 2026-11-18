"""M3 方案保真度：高亮格式、表格、图片、HTML 等价。"""
from __future__ import annotations
import json, os, re, sys, time
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

MD = """## 标题

段落含 `inline` 与 [链接](https://e.com)。

```python
if x: pass
def f(): return 1
```

| a | b |
|---|---|
| 1 | 2 |

![pic](my://pic)

> 引用

1. 有序
- 无序

---
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
img = QImage(8, 6, QImage.Format.Format_RGB32); img.fill(0xFF00FF00)
def resolver(src): return img if src.startswith("my://") else None

def fmt_of(doc, text):
    b = doc.begin()
    while b.isValid() and b.text() != text: b = b.next()
    if not b.isValid() or b.layout() is None: return None
    return {text[f.start:f.start+f.length]: f.format.foreground().color().name()
            for f in b.layout().formats()}

def norm(h):
    h = re.sub(r"<head>.*?</head>", "", h, flags=re.S)
    return re.sub(r"\s+", " ", h).strip()

# 参照：直接渲染
ref = QTextDocument(); ref.setTextWidth(696.0)
render_markdown(ref, MD, style, content_width=676.0, image_resolver=resolver)
hlr = CodeHighlighter(ref, style); hlr.rehighlight(); ref.documentLayout()
ref_fmt = fmt_of(ref, "if x: pass")

# M3
scratch = QTextDocument(); scratch.setTextWidth(696.0)
render_markdown(scratch, MD, style, content_width=676.0, image_resolver=resolver)
hls = CodeHighlighter(scratch, style); hls.rehighlight(); scratch.documentLayout()

cur = QTextCursor(qd); cur.beginEditBlock()
cur.select(QTextCursor.Document); cur.removeSelectedText()
cur.insertFragment(QTextDocumentFragment(scratch)); cur.endEditBlock()
moved = 0
sb, tb = scratch.begin(), qd.begin()
while sb.isValid() and tb.isValid():
    slay = sb.layout()
    if slay is not None and slay.formats():
        tlay = tb.layout()
        if tlay is not None:
            tlay.setFormats(list(slay.formats())); moved += 1
    sb, tb = sb.next(), tb.next()
# 图片资源
for b in [scratch]:
    pass
name = "md-image:%d" % id(img)
qd.addResource(QTextDocument.ResourceType.ImageResource.value, QUrl(name), img)
qd.documentLayout()
m3_fmt = fmt_of(qd, "if x: pass")

def _diff(a, b):
    import difflib
    sm = difflib.SequenceMatcher(None, a, b)
    return [{"op": op, "a": a[i1:i2][:200], "b": b[j1:j2][:200]}
            for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"][:8]

print(json.dumps({
    "ref_fmt": ref_fmt, "m3_fmt": m3_fmt, "highlight_equal": ref_fmt == m3_fmt,
    "blocks_with_formats_moved": moved,
    "html_equal": norm(ref.toHtml()) == norm(qd.toHtml()),
    "tables": qd.toHtml().count("<table"),
    "img_ok": not qd.resource(QTextDocument.ResourceType.ImageResource.value, QUrl(name)).isNull(),
    "ref_chars": ref.characterCount(), "m3_chars": qd.characterCount(),
    "html_diff": _diff(norm(ref.toHtml()), norm(qd.toHtml())),
}, ensure_ascii=False, indent=2))
