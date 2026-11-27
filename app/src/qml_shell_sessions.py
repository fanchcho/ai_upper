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

import json
from typing import Any, Dict, List, Optional
from native_i18n import translate

from mvvm.services.attachments import (
    ATTACH_FOLDER_PREFIX,
    ATTACH_PATH_PREFIX,
    ATTACH_TEXT_PREFIX,
)
from mvvm.services.deliverables import delivered_paths
from mvvm.services.transcript_parts import attachment_chips, base64_bytes, delivery_row

PREVIEW_MAX = 60
USER_HEADING = "## " + translate("zh-CN", "legacy.5630b886f9cd")
ASSISTANT_HEADING = "## " + translate("zh-CN", "cf.assistant")


def format_bytes(size: Any) -> str:
    """体积文案，逐字对齐原版渲染层的 `formatSize`（`0 B` / `221 B` / `1 KB` / `1.5 MB`）。

    交付卡与附件贴片都必须显示磁盘上的真实体积——原版占位值是 0，界面就曾显示 `0 B`。
    """
    try:
        value = int(size)
    except (TypeError, ValueError):
        return ""
    if value < 0:
        return ""
    if value < 1024:
        return translate("en", "finish.size.bytes") % value
    if value < 1024 * 1024:
        return translate("en", "finish.size.kilobytes") % round(value / 1024)
    if value < 1024 * 1024 * 1024:
        return translate("en", "finish.size.megabytes") % (value / 1024 / 1024)
    return translate("en", "finish.size.gigabytes") % (value / 1024 / 1024 / 1024)



_ATTACH_PREFIXES = (ATTACH_TEXT_PREFIX, ATTACH_FOLDER_PREFIX, ATTACH_PATH_PREFIX)


def message_body(message: Any) -> str:
    """一条消息的**提问/回复正文**（不含附件注入块）。

    `Message.text()` 按顺序拼接所有 `text` 块，用户消息里的附件是注入的 text 块
    （`[附件文件] …` / `[附件文件夹] …` / `[附件文件路径] …`，见
    `AttachmentService.build_attachment_part`），拼进来就会在正文里看到「[附件文件]
    spec.txt」加一段原文。原版 `toDisplayMessages` 把这些块单独还原成贴片、只把最后
    一个 text 块当提问正文；这里按同一口径过滤掉注入块。
    """
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    texts: List[str] = []
    for part in content:
        if str(getattr(part, "type", "") or "") != "text":
            continue
        text = str(getattr(part, "text", "") or "")
        if text.startswith(_ATTACH_PREFIXES):
            continue
        texts.append(text)
    return "".join(texts)


def _one_line(text: str) -> str:
    return " ".join((text or "").split())


def preview_text(session: Any) -> str:
    """会话预览：最后一条有正文的消息压成一行，超长截断加省略号。"""
    messages = getattr(session, "messages", None) or []
    for message in reversed(messages):
        text = _one_line(message_body(message))
        if text:
            return text[:PREVIEW_MAX] + "…" if len(text) > PREVIEW_MAX else text
    return ""


# 相对时间词表：逐字对齐原版 i18n/messages.ts 的 chat.time（zh 见 :269，en 见 :1733）。
# 原版拼法是 `${n} ${word}`（数字与词之间一个空格），中文也不例外。
_TIME_WORDS = {
    lang: tuple(translate(locale, 'chat.time.' + name)
                for name in ('now', 'min', 'hr', 'yesterday', 'day'))
    for lang, locale in (('zh', 'zh-CN'), ('en', 'en'))
}


def time_label(ms: Any, now: Optional[int] = None, lang: str = "zh") -> str:
    """毫秒时间戳 → 列表里的相对时间文案。

    口径逐字对齐原版 `useRelativeTime`（redesign/ChatFirstShell.tsx:338）：<1 分钟
    "just now / 刚刚"、<60 分钟 "N min ago / N 分钟前"、<24 小时 "N hr ago / N 小时前"、
    正好 1 天 "yesterday / 昨天"、更早 "N days ago / N 天前"。原版没有「绝对日期」这一档，
    跨月也只写天数。
    """
    from mvvm.models.chat_models import now_ms

    words = _TIME_WORDS.get(lang, _TIME_WORDS["zh"])
    try:
        value = int(ms)
    except (TypeError, ValueError):
        return ""
    current = now_ms() if now is None else int(now)
    delta = current - value
    if delta < 0:
        delta = 0
    minutes = delta // 60_000
    if minutes < 1:
        return words[0]
    if minutes < 60:
        return "%d %s" % (minutes, words[1])
    hours = minutes // 60
    if hours < 24:
        return "%d %s" % (hours, words[2])
    days = hours // 24
    if days == 1:
        return words[3]
    return "%d %s" % (days, words[4])


