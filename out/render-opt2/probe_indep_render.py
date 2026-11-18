"""独立进程整篇渲染计时：每次进程只跑一种实现，3 次取最小。"""
import json, os, sys, time
ROOT = "/home/agent/shared_workspace/ai_upper"
sys.path.insert(0, ROOT + "/app/src")
sys.path.insert(0, ROOT + "/out/render-opt2")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import QApplication
from markdown import document as mdoc
from markdown.document import BodyStyle
from probe_table_fast import make_md
mode = sys.argv[1]
if mode == "old":
    import probe_old_table
    probe_old_table.apply(mdoc, "HEAD")
app = QApplication.instance() or QApplication([])
style = BodyStyle()
blocks = mdoc.parse_markdown(make_md(400))
best = None
for _ in range(3):
    doc = QTextDocument(); doc.setDocumentMargin(0)
    t = time.perf_counter()
    mdoc._Renderer(doc, style, 676.0, None).render_blocks(blocks, QTextCursor(doc))
    mdoc._collapse_edge_margins(doc)
    dt = (time.perf_counter() - t) * 1000.0
    best = dt if best is None else min(best, dt)
print(json.dumps({mode: round(best, 1)}))
