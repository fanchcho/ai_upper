"""干净场景：目标文档无任何先验资源时，fragment 搬运后图片资源是否还在。"""
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

MD = "![img](my://pic)\n\n普通段落\n"

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
style = BodyStyle()

img = QImage(12, 9, QImage.Format.Format_RGB32); img.fill(0xFF00FF00)
def resolver(src):
    return img if src.startswith("my://") else None
name = "md-image:%d" % id(img)

def res_ok(doc):
    r = doc.resource(QTextDocument.ResourceType.ImageResource.value, QUrl(name))
    return {"is_none": r is None, "is_null": (r is not None and r.isNull()),
            "size": None if r is None else [r.width(), r.height()]}

# 本次新建的 QML 文档：没被任何渲染污染过
qd_fresh = QTextDocument(); qd_fresh.setTextWidth(696.0)
scratch = QTextDocument(); scratch.setTextWidth(696.0)
render_markdown(scratch, MD, style, content_width=676.0, image_resolver=resolver)
scratch_res = res_ok(scratch)

cur = QTextCursor(qd_fresh); cur.beginEditBlock()
cur.select(QTextCursor.Document); cur.removeSelectedText()
cur.insertFragment(QTextDocumentFragment(scratch)); cur.endEditBlock()
copied_res = res_ok(qd_fresh)

# 补救：把 scratch 的资源显式搬到目标文档
qd_fixed = QTextDocument(); qd_fixed.setTextWidth(696.0)
cur = QTextCursor(qd_fixed); cur.beginEditBlock()
cur.select(QTextCursor.Document); cur.removeSelectedText()
cur.insertFragment(QTextDocumentFragment(scratch)); cur.endEditBlock()
qd_fixed.addResource(QTextDocument.ResourceType.ImageResource.value, QUrl(name), img)
fixed_res = res_ok(qd_fixed)

print(json.dumps({"scratch": scratch_res, "fragment_only": copied_res,
                  "after_explicit_addResource": fixed_res,
                  "html_has_img": "<img" in qd_fixed.toHtml()},
                 ensure_ascii=False, indent=2))
