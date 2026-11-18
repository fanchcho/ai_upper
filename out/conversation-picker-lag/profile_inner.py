"""cProfile render_markdown：找出超线性来源；并按块类型分别计时。"""
from __future__ import annotations
import cProfile, io, json, pstats, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
from utils.qt_compat import QtGui
app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
from markdown.document import BodyStyle, render_markdown

def para_md(n):   return "\n".join(f"Paragraph {i} with some ordinary prose text that wraps a little." for i in range(n))
def code_md(n):   return "\n\n".join(f"```python\ndef f{i}(x):\n    return x + {i}\n```" for i in range(n))
def table_md(n):  return "\n\n".join(f"| a | b |\n|---|---|\n| {i} | {i*2} |" for i in range(n))
def quote_md(n):  return "\n\n".join(f"> quote line {i} with text" for i in range(n))
def head_md(n):   return "\n\n".join(f"## Heading {i}" for i in range(n))

def timed(md, style, width=676.0):
    doc = QtGui.QTextDocument()
    t = time.perf_counter(); render_markdown(doc, md, style, content_width=width); dt = (time.perf_counter()-t)*1000
    return dt, doc.characterCount()

style = BodyStyle()
rows = []
for name, fn in (("paragraph", para_md), ("code", code_md), ("table", table_md), ("quote", quote_md), ("heading", head_md)):
    for n in (50, 100, 200, 400):
        dt, cc = timed(fn(n), style)
        rows.append({"kind": name, "n": n, "ms": round(dt,1), "chars": cc})
        print(json.dumps(rows[-1]), flush=True)
print("--- cProfile 400 code blocks ---")
doc = QtGui.QTextDocument()
pr = cProfile.Profile(); pr.enable()
render_markdown(doc, code_md(400), style, content_width=676.0)
pr.disable()
s = io.StringIO(); pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(18)
print(s.getvalue())
