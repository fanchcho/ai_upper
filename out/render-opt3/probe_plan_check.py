"""判据复核：把 ``_chunk_plan`` 的决定与逐档实测的最优值逐条对照。

对 ``group_calib`` / ``group_sweep`` / ``probe_quadratic`` 覆盖的每一份正文：

- 计划值（0=整篇，16/50=分组）；
- 该计划对应的实测耗时；
- 逐档扫描里的最优耗时；
- 相对最优的损失百分比。

判据合格的标准是「不亏」：选中的档与最优档的差距在测量噪声内（``TOLERANCE``
相对 + ``ABS_FLOOR`` 绝对双门槛）。绝对门槛来自同一份正文重复渲染的抖动
（见 ``out/render-opt3/plan_noise.log``）：小文档上 1~2 ms 的差距换一档分组
就会翻转，单看百分比会把噪声判成亏。

同一份实测表还会评估几套候选判据（``variants``），这样调整常量时不必重跑。
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

from PySide6.QtGui import QTextDocument  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from markdown import document as mdoc  # noqa: E402
from markdown.document import BodyStyle, parse_markdown, render_markdown  # noqa: E402
from probe_group_calib import CASES as CALIB_CASES, density_md  # noqa: E402
from probe_group_sweep import mixed_md, para_md, struct_md  # noqa: E402
from probe_quadratic import para_md as q_para_md, table_md as q_table_md  # noqa: E402

TOLERANCE = 0.02
ABS_FLOOR_MS = 2.0
CANDIDATES = (0, 8, 12, 16, 24, 32, 50)

# 判据交界附近的额外实测点（probe_dense_groups / probe_group_boundary 的同一套
# 造数函数），否则 0.31 与 0.44 之间只有外推。
EXTRA_CASES = {
    "b36": (lambda n: density_md(n, 3, 3, 3), (400, 1200, 2400)),
    "b40": (lambda n: density_md(n, 2, 2, 0), (400, 1200, 2400)),
    "d52": (lambda n: density_md(n, 1, 2, 2, 2), (400, 1200)),
    "d73": (lambda n: density_md(n, 1, 1, 1), (400, 1200)),
}


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


def cases():
    for name, build in CALIB_CASES.items():
        for turns in (30, 120, 400, 1200):
            yield "%s_t%d" % (name, turns), build(turns)
    for name, build in (("para", para_md), ("mixed", mixed_md), ("struct", struct_md)):
        for turns in (12, 30, 120, 400):
            yield "sweep_%s_t%d" % (name, turns), build(turns)
    for name, build in (("qpara", q_para_md), ("qtable", q_table_md)):
        for turns in (30, 120, 400, 1200, 2400):
            yield "%s_t%d" % (name, turns), build(turns)
    for name, (build, turn_list) in EXTRA_CASES.items():
        for turns in turn_list:
            yield "%s_t%d" % (name, turns), build(turns)


def rule(blocks, *, floor, pressure, dense_density, dense_group, mid_group):
    """候选判据：与 ``_chunk_plan`` 同形，只把常量参数化。"""
    count = len(blocks)
    if count <= mdoc._CHUNK_BLOCKS:
        return 0
    load = mdoc._structural_load(blocks)
    if load <= 0:
        return 0
    density = load / count
    if density < floor or load * count < pressure:
        return 0
    if density >= dense_density:
        return dense_group
    return mid_group


VARIANTS = {
    "current(32@.40/50)": dict(floor=0.15, pressure=45000, dense_density=0.40,
                               dense_group=32, mid_group=50),
    "old(16@.30/50)": dict(floor=0.15, pressure=45000, dense_density=0.30,
                           dense_group=16, mid_group=50),
    "24@.40/50": dict(floor=0.15, pressure=45000, dense_density=0.40,
                      dense_group=24, mid_group=50),
    "16@.40/50": dict(floor=0.15, pressure=45000, dense_density=0.40,
                      dense_group=16, mid_group=50),
    "32@.35/50": dict(floor=0.15, pressure=45000, dense_density=0.35,
                      dense_group=32, mid_group=50),
    "32@.45/50": dict(floor=0.15, pressure=45000, dense_density=0.45,
                      dense_group=32, mid_group=50),
}


def main():
    QApplication.instance() or QApplication([])
    style = BodyStyle()
    rows = {}
    failures = []
    for name, md in cases():
        blocks = parse_markdown(md)
        plan = mdoc._chunk_plan(blocks)
        load = mdoc._structural_load(blocks)
        times = {group: render(md, style, group) for group in CANDIDATES}
        best_group = min(CANDIDATES, key=lambda g: times[g])
        chosen = times[plan]
        best = times[best_group]
        loss = (chosen - best) / best
        bad = loss > TOLERANCE and (chosen - best) > ABS_FLOOR_MS
        rows[name] = {
            "blocks": len(blocks),
            "density": round(load / max(1, len(blocks)), 3),
            "load_x_blocks": round(load * len(blocks)),
            "plan": plan,
            "plan_ms": round(chosen, 1),
            "best_group": best_group,
            "best_ms": round(best, 1),
            "loss": round(loss * 100, 1),
            "ok": not bad,
            "ms": {str(g): round(times[g], 1) for g in CANDIDATES},
        }
        if bad:
            failures.append(name)
        print("%-16s N=%-5d d=%-5.2f plan=%-3s %-8.1f best=g%-3d %-8.1f loss=%+5.1f%% %s"
              % (name, len(blocks), rows[name]["density"], plan or "whole", chosen,
                 best_group, best, loss * 100, "FAIL" if bad else "ok"), flush=True)

    # 用同一张实测表评估候选判据，避免换常量就重跑带来的机器漂移。
    print("\n== variants (worst loss / mean loss / failures over %d fixtures) =="
          % len(rows), flush=True)
    variants = {}
    block_index = {}
    for name, md in cases():
        block_index[name] = parse_markdown(md)
    for label, params in VARIANTS.items():
        losses, failing = [], []
        for name, row in rows.items():
            plan = rule(block_index[name], **params)
            chosen = row["ms"][str(plan)]
            best = row["best_ms"]
            loss = (chosen - best) / best * 100.0
            losses.append(loss)
            if loss > TOLERANCE * 100 and (chosen - best) > ABS_FLOOR_MS:
                failing.append((name, round(loss, 1)))
        variants[label] = {
            "worst_loss": round(max(losses), 1),
            "mean_loss": round(sum(losses) / len(losses), 2),
            "failures": failing,
        }
        print("%-18s worst=%+5.1f%% mean=%+5.2f%% failures=%s"
              % (label, variants[label]["worst_loss"], variants[label]["mean_loss"],
                 failing or "none"), flush=True)

    print("PLANCHECK " + json.dumps(
        {"tolerance": TOLERANCE, "abs_floor_ms": ABS_FLOOR_MS, "rows": rows,
         "failures": failures, "variants": variants}, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
