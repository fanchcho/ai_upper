"""同一份正文在不同规模下：裸 QTextDocument 渲染 vs 真实 QQuickTextEdit 文档渲染。"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QTextDocument
from PySide6.QtQml import QQmlApplicationEngine
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
style = BodyStyle()
rows = []
for turns in (200, 400, 800, 1200):
    md = make_md(turns)
    d = QTextDocument(); t = time.perf_counter()
    render_markdown(d, md, style, content_width=676.0); a = (time.perf_counter()-t)*1000
    rows.append({"turns": turns, "chars": len(md), "bare_ms": round(a,1)})
    print(json.dumps(rows[-1]), flush=True)
