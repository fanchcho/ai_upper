"""归因：自适应分组与热路径（缓存 + 表格逐格格式）各贡献多少（2×2 正交）。

四格都必须与「旧口径」逐字节一致（``toHtml()`` 相等），否则收益不成立。

- 分组：50（旧） / 当前判据（mixed_t400 与 struct_t400 密度 0.44 / 0.73，判据给 32）；
- 热路径：HEAD 实现（无缓存 + 逐格新建格式） / 当前源码。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont, QFontMetricsF, QGuiApplication, QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle, parse_markdown, render_markdown  # noqa: E402
from probe_old_opt3 import install_before, restore, snapshot  # noqa: E402
from probe_group_sweep import mixed_md, struct_md  # noqa: E402


def run(md_text, style, group, cached):
    """cached=True 用当前源码；False 用 HEAD 实现。group 覆盖两边的分块计划。"""
    before = snapshot()
    undo = (lambda: None) if cached else install_before()
    try:
        if group:
            mdoc._chunk_plan = lambda blocks: group
        start = time.perf_counter()
        doc = render_markdown(QTextDocument(), md_text, style, 676.0, None)
        took = (time.perf_counter() - start) * 1000.0
    finally:
        undo()
        restore(before)
    return took, doc


def main():
    QApplication.instance() or QApplication([])
    style = BodyStyle()
    out = {}
    # 六种配置在同一轮里交替跑：早先按配置分组连跑 3 次时，同一配置（gplan vs g32
    # 在 struct 上都是分组 32）两次被测出 768.9 / 805.9 ms，差 4.8%，漂移盖过了要
    # 测的分组差异。交替后每个配置每轮只出现一次，轮间取最小。
    configs = [(group, cached) for group in (0, 32, 50) for cached in (False, True)]
    for name, md in (("mixed_t400", mixed_md(400)), ("struct_t400", struct_md(400))):
        parse_markdown(md)
        rows = {}
        docs = {}
        best = {key: float("inf") for key in configs}
        for round_index in range(3):
            order = configs if round_index % 2 == 0 else list(reversed(configs))
            for key in order:
                group, cached = key
                took, doc = run(md, style, group, cached)
                best[key] = min(best[key], took)
                docs[key] = doc
        for (group, cached), took in best.items():
            rows["g%s_%s" % (group or "plan", "cache" if cached else "raw")] = round(took, 1)
        for doc in docs.values():
            doc.setTextWidth(696.0)
            doc.documentLayout()
        base = docs[(50, False)]
        rows["html_all_eq"] = all(d.toHtml() == base.toHtml() for d in docs.values())
        rows["height_all_eq"] = all(d.size().height() == base.size().height()
                                    for d in docs.values())
        out[name] = rows
        print(name, json.dumps(rows, ensure_ascii=False), flush=True)
    print("ATTRIB " + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
