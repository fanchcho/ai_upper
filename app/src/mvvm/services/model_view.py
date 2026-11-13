"""对话记录里「模型实际看到的部分」。

逐条对齐 Deva `apps/desktop/src/main/services/model-view.ts`。压缩不删消息（见
`compaction.py`），只在边界插入一条摘要；发给模型的内容、要不要压缩、对话文件怎么拆分
存盘（见 `chat_session_store.py` 的 `_sync_compacted`）都按这里截取。

这是叶子模块：只依赖消息模型，`compaction.py` 与 `chat_session_store.py` 都引用它而
不互相引用。
"""
from __future__ import annotations

from typing import Sequence

from mvvm.models.chat_models import Message, TextPart, ToolResultPart

# 摘要消息的标记前缀：极不可能被用户键入；发给模型时据此截取、界面上据此画压缩提示。
COMPACT_MARKER = "⟦deva:compaction⟧"
# 引擎自愈引导消息的标记前缀（输出被截断后续写、空回合追问等）。这类 user 消息由主进程
# 注入，不是用户说的话：不算一轮起点、不渲染成用户气泡、不进压缩转录。
AUTO_MARKER = "⟦deva:auto⟧"
# 后台任务通知消息的标记前缀。算一轮起点（展示为系统通知而非用户气泡）。
NOTIFY_MARKER = "⟦deva:notify⟧"
# 回合进行中用户发来的消息，以 text 块附在某步工具结果之后。不算一轮起点。
INSERT_MARKER = "⟦deva:insert⟧"


def _plain(message: Message) -> str | None:
    """消息的纯文本内容；内容块数组时返回 None。"""
    return message.content if isinstance(message.content, str) else None


def is_compaction_summary(message: Message) -> bool:
    """该消息是否为压缩摘要。"""
    text = _plain(message)
    return message.role == "user" and isinstance(text, str) and text.startswith(COMPACT_MARKER)


def is_auto_nudge(message: Message) -> bool:
    """该消息是否为引擎注入的自愈引导。"""
    text = _plain(message)
    return message.role == "user" and isinstance(text, str) and text.startswith(AUTO_MARKER)


def is_task_notification(message: Message) -> bool:
    """该消息是否为后台任务通知。"""
    text = _plain(message)
    return message.role == "user" and isinstance(text, str) and text.startswith(NOTIFY_MARKER)


def has_tool_result(message: Message) -> bool:
    if isinstance(message.content, str):
        return False
    return any(isinstance(part, ToolResultPart) for part in message.content)


def is_genuine_user_turn(message: Message) -> bool:
    """真实用户轮：role=user 且不含 tool_result，也不是摘要 / 自愈引导。

    轮中压缩会把摘要放在本轮中间；摘要若算作轮起点，下次压缩就会把它当成「本轮请求」保留，
    而把真正的请求原文压掉。
    """
    return (
        message.role == "user"
        and not has_tool_result(message)
        and not is_compaction_summary(message)
        and not is_auto_nudge(message)
    )


def last_turn_start(messages: Sequence[Message]) -> int:
    """最后一轮（一轮进行中即当前这轮）的起点：最后一条真实用户消息的下标，没有则 -1。"""
    for index in range(len(messages) - 1, -1, -1):
        if is_genuine_user_turn(messages[index]):
            return index
    return -1


def model_range(messages: Sequence[Message]) -> tuple[int, int]:
    """模型视图的 (head, start)。

    从最后一条压缩摘要起（start），一轮进行中压缩的还要在前面带上那一轮的请求原文
    （head，否则 -1）。没压缩过时 start = 0、head = -1。

    由消息结构判断、不需额外字段：两轮之间压缩，摘要紧挨着保留部分的第一条真实用户消息；
    一轮进行中压缩，摘要插在这一轮中间，后面紧跟的是助手消息，这一轮的请求在摘要之前。
    """
    start = -1
    for index in range(len(messages) - 1, -1, -1):
        if is_compaction_summary(messages[index]):
            start = index
            break
    if start < 0:
        return -1, 0
    following = messages[start + 1] if start + 1 < len(messages) else None
    if following is None or is_genuine_user_turn(following):
        return -1, start
    return last_turn_start(messages[:start]), start


def model_start(messages: Sequence[Message]) -> int:
    """对话记录里从哪条起仍会发给模型。"""
    return model_range(messages)[1]


def model_first(messages: Sequence[Message]) -> int:
    """模型视图最早用到的那条消息的下标（有 head 即 head）：它之前的不再发给模型。"""
    head, start = model_range(messages)
    return head if head >= 0 else start


def model_messages(messages: Sequence[Message]) -> list[Message]:
    """发给模型的消息。没压缩过时原样返回同一个列表（不复制）。"""
    head, start = model_range(messages)
    if head < 0 and start == 0:
        return list(messages) if not isinstance(messages, list) else messages
    tail = list(messages[start:])
    return [messages[head], *tail] if head >= 0 else tail


def insert_text(body: str, zh: bool = True) -> str:
    """回合进行中插入的消息交给模型的完整文本。"""
    note = (
        "（以下是用户在你执行过程中发来的消息，请据此调整接下来的工作，然后继续完成任务。）"
        if zh
        else "(The user sent the following message while you were working. Take it into account for the rest of the task, then carry on.)"
    )
    return f"{INSERT_MARKER}{note}\n{body}"


def insert_body(text: str) -> str | None:
    """插入消息的用户原文；不是插入消息则为 None。"""
    if not text.startswith(INSERT_MARKER):
        return None
    newline = text.find("\n")
    return text[newline + 1:] if newline >= 0 else ""


def text_of(message: Message) -> str:
    """消息的全部文本（压缩转录用；空内容返回空串）。"""
    if isinstance(message.content, str):
        return message.content
    return "".join(part.text for part in message.content if isinstance(part, TextPart))


__all__ = [
    "AUTO_MARKER",
    "COMPACT_MARKER",
    "INSERT_MARKER",
    "NOTIFY_MARKER",
    "has_tool_result",
    "insert_body",
    "insert_text",
    "is_auto_nudge",
    "is_compaction_summary",
    "is_genuine_user_turn",
    "is_task_notification",
    "last_turn_start",
    "model_first",
    "model_messages",
    "model_range",
    "model_start",
    "text_of",
]
