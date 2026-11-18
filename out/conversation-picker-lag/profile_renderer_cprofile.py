"""cProfile 裸文档渲染 400 轮真实正文，找超线性来源。"""
from __future__ import annotations
import cProfile, io, json, os, pstats, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QGuiApplication, QTextDocument
from markdown.document import BodyStyle, render_markdown

CODE = "```python\ndef handler(payload):\n    items = payload.get('items') or []\n    return [x * 2 for x in items]\n```"
TABLE = "| 名称 | 数值 |\n|---|---|\n| alpha | 1 |\n| beta | 2 |"

def make_md(turns):
    out = []
    for i in range(turns):
        out.append("第 %d 轮的提问：请把这一轮的结果整理成表格并给出要点。" % i)
        out.append("这是第 %d 轮回复。\n\n%s\n\n要点：\n\n1. 先读 README\n2. 再看依赖\n\n%s" % (i, CODE, TABLE))
    return "\n\n".join(out)

app = QGuiApplication.instance() or QGuiApplication([])
md = make_md(400)
d = QTextDocument()
pr = cProfile.Profile(); pr.enable()
render_markdown(d, md, BodyStyle(), content_width=676.0)
pr.disable()
s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats("tottime").print_stats(20)
print(s.getvalue())
