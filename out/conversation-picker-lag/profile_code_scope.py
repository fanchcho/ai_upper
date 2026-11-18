"""高亮器是否已经会把非代码块跳过？统计 highlightBlock 调用次数与 setFormat 次数。"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QGuiApplication, QTextDocument
from markdown.document import BodyStyle, render_markdown
from markdown.highlight import CodeHighlighter, language_for

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
md = make_md(400)
doc = QTextDocument(); doc.setTextWidth(696.0)
render_markdown(doc, md, style, content_width=676.0)

class Counting(CodeHighlighter):
    calls = 0
    tagged = 0
    formats = 0
    def highlightBlock(self, text):
        Counting.calls += 1
        b = self.currentBlock()
        v = b.blockFormat().property(0x100001) if b.isValid() else None
        if isinstance(v, str) and v.strip():
            Counting.tagged += 1
        before = Counting.formats
        super().highlightBlock(text)
    def setFormat(self, start, length, fmt):
        Counting.formats += 1
        return super().setFormat(start, length, fmt)

hl = Counting(doc, style)
t = time.perf_counter(); hl.rehighlight(); dt = (time.perf_counter()-t)*1000
print(json.dumps({"blocks": doc.blockCount(), "highlightBlock_calls": Counting.calls,
                  "blocks_with_language": Counting.tagged,
                  "setFormat_calls": Counting.formats,
                  "ms": round(dt,1)}, ensure_ascii=False))
