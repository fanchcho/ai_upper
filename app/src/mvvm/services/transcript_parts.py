"""落盘消息 → 展示形态的共用判据：附件贴片、图片 ref、交付卡行。

两个入口（WebEngine 渲染层与 QML 壳）都要回答同样三个问题，答案只能有一份：

- **用户消息带了哪些附件**（`attachment_chips`）：原版 `toDisplayMessages` 的 user 分支
  把图片 / PDF 内容块与三种注入文本块（`[附件文件]` / `[附件文件夹]` / `[附件文件路径]`）
  还原成贴片；贴片只给名称、类型、体积，图片另给 ref，界面按 ref 现取缩略图。
- **图片 ref 怎么算**（`image_ref`）：`消息下标:块下标:指纹`。指纹取 base64 长度（36 进制）
  + 中段 8 字符——按轮删除后下标会前移，同一个「下标:块下标」可能换成另一张图，取图时
  对不上就不给（同 Deva `imageRef`）。
- **交付卡的每一行长什么样**（`delivery_rows`）：路径只从 `StoredSession.delivered` 边车
  取（见 `mvvm/services/deliverables.py` 文件头的安全不变式），大小按磁盘现算，
  文件不存在时 `size=None` 让界面标「已不存在」。

这里是纯函数：不 import Qt，不做 IO 之外的副作用（`delivery_rows` 只 `os.stat`）。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from mvvm.services.attachments import (
    ATTACH_FOLDER_PREFIX,
    ATTACH_PATH_PREFIX,
    ATTACH_TEXT_PREFIX,
)
from mvvm.services.deliverables import delivered_paths, is_openable


# ── 附件贴片 ──────────────────────────────────────────────────────────────
def base36(value: int) -> str:
    """非负整数 → 36 进制小写串（与 JS `Number.prototype.toString(36)` 同形）。"""
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if value <= 0:
        return "0"
    out: List[str] = []
    while value:
        value, rem = divmod(value, 36)
        out.append(digits[rem])
    return "".join(reversed(out))


def base64_bytes(b64: str) -> int:
    """base64 串解码后的字节数（同 Deva `base64Bytes`，不为解码多分配一份）。"""
    pad = 2 if b64.endswith("==") else 1 if b64.endswith("=") else 0
    return max(0, (len(b64) * 3) // 4 - pad)


def image_ref(msg_index: int, part_index: int, data: str) -> str:
    """图片 ref：`消息下标:块下标:指纹`（同 Deva `imageRef`）。"""
    mid = len(data) // 2
    return "%d:%d:%s%s" % (msg_index, part_index, base36(len(data)), data[mid:mid + 8])


def attachment_chips(parts: List[Any], msg_index: int) -> List[Dict[str, Any]]:
    """用户消息里的附件 → `AttachmentChip[]`（同 Deva `toDisplayMessages` 的 user 分支）。

    - 图片 / PDF 是结构化内容块：只回名称、类型、体积；图片另给 ref，界面按 ref 现取缩略图；
    - 文本 / 文件夹 / 只给位置的文件是注入的 text 块，靠前缀标记认出来再还原贴片；
    - 提问正文是最后一个 text 块，不在 chips 里。
    """
    chips: List[Dict[str, Any]] = []
    text_parts = [
        str(getattr(p, "text", "")) for p in parts if getattr(p, "type", "") == "text"
    ]
    for part_index, part in enumerate(parts):
        kind = getattr(part, "type", "")
        if kind == "image":
            data = str(getattr(part, "data", "") or "")
            chips.append(
                {
                    "name": str(getattr(part, "name", "") or "图片"),
                    "kind": "image",
                    "size": base64_bytes(data),
                    "ref": image_ref(msg_index, part_index, data),
                    "partIndex": part_index,
                }
            )
        elif kind == "document":
            data = str(getattr(part, "data", "") or "")
            chips.append(
                {
                    "name": str(getattr(part, "name", "") or "文档"),
                    "kind": "document",
                    "size": base64_bytes(data),
                    "partIndex": part_index,
                }
            )
    # 注入文本块：除最后一个 text（提问正文）之外，其余按前缀重建。
    for text in text_parts[:-1]:
        if text.startswith(ATTACH_TEXT_PREFIX):
            # 形如「前缀 + 文件名\n```\n正文\n```」，体积按正文算。
            head, _, body = text.partition("\n")
            body = body[4:] if body.startswith("```\n") else body
            body = body[:-4] if body.endswith("\n```") else body
            chips.append(
                {
                    "name": head[len(ATTACH_TEXT_PREFIX):].strip(),
                    "kind": "text",
                    "size": len(body.encode("utf-8")),
                }
            )
        elif text.startswith(ATTACH_FOLDER_PREFIX):
            directory = text[len(ATTACH_FOLDER_PREFIX):].split("\n", 1)[0].strip()
            chips.append(
                {
                    "name": os.path.basename(directory) or directory,
                    "kind": "folder",
                    "path": directory,
                }
            )
        elif text.startswith(ATTACH_PATH_PREFIX):
            file_path = text[len(ATTACH_PATH_PREFIX):].split("\n", 1)[0].strip()
            chips.append(
                {
                    "name": os.path.basename(file_path) or file_path,
                    "kind": "file",
                    "path": file_path,
                }
            )
    return chips


# ── 交付卡 ────────────────────────────────────────────────────────────────
def delivery_rows(session: Any, tool_use_ids: List[str]) -> List[Dict[str, Any]]:
    """某几条工具调用交付的文件 → 交付卡的行（顺序即边车里的交付顺序）。

    `tool_use_ids` 是正文里出现过的 `present_files` 调用 id（按出现顺序）。只取边车
    `session.delivered`，路径不接受调用方传入——与 `deliverables:inspect` 同一条不变式。
    同一份文件被多次交付时按首现去重（原版 `placeholders` 里 `new Set(paths)` 同义）。
    """
    rows: List[Dict[str, Any]] = []
    seen: set = set()
    for tool_use_id in tool_use_ids:
        for path in delivered_paths(session, tool_use_id):
            if path in seen:
                continue
            seen.add(path)
            rows.append(delivery_row(path))
    return rows


def delivery_row(path: str) -> Dict[str, Any]:
    """单个交付文件的行：名称 / 目录 / 体积（None=已不存在）/ 能否用默认应用打开。"""
    try:
        size: Optional[int] = os.stat(path).st_size if os.path.isfile(path) else None
    except OSError:
        size = None
    return {
        "path": path,
        "name": os.path.basename(path),
        "dir": os.path.dirname(path),
        "size": size,
        "openable": is_openable(path),
    }


__all__ = [
    "attachment_chips",
    "base36",
    "base64_bytes",
    "delivery_row",
    "delivery_rows",
    "image_ref",
]
