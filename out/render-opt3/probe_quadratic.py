"""纯段落 vs 结构密集：整篇路径的规模指数，以及分块在什么规模上才「回本」。

两件事：

1. **纯段落没有二次成本**。同一份文档不断加段落，整篇路径耗时若 ∝ N，log-log
   斜率应 ≈ 1.0；每轮带一张表的文档斜率应 ≈ 2.0。这是自适应判据的前提。
2. **分块在临界点附近**。对同一份文档量「整篇」与「固定分组 16 / 50」，给出
   加速比随规模的变化，说明小文档分块不划算、从哪个规模开始划算。

渲染器口径（不含 Markdown 解析之外的壳层）：直接 ``render_markdown``，每组取 3 次
最小值，长/短规模分开列出，不做混合。
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle, parse_markdown, render_markdown  # noqa: E402

TABLE = """| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `README.md` | 文档 | 项目用途与运行方式 |
| `src/` | 目录 | 源代码 |"""


def para_md(turns):
    """纯段落：每轮两段，没有任何结构性插入。"""
    return "\n\n".join(
        "第 %d 轮提问：请把结果整理成要点。\n\n第 %d 轮回复：先读 README，再看依赖。" % (t, t)
        for t in range(turns)
    )


def table_md(turns):
    """每轮一张表：结构性插入的二次成本会主导。"""
    return "\n\n".join("第 %d 轮回复。\n\n%s" % (t, TABLE) for t in range(turns))


def render(md_text, style, group):
    saved = mdoc._chunk_plan
    mdoc._chunk_plan = lambda blocks: group
    try:
        best = float("inf")
        for _ in range(3):
            start = time.perf_counter()
            render_markdown(QTextDocument(), md_text, style, 676.0, None)
            best = min(best, (time.perf_counter() - start) * 1000.0)
        return best
    finally:
        mdoc._chunk_plan = saved


def slope(points):
    """log(ms) ~ k·log(N) 的最小二乘斜率。"""
    xs = [math.log(n) for n, _ in points]
    ys = [math.log(max(t, 1e-6)) for _, t in points]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den


def main():
    QApplication.instance() or QApplication([])
    style = BodyStyle()
    out = {}
    for name, build in (("para", para_md), ("table", table_md)):
        rows = {}
        points = []
        for turns in (12, 30, 120, 400, 1200, 2400):
            md = build(turns)
            count = len(parse_markdown(md))
            whole = render(md, style, 0)
            g16 = render(md, style, 16)
            g50 = render(md, style, 50)
            rows["t%d" % turns] = {
                "blocks": count,
                "whole_ms": round(whole, 1),
                "g16_ms": round(g16, 1),
                "g50_ms": round(g50, 1),
                "g16_speedup": round(whole / g16, 2),
                "g50_speedup": round(whole / g50, 2),
            }
            points.append((count, whole))
            print("%-6s turns=%-5d blocks=%-6d whole=%-9.1f g16=%-9.1f g50=%-9.1f "
                  "g16×%.2f g50×%.2f" % (name, turns, count, whole, g16, g50,
                                         whole / g16, whole / g50), flush=True)
        out[name] = {"rows": rows, "whole_exponent": round(slope(points), 3),
                     "ms_per_block": {k: round(v["whole_ms"] / v["blocks"], 4)
                                      for k, v in rows.items()}}
        print("%s whole-path exponent = %.3f" % (name, out[name]["whole_exponent"]),
              flush=True)
    print("QUADRATIC " + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
