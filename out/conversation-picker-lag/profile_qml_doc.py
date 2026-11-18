"""对比：裸 QTextDocument / 设了 textWidth 的文档 / 真实 QQuickTextEdit 文档上渲染同一份正文。"""
from __future__ import annotations
import json, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication, QTextDocument
from PySide6.QtQml import QQmlApplicationEngine
from markdown.document import BodyStyle, render_markdown

def make_md(turns):
    out = []
    for i in range(turns):
        out.append("第 %d 轮的提问：请把这一轮的结果整理成表格并给出要点。" % i)
        out.append("这是第 %d 轮回复。\n\n```python\ndef f%d(x):\n    return x + %d\n```\n\n要点：\n\n1. 先读 README\n2. 再看依赖\n\n| a | b |\n|---|---|\n| %d | %d |\n" % (i, i, i, i, i*2))
    return "\n\n".join(out)

app = QGuiApplication.instance() or QGuiApplication([])
style = BodyStyle()
rows = []
for turns in (40, 100, 200, 400):
    md = make_md(turns)
    # A: 裸文档
    d1 = QTextDocument(); t = time.perf_counter()
    render_markdown(d1, md, style, content_width=676.0); a = (time.perf_counter()-t)*1000
    # B: 设了 textWidth 的文档
    d2 = QTextDocument(); d2.setTextWidth(696.0); t = time.perf_counter()
    render_markdown(d2, md, style, content_width=676.0); b = (time.perf_counter()-t)*1000
    # C: 强制布局（模拟 QQuickTextEdit 的可见文档）
    d3 = QTextDocument(); d3.setTextWidth(696.0)
    t = time.perf_counter(); render_markdown(d3, md, style, content_width=676.0); c0 = time.perf_counter()-t
    d3.documentLayout(); c = (time.perf_counter()-t)*1000
    rows.append({"turns": turns, "chars": len(md), "bare_ms": round(a,1),
                 "textwidth_ms": round(b,1), "textwidth_layout_ms": round(c,1)})
    print(json.dumps(rows[-1]), flush=True)
print(json.dumps(rows, ensure_ascii=False))
