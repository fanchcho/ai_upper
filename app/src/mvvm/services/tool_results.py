"""工具结果的两处落盘形态：`tool_result` 消息，与 `todo_write` 的会话边车应用。

## 为什么单独成模块

`tool_result_message` 被 `ChatViewModel` 用：Anthropic 风味下工具结果挂在 user 轮的
`content` 里；图片结果（`read_file` 读到图片）按 Deva `chat.ts` 的做法把 `images` 挂在
同一个 `tool_result` 块上——不是另起一条消息，否则模型会看到「结果说附了图片、历史里
却没有图」。以前它住在 `fake_provider` 里，生产代码不该依赖测试替身。

`apply_todo_write_to` 对应 Deva `chat.ts` 里 `todo_write` 的执行分支（约 5729 行）：
解析 → 取消或追加快照 → 恢复被取消的清单 → 返回给模型的正文。清单是**纯展示产物**，
不写进 messages，只落在会话边车（`StoredSession.todos` / `todoCancelled`）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from mvvm.models.chat_models import ImagePart, Message, ToolResultPart
from mvvm.services.todos import (
    active_todo_list,
    apply_todo_write,
    todo_result_text,
)
from mvvm.services.tool_runtime import ToolResult


def tool_result_message(
    call: object,
    content: str,
    is_error: bool,
    images: Optional[list[ImagePart]] = None,
) -> Message:
    """把一次工具调用的结果包成 user 消息。`call` 只要有 `.id` 即可（`ToolCall` / `ToolUsePart`）。"""
    return Message(
        role="user",
        content=[
            ToolResultPart(
                toolUseId=getattr(call, "id"),
                content=content,
                isError=True if is_error else None,
                images=images or None,
            )
        ],
    )


def record_delivered(
    delivered: Optional[Dict[str, List[str]]],
    tool_use_id: str,
    result: ToolResult,
) -> Optional[Dict[str, List[str]]]:
    """把一次工具结果交付的文件写进 `StoredSession.delivered` 边车；无交付则原样返回。

    语义对齐 Deva `chat.ts:5294-5297`：按 `toolUseId` 记**已解析的绝对路径**（`present_files`
    在 `tool_runtime.py` 里已去重），messages 里保留模型原样发出的参数——改写它会让模型
    以为没照做而反复重试。边车是纯展示产物，交付卡与「打开 / 定位」据此取路径。

    返回新的边车字典（不改传入的那份）；`result.delivered` 为空时返回原值（可能是 None）。
    """
    paths = [str(p) for p in (result.delivered or []) if str(p)]
    if not paths:
        return delivered
    merged: Dict[str, List[str]] = dict(delivered or {})
    merged[str(tool_use_id)] = paths
    return merged


@dataclass
class TodoApplied:
    """一次 `todo_write` 的结果与新的边车状态（调用方负责写回会话）。"""

    result: ToolResult
    entries: list[dict[str, Any]] = field(default_factory=list)
    cancelled: list[str] = field(default_factory=list)
    changed: bool = False
    done: Optional[dict[str, Any]] = None

    @property
    def active(self) -> Optional[dict[str, Any]]:
        """当前进行中的清单（界面胶囊条的数据源）；没有则为 None。"""
        return active_todo_list(self.entries, self.cancelled)


def apply_todo_write_to(
    entries: Optional[list[dict[str, Any]]],
    cancelled: Optional[list[str]],
    tool_use_id: str,
    raw_input: Any,
    now: int,
) -> TodoApplied:
    """把一次 `todo_write` 应用到边车状态。语义逐条对齐 Deva（取消 / 追加 / 恢复 / 已全部完成）。"""
    current_entries = list(entries or [])
    current_cancelled = list(cancelled or [])
    outcome = apply_todo_write(current_entries, current_cancelled, tool_use_id, raw_input, now)

    if "error" in outcome:
        return TodoApplied(ToolResult(outcome["error"], True, "参数错误"), current_entries, current_cancelled)

    if "cancel" in outcome:
        list_id = outcome["cancel"]
        if not list_id:
            return TodoApplied(
                ToolResult("当前没有进行中的待办清单，无需取消。", False, "无需取消"),
                current_entries,
                current_cancelled,
            )
        current_cancelled.append(list_id)
        return TodoApplied(
            ToolResult("已取消当前待办清单。", False, "已取消"),
            current_entries,
            current_cancelled,
            changed=True,
        )

    current_entries.append(outcome)
    # 已取消的清单又被写入（条目有重合）：模型恢复了这项任务，重新显示。
    if outcome["listId"] in current_cancelled:
        current_cancelled.remove(outcome["listId"])
    done = (
        {"id": tool_use_id, "title": outcome.get("title", ""), "items": outcome.get("items", [])}
        if outcome.get("done")
        else None
    )
    return TodoApplied(
        ToolResult(todo_result_text(outcome), False, "已更新"),
        current_entries,
        current_cancelled,
        changed=True,
        done=done,
    )


__all__ = [
    "TodoApplied",
    "apply_todo_write_to",
    "record_delivered",
    "tool_result_message",
]
