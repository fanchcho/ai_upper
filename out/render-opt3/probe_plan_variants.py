"""用 ``probe_plan_check.py`` 已测出的逐档耗时表，扫一遍判据常量组合。

调常量不该每次重跑渲染：同一张实测表可以离线评估任意 ``(floor, pressure,
dense_density, dense_group, mid_group)`` 组合，比较「相对最优的损失」。

用法：``python probe_plan_variants.py out/render-opt3/plan_check.log``
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path


def load(path):
    for line in Path(path).read_text().splitlines():
        if line.startswith("PLANCHECK "):
            return json.loads(line[len("PLANCHECK "):])
    raise SystemExit("no PLANCHECK line in " + str(path))


def evaluate(rows, floor, pressure, dense_density, dense_group, mid_group):
    losses, failures = [], []
    for name, row in rows.items():
        density = row["density"]
        if row["blocks"] <= 50 or density < floor or row["load_x_blocks"] < pressure:
            plan = 0
        elif density >= dense_density:
            plan = dense_group
        else:
            plan = mid_group
        chosen = row["ms"][str(plan)]
        best = row["best_ms"]
        loss = (chosen - best) / best * 100.0
        losses.append(loss)
        if loss > 2.0 and (chosen - best) > 2.0:
            failures.append((name, round(loss, 1)))
    return {
        "worst": round(max(losses), 1),
        "mean": round(sum(losses) / len(losses), 2),
        "failures": failures,
        "plans": None,
    }


def main():
    data = load(sys.argv[1] if len(sys.argv) > 1 else "out/render-opt3/plan_check.log")
    rows = data["rows"]
    grid = []
    for dense_density in (0.30, 0.35, 0.40, 0.45, 0.50):
        for dense_group in (12, 16, 24, 32):
            for mid_group in (24, 32, 50):
                if mid_group <= dense_group:
                    continue
                result = evaluate(rows, 0.15, 45000, dense_density, dense_group, mid_group)
                grid.append((result["worst"], len(result["failures"]), result["mean"],
                             dense_density, dense_group, mid_group, result["failures"]))
    grid.sort(key=lambda item: (item[0], item[1], item[2]))
    print("%-6s %-6s %-4s %-8s %-8s %s" % ("worst", "fails", "mean", "dense_d", "g_dense", "g_mid"))
    for worst, nfail, mean, dense_density, dense_group, mid_group, failures in grid[:15]:
        print("%+6.1f %-6d %+6.2f %-8.2f %-8d %-5d %s"
              % (worst, nfail, mean, dense_density, dense_group, mid_group,
                 failures if failures else ""))
    # 当前的常量
    current = evaluate(rows, 0.15, 45000, 0.30, 16, 50)
    print("\ncurrent (0.15 / 45000 / 0.30 / 16 / 50): worst=%+.1f%% mean=%+.2f%% failures=%s"
          % (current["worst"], current["mean"], current["failures"]))
    print("VARIANTS " + json.dumps(
        [{"worst": w, "failures": f, "mean": m, "dense_density": dd,
          "dense_group": dg, "mid_group": mg}
         for w, _, m, dd, dg, mg, f in grid], ensure_ascii=False))


if __name__ == "__main__":
    main()
