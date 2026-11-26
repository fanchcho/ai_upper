"""展示条目 → Qt 富文本（工具卡片、图片、待办胶囊的文案都在这里）。

为什么单独成模块：`ChatPane` 只该做「把字符串塞给控件」，而「一条工具结果画成什么卡、
图片怎么缩、清单胶囊显示哪一行」是能脱离 Qt 单测的纯函数。这里不 import Qt。

Qt 富文本只支持 HTML 的一个子集（见 Qt 文档 Rich Text / Supported HTML Subset）：
块级背景与边框只对 `table` 稳定生效，所以工具卡用单格表画，而不是给 `div` 加 CSS 边框。

图片走「占位 URL + 文档资源」而不是 `data:` URI：`QTextDocument` 对 `data:` 的支持随
版本/绑定漂移，而 `addResource(ImageResource, QUrl, QImage)` 在四个绑定上语义一致。
`transcript_html()` 同时返回需要注册的资源列表，`ChatPane` 负责按序 `addResource`。
"""
from __future__ import annotations
from locale_runtime import tr, display_text

import base64
from typing import Any, Iterable, Optional

MESSAGE_ROLE_HEAD = {
    "user": tr('legacy.5630b886f9cd'),
    "assistant": tr('legacy.9b0519a157ee'),
    "tool": tr('legacy.a72ef18d9a0e'),
    "error": tr('legacy.b859c7be7501'),
    "compaction": tr('legacy.ed4240ed1fd4'),
    "notice": tr('legacy.ab3656a956f5'),
}

TOOL_STATUS_OK = tr('legacy.51991a5d111a')
TOOL_STATUS_ERROR = tr('legacy.3e3c8068bb0e')

# 单张图片在正文里的最大显示宽度（像素）：再宽会撑破聊天区，正文滚动条只该出现在长文本上。
IMAGE_MAX_WIDTH = 360
# 同一条工具结果最多内联几张图：read_file 一次只读一张，但工具结果结构允许多张。
IMAGE_MAX_COUNT = 4

IMAGE_URL_PREFIX = "deva-image:"


def _escape(value: Any) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _preserve(text: str) -> str:
    """保留换行与连续空格（Qt 富文本按 HTML 规则折叠空白）。"""
    return _escape(text).replace("\n", "<br/>").replace("  ", "&nbsp;&nbsp;")


def tool_status_text(entry: dict[str, Any]) -> str:
    return (tr('legacy.3e3c8068bb0e')) if entry.get("is_error") else (tr('legacy.51991a5d111a'))


def tool_card_title(entry: dict[str, Any]) -> str:
    """工具卡标题：`工具 read_file`；有摘要时附在后面。"""
    name = str(entry.get("name") or tr('legacy.a72ef18d9a0e'))
    summary = display_text(entry.get("summary") or "").strip()
    return f"{name} · {summary}" if summary else name


def image_placeholder(index: int) -> str:
    return f"{IMAGE_URL_PREFIX}{index}"


def decode_images(entries: Iterable[dict[str, Any]]) -> list[tuple[str, bytes]]:
    """按出现顺序取出所有内联图片：`[(mediaType, 原始字节)]`。

    占位 URL 的序号就是这里的下标；坏数据（缺 base64、解码失败）直接跳过，不占序号——
    宁可少一张图，也不要整份正文加载失败。
    """
    out: list[tuple[str, bytes]] = []
    for entry in entries or []:
        for image in entry.get("images") or []:
            data = image.get("data") if isinstance(image, dict) else None
            if not data:
                continue
            try:
                raw = base64.b64decode(str(data), validate=True)
            except (ValueError, TypeError):
                continue
            out.append((str(image.get("mediaType") or "image/png"), raw))
    return out


def _tool_card(entry: dict[str, Any], image_index: list[int]) -> str:
    error = bool(entry.get("is_error"))
    color = "#b42318" if error else "#475467"
    background = "#fef3f2" if error else "#f8fafc"
    title = _escape(tool_card_title(entry))
    body = _preserve(str(entry.get("text") or ""))
    images: list[str] = []
    for image in entry.get("images") or []:
        if not isinstance(image, dict):
            continue
        if image_index[0] >= IMAGE_MAX_COUNT:
            break
        index = image_index[0]
        image_index[0] += 1
        name = _escape(image.get("name") or tr('legacy.be8da62ea113'))
        images.append(
            f'<p><img src="{image_placeholder(index)}" width="{IMAGE_MAX_WIDTH}"/></p>'
            f"<p style='color:#667085;'>［{tr('legacy.be8da62ea113')}］{name}</p>"
        )
    return (
        f'<table width="100%" cellspacing="0" cellpadding="8" '
        f'style="background-color:{background}; border:1px solid #e4e7ec;">'
        f'<tr><td>'
        f'<p style="color:{color};"><b>{title}</b>（{(tr('legacy.3e3c8068bb0e')) if error else (tr('legacy.51991a5d111a'))}）</p>'
        f'<p style="color:#344054;">{body}</p>'
        f"{''.join(images)}"
        f"</td></tr></table>"
    )


