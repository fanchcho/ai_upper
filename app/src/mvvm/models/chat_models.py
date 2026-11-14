"""Deva 对话数据模型（pydantic）。

字段口径以 Deva `apps/desktop/src/main/providers/types.ts`（Message / ContentPart）与
`apps/desktop/src/main/services/chat-store.ts`（StoredSession / ChatSessionMeta / StoredNotice）
为准。与 Deva 的 JSON 文件逐字段兼容是硬要求：历史文件里还有 `bucket` 等已废弃字段，
未知字段一律保留（``extra="allow"``），读进来再写回去不能丢东西。

时间戳沿用 Deva 的毫秒整数（``Date.now()``），不用 datetime：同一份 ``data/chats``
目录两边都要能读，多一种表示就多一次转换出错的机会。
"""
from __future__ import annotations

import sys
import time
import types
from typing import Any, Dict, List, Literal, Optional, Union

# `typing.Annotated` 是 3.9 才有的名字。这里按解释器版本显式分支，而不是
# `try: from typing import ...; except ImportError:`——后者会把「3.8 上没有」
# 和「typing_extensions 没装」两类不同的故障混成一个静默回退，装漏了依赖也照样过。
if sys.version_info >= (3, 9):
    from typing import Annotated
else:  # 3.8：Annotated 由 typing_extensions 提供（已列入 app/requirements.txt）
    from typing_extensions import Annotated

from pydantic import BaseModel, ConfigDict, Field

MessageRole = Literal["user", "assistant"]
StopReason = Literal[
    "end_turn",
    "tool_use",
    "max_tokens",
    "stop",
    "refusal",
    "aborted",
    "error",
    "step_limit",
    "repeated",
    "degenerate",
]


def now_ms() -> int:
    """当前时间（毫秒），与 Deva 的 Date.now() 同一口径。"""
    return int(time.time() * 1000)


def _method_types() -> tuple[type, ...]:
    """本工程的模型可以带普通方法，而 Cython 会把它们编译成另一种类型。

    打包时应用源码被 Cython 编译成一个合并扩展，类体里的 ``def`` 不再是
    ``types.FunctionType``，而 pydantic 建类时只按类型忽略方法
    （``_model_construction.default_ignored_types``），于是编译后的
    ``Message.text`` 被判成「无注解字段」，**打包产物一启动就抛
    PydanticUserError**——源码态测试全绿，只有真跑产物才会暴露。

    这里把编译后的方法类型补进 ``ignored_types``。类型从模块自身的函数上取，
    而不是 import ``cython``：产物里没有 Cython 运行时，未编译时该类型就是
    ``types.FunctionType``（pydantic 默认已忽略，不必重复列）。
    """
    method_type = type(now_ms)
    if method_type is types.FunctionType:
        return ()
    return (method_type,)


class _Model(BaseModel):
    """所有对话模型的共同配置：未知字段保留，按字段名填充。"""

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
        # 编译后的方法必须被当成方法，不能当成字段（见 `_method_types`）。
        ignored_types=_method_types(),
    )


class TextPart(_Model):
    type: Literal["text"] = "text"
    text: str
    # 清单块（技能/记忆/成员告知记录），Deva 只在主进程内部使用；保留以便原样写回。
    listing: Optional[Dict[str, Any]] = None


class ToolUsePart(_Model):
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: Any = None


class ImagePart(_Model):
    type: Literal["image"] = "image"
    mediaType: str
    data: str
    name: Optional[str] = None


class DocumentPart(_Model):
    type: Literal["document"] = "document"
    mediaType: str
    data: str
    name: Optional[str] = None


class ToolResultPart(_Model):
    type: Literal["tool_result"] = "tool_result"
    toolUseId: str  # noqa: N815 - 与 Deva 的 JSON 字段名一致
    content: str
    isError: Optional[bool] = None  # noqa: N815
    images: Optional[List[ImagePart]] = None
    listing: Optional[Dict[str, Any]] = None


ContentPart = Annotated[
    Union[TextPart, ToolUsePart, ToolResultPart, ImagePart, DocumentPart],
    Field(discriminator="type"),
]


class Message(_Model):
    """一条模型上下文消息。content 可以是纯文本，也可以是内容块数组（Anthropic 风味）。"""

    role: MessageRole
    content: Union[str, List[ContentPart]]

    def text(self) -> str:
        """只取文本部分，按顺序拼接（展示用；工具调用不算正文）。"""
        if isinstance(self.content, str):
            return self.content
        return "".join(p.text for p in self.content if isinstance(p, TextPart))


