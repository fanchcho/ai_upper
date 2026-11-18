"""拆开一次 _render：set_markdown(自文档) / attach(QML 文档) / rehighlight 各占多少。"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(ROOT / "out" / "conversation-picker-lag"))

from utils.qt_compat import QtCore, QtGui
app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])

import markdown.body as bodymod
from markdown.body import BodyDocument
from markdown.document import render_markdown
from markdown.parser import parse_markdown

def make_md(turns: int) -> str:
    out = []
    for i in range(turns):
        out.append(f"## Turn {i}\n\nSome prose about step {i} with `inline code` and a [link](https://x/{i}).\n\n```python\ndef f{i}(x):\n    return x + {i}\n```\n\n| a | b |\n|---|---|\n| {i} | {i*2} |\n")
    return "\n".join(out)

def timed(fn):
    t = time.perf_counter(); v = fn(); return (time.perf_counter() - t) * 1000, v

res = []
for turns in (40, 100, 400):
    md = make_md(turns)
    body = BodyDocument()
    # 1. set_markdown 到自己的文档（含 highlighter.rehighlight）
    set_ms, _ = timed(lambda: body.set_markdown(md))
    # 2. 再 attach 到一份 QML 文档（含第二次 render + 第二次 rehighlight）
    quick = QtGui.QTextDocument()
    class FakeQuick:
        def textDocument(self): return quick
    attach_ms, _ = timed(lambda: body.attach(FakeQuick()))
    # 3. 纯 render_markdown（无 highlighter）
    plain = QtGui.QTextDocument()
    render_ms, _ = timed(lambda: render_markdown(plain, md, body.style))
    # 4. 只 parse
    parse_ms, _ = timed(lambda: parse_markdown(md))
    # 5. 只 rehighlight 一次
    rh_ms, _ = timed(lambda: body.highlighter.rehighlight()) if body.highlighter else (0, None)
    res.append({"turns": turns, "chars": len(md), "set_markdown_ms": round(set_ms, 1),
                "attach_ms": round(attach_ms, 1), "render_markdown_only_ms": round(render_ms, 1),
                "parse_ms": round(parse_ms, 1), "rehighlight_alone_ms": round(rh_ms, 1),
                "attach_render_share": round(render_ms / attach_ms * 100, 1) if attach_ms else None})
print(json.dumps(res, ensure_ascii=False, indent=2))