def _message(role: str, text: str, *, is_error: bool = False) -> str:
    head = ({'user': tr('legacy.5630b886f9cd'), 'assistant': tr('legacy.9b0519a157ee'), 'tool': tr('legacy.a72ef18d9a0e'), 'error': tr('legacy.b859c7be7501'), 'compaction': tr('legacy.ed4240ed1fd4'), 'notice': tr('legacy.ab3656a956f5')}).get(role, role)
    if is_error:
        head = tr('legacy.1c9f086d2b88' ,p0=head)
    color = "#b42318" if is_error or role == "error" else "#101828"
    return (
        f'<p style="color:{color};"><b>［{_escape(head)}］</b></p>'
        f'<p style="color:#344054;">{_preserve(text)}</p>'
    )


def transcript_html(entries: Any) -> str:
    """展示条目 → 富文本正文。

    工具条目画成卡片；其余角色是「角色 + 正文」两段。空正文也保留角色行：压缩摘要、
    失败原因之类有时正文很短，丢掉角色会看不出是谁说的。
    """
    images_left = [0]
    blocks: list[str] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        role = str(entry.get("role") or "")
        if role == "tool":
            blocks.append(_tool_card(entry, images_left))
        else:
            blocks.append(
                _message(role, str(entry.get("text") or ""), is_error=bool(entry.get("is_error")))
            )
    return "".join(blocks) if blocks else ""


def transcript_plain_text(entries: Any) -> str:
    """纯文本投影（无障碍/日志/测试用）：与旧版 `transcript_to_text` 同一口径。"""
    lines: list[str] = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        role = str(entry.get("role", ""))
        head = ({'user': tr('legacy.5630b886f9cd'), 'assistant': tr('legacy.9b0519a157ee'), 'tool': tr('legacy.a72ef18d9a0e'), 'error': tr('legacy.b859c7be7501'), 'compaction': tr('legacy.ed4240ed1fd4'), 'notice': tr('legacy.ab3656a956f5')}).get(role, role)
        if entry.get("is_error"):
            head = tr('legacy.1c9f086d2b88' ,p0=head)
        name = entry.get("name")
        if name:
            head = f"{head} {name}"
        lines.append(f"[{head}] {entry.get('text', '')}")
    return "\n\n".join(lines)


# ── 待办胶囊 ──────────────────────────────────────────────────────────────
def todo_counts(state: Optional[dict[str, Any]]) -> tuple[int, int]:
    items = (state or {}).get("items") or []
    done = sum(1 for item in items if item.get("status") == "completed")
    return done, len(items)


def todo_now_text(state: Optional[dict[str, Any]]) -> str:
    """胶囊主行：优先显示进行中的那一项，没有进行中则显示「等待开始下一项」。"""
    items = (state or {}).get("items") or []
    for item in items:
        if item.get("status") == "in_progress":
            return str(item.get("content") or "")
    for item in items:
        if item.get("status") != "completed":
            return str(item.get("content") or "")
    return ""


def todo_capsule_text(state: Optional[dict[str, Any]]) -> str:
    """`待办：写实现（已完成 1/3）`；无清单返回空串（胶囊收起）。"""
    if not state:
        return ""
    done, total = todo_counts(state)
    now = todo_now_text(state)
    title = str(state.get("title") or "").strip()
    head = tr('legacy.3be3bbe2d941' ,p1=title) if title else tr('legacy.f38aef0f951a')
    if now:
        return tr('legacy.1d91e5140320' ,p0=head, p2=now, p4=done, p6=total)
    return tr('legacy.b496542da6af' ,p0=head, p2=done, p4=total)


def todo_item_lines(state: Optional[dict[str, Any]]) -> list[str]:
    """展开面板的条目行：`[x] 已完成 / [~] 进行中 / [ ] 待办`。"""
    mark = {"completed": "[x]", "in_progress": "[~]", "pending": "[ ]"}
    return [
        f"{mark.get(str(item.get('status')), '[ ]')} {item.get('content', '')}"
        for item in (state or {}).get("items") or []
    ]


__all__ = [
    "IMAGE_MAX_COUNT",
    "IMAGE_MAX_WIDTH",
    "IMAGE_URL_PREFIX",
    "MESSAGE_ROLE_HEAD",
    "decode_images",
    "image_placeholder",
    "todo_capsule_text",
    "todo_counts",
    "todo_item_lines",
    "todo_now_text",
    "tool_card_title",
    "tool_status_text",
    "transcript_html",
    "transcript_plain_text",
]
