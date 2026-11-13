"""模型视图（model-view.ts）、复读检测（repetition.ts）、待办清单（todos.ts）的离线测试。"""
from __future__ import annotations

from mvvm.models.chat_models import Message, TextPart, ToolResultPart, ToolUsePart
from mvvm.services import model_view as mv
from mvvm.services import repetition as rp
from mvvm.services import todos as td


def user(text: str) -> Message:
    return Message(role="user", content=text)


def assistant(text: str) -> Message:
    return Message(role="assistant", content=text)


def tool_result(tool_use_id: str, text: str, is_error: bool = False) -> Message:
    return Message(
        role="user",
        content=[ToolResultPart(toolUseId=tool_use_id, content=text, isError=True if is_error else None)],
    )


# ── model_view ────────────────────────────────────────────────────────────────
def test_markers_and_classification():
    summary = user(f"{mv.COMPACT_MARKER}\n摘要正文")
    nudge = user(f"{mv.AUTO_MARKER}继续")
    notice = user("⟦deva:notify⟧任务结束")

    assert mv.is_compaction_summary(summary) is True
    assert mv.is_compaction_summary(user("普通消息")) is False
    assert mv.is_auto_nudge(nudge) is True
    assert mv.is_task_notification(notice) is True
    # marker 只在 role=user 的纯文本消息上成立
    assert mv.is_compaction_summary(Message(role="assistant", content=f"{mv.COMPACT_MARKER}x")) is False


def test_has_tool_result_and_genuine_user_turn():
    assert mv.has_tool_result(tool_result("c1", "ok")) is True
    assert mv.has_tool_result(user("hi")) is False
    assert mv.is_genuine_user_turn(user("hi")) is True
    assert mv.is_genuine_user_turn(tool_result("c1", "ok")) is False
    assert mv.is_genuine_user_turn(user(f"{mv.COMPACT_MARKER}x")) is False
    assert mv.is_genuine_user_turn(user(f"{mv.AUTO_MARKER}x")) is False
    assert mv.is_genuine_user_turn(assistant("hi")) is False


def test_last_turn_start():
    messages = [user("问题一"), assistant("答一"), user("问题二"), assistant("答二")]
    assert mv.last_turn_start(messages) == 2
    assert mv.last_turn_start([assistant("x")]) == -1


def test_model_range_without_compaction():
    messages = [user("hi"), assistant("hello")]
    assert mv.model_range(messages) == (-1, 0)
    assert mv.model_start(messages) == 0
    assert mv.model_first(messages) == 0
    # 没压缩过时原样返回同一个列表
    assert mv.model_messages(messages) is messages


def test_model_range_between_turns():
    summary = user(f"{mv.COMPACT_MARKER}\n旧摘要")
    messages = [user("很早"), assistant("很早的答"), summary, user("新问题"), assistant("新答")]
    assert mv.model_range(messages) == (-1, 2)
    assert [m.text() for m in mv.model_messages(messages)] == [summary.text(), "新问题", "新答"]


def test_model_range_mid_turn_keeps_head():
    """轮中压缩：摘要插在本轮中间，本轮请求原文要额外带上。"""
    messages = [
        user("上一轮"),
        assistant("上一轮的答"),
        user("本轮请求"),
        assistant("第一步"),
        tool_result("c1", "结果"),
        user(f"{mv.COMPACT_MARKER}\n摘要"),
        assistant("第二步"),
    ]
    head, start = mv.model_range(messages)
    assert head == 2
    assert start == 5
    view = mv.model_messages(messages)
    assert [m.text() for m in view] == ["本轮请求", messages[5].text(), "第二步"]
    assert mv.model_first(messages) == 2


def test_insert_text_and_body():
    text = mv.insert_text("补充说明")
    assert text.startswith(mv.INSERT_MARKER)
    assert mv.insert_body(text) == "补充说明"
    assert mv.insert_body("普通文本") is None
    assert mv.insert_body(mv.INSERT_MARKER) == ""


def test_text_of_concatenates_text_parts():
    message = Message(role="assistant", content=[TextPart(text="甲"), TextPart(text="乙")])
    assert mv.text_of(message) == "甲乙"
    assert mv.text_of(Message(role="assistant", content="丙")) == "丙"


# ── repetition ────────────────────────────────────────────────────────────────
def test_find_repetition_detects_paragraph_loop():
    text = "开头。" + "同一段话。" * 60 + "结尾。"
    hit = rp.find_repetition(text)
    assert hit is not None
    assert hit.period == len("同一段话。")
    assert hit.span >= 250


def test_find_repetition_ignores_normal_output():
    text = "\n".join(f"- 第 {i} 条内容各有不同" for i in range(200))
    assert rp.find_repetition(text) is None


def test_find_repetition_needs_both_count_and_span():
    # 只重复 3 遍、总长不足 → 不算
    assert rp.find_repetition("同一段话。" * 3) is None


def test_min_span_for():
    # 短周期走「重复 10 遍、200 字符」这档更宽松；长周期两档都要求更多字符
    assert rp.min_span_for(1) == 200
    assert rp.min_span_for(20) == 200
    assert rp.min_span_for(25) == 250
    assert rp.min_span_for(30) == 250
    assert rp.min_span_for(100) == 400
    # 门槛不可能低于任何一档的绝对下限
    assert rp.min_span_for(1000) == 4_000


