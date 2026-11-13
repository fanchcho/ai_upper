"""测试用的最小合法 PNG（1×1 红色）与其它图片夹具。"""
from __future__ import annotations

import struct
import zlib


def png_bytes() -> bytes:
    """1×1 真彩 PNG：魔数、IHDR/IDAT/IEND 齐全，`QImage` 与 `sniff_image_mime` 都能认。"""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        + chunk(b"IEND", b"")
    )