def session_row(
    meta: Any, session: Any, now: Optional[int] = None, lang: str = "zh"
) -> Dict[str, Any]:
    """列表一行：id / 标题 / 预览 / 时间文案。标题为空时退回预览的首行。"""
    title = str(getattr(meta, "title", "") or "").strip()
    preview = preview_text(session) if session is not None else ""
    if not title:
        title = preview or translate("en" if lang == "en" else "zh-CN", "finish.session.untitled")
    return {
        "id": str(getattr(meta, "id", "")),
        "title": title,
        "preview": preview,
        "time": time_label(getattr(meta, "updatedAt", None), now, lang),
    }


def session_rows(
    store: Any,
    now: Optional[int] = None,
    lang: str = "zh",
    metas: Optional[List[Any]] = None,
) -> List[Dict[str, Any]]:
    """真实会话 → 列表行（顺序沿用服务层：updatedAt 倒序）。

    `metas` 可由调用方传入已取到的 `visible_sessions()` 结果，省掉再列一次索引。
    会话记录走 `load_sessions()` 批量载入：目录只扫一遍，行内容与逐条载入逐字相同。
    """
    if metas is None:
        metas = store.visible_sessions()
    sessions = store.load_sessions([meta.id for meta in metas])
    return [
        session_row(meta, session, now, lang)
        for meta, session in zip(metas, sessions)
    ]


def _role_heading(role: str, lang: str = "zh") -> str:
    if lang == "en":
        return "## " + translate("en", "chat.role.user" if role == "user" else "cf.assistant")
    return USER_HEADING if role == "user" else ASSISTANT_HEADING


def _attachment_lines(parts: List[Any], msg_index: int, lang: str = "zh") -> List[str]:
    """用户消息里的附件 → 正文行（图片内联成 Markdown 图，其余列一行「附件：名 · 体积」）。

    图片直接内联 `data:` URI：`markdown.body` 的 image_resolver 会解码成 QTextDocument
    资源（`markdown/document.py:738-761`），QML 的 TextEdit 因此能在历史里看到缩略图，
    位置也与原版一致（附件排在提问正文之前）。非图片附件没有可画的内容，按原版贴片的
    信息量给一行文字（名称 + 真实体积），并且**不把正文塞进来**。
    """
    from native_i18n import translate
    def t(key):
        return translate("zh-CN" if lang == "zh" else "en", "native." + key)
    lines: List[str] = []
    for part in parts:
        kind = str(getattr(part, "type", "") or "")
        if kind == "image":
            data = str(getattr(part, "data", "") or "")
            name = str(getattr(part, "name", "") or t('image'))
            mime = str(getattr(part, "mediaType", "") or "image/png")
            if data:
                lines.append("![%s](data:%s;base64,%s)" % (name, mime, data))
            else:
                lines.append(t('missingImage') % name)
        elif kind == "document":
            name = str(getattr(part, "name", "") or t('document'))
            # 体积是 base64 解码后的字节数（与贴片同一算法），不是 base64 串长度。
            size = base64_bytes(str(getattr(part, "data", "") or ""))
            lines.append(t('attachedDocument') % (name, format_bytes(size)))
    for chip in attachment_chips(parts, msg_index):
        if chip.get("kind") in ("image", "document"):
            continue  # 上面已按内容块输出
        label = {
            "text": t('attachedText'),
            "folder": t('attachedFolder'),
            "file": t('attachedPath'),
        }.get(str(chip.get("kind")), t('attachment'))
        size = format_bytes(chip.get("size")) if chip.get("size") is not None else ""
        suffix = "（%s）" % size if size else ""
        lines.append("- %s：%s%s" % (label, chip.get("name", ""), suffix))
    return lines