def test_trailing_repetition_only_looks_at_tail():
    loop = "不断重复的一句话。" * 40
    assert rp.trailing_repetition("正常开头" + loop) is not None
    assert rp.trailing_repetition(loop + "然后恢复了正常输出，各有不同。") is None


def test_watch_repetition_throttles_by_step():
    feed = rp.watch_repetition()
    assert feed("短") is None  # 未达 WATCH_STEP
    hit = None
    for _ in range(60):
        hit = feed("重复的一句话。")
        if hit is not None:
            break
    assert hit is not None
    assert hit.period == len("重复的一句话。")


# ── todos ─────────────────────────────────────────────────────────────────────
def test_parse_todo_input_validation():
    assert "error" in td.parse_todo_input({"todos": "nope"})
    assert "error" in td.parse_todo_input({"todos": []})
    assert td.parse_todo_input({"cancel": True}) == {"cancel": True}
    parsed = td.parse_todo_input(
        {"title": "计划", "todos": [{"content": " 第一步 ", "status": "in_progress"}, {"content": ""}]}
    )
    assert parsed["title"] == "计划"
    assert parsed["items"] == [{"content": "第一步", "status": "in_progress"}]
    assert parsed["newList"] is False


def test_parse_todo_input_rejects_too_many_items():
    raw = {"todos": [{"content": f"项 {i}", "status": "pending"} for i in range(td.MAX_ITEMS + 1)]}
    assert "error" in td.parse_todo_input(raw)


def test_apply_todo_write_creates_then_updates_list():
    first = td.apply_todo_write(None, None, "c1", {"title": "计划", "todos": [{"content": "甲", "status": "in_progress"}]}, 100)
    assert first["listId"] == "l_c1"
    assert first["createdAt"] if "createdAt" in first else True  # 快照本身不带 createdAt

    second = td.apply_todo_write(
        [first], None, "c2", {"todos": [{"content": "甲", "status": "completed"}, {"content": "乙", "status": "in_progress"}]}, 200
    )
    assert second["listId"] == "l_c1"
    assert second["title"] == "计划"  # 未给标题时沿用
    assert "done" not in second

    third = td.apply_todo_write(
        [first, second], None, "c3", {"todos": [{"content": "甲", "status": "completed"}, {"content": "乙", "status": "completed"}]}, 300
    )
    assert third.get("done") is True


def test_apply_todo_write_new_list_and_cancel():
    first = td.apply_todo_write(None, None, "c1", {"todos": [{"content": "甲", "status": "pending"}]}, 100)
    fresh = td.apply_todo_write([first], None, "c2", {"new_list": True, "todos": [{"content": "乙", "status": "pending"}]}, 200)
    assert fresh["listId"] == "l_c2"

    # 取消当前清单
    assert td.apply_todo_write([first], None, "c3", {"cancel": True}, 300) == {"cancel": "l_c1"}


def test_fold_todos_last_snapshot_wins():
    entries = [
        {"id": "a", "listId": "l1", "at": 1, "title": "旧", "items": [{"content": "甲", "status": "pending"}]},
        {"id": "b", "listId": "l2", "at": 2, "title": "另一个", "items": [{"content": "乙", "status": "pending"}]},
        {"id": "c", "listId": "l1", "at": 3, "title": "", "items": [{"content": "甲", "status": "completed"}]},
    ]
    folded = td.fold_todos(entries)
    assert [t["id"] for t in folded] == ["l1", "l2"]
    assert folded[0]["title"] == "旧"  # 空标题不覆盖
    assert folded[0]["items"][0]["status"] == "completed"
    assert folded[0]["updatedAt"] == 3


def test_active_todo_list_skips_done_and_cancelled():
    done = {"id": "a", "listId": "l1", "at": 1, "title": "", "items": [{"content": "甲", "status": "completed"}]}
    assert td.active_todo_list([done]) is None

    open_ = {"id": "b", "listId": "l2", "at": 2, "title": "", "items": [{"content": "乙", "status": "pending"}]}
    assert td.active_todo_list([done, open_])["id"] == "l2"
    assert td.active_todo_list([done, open_], ["l2"]) is None


def test_todo_result_text_hints():
    items = [{"content": "甲", "status": "in_progress"}]
    assert "继续推进" in td.todo_result_text({"items": items})
    assert "标为 in_progress" in td.todo_result_text({"items": [{"content": "甲", "status": "pending"}]})
    assert "收敛" in td.todo_result_text({"items": [{"content": "甲", "status": "in_progress"}] * 2})
    assert "全部完成" in td.todo_result_text({"items": [{"content": "甲", "status": "completed"}]})


def test_todo_snapshot_text_lists_current_only():
    entries = [
        {"id": "a", "listId": "l1", "at": 1, "title": "计划", "items": [
            {"content": "甲", "status": "completed"}, {"content": "乙", "status": "in_progress"}]},
    ]
    text = td.todo_snapshot_text(entries, None)
    assert "当前待办清单：计划" in text
    assert "- [x] 甲" in text
    assert "- [~] 乙" in text
    assert td.todo_snapshot_text([], None) == ""


def test_todo_reminder_text_mentions_cancel():
    entries = [{"id": "a", "listId": "l1", "at": 1, "title": "", "items": [{"content": "甲", "status": "pending"}]}]
    text = td.todo_reminder_text(entries, None)
    assert "cancel: true" in text
    assert "已完成 0/1" in text
    assert td.todo_reminder_text([], None) == ""
