"""fragment 搬运会把根框边距设成 4（QTextDocumentFragment 的默认），可见上边距多 4px。"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
ROOT = Path("/home/agent/shared_workspace/ai_upper")
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QTextCursor, QTextDocument, QTextDocumentFragment
from PySide6.QtWidgets import QApplication
from markdown.body import BodyDocument
from markdown.document import BodyStyle, render_markdown

MD = "段落一\n\n段落二\n"
app = QApplication.instance() or QApplication([])
style = BodyStyle()

class Stub:
    def __init__(self):
        self.document = QTextDocument()
    def textDocument(self):
        return self.document

body = BodyDocument(style, content_width=676.0)
body.set_markdown(MD)
stub = Stub()
print("before attach target margins:", stub.document.rootFrame().frameFormat().leftMargin(),
      stub.document.documentMargin())
body.attach(stub)
fm = stub.document.rootFrame().frameFormat()
print(json.dumps({"after_attach": {"left": fm.leftMargin(), "top": fm.topMargin(),
                                   "right": fm.rightMargin(), "bottom": fm.bottomMargin()},
                  "document_margin": stub.document.documentMargin()}, ensure_ascii=False))

# 还原成 0 后再看
fm.setLeftMargin(0); fm.setTopMargin(0); fm.setRightMargin(0); fm.setBottomMargin(0)
stub.document.rootFrame().setFrameFormat(fm)
stub.document.setTextWidth(696.0); stub.document.documentLayout()
fm2 = stub.document.rootFrame().frameFormat()
print(json.dumps({"after_reset": {"left": fm2.leftMargin(), "top": fm2.topMargin()},
                  "doc_size": [round(stub.document.size().width(),1), round(stub.document.size().height(),1)]},
                 ensure_ascii=False))

a = QTextDocument(); render_markdown(a, MD, style, content_width=676.0)
a.setTextWidth(696.0); a.documentLayout()
print(json.dumps({"direct_doc_size": [round(a.size().width(),1), round(a.size().height(),1)],
                  "direct_margins": [a.rootFrame().frameFormat().leftMargin(), a.rootFrame().frameFormat().topMargin()]},
                 ensure_ascii=False))
