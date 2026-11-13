"""待办清单：`todo_write` 工具的快照日志与折叠视图。

逐条对齐 Deva `apps/desktop/src/main/services/todos.ts`：

- 每次 `todo_write` 追加一条快照（`StoredSession.todos` 的元素），清单按 `listId` 折叠，
  取每个清单的最后一条快照；
- 「当前清单」= 最后一个清单，且尚未全部完成、也没被取消；
- 新开清单还是更新当前清单，看显式 `new_list`、当前清单是否已收尾、以及新旧条目有无重合；
- 压缩摘要后附当前清单（`todo_snapshot_text`）：写清单的那次 `tool_use` 可能刚被压掉，
  模型从此只能从这里知道清单进度。

这是纯数据模块：不读磁盘、不认识 Qt。
"""
from __future__ import annotations

from typing import Any, Optional

TODO_STATUSES = ("pending", "in_progress", "completed")
# 单个清单的条目上限：防模型把整份计划逐行塞进来，清单失去「一眼看进度」的意义。
MAX_ITEMS = 50
MAX_CONTENT = 200
MAX_TITLE = 60

_STATUS_MARK = {"completed": "[x]", "in_progress": "[~]", "pending": "[ ]"}


def _str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def is_list_done(items: list[dict[str, Any]]) -> bool:
    return bool(items) and all(item.get("status") == "completed" for item in items)


def fold_todos(entries: Optional[list[dict[str, Any]]] = None) -> list[dict[str, Any]]:
    """快照日志 → 清单列表（按首次出现先后排列；每个清单取其最后一条快照）。"""
    by_id: dict[str, dict[str, Any]] = {}
    for entry in entries or []:
        list_id = str(entry.get("listId") or "")
        if not list_id:
            continue
        items = [i for i in entry.get("items") or [] if isinstance(i, dict)]
        current = by_id.get(list_id)
        if current is not None:
            current["items"] = items
            if entry.get("title"):
                current["title"] = str(entry["title"])
            current["updatedAt"] = int(entry.get("at") or 0)
        else:
            at = int(entry.get("at") or 0)
            by_id[list_id] = {
                "id": list_id,
                "title": str(entry.get("title") or ""),
                "items": items,
                "createdAt": at,
                "updatedAt": at,
            }
    return list(by_id.values())


def active_todo_list(
    entries: Optional[list[dict[str, Any]]] = None,
    cancelled: Optional[list[str]] = None,
) -> Optional[dict[str, Any]]:
    """当前清单：最近一个清单，且尚未全部完成、也没被取消。"""
    lists = fold_todos(entries)
    if not lists:
        return None
    last = lists[-1]
    if is_list_done(last["items"]) or list_id_cancelled(last["id"], cancelled):
        return None
    return last


def list_id_cancelled(list_id: str, cancelled: Optional[list[str]]) -> bool:
    return list_id in (cancelled or [])


def parse_todo_input(
    raw: Any,
) -> dict[str, Any]:
    """解析 todo_write 入参；不合法返回 `{"error": ...}`。"""
    args = raw if isinstance(raw, dict) else {}
    if args.get("cancel") is True:
        return {"cancel": True}
    todos = args.get("todos")
    if not isinstance(todos, list):
        return {"error": "todos 必须是数组：[{ content, status }]（取消清单请传 cancel: true）。"}
    items: list[dict[str, Any]] = []
    for candidate in todos:
        entry = candidate if isinstance(candidate, dict) else {}
        content = _str(entry.get("content"))[:MAX_CONTENT]
        if not content:
            continue
        status = entry.get("status")
        items.append(
            {"content": content, "status": status if status in TODO_STATUSES else "pending"}
        )
    if not items:
        return {"error": "todos 不能为空：至少给出一项 { content, status }（取消清单请传 cancel: true）。"}
    if len(items) > MAX_ITEMS:
        return {"error": f"清单最多 {MAX_ITEMS} 项，请合并为更粗粒度的步骤后重写。"}
    return {
        "title": _str(args.get("title"))[:MAX_TITLE],
        "items": items,
        "newList": args.get("new_list") is True,
    }


