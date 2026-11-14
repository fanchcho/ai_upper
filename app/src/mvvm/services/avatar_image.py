"""头像图片落盘：`data URI` ↔ `<dir>/<name>.<webp|png|jpg>`（Deva `services/avatar-image.ts`）。

角色头像与用户头像共用同一套规则，所以单独成模块而不是各写一遍：

- 读：按扩展名顺序找，命中即回 `data:<mime>;base64,...`，没有则空串；
- 写：MIME 白名单仅 `webp` / `png` / `jpeg`（含 `image/jpg`），解码后字节数须在
  `[1, 2MB]`；写入前先删同名其它后缀，保证一个名字只有一张图；
- 非法入参或写失败一律返回空串——原版就是「失败回 ''」，界面据空串回落确定性头像。
"""
from __future__ import annotations

import base64
import binascii
from pathlib import Path

# 扩展名 → MIME（读的时候按这个顺序找；原版同样先 webp 再 png 再 jpg）。
EXTENSIONS = (("webp", "image/webp"), ("png", "image/png"), ("jpg", "image/jpeg"))
MIME_TO_EXT = {
    "image/webp": "webp",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
}
MIN_BYTES = 1
MAX_BYTES = 2 * 1024 * 1024


def read_avatar_image(directory: Path, name: str) -> str:
    """读 `<directory>/<name>.<ext>` → data URI；没有任何变体或读失败回空串。"""
    for ext, mime in EXTENSIONS:
        try:
            data = (directory / f"{name}.{ext}").read_bytes()
        except OSError:
            continue
        return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"
    return ""


def clear_avatar_image(directory: Path, name: str) -> None:
    """删掉该名字的三个扩展名变体（不存在不算错）。"""
    for ext, _mime in EXTENSIONS:
        (directory / f"{name}.{ext}").unlink(missing_ok=True)


def write_avatar_image(directory: Path, name: str, data_uri: str) -> str:
    """把 data URI 落盘并读回；任何不合格或写失败返回空串（原版语义）。

    `directory` 不存在会被创建。写入前清掉其它后缀，避免 webp/png 并存导致读到旧图。
    """
    mime, _, payload = str(data_uri or "").partition(";base64,")
    mime = mime[len("data:"):].strip().lower() if mime.startswith("data:") else ""
    ext = MIME_TO_EXT.get(mime)
    if not ext or not payload:
        return ""
    try:
        raw = base64.b64decode(payload, validate=False)
    except (binascii.Error, ValueError):
        return ""
    if not MIN_BYTES <= len(raw) <= MAX_BYTES:
        return ""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        clear_avatar_image(directory, name)
        (directory / f"{name}.{ext}").write_bytes(raw)
    except OSError:
        return ""
    return read_avatar_image(directory, name)


__all__ = [
    "EXTENSIONS",
    "MAX_BYTES",
    "clear_avatar_image",
    "read_avatar_image",
    "write_avatar_image",
]