class StoredNotice(_Model):
    """回合终态提示（错误红框/截断/空回合/中止），Deva 的展示边车，不属于模型上下文。"""

    after: int
    kind: Literal["error", "notice"]
    message: Optional[str] = None
    code: Optional[str] = None


class CompactedRef(_Model):
    """已拆分到 `.jsonl` 的早期消息段：前 count 条在 file 里。"""

    count: int
    file: str


class StoredSession(_Model):
    """一条对话的完整落盘结构（`data/chats/<id>.json`）。"""

    id: str
    title: str = ""
    createdAt: int = Field(default_factory=now_ms)  # noqa: N815 - Deva 字段名
    updatedAt: int = Field(default_factory=now_ms)  # noqa: N815
    messages: List[Message] = Field(default_factory=list)

    compacted: Optional[CompactedRef] = None
    lastInputTokens: Optional[int] = None  # noqa: N815
    lastCacheRead: Optional[int] = None  # noqa: N815
    lastCacheWrite: Optional[int] = None  # noqa: N815
    lastRequestAt: Optional[int] = None  # noqa: N815
    personaId: Optional[str] = None  # noqa: N815
    focusRoot: Optional[str] = None  # noqa: N815
    # 模型引用 "providerId:modelId"；空串/缺省 = 跟随全局默认（Deva 的语义）。
    model: Optional[str] = None
    effort: Optional[str] = None
    archived: Optional[bool] = None
    members: Optional[List[Dict[str, Any]]] = None
    parentId: Optional[str] = None  # noqa: N815
    notices: Optional[List[StoredNotice]] = None
    proposals: Optional[Dict[str, str]] = None
    asks: Optional[Dict[str, Dict[str, Any]]] = None
    summaries: Optional[Dict[str, str]] = None
    delivered: Optional[Dict[str, List[str]]] = None
    background: Optional[Dict[str, str]] = None
    durations: Optional[Dict[str, int]] = None
    plans: Optional[Dict[str, Dict[str, Any]]] = None
    autotasks: Optional[Dict[str, Dict[str, Any]]] = None
    todos: Optional[List[Dict[str, Any]]] = None
    todoCancelled: Optional[List[str]] = None  # noqa: N815
    todoCancelNote: Optional[str] = None  # noqa: N815
    checkpoints: Optional[Dict[str, List[Dict[str, Any]]]] = None
    lastKnown: Optional[Dict[str, Optional[str]]] = None  # noqa: N815
    baselines: Optional[Dict[str, Optional[str]]] = None
    restoreNote: Optional[str] = None  # noqa: N815

    def meta(self) -> "ChatSessionMeta":
        """左侧列表用的元信息（不含正文），与 Deva 的 metaOf 同口径。"""
        return ChatSessionMeta(
            id=self.id,
            title=self.title,
            createdAt=self.createdAt,
            updatedAt=self.updatedAt,
            personaId=self.personaId,
            focusRoot=self.focusRoot,
            model=self.model,
            effort=self.effort,
            archived=self.archived,
            members=self.members,
            parentId=self.parentId,
        )

    def touch(self) -> None:
        """更新修改时间（Deva 在 append/save 时刷新）。"""
        self.updatedAt = now_ms()


class ChatSessionMeta(_Model):
    """会话元信息（`_index.json` 的元素，不含正文）。"""

    id: str
    title: str = ""
    createdAt: int = Field(default_factory=now_ms)  # noqa: N815
    updatedAt: int = Field(default_factory=now_ms)  # noqa: N815
    personaId: Optional[str] = None  # noqa: N815
    focusRoot: Optional[str] = None  # noqa: N815
    model: Optional[str] = None
    effort: Optional[str] = None
    archived: Optional[bool] = None
    members: Optional[List[Dict[str, Any]]] = None
    parentId: Optional[str] = None  # noqa: N815


__all__ = [
    "ChatSessionMeta",
    "CompactedRef",
    "ContentPart",
    "DocumentPart",
    "ImagePart",
    "Message",
    "MessageRole",
    "StoredNotice",
    "StoredSession",
    "StopReason",
    "TextPart",
    "ToolResultPart",
    "ToolUsePart",
    "now_ms",
]
