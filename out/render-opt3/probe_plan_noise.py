"""同一配置重复渲染的抖动：给 ``probe_plan_check`` 的绝对容差找依据。

判据检查里小文档上 1~2 ms 的差距会决定「换一档分组更快」，但同一份正文、同一套
代码重复渲染本身就有这个量级的抖动。这里把每份小/中文档连做 6 次，报 min/median/max
与极差；极差的中位数就是绝对容差的下限。
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle, parse_markdown, render_markdown  # noqa: E402
from probe_group_calib import CASES as CALIB_CASES  # noqa: E402
from probe_group_sweep import mixed_md, struct_md  # noqa: E402

REPEATS = 6
FIXTURES = (
    ("d43_t30", CALIB_CASES["d43"](30)),
    ("mixed_t30", mixed_md(30)),
    ("struct_t30", struct_md(30)),
    ("mixed_t120", mixed_md(120)),
)


def main():
    QApplication.instance() or QApplication([])
    style = BodyStyle()
    out = {}
    for name, md in FIXTURES:
        blocks = parse_markdown(md)
        plan = mdoc._chunk_plan(blocks)
        values = []
        for _ in range(REPEATS):
            start = time.perf_counter()
            render_markdown(QTextDocument(), md, style, 676.0, None)
            values.append((time.perf_counter() - start) * 1000.0)
        spread = max(values) - min(values)
        out[name] = {"blocks": len(blocks), "plan": plan,
                     "min": round(min(values), 1),
                     "median": round(statistics.median(values), 1),
                     "max": round(max(values), 1),
                     "spread": round(spread, 2),
                     "all": [round(v, 1) for v in values]}
        print("%-12s N=%-5d plan=%-3s min=%-7.1f med=%-7.1f max=%-7.1f spread=%.2f ms"
              % (name, len(blocks), plan or "whole", min(values),
                 statistics.median(values), max(values), spread), flush=True)
    print("NOISE " + json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
