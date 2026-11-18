"""-qt-user-state 的唯一差异是否影响可见排版：对照块高、行高、字体、颜色。"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
ROOT = Path("/home/agent/shared_workspace/ai_upper")
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QApplication
from markdown.body import BodyDocument
from markdown.document import BodyStyle, render_markdown

MD = """# 标题

段落 **粗体** *斜体* `codespan`

- 列表一
- 列表二

```python
def handler(payload):
    return [x * 2 for x in payload]
```

| a | b |
|---|---|
| 1 | 2 |

> 引用
"""

app = QApplication.instance() or QApplication([])
style = BodyStyle()


class Stub:
    def __init__(self):
        self.document = QTextDocument()

    def textDocument(self):
        return self.document


def rows(doc):
    out = []
    b = doc.begin()
    while b.isValid():
        out.append({
            "text": b.text(),
            "block_h": round(doc.documentLayout().blockBoundingRect(b).height(), 2),
            "layout_h": round(b.layout().boundingRect().height(), 2) if b.layout() else None,
            "line_h": round(b.layout().lineAt(0).height(), 2) if b.layout() and b.layout().lineCount() else None,
            "formats": [(f.start, f.length,
                         f.format.font().family(), f.format.font().pixelSize(),
                         f.format.fontWeight(), f.format.fontItalic(),
                         f.format.foreground().color().name() if f.format.foreground().style() else None)
                        for f in b.textFormats()],
        })
        b = b.next()
    return out


# A 直接渲染
a = QTextDocument()
render_markdown(a, MD, style, content_width=676.0)
a.setTextWidth(696.0)
a.documentLayout()
app.processEvents()

# B 自有文档 + fragment
body = BodyDocument(style, content_width=676.0)
stub = Stub()
body.set_markdown(MD)
body.attach(stub)
b_doc = stub.document
b_doc.setTextWidth(696.0)
b_doc.documentLayout()
app.processEvents()

ra, rb = rows(a), rows(b_doc)
same = ra == rb
print(json.dumps({"same_geometry_and_chars": same,
                  "n_blocks": [len(ra), len(rb)],
                  "first_diff": next(({"direct": x, "fragment": y} for x, y in zip(ra, rb) if x != y), None),
                  "doc_size": [[round(a.size().width(), 1), round(a.size().height(), 1)],
                               [round(b_doc.size().width(), 1), round(b_doc.size().height(), 1)]]},
                 ensure_ascii=False, indent=1))

print(json.dumps({
    "a_margin": a.documentMargin(), "b_margin": b_doc.documentMargin(),
    "a_root_margins": [a.rootFrame().frameFormat().topMargin(), a.rootFrame().frameFormat().bottomMargin(),
                       a.rootFrame().frameFormat().leftMargin(), a.rootFrame().frameFormat().rightMargin()],
    "b_root_margins": [b_doc.rootFrame().frameFormat().topMargin(), b_doc.rootFrame().frameFormat().bottomMargin(),
                       b_doc.rootFrame().frameFormat().leftMargin(), b_doc.rootFrame().frameFormat().rightMargin()],
    "a_last_block_pos": a.lastBlock().position(), "b_last_block_pos": b_doc.lastBlock().position(),
    "a_blocks": a.blockCount(), "b_blocks": b_doc.blockCount(),
}, ensure_ascii=False, indent=1))
