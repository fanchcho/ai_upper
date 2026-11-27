"""同数据 fixture：原版 Electron 与 Qt 的 MCP 详情并排对照 + 字段纵向坐标核对。"""
import json, os, sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QColor, QFont
from PySide6.QtCore import QRect, Qt

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "out/final-port"
CROP = QRect(280, 128, 720, 567)
LABELS = ("Available to", "Transport", "Command", "Arguments", "Environment variables", "Discovered tools")

app = QGuiApplication.instance() or QGuiApplication([])
result = {"themes": {}, "label_tops": {}}
for theme in ("dark", "light"):
    left = QImage(str(OUT / f"deva-saved-{theme}.png"))
    right = QImage(str(OUT / f"{theme}-secret-real-os-saved.png"))
    assert not left.isNull() and not right.isNull()
    assert (left.width(), left.height()) == (1280, 820) == (right.width(), right.height())
    a, b = left.copy(CROP), right.copy(CROP)
    gap, label_h = 16, 28
    out = QImage(a.width() * 2 + gap, a.height() + label_h, QImage.Format_RGB32)
    out.fill(QColor("#ffffff"))
    p = QPainter(out); p.setPen(QColor("#111111")); f = QFont(); f.setPixelSize(13); p.setFont(f)
    p.drawText(QRect(0, 0, a.width(), label_h), Qt.AlignCenter, f"Original Electron safeStorage ({theme}, Saved)")
    p.drawText(QRect(a.width() + gap, 0, b.width(), label_h), Qt.AlignCenter, f"ai_upper QML (same fixture/{theme}, Saved)")
    p.drawImage(0, label_h, a); p.drawImage(a.width() + gap, label_h, b); p.end()
    dst = OUT / f"compare-identical-{theme}.png"; assert out.save(str(dst))
    total = a.width() * a.height(); equal = 0; diff = 0
    for y in range(a.height()):
        for x in range(a.width()):
            pa, pb = a.pixel(x, y), b.pixel(x, y)
            d = abs((pa >> 16 & 255) - (pb >> 16 & 255)) + abs((pa >> 8 & 255) - (pb >> 8 & 255)) + abs((pa & 255) - (pb & 255))
            diff += d; equal += d == 0
    # 字段 label 的 y 坐标：deva DOM vs Qt 几何（只比同名 label）。
    deva = json.loads((OUT / f"deva-fields-{theme}.json").read_text())
    qt = json.loads((OUT / f"{theme}-secret-real-os-saved-geometry.json").read_text())
    deva_y = {}
    for item in deva:
        text = (item.get("text") or "").strip().replace("\n", " ")
        if item.get("cls") == "ext-field__label" and text in LABELS:
            deva_y[text] = round(item["rect"]["y"], 1)
    qt_y = {}
    for item in qt:
        text = (item.get("text") or "").strip()
        if text in LABELS and text not in qt_y:
            qt_y[text] = round(item["y"], 1)
    pairs = {k: {"deva": deva_y.get(k), "qt": qt_y.get(k), "delta": None if k not in qt_y or k not in deva_y else round(qt_y[k] - deva_y[k], 1)} for k in LABELS}
    result["label_tops"][theme] = pairs
    result["themes"][theme] = {"png": str(dst), "crop": [CROP.x(), CROP.y(), CROP.width(), CROP.height()],
                               "pixel_equal_percent": round(equal * 100 / total, 3), "mean_abs_rgb_sum": round(diff / total, 3)}
(OUT / "compare-identical.json").write_text(json.dumps(result, ensure_ascii=False, indent=1))
print(json.dumps(result, ensure_ascii=False, indent=1))
