"""C9：原版 Electron safeStorage 成功态 vs 移植版同状态，同尺寸并排对照。

输入两张 1280×820 实拍；裁设置弹窗同区域（280,128,720,567），左原版右 Qt，
输出原生 1:1 两拼图并计算逐像素差异。不做缩放。
"""
from __future__ import annotations
import json, os, sys
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QColor, QFont
from PySide6.QtCore import QRect

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out/electron-safe-storage"
LEFT = OUT / "deva-secret-saved.png"
RIGHT = ROOT / "out/extensions-os/light-secret-real-os-saved.png"
CROP = QRect(280, 128, 720, 567)

def load(p):
    im = QImage(str(p))
    assert not im.isNull(), p
    assert (im.width(), im.height()) == (1280, 820), (p, im.width(), im.height())
    return im

def main():
    app = QGuiApplication.instance() or QGuiApplication([])
    a, b = load(LEFT), load(RIGHT)
    ca, cb = a.copy(CROP), b.copy(CROP)
    gap, label_h = 16, 28
    out = QImage(ca.width() * 2 + gap, ca.height() + label_h, QImage.Format_RGB32)
    out.fill(QColor("#ffffff"))
    painter = QPainter(out)
    painter.setPen(QColor("#111111"))
    font = QFont(); font.setPixelSize(13); painter.setFont(font)
    painter.drawText(QRect(0, 0, ca.width(), label_h), 0x0084, "Original Electron safeStorage (private D-Bus, Saved)")
    painter.drawText(QRect(ca.width() + gap, 0, cb.width(), label_h), 0x0084, "ai_upper QML (same GNOME Secret Service, Saved)")
    painter.drawImage(0, label_h, ca)
    painter.drawImage(ca.width() + gap, label_h, cb)
    painter.end()
    dst = OUT / "compare-secret-saved.png"
    assert out.save(str(dst))

    total = ca.width() * ca.height()
    equal = 0
    diff_sum = 0
    max_diff = 0
    for y in range(ca.height()):
        for x in range(ca.width()):
            pa, pb = ca.pixel(x, y), cb.pixel(x, y)
            d = (abs((pa >> 16 & 255) - (pb >> 16 & 255)) + abs((pa >> 8 & 255) - (pb >> 8 & 255)) + abs((pa & 255) - (pb & 255)))
            diff_sum += d
            max_diff = max(max_diff, d)
            if d == 0:
                equal += 1
    data = {
        "left": str(LEFT), "right": str(RIGHT), "crop": [CROP.x(), CROP.y(), CROP.width(), CROP.height()],
        "size": [out.width(), out.height()],
        "pixel_equal_percent": round(equal * 100.0 / total, 3),
        "mean_abs_rgb_sum": round(diff_sum / total, 3),
        "max_channel_diff": max_diff,
        "note": "两图均为 1280×820 实拍；裁同一设置弹窗区域 720×567，1:1 并排，无缩放。差异包含原版/移植版既有的弹窗版式差，不等于 safeStorage 功能差异。",
    }
    (OUT / "compare-secret-saved.json").write_text(json.dumps(data, ensure_ascii=False, indent=1))
    print(json.dumps(data, ensure_ascii=False))

if __name__ == "__main__":
    main()
