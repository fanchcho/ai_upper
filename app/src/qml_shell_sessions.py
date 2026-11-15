"""QML 壳的数据投影：真实会话 → 列表行、落盘消息 → 正文 Markdown、回合增量状态机。

为什么单独成模块：`qml_shell` 里的 QML 桥是 `QObject`，建它就要 Qt；而「列表一行长
什么样、正文按什么顺序拼、流式增量怎么追加」是能脱离 Qt 单测的纯函数。壳里只做
「把结果塞进 QML 属性」，判据全在这里。

三条口径（都对齐现有服务层，不另造真相源）：

- 列表：`ChatSessionStore.visible_sessions()` 的元信息（标题、updatedAt），预览取该
  会话最后一条有正文的消息，时间按毫秒时间戳现算相对文案；
- 正文：**落盘消息按顺序**拼成 Markdown，交给 `markdown.body` 渲染——用户消息与助手
  回复各起一个小标题；工具调用 / 工具结果没有正文可渲染，跳过（`Message.text()` 本就
  只取 text 块）；
- 流式：`TurnState` 只做「基础正文 + 本轮用户消息 + 收到的增量」的拼接，重渲染整篇
  由调用方决定（正文层是唯一渲染实现，这里不生成富文本）。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

PREVIEW_MAX = 60
USER_HEADING = "## 你"
ASSISTANT_HEADING = "## 助手"


def _one_line(text: str) -> str:
    return " ".join((text or "").split())


def preview_text(session: Any) -> str:
    """会话预览：最后一条有正文的消息压成一行，超长截断加省略号。"""
    messages = getattr(session, "messages", None) or []
    for message in reversed(messages):
        text = _one_line(
            message.text() if hasattr(message, "text") else str(getattr(message, "content", ""))
        )
        if text:
            return text[:PREVIEW_MAX] + "…" if len(text) > PREVIEW_MAX else text
    return ""


def time_label(ms: Any, now: Optional[int] = None) -> str:
    """毫秒时间戳 → 列表里的时间文案（绝对日期，不做时区换算之外的花样）。"""
    from mvvm.models.chat_models import now_ms

    try:
        value = int(ms)
    except (TypeError, ValueError):
        return ""
    current = now_ms() if now is None else int(now)
    delta = current - value
    if delta < 0:
        delta = 0
    if delta < 60_000:
        return "刚刚"
    if delta < 3_600_000:
        return "%d 分钟前" % (delta // 60_000)
    if delta < 86_400_000:
        return "%d 小时前" % (delta // 3_600_000)
    # 更早的按本地日期显示（毫秒 → 本地时区）。
    import time as _time

    return _time.strftime("%m-%d %H:%M", _time.localtime(value / 1000.0))


def session_row(meta: Any, session: Any, now: Optional[int] = None) -> Dict[str, Any]:
    """列表一行：id / 标题 / 预览 / 时间文案。标题为空时退回预览的首行。"""
    title = str(getattr(meta, "title", "") or "").strip()
    preview = preview_text(session) if session is not None else ""
    if not title:
        title = preview or "未命名会话"
    return {
        "id": str(getattr(meta, "id", "")),
        "title": title,
        "preview": preview,
        "time": time_label(getattr(meta, "updatedAt", None), now),
    }


def session_rows(store: Any, now: Optional[int] = None) -> List[Dict[str, Any]]:
    """真实会话 → 列表行（顺序沿用服务层：updatedAt 倒序）。"""
    rows: List[Dict[str, Any]] = []
    for meta in store.visible_sessions():
        rows.append(session_row(meta, store.load_session(meta.id), now))
    return rows


def _role_heading(role: str) -> str:
    return USER_HEADING if role == "user" else ASSISTANT_HEADING


def transcript_markdown(
    messages: List[Any],
    pending_user: Optional[str] = None,
    streaming: Optional[str] = None,
) -> str:
    """落盘消息（+ 本轮进行中的用户消息与流式增量）→ 一份正文 Markdown。

    顺序即落盘顺序；没有正文的消息（纯工具调用 / 纯工具结果）跳过。`pending_user`
    与 `streaming` 只在回合进行中使用——用户消息在 `run_turn` 里才落盘，先显示要
    自己补；增量在 `done` 之后会以落盘消息为准重新拼一遍。
    """
    blocks: List[str] = []
    for message in messages or []:
        text = message.text() if hasattr(message, "text") else str(getattr(message, "content", ""))
        if not text.strip():
            continue
        blocks.append("%s\n\n%s" % (_role_heading(str(getattr(message, "role", ""))), text.strip()))
    if pending_user and pending_user.strip():
        blocks.append("%s\n\n%s" % (USER_HEADING, pending_user.strip()))
    if streaming is not None:
        # 空增量也起标题：界面上先出现「助手」，随后正文一段段长出来。
        blocks.append(("%s\n\n%s" % (ASSISTANT_HEADING, (streaming or "").strip())).rstrip())
    return "\n\n".join(blocks)


class TurnState:
    """一轮进行中的正文状态：已落盘历史的 Markdown + 本轮用户消息 + 流式增量。

    `apply(event)` 吃的是宿主推出来的 `chat:event` 的事件体（`{type: ...}`），只认
    `text_delta` / `done` / `error` 三类；返回 True 表示正文变了、调用方该重渲染。
    """

    def __init__(self, base: str, pending_user: str) -> None:
        self.base = base
        self.pending_user = pending_user
        self.stream = ""
        self.finished = False
        self.stop = ""
        self.error = ""

    def apply(self, event: Dict[str, Any]) -> bool:
        kind = event.get("type")
        if kind == "text_delta":
            self.stream += str(event.get("text") or "")
            return True
        if kind == "done":
            self.finished = True
            self.stop = str(event.get("stopReason") or "")
            return True
        if kind == "error":
            self.error = str(event.get("message") or "")
            self.finished = True
            return True
        return False

    def markdown(self) -> str:
        """整篇正文：落盘历史（已是 Markdown）+ 本轮用户消息 + 已收到的增量。"""
        tail = transcript_markdown([], pending_user=self.pending_user, streaming=self.stream)
        pieces = [self.base] if self.base.strip() else []
        if tail.strip():
            pieces.append(tail)
        return "\n\n".join(pieces)


__all__ = [
    "ASSISTANT_HEADING",
    "PREVIEW_MAX",
    "TurnState",
    "USER_HEADING",
    "preview_text",
    "session_row",
    "session_rows",
    "time_label",
    "transcript_markdown",
]