def apply_todo_write(
    entries: Optional[list[dict[str, Any]]],
    cancelled: Optional[list[str]],
    tool_use_id: str,
    raw_input: Any,
    now: int,
) -> dict[str, Any]:
    """应用一次 todo_write：返回新快照、`{"cancel": listId|null}` 或 `{"error": ...}`。"""
    parsed = parse_todo_input(raw_input)
    if "error" in parsed:
        return parsed
    if "cancel" in parsed:
        current = active_todo_list(entries, cancelled)
        return {"cancel": current["id"] if current else None}

    lists = fold_todos(entries)
    current = lists[-1] if lists else None
    items = parsed["items"]

    def overlap(existing: list[dict[str, Any]], fresh: list[dict[str, Any]]) -> bool:
        existing_contents = {item.get("content") for item in existing}
        return any(item.get("content") in existing_contents for item in fresh)

    def closed(todo_list: dict[str, Any]) -> bool:
        return is_list_done(todo_list["items"]) or list_id_cancelled(todo_list["id"], cancelled)

    base = None
    if not (parsed["newList"] or current is None or (closed(current) and not overlap(current["items"], items))):
        base = current
    done = is_list_done(items) and (base is None or not is_list_done(base["items"]))
    entry: dict[str, Any] = {
        "id": tool_use_id,
        "listId": base["id"] if base else f"l_{tool_use_id}",
        "at": now,
        "title": parsed["title"] or (base["title"] if base else ""),
        "items": items,
    }
    if done:
        entry["done"] = True
    return entry


def todo_result_text(entry: dict[str, Any]) -> str:
    """回灌给模型的 tool_result 正文。"""
    items = entry.get("items") or []
    total = len(items)
    finished = sum(1 for item in items if item.get("status") == "completed")
    if finished == total:
        return f"清单已全部完成（{finished}/{total}）。"
    doing = sum(1 for item in items if item.get("status") == "in_progress")
    if doing == 0:
        hint = "当前没有进行中的项：开始下一项前先把它标为 in_progress。"
    elif doing > 1:
        hint = "同一时刻只应有一项 in_progress，请收敛为一项。"
    else:
        hint = "继续推进：完成一项立即标为 completed，再开始下一项。"
    return f"已更新待办清单（已完成 {finished}/{total}）。{hint}"


def list_lines(todo_list: dict[str, Any]) -> str:
    """清单条目的纯文本形态（[x] 已完成 / [~] 进行中 / [ ] 待办）。"""
    return "\n".join(
        f"- {_STATUS_MARK.get(str(item.get('status')), '[ ]')} {item.get('content')}"
        for item in todo_list.get("items") or []
    )


def todo_snapshot_text(
    entries: Optional[list[dict[str, Any]]] = None,
    cancelled: Optional[list[str]] = None,
    zh: bool = True,
) -> str:
    """压缩摘要后附的当前清单；无进行中的清单返回空串。"""
    current = active_todo_list(entries, cancelled)
    if current is None:
        return ""
    title = f"：{current['title']}" if current.get("title") else ""
    if zh:
        head = f"【当前待办清单{title}】（[x] 已完成 / [~] 进行中 / [ ] 待办；继续用 todo_write 更新）"
    else:
        head = (
            f"[Current todo list{title}] ([x] done / [~] in progress / [ ] pending; "
            "keep updating it with todo_write)"
        )
    return f"{head}\n{list_lines(current)}"


def todo_reminder_text(
    entries: Optional[list[dict[str, Any]]] = None,
    cancelled: Optional[list[str]] = None,
) -> str:
    """新一轮开始时仍留着上一轮未完成的清单时的提醒；无进行中的清单返回空串。"""
    current = active_todo_list(entries, cancelled)
    if current is None:
        return ""
    items = current.get("items") or []
    done = sum(1 for item in items if item.get("status") == "completed")
    title = f"「{current['title']}」" if current.get("title") else ""
    return (
        f"【待办清单提醒】此前留有一个未完成的待办清单{title}（已完成 {done}/{len(items)}）：\n"
        f"{list_lines(current)}\n"
        "若本轮继续这项任务，请照常用 todo_write 更新它；若用户已转向别的事、不再进行它，"
        "请调用 todo_write 并传 cancel: true 取消。"
    )


__all__ = [
    "MAX_CONTENT",
    "MAX_ITEMS",
    "MAX_TITLE",
    "TODO_STATUSES",
    "active_todo_list",
    "apply_todo_write",
    "fold_todos",
    "is_list_done",
    "list_lines",
    "parse_todo_input",
    "todo_reminder_text",
    "todo_result_text",
    "todo_snapshot_text",
]
