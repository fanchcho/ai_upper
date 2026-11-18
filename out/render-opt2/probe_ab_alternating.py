"""同进程交替 A/B：旧表格实现 vs 新表格实现，交替渲染同一份 400 轮正文。

交替进行以抵消热漂移；各取 7 次，报中位数/最小/最大。只测渲染器本身的整篇路径
（``_Renderer.render_blocks``），因为这是表格改动唯一作用的位置。
"""
import json, os, statistics, sys, time
ROOT = "/home/agent/shared_workspace/ai_upper"
sys.path.insert(0, ROOT + "/app/src")
sys.path.insert(0, ROOT + "/out/render-opt2")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import QApplication

from markdown import document as mdoc
from markdown.document import BodyStyle
import probe_old_table
from probe_table_fast import make_md

app = QApplication.instance() or QApplication([])
style = BodyStyle()
md = make_md(400)
blocks = mdoc.parse_markdown(md)

new_table = mdoc._Renderer._table
new_row = mdoc._Renderer._table_row
probe_old_table.apply(mdoc, "HEAD")
old_table = mdoc._Renderer._table
old_row = mdoc._Renderer._table_row


def render():
    doc = QTextDocument()
    doc.setDocumentMargin(0)
    t = time.perf_counter()
    mdoc._Renderer(doc, style, 676.0, None).render_blocks(blocks, QTextCursor(doc))
    mdoc._collapse_edge_margins(doc)
    return (time.perf_counter() - t) * 1000.0


def use_old():
    mdoc._Renderer._table = old_table
    mdoc._Renderer._table_row = old_row


def use_new():
    mdoc._Renderer._table = new_table
    mdoc._Renderer._table_row = new_row


values = {"old": [], "new": []}
for i in range(7):
    for tag, setter in (("old", use_old), ("new", use_new)) if i % 2 == 0 else (("new", use_new), ("old", use_old)):
        setter()
        values[tag].append(render())


def stats(v):
    return {"median": round(statistics.median(v), 1), "min": round(min(v), 1),
            "max": round(max(v), 1), "all": [round(x, 1) for x in v]}


print("AB " + json.dumps({"old": stats(values["old"]), "new": stats(values["new"]),
                          "delta_median": round(statistics.median(values["old"]) - statistics.median(values["new"]), 1),
                          "delta_pct": round((statistics.median(values["old"]) - statistics.median(values["new"])) / statistics.median(values["old"]) * 100, 1)}, ensure_ascii=False))
