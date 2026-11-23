#!/usr/bin/env python3
"""Read-only measurements for the still-open parity items.

No QML / deva files are modified. Values are measured from the checked-in
1280x820 screenshots under out/latest-parity/{qml,deva}.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("pngread", ROOT / "scripts/parity/pngread.py")
pngread = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(pngread)


def image_path(side: str, page: str) -> Path:
    if side == "qml":
        return ROOT / "out/latest-parity/qml" / f"{page}.png"
    return ROOT / "out/latest-parity/deva" / f"{page}-deva.png"


def load(side: str, page: str):
    return pngread.read_png(image_path(side, page))


def pixel(px, w: int, x: int, y: int):
    return px[y * w + x]


def bbox_color(side: str, page: str, color, region):
    w, h, px = load(side, page)
    x0, y0, x1, y1 = region
    n = 0
    xs = []
    ys = []
    for y in range(y0, y1):
        for x in range(x0, x1):
            if px[y * w + x] == color:
                n += 1
                xs.append(x)
                ys.append(y)
    box = (min(xs), min(ys), max(xs), max(ys)) if xs else None
    return n, box


def hover_rows(side: str, page: str, color=(236, 236, 237)):
    w, h, px = load(side, page)
    rows = []
    for y in range(50, 810):
        count = sum(1 for x in range(64, 339) if px[y * w + x] == color)
        if count > 100:
            rows.append(y)
    if not rows:
        return 0, None
    return len(rows), (rows[0], rows[-1])


def text_bands(side: str, page: str, x0: int, x1: int, y0: int, y1: int, threshold=200):
    w, h, px = load(side, page)
    rows = []
    for y in range(y0, y1):
        dark = 0
        for x in range(x0, x1):
            r, g, b = px[y * w + x]
            if max(r, g, b) < threshold:
                dark += 1
        if dark > 3:
            rows.append(y)
    bands = []
    for y in rows:
        if not bands or y > bands[-1][1] + 1:
            bands.append([y, y])
        else:
            bands[-1][1] = y
    return [tuple(band) for band in bands]


def white_panel(side: str, page: str):
    w, h, px = load(side, page)
    xs = []
    ys = []
    for y in range(70, 280):
        for x in range(120, 340):
            if px[y * w + x] == (255, 255, 255):
                xs.append(x)
                ys.append(y)
    return (len(xs), (min(xs), min(ys), max(xs), max(ys)) if xs else None)


def composer_clusters(side: str, page: str):
    w, h, px = load(side, page)
    groups = []
    for x in range(400, 1230):
        dark = 0
        for y in range(730, 800):
            r, g, b = px[y * w + x]
            if max(r, g, b) < 200:
                dark += 1
        if dark:
            if not groups or x > groups[-1][1] + 1:
                groups.append([x, x])
            else:
                groups[-1][1] = x
    return [tuple(group) for group in groups]


print("== A5/F3 mask samples (from d1-mask-attribution.log) ==")
for page, point in [("delete-confirm", (60, 120)), ("delete-confirm", (300, 700)),
                    ("settings-general", (60, 120)), ("settings-general", (300, 700))]:
    q = pixel(load("qml", page)[2], 1280, *point)
    d = pixel(load("deva", page)[2], 1280, *point)
    print(f"{page} {point}: QML={q} deva={d} delta={tuple(a-b for a,b in zip(q,d))}")

print("\n== B1/B2 hover band (exact rgb(236,236,237), rows with >100 px, x64..338) ==")
for page in ("chat", "hover-thread", "long-mid"):
    for side in ("qml", "deva"):
        n, span = hover_rows(side, page)
        print(f"{page:12s} {side:4s} rows={n:3d} span={span}")

print("\n== B3 selected band (exact rgb(228,228,244), x0..359) ==")
for page in ("chat", "hover-thread", "long-mid"):
    for side in ("qml", "deva"):
        n, box = bbox_color(side, page, (228, 228, 244), (0, 40, 360, 810))
        print(f"{page:12s} {side:4s} n={n:5d} bbox={box}")

print("\n== C2/C3 context menu white panel (x120..339, y70..279) ==")
for side in ("qml", "deva"):
    n, box = white_panel(side, "ctx-menu")
    print(f"ctx-menu {side:4s} white_px={n:5d} bbox={box}")

print("\n== G1 composer left icon clusters (dark max(r,g,b)<200, y730..799) ==")
for side in ("qml", "deva"):
    clusters = composer_clusters(side, "chat")
    print(f"chat {side:4s} first_clusters={clusters[:8]} total_groups={len(clusters)}")

print("\n== E1/E3/E5 visible text bands (x430..1199, y40..639, max<200) ==")
for page in ("chat", "search-none"):
    for side in ("qml", "deva"):
        bands = text_bands(side, page, 430, 1200, 40, 640)
        print(f"{page:12s} {side:4s} E1 n={len(bands):2d} first={bands[:2]} last={bands[-2:]}")
        bands5 = text_bands(side, page, 430, 1200, 200, 700)
        print(f"{page:12s} {side:4s} E5 n={len(bands5):2d} last={bands5[-2:]}")

print("\n== E2/E4 table + image placeholder (same screenshot) ==")
for side in ("qml", "deva"):
    n, box = bbox_color(side, "chat", (244, 244, 244), (470, 80, 801, 230))
    bands = text_bands(side, "chat", 430, 1200, 560, 700)
    print(f"chat {side:4s} E2 table_bg_244 n={n:5d} bbox={box}; E3/E4 bands y560..699={bands}")

print("\n== H1 empty diff (from d-page-diff18-final.log) ==")
log = (ROOT / "out/latest-parity/logs/d-page-diff18-final.log").read_text()
for line in log.splitlines():
    if line.startswith("empty ") or line.startswith("first-run "):
        print(line)
