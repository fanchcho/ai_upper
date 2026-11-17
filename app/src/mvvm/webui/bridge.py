"""宿主侧的展示层转换：存储消息 → QML 壳正文/工具卡需要的形状。

本模块原先还承载 QtWebChannel 的桥对象（`DevaBridge`），把原版渲染层的
`window.deva` 调用分发到 Python 服务。用户已裁决「唯一界面 = QML 壳 + QTextDocument」，
WebEngine 承载窗口与那条桥一并删除，只剩 QML 壳仍在用的这两件：

- `BridgeError`：回合宿主（`mvvm.webui.host`）对外报告「这次调用不合法」的错误类型；
- `display_messages`：把落盘消息转换成展示形状（合并 assistant 段、回填工具卡状态、
  还原附件贴片）。QML 壳重建历史、`turn_start` 增量、删除轮次后的回显都走它。

**这是唯一一份转换**：QML 壳重建历史、`turn_start` 增量、删除轮次后的回显都调它，
形状一变界面立刻跟着变——改它之前先看 `app/tests/test_qml_chat_files.py`（正文/附件贴片形状）
与 `app/tests/test_host_write.py`（宿主回显的入口形状）。
"""
from __future__ import annotations

from typing import Any

from mvvm.services.transcript_parts import attachment_chips


# 后台任务通知前缀，与 Deva `main/services/compaction.ts` 的 NOTIFY_MARKER 同值。
NOTIFY_MARKER = "⟦deva:notify⟧"


class BridgeError(RuntimeError):
    """宿主调用不合法时抛出的错误（`mvvm.webui.host` 用它区分「拒绝」与「崩溃」）。"""


def display_messages(
    messages: list[Any], index_base: int = 0
) -> list[dict[str, Any]]:
    """存储消息 → Deva 的 `DisplayMessage[]`（渲染层重建历史用）。

    规则照抄原版 `main/services/chat.ts` 的 `toDisplayMessages`，界面才与重开原版会话一致：
    - 同一轮内、只被 tool_result（user 角色）隔开的连续 assistant 段**并入上一条展示气泡**——
      有工具调用时一轮在持久化历史里是多条 assistant，逐条成气泡会重开后每段各显一个头像；
    - tool_result 不单独成气泡，而是按 toolUseId **回填**上一条 assistant 里那张工具卡的 status；
    - 真实用户消息把合并链断开（lastAssistant = None），其后的 assistant 另起新气泡；
    - 用户消息的附件按原版重建为贴片：图片 `{name,kind:image,size,ref}`、PDF `{name,kind:document,size}`、
      文本注入块按前缀标记还原 `{name,kind:text,size}`、文件夹/只给位置的文件 `{name,kind,path}`。
      图片**不回传 base64**，界面按 `ref`（`消息下标:块下标:指纹`）现取。

    `index_base`：`messages` 首条在整份对话记录里的下标。只转换末尾几条时（`turn_start`）
    图片 ref 仍要指向记录里的真实位置，否则按 ref 取图时对不上指纹。
    形状仍沿用原 Electron 版 `toDisplayMessages` 的 `DisplayMessage` / `DisplayBlock` / `AttachmentChip`。
    """
    out: list[dict[str, Any]] = []
    last_assistant: dict[str, Any] | None = None

    for offset, message in enumerate(messages):
        msg_index = index_base + offset
        content = getattr(message, "content", None)
        role = getattr(message, "role", "")

        if role == "assistant":
            parts = [{"type": "text", "text": content}] if isinstance(content, str) else list(content or [])
            blocks: list[dict[str, Any]] = []
            for part in parts:
                kind = getattr(part, "type", "")
                if kind == "text":
                    text = str(getattr(part, "text", ""))
                    if text:
                        blocks.append({"kind": "text", "text": text})
                elif kind == "tool_use":
                    blocks.append(
                        {
                            "kind": "tool",
                            "id": str(getattr(part, "id", "")),
                            "name": str(getattr(part, "name", "")),
                            "args": getattr(part, "input", {}) or {},
                            "status": "ok",
                        }
                    )
            if last_assistant is not None:
                last_assistant["blocks"].extend(blocks)
            else:
                last_assistant = {"role": "assistant", "blocks": blocks}
                out.append(last_assistant)
            continue

        # ── user ──────────────────────────────────────────────────────────
        if isinstance(content, str):
            if content.startswith(NOTIFY_MARKER):
                out.append(
                    {
                        "role": "user",
                        "text": _notify_headline(content[len(NOTIFY_MARKER) :]),
                        "attachments": [],
                        "notify": True,
                    }
                )
            else:
                out.append({"role": "user", "text": content, "attachments": []})
            last_assistant = None
            continue

        parts = list(content or [])
        if any(getattr(p, "type", "") == "tool_result" for p in parts):
            # 工具结果回灌：回填工具卡状态，不生成气泡、也不断开合并链。
            if last_assistant is not None:
                cards = {
                    b.get("id"): b
                    for b in last_assistant["blocks"]
                    if b.get("kind") == "tool" and b.get("id")
                }
                for part in parts:
                    if getattr(part, "type", "") != "tool_result":
                        continue
                    card = cards.get(str(getattr(part, "toolUseId", "")))
                    if card is None:
                        continue
                    card["status"] = "error" if getattr(part, "isError", False) else "ok"
            continue

        # 真实用户消息（可能带附件）：附件贴片在前、提问正文在最后一个 text 块。
        text_parts = [str(getattr(p, "text", "")) for p in parts if getattr(p, "type", "") == "text"]
        attachments = attachment_chips(parts, msg_index)
        out.append(
            {
                "role": "user",
                "text": text_parts[-1] if text_parts else "",
                "attachments": attachments,
            }
        )
        last_assistant = None
    return out


def _notify_headline(body: str) -> str:
    """后台任务通知：原版取标记后的首行作标题（`noticeHeadline`）。"""
    line = body.lstrip("\n").split("\n", 1)[0]
    return line.strip()


__all__ = [
    "BridgeError",
    "NOTIFY_MARKER",
    "display_messages",
]
