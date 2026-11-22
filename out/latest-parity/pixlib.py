"""逐页对比用的极简像素工具（环境里没有 PIL/numpy/ImageMagick，靠标准库解 PNG）。

只用标准库：`scripts/parity/pngread.py` 读图、`bbox()` 求墨迹包围盒、`runs()` 求
某行/列的连续非背景段（用来数分隔线/行距）。所有坐标都是整图像素坐标。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "parity"))

from pngread import read_png


class Image:
    def __init__(self, path: str) -> None:
        self.w, self.h, pixels = read_png(path)
        flat = bytearray(self.w * self.h * 3)
        i = 0
        for pixel in pixels:
            flat[i] = pixel[0]
            flat[i + 1] = pixel[1]
            flat[i + 2] = pixel[2]
            i += 3
        self.data = bytes(flat)

    def px(self, x: int, y: int) -> tuple[int, int, int]:
        i = (y * self.w + x) * 3
        return (self.data[i], self.data[i + 1], self.data[i + 2])

    def bbox(
        self,
        x0: int,
        x1: int,
        y0: int,
        y1: int,
        bg: tuple[int, int, int] = (247, 247, 248),
        tol: int = 12,
    ):
        """区域内的墨迹包围盒 (left, right, top, bottom)；全背景返回 None。"""
        xs: list[int] = []
        ys: list[int] = []
        for y in range(y0, min(y1, self.h)):
            for x in range(x0, min(x1, self.w)):
                c = self.px(x, y)
                if any(abs(c[k] - bg[k]) > tol for k in range(3)):
                    xs.append(x)
                    ys.append(y)
        if not xs:
            return None
        return (min(xs), max(xs), min(ys), max(ys))

    def runs(self, axis: str, fixed: int, lo: int, hi: int, bg, tol: int = 12):
        """沿一行(axis='x')/一列(axis='y') 找非背景连续段 [(start,end), ...]。"""
        out = []
        start = None
        for pos in range(lo, hi):
            c = self.px(pos, fixed) if axis == "x" else self.px(fixed, pos)
            ink = any(abs(c[k] - bg[k]) > tol for k in range(3))
            if ink and start is None:
                start = pos
            elif not ink and start is not None:
                out.append((start, pos - 1))
                start = None
        if start is not None:
            out.append((start, hi - 1))
        return out

    def row_bands(self, x0: int, x1: int, y0: int, y1: int, bg, tol: int = 12):
        """区域内「有墨迹」的连续行段：用来数文字行/卡片行。"""
        out = []
        start = None
        for y in range(y0, y1):
            has = False
            for x in range(x0, x1):
                c = self.px(x, y)
                if any(abs(c[k] - bg[k]) > tol for k in range(3)):
                    has = True
                    break
            if has and start is None:
                start = y
            elif not has and start is not None:
                out.append((start, y - 1))
                start = None
        if start is not None:
            out.append((start, y1 - 1))
        return out


def diff_pixels(a: Image, b: Image, tol: int = 13, box=None):
    """两图逐像素差（任一通道 > tol 记为差异）。返回 (计数, 包围盒, 占比)。"""
    if box is None:
        box = (0, 0, a.w, a.h)
    x0, y0, x1, y1 = box
    n = 0
    bb = None
    for y in range(y0, y1):
        for x in range(x0, x1):
            i = (y * a.w + x) * 3
            if max(abs(a.data[i + k] - b.data[i + k]) for k in range(3)) > tol:
                n += 1
                if bb is None:
                    bb = [x, y, x, y]
                else:
                    bb[0] = min(bb[0], x)
                    bb[1] = min(bb[1], y)
                    bb[2] = max(bb[2], x)
                    bb[3] = max(bb[3], y)
    return n, bb, n / ((x1 - x0) * (y1 - y0))