# 工具名 → 原版 i18n 的中文/英文标签（deva Composer/blocks 的 chat.tool.* 同名键）。
_TOOL_LABEL_KEYS = {
    "read_file": "chat.tool.readFile",
    "list_dir": "chat.tool.listDir",
    "glob": "chat.tool.glob",
    "grep": "chat.tool.grep",
    "web_fetch": "chat.tool.webFetch",
    "write_file": "chat.tool.writeFile",
    "edit_file": "chat.tool.editFile",
    "run_command": "chat.tool.runCommand",
    "ask_user": "chat.tool.askUser",
    "create_skill": "chat.tool.createSkill",
    "create_mcp": "chat.tool.createMcp",
    "memory_read": "chat.tool.memoryRead",
    "memory_write": "chat.tool.memoryWrite",
    "memory_delete": "chat.tool.memoryDelete",
    "todo_write": "chat.tool.todoWrite",
    "present_files": "chat.tool.presentFiles",
    "mount_workspace": "chat.tool.mountWorkspace",
    "create_member": "chat.tool.createMember",
    "member_send": "chat.tool.memberSend",
    "member_stop": "chat.tool.memberStop",
    "member_status": "chat.tool.memberStatus",
    "read_main": "chat.tool.readMain",
    "report_to_main": "chat.tool.reportToMain",
    "reply_task": "chat.tool.replyTask",
    "skill": "chat.tool.skill",
    "tool_search": "chat.tool.toolSearch",
    "create_task": "chat.tool.createTask",
    "propose_agent": "chat.tool.proposeAgent",
    "browser": "chat.tool.browser",
}
_MEMBER_TOOLS = {"create_member", "member_send", "member_stop", "member_status", "read_main", "report_to_main", "reply_task"}
_SUBAGENT_TOOLS = {"run_subagent", "subagent", "run_subagent_batch"}


def _locale(lang: str) -> str:
    return "en" if lang == "en" else "zh-CN"


def _tool_label(name: str, lang: str) -> str:
    key = _TOOL_LABEL_KEYS.get(name)
    if key:
        return translate(_locale(lang), key)
    return name or translate(_locale(lang), "chat.tool.unknown")


def _activity_label(part: Any, lang: str) -> str:
    kind = str(getattr(part, "type", "") or "")
    name = str(getattr(part, "name", "") or (getattr(part, "toolUseId", "") if kind == "tool_result" else "") or "")
    if kind == "thinking":
        return translate(_locale(lang), "chat.thinking")
    if kind == "tool_result":
        return translate(_locale(lang), "chat.tool.result") + " · " + _tool_label(name, lang)
    if name in _MEMBER_TOOLS or name in _SUBAGENT_TOOLS:
        return translate(_locale(lang), "chat.work.subagent") + " · " + _tool_label(name, lang)
    return translate(_locale(lang), "chat.tool.call") + " · " + _tool_label(name, lang)


def _clip_activity(text: Any, limit: int = 1200) -> str:
    value = " ".join(str(text or "").replace("\r", " ").replace("\n", " ").split())
    return value[:limit] + ("…" if len(value) > limit else "")


def _activity_markdown(part: Any, lang: str, result_names: Optional[Dict[str, str]] = None) -> str:
    """一个工具/思考/子代理块 → QTextDocument 能渲染的引用卡。

    原版是时间线卡片；QTextDocument 的 Markdown 渲染器没有可折叠卡片，改用
    blockquote（左侧竖条 + 缩进）承载标题与摘要，信息等价且不依赖 QtWebEngine。
    """
    kind = str(getattr(part, "type", "") or "")
    if kind == "thinking":
        return "> **%s**\n>\n> %s" % (
            translate(_locale(lang), "chat.thinking"),
            _clip_activity(getattr(part, "text", "") or getattr(part, "thinking", "")),
        )
    if kind == "tool_use":
        name = str(getattr(part, "name", "") or "")
        args = getattr(part, "input", None)
        detail = _clip_activity(json.dumps(args, ensure_ascii=False, sort_keys=True) if args is not None else "")
        return "> **%s** · `%s`\n>\n> %s" % (_activity_label(part, lang), name, detail or "—")
    if kind == "tool_result":
        tool_id = str(getattr(part, "toolUseId", "") or "")
        name = (result_names or {}).get(tool_id, tool_id)
        state = "失败" if bool(getattr(part, "isError", False)) else "成功"
        if lang == "en":
            state = "failed" if bool(getattr(part, "isError", False)) else "ok"
        return "> **%s** · `%s` · %s\n>\n> %s" % (
            _activity_label(part, lang), name, state,
            _clip_activity(getattr(part, "content", "") or ""),
        )
    return ""


def _tool_result_names(messages: List[Any]) -> Dict[str, str]:
    names: Dict[str, str] = {}
    for message in messages or []:
        content = getattr(message, "content", None)
        if not isinstance(content, list):
            continue
        for part in content:
            if str(getattr(part, "type", "") or "") == "tool_use":
                names[str(getattr(part, "id", "") or "")] = str(getattr(part, "name", "") or "")
    return names


