"""假设：QSyntaxHighlighter 挂在目标文档上时，渲染期间的每次插入都会触发重高亮。

对比 A（文档无高亮器）/ B（高亮器已挂在该文档上）/ C（渲染时临时摘掉高亮器，最后统一 rehighlight）。
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QGuiApplication, QTextDocument
from markdown.document import BodyStyle, render_markdown
from markdown.highlight import CodeHighlighter

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
for turns in (50, 100, 200, 400):
    md = make_md(turns)
    # A: 无高亮器
    da = QTextDocument(); t = time.perf_counter()
    render_markdown(da, md, style, content_width=676.0); a = (time.perf_counter()-t)*1000
    # B: 高亮器挂在目标文档上
    db = QTextDocument(); hl = CodeHighlighter(db, style); t = time.perf_counter()
    render_markdown(db, md, style, content_width=676.0); b = (time.perf_counter()-t)*1000
    hl.rehighlight(); b_total = (time.perf_counter()-t)*1000
    # C: 渲染前把高亮器摘到一次性空文档（脱离目标），渲染完再挂回并 rehighlight 一次
    dc = QTextDocument(); hl2 = CodeHighlighter(dc, style)
    hl2.setDocument(QTextDocument())     # 摘掉
    t = time.perf_counter()
    render_markdown(dc, md, style, content_width=676.0)
    hl2.setDocument(dc); hl2.rehighlight()
    c = (time.perf_counter()-t)*1000
    rows.append({"turns": turns, "chars": len(md), "no_highlighter_ms": round(a,1),
                 "highlighter_attached_ms": round(b,1),
                 "highlighter_after_rehighlight_ms": round(b_total,1),
                 "detach_during_render_ms": round(c,1)})
    print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
