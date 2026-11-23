"""Reproduce the bounded review using fresh QML shots and tracked deva references.

Usage: python3 out/retest-20261123/measure.py QML_DIRECTORY
Coordinates are half-open. Counts describe pixels, not semantic text lines.
"""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/parity"))
from pngread import read_png

PAGES = ("chat", "search-none", "long-mid", "long-bottom", "settings-general",
         "settings-models", "settings-extensions", "settings-about", "delete-confirm")


def bands(px, w, box, threshold=200):
    x0, y0, x1, y1 = box
    result = []
    for y in range(y0, y1):
        if sum(max(px[y*w+x]) < threshold for x in range(x0, x1)) <= 3:
            continue
        if result and result[-1][1] == y - 1:
            result[-1][1] = y
        else:
            result.append([y, y])
    return result


def hover(px, w):
    rows = [y for y in range(50, 810)
            if sum(px[y*w+x] == (236, 236, 237) for x in range(64, 339)) > 100]
    return {"rows": len(rows), "span": [rows[0], rows[-1]] if rows else None}


def measure(qml_dir):
    result = {}
    for page in PAGES:
        qpath = qml_dir / (page + ".png")
        dpath = ROOT / "out/latest-parity/deva" / (page + "-deva.png")
        w, h, q = read_png(str(qpath))
        dw, dh, d = read_png(str(dpath))
        assert (w, h) == (dw, dh) == (1280, 820)
        row = {"qml_sha256": hashlib.sha256(qpath.read_bytes()).hexdigest(),
               "deva_sha256": hashlib.sha256(dpath.read_bytes()).hexdigest()}
        panel = ((430, 317, 850, 503) if page == "delete-confirm"
                 else (280, 130, 1000, 690) if page.startswith("settings-") else None)
        totals = dict(total=0, d1_2=0, outside=0, outside_d1_2=0, inside=0, inside_gt8=0)
        for i, (a, b) in enumerate(zip(q, d)):
            delta = max(abs(x-y) for x, y in zip(a, b))
            if not delta:
                continue
            totals["total"] += 1
            totals["d1_2"] += delta <= 2
            if panel:
                x, y = i % w, i // w
                inside = panel[0] <= x < panel[2] and panel[1] <= y < panel[3]
                totals["inside" if inside else "outside"] += 1
                totals["inside_gt8"] += inside and delta > 8
                totals["outside_d1_2"] += not inside and delta <= 2
        row.update(totals)
        row["percent"] = round(totals["total"] * 100 / (w*h), 4)
        row["panel"] = panel
        row["qml_bands"] = bands(q, w, (430, 40, 1200, 640))
        row["deva_bands"] = bands(d, w, (430, 40, 1200, 640))
        row["qml_hover"] = hover(q, w)
        row["deva_hover"] = hover(d, w)
        row["samples"] = {f"{x},{y}": {"qml": q[y*w+x], "deva": d[y*w+x]}
                          for x, y in ((60, 120), (300, 700), (1100, 100))}
        result[page] = row
    return result


if __name__ == "__main__":
    print(json.dumps(measure(Path(sys.argv[1])), indent=2))