def transcript_markdown(
    messages: List[Any],
    pending_user: Optional[str] = None,
    streaming: Optional[str] = None,
    lang: str = "zh",
    include_activity: bool = False,
) -> str:
    """落盘消息（+ 本轮进行中的用户消息与流式增量）→ 一份正文 Markdown。

    顺序即落盘顺序；没有正文的消息（纯工具调用 / 纯工具结果）跳过。`pending_user`
    与 `streaming` 只在回合进行中使用——用户消息在 `run_turn` 里才落盘，先显示要
    自己补；增量在 `done` 之后会以落盘消息为准重新拼一遍。

    用户消息的附件排在提问正文之前（与原版贴片顺序一致）：图片内联成 Markdown 图，
    文档/文本/文件夹/只给位置的附件各一行「附件：名 · 体积」。
    """
    blocks: List[str] = []
    result_names = _tool_result_names(messages or []) if include_activity else {}
    for msg_index, message in enumerate(messages or []):
        text = message_body(message)
        attachment_lines: List[str] = []
        content = getattr(message, "content", None)
        if str(getattr(message, "role", "")) == "user" and not isinstance(content, str):
            attachment_lines = _attachment_lines(list(content or []), msg_index, lang)
        pieces = list(attachment_lines)
        if include_activity and isinstance(content, list):
            # 按内容块真实顺序：正文、tool_use、tool_result、thinking 各自成段。
            for part in content or []:
                kind = str(getattr(part, "type", "") or "")
                if kind == "text":
                    part_text = str(getattr(part, "text", "") or "")
                    if part_text.startswith(_ATTACH_PREFIXES):
                        continue
                    if part_text.strip():
                        pieces.append(part_text.strip())
                else:
                    card = _activity_markdown(part, lang, result_names)
                    if card:
                        pieces.append(card)
        elif text.strip():
            pieces.append(text.strip())
        if not text.strip() and not pieces:
            continue
        blocks.append("%s\n\n%s" % (_role_heading(str(getattr(message, "role", "")), lang), "\n\n".join(pieces)))
    if pending_user and pending_user.strip():
        blocks.append("%s\n\n%s" % (_role_heading("user", lang), pending_user.strip()))
    if streaming is not None:
        # 空增量也起标题：界面上先出现「助手」，随后正文一段段长出来。
        blocks.append(("%s\n\n%s" % (_role_heading("assistant", lang), (streaming or "").strip())).rstrip())
    return "\n\n".join(blocks)


def delivery_tool_use_ids(messages: List[Any]) -> List[str]:
    """正文里出现过的 `present_files` 工具调用 id（按出现顺序，去重）。

    交付卡只认这些 id，再去边车取路径——与 `deliverables:inspect` 同一条安全不变式。
    """
    ids: List[str] = []
    for message in messages or []:
        content = getattr(message, "content", None)
        if isinstance(content, str):
            continue
        for part in content or []:
            if str(getattr(part, "type", "") or "") != "tool_use":
                continue
            if str(getattr(part, "name", "") or "") != "present_files":
                continue
            tool_id = str(getattr(part, "id", "") or "")
            if tool_id and tool_id not in ids:
                ids.append(tool_id)
    return ids


def delivery_rows(session: Any) -> List[Dict[str, Any]]:
    """当前会话的交付卡行：`present_files` 调用 id → 边车 `delivered` → 真实文件信息。

    没有会话 / 没有边车时返回空列表（界面不画卡）。每行带 `sizeText`（真实体积文案）
    与 `missing`（文件已不存在），QML 直接用，不再自己算。
    """
    if session is None:
        return []
    ids = delivery_tool_use_ids(getattr(session, "messages", None) or [])
    rows: List[Dict[str, Any]] = []
    seen: set = set()
    for tool_id in ids:
        for path in delivered_paths(session, tool_id):
            if path in seen:
                continue
            seen.add(path)
            row = delivery_row(path)
            row["sizeText"] = format_bytes(row["size"]) if row["size"] is not None else ""
            row["missing"] = row["size"] is None
            row["toolUseId"] = tool_id
            rows.append(row)
    return rows


