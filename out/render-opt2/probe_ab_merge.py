"""交替 A/B：只改行数（once_insert）vs 再把边框并进同一次 setFormat（landed），400 轮。"""
import json, os, statistics, sys, time
ROOT = "/home/agent/shared_workspace/ai_upper"
sys.path.insert(0, ROOT + "/app/src"); sys.path.insert(0, ROOT + "/out/render-opt2")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import QApplication
from markdown import document as mdoc
from markdown.document import BodyStyle
import probe_old_table
from probe_table_fast import make_md

app = QApplication.instance() or QApplication([])
style = BodyStyle(); blocks = mdoc.parse_markdown(make_md(400))

landed_table, landed_row = mdoc._Renderer._table, mdoc._Renderer._table_row
probe_old_table.apply(mdoc, "HEAD")
old_table, old_row, old_borders = mdoc._Renderer._table, mdoc._Renderer._table_row, mdoc._Renderer._apply_cell_borders

def once_insert(self, cursor, block):
    header = block.get("header") or []
    rows = block.get("rows") or []
    if not header: return
    align = list(block.get("align") or ["left"] * len(header))
    if self._has_content: cursor.insertBlock()
    tf = mdoc.QTextTableFormat(); tf.setBorder(1.0)
    tf.setBorderBrush(mdoc.QtGui.QBrush(self.color(self.palette.border)))
    tf.setCellSpacing(0.0); tf.setCellPadding(0.0); tf.setBorderCollapse(True)
    tf.setMargin(12.0); tf.setAlignment(mdoc.ALIGN_LEFT)
    t = cursor.insertTable(1 + len(rows), len(header), tf)
    self._table_row(t, 0, header, align, header_row=True)
    for i, row in enumerate(rows, start=1):
        self._table_row(t, i, row, align, header_row=False)
    old_borders.__get__(self)(t)
    self._after_frame(cursor, t.lastPosition() + 1)

def use_once():
    mdoc._Renderer._table = once_insert; mdoc._Renderer._table_row = old_row
    mdoc._Renderer._apply_cell_borders = old_borders
def use_landed():
    mdoc._Renderer._table = landed_table; mdoc._Renderer._table_row = landed_row
    if hasattr(mdoc._Renderer, "_apply_cell_borders"): del mdoc._Renderer._apply_cell_borders

def render():
    doc = QTextDocument(); doc.setDocumentMargin(0)
    t = time.perf_counter()
    mdoc._Renderer(doc, style, 676.0, None).render_blocks(blocks, QTextCursor(doc))
    mdoc._collapse_edge_margins(doc)
    return (time.perf_counter() - t) * 1000.0

v = {"once": [], "landed": []}
for i in range(7):
    pair = (("once", use_once), ("landed", use_landed)) if i % 2 == 0 else (("landed", use_landed), ("once", use_once))
    for tag, setter in pair:
        setter(); v[tag].append(render())
s = lambda xs: {"median": round(statistics.median(xs),1), "min": round(min(xs),1), "max": round(max(xs),1), "all": [round(x,1) for x in xs]}
print(json.dumps({"once_insert": s(v["once"]), "landed": s(v["landed"]),
                  "delta_median": round(statistics.median(v["once"]) - statistics.median(v["landed"]), 1)}, ensure_ascii=False))
