"""纯标准库 PNG 解码（8 位真彩 / 灰度 / 带 alpha，逐行反滤波）。

环境里可能没有 ImageMagick（本轮实测 `convert` / `identify` 都不在 PATH），
逐页像素对照又必须有真实数字，所以这里按 PNG 规范自己解：

- 只覆盖截图会产生的形态：位深 8、非隔行、颜色类型 0/2/4/6（灰度 / 真彩 / 带 alpha）；
  其它形态直接抛错，不静默返回半张图。
- 返回统一是 RGB 三元组序列（alpha 先与白底合成，截图都是不透明的）。
- 帧间无依赖，纯函数，测试与脚本共用。
"""
from __future__ import annotations

import struct
import zlib
from typing import List, Tuple

SIGNATURE = b"\x89PNG\r\n\x1a\n"

_CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter(raw: bytes, width: int, height: int, bpp: int, stride: int) -> List[bytearray]:
    """把 IDAT 解压后的扫描线还原成逐行像素字节（每行 stride 字节，不含滤波字节）。"""
    rows: List[bytearray] = []
    pos = 0
    previous = bytearray(stride)
    for _ in range(height):
        method = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if len(line) != stride:
            raise ValueError("PNG 数据被截断")
        if method == 1:      # Sub
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif method == 2:    # Up
            for i in range(stride):
                line[i] = (line[i] + previous[i]) & 0xFF
        elif method == 3:    # Average
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 0xFF
        elif method == 4:    # Paeth
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                up_left = previous[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(left, previous[i], up_left)) & 0xFF
        elif method != 0:
            raise ValueError(f"未知滤波类型 {method}")
        rows.append(line)
        previous = line
    return rows


def read_png(path: str) -> Tuple[int, int, List[Tuple[int, int, int]]]:
    """读一张 PNG → `(宽, 高, RGB 像素序列)`（行优先）。"""
    with open(path, "rb") as handle:
        data = handle.read()
    if data[:8] != SIGNATURE:
        raise ValueError(f"{path}: 不是 PNG")
    pos = 8
    width = height = depth = color = interlace = -1
    idat = bytearray()
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
    if width <= 0 or height <= 0:
        raise ValueError(f"{path}: 缺少 IHDR")
    if depth != 8:
        raise ValueError(f"{path}: 只支持 8 位深度，实际 {depth}")
    if interlace != 0:
        raise ValueError(f"{path}: 不支持隔行扫描")
    if color not in _CHANNELS:
        raise ValueError(f"{path}: 不支持颜色类型 {color}")

    channels = _CHANNELS[color]
    bpp = channels
    stride = width * channels
    rows = _unfilter(zlib.decompress(bytes(idat)), width, height, bpp, stride)

    pixels: List[Tuple[int, int, int]] = []
    for line in rows:
        if channels == 3:
            pixels.extend((line[i], line[i + 1], line[i + 2]) for i in range(0, stride, 3))
        elif channels == 1:
            pixels.extend((line[i], line[i], line[i]) for i in range(stride))
        elif channels == 2:
            for i in range(0, stride, 2):
                gray, alpha = line[i], line[i + 1]
                pixels.append(_over_white(gray, gray, gray, alpha))
        else:  # RGBA
            for i in range(0, stride, 4):
                pixels.append(_over_white(line[i], line[i + 1], line[i + 2], line[i + 3]))
    return width, height, pixels


def _over_white(r: int, g: int, b: int, alpha: int) -> Tuple[int, int, int]:
    """与白底合成（截图不透明，带 alpha 的形态只为不静默出错）。"""
    if alpha == 255:
        return (r, g, b)
    inv = 255 - alpha
    return (
        (r * alpha + 255 * inv) // 255,
        (g * alpha + 255 * inv) // 255,
        (b * alpha + 255 * inv) // 255,
    )


__all__ = ["read_png"]