def attachment_rows(session: Any) -> List[Dict[str, Any]]:
    """当前会话里的用户附件贴片（供 QML 侧画缩略图条；正文里已经内联图片）。

    每行：名称 / 类型 / 真实体积文案 / 图片的 data URI（非图片为空串）/ 所属消息下标。
    图片 data URI 直接取自落盘消息，不额外读盘。
    """
    if session is None:
        return []
    rows: List[Dict[str, Any]] = []
    for msg_index, message in enumerate(getattr(session, "messages", None) or []):
        content = getattr(message, "content", None)
        if str(getattr(message, "role", "")) != "user" or isinstance(content, str):
            continue
        parts = list(content or [])
        for chip in attachment_chips(parts, msg_index):
            row = dict(chip)
            row["index"] = msg_index
            row["thumb"] = ""
            part_index = chip.get("partIndex")
            if chip.get("kind") == "image" and isinstance(part_index, int) and 0 <= part_index < len(parts):
                data = str(getattr(parts[part_index], "data", "") or "")
                mime = str(getattr(parts[part_index], "mediaType", "") or "image/png")
                row["thumb"] = "data:%s;base64,%s" % (mime, data) if data else ""
            row["sizeText"] = format_bytes(row.get("size")) if row.get("size") is not None else ""
            rows.append(row)
    return rows


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
        # 真实活动块：thinking / tool_call / tool_result，按事件顺序保存。
        self.activities: List[Dict[str, Any]] = []

    def _append_activity(self, kind: str, text: str) -> None:
        if self.activities and self.activities[-1].get("kind") == kind:
            self.activities[-1]["text"] += text
        else:
            self.activities.append({"kind": kind, "text": text})

    def apply(self, event: Dict[str, Any]) -> bool:
        kind = event.get("type")
        if kind == "text_delta":
            self.stream += str(event.get("text") or "")
            self._append_activity("text", str(event.get("text") or ""))
            return True
        if kind == "thinking_delta":
            self._append_activity("thinking", str(event.get("text") or ""))
            return True
        if kind == "tool_call":
            self._append_activity("tool_call", json.dumps({
                "name": event.get("name") or "", "args": event.get("args") or {},
            }, ensure_ascii=False))
            return True
        if kind == "tool_result":
            self._append_activity("tool_result", json.dumps({
                "name": event.get("name") or "", "summary": event.get("summary") or "",
                "isError": bool(event.get("isError")),
            }, ensure_ascii=False))
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

    def markdown(self, lang: str = "zh") -> str:
        """整篇正文：落盘历史 + 本轮用户消息 + 活动块/流式增量。"""
        if not self.activities:
            tail = transcript_markdown([], pending_user=self.pending_user, streaming=self.stream, lang=lang)
            pieces = [self.base] if self.base.strip() else []
            if tail.strip():
                pieces.append(tail)
            return "\n\n".join(pieces)
        pieces = [self.base] if self.base.strip() else []
        if self.pending_user and self.pending_user.strip():
            pieces.append("%s\n\n%s" % (_role_heading("user", lang), self.pending_user.strip()))
        body = []
        for item in self.activities:
            kind = item["kind"]
            text = item["text"]
            if kind == "text":
                body.append(text)
            elif kind == "thinking":
                body.append("> **%s**\n>\n> %s" % (translate(_locale(lang), "chat.thinking"), _clip_activity(text)))
            elif kind == "tool_call":
                try:
                    payload = json.loads(text)
                except Exception:
                    payload = {"name": text, "args": {}}
                body.append("> **%s** · `%s`\n>\n> %s" % (
                    _tool_label(str(payload.get("name") or ""), lang), str(payload.get("name") or ""),
                    _clip_activity(json.dumps(payload.get("args") or {}, ensure_ascii=False, sort_keys=True))))
            elif kind == "tool_result":
                try:
                    payload = json.loads(text)
                except Exception:
                    payload = {"name": text, "summary": "", "isError": False}
                state = ("失败" if payload.get("isError") else "成功") if lang != "en" else ("failed" if payload.get("isError") else "ok")
                body.append("> **%s** · `%s` · %s\n>\n> %s" % (
                    translate(_locale(lang), "chat.tool.result"), str(payload.get("name") or ""), state,
                    _clip_activity(payload.get("summary") or "")))
        if body:
            pieces.append("%s\n\n%s" % (_role_heading("assistant", lang), "\n\n".join(body)))
        return "\n\n".join(pieces)


__all__ = [
    "ASSISTANT_HEADING",
    "PREVIEW_MAX",
    "TurnState",
    "USER_HEADING",
    "attachment_rows",
    "delivery_rows",
    "delivery_tool_use_ids",
    "format_bytes",
    "message_body",
    "preview_text",
    "session_row",
    "session_rows",
    "time_label",
    "transcript_markdown",
]
