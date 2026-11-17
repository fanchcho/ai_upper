"""附件服务：附件白名单 + 发送时把授权过的文件读成内容块。

对齐 Deva `apps/desktop/src/main/services/attachments.ts` 里**QML 壳仍在使用**的部分：

- **附件白名单**：只有用户亲手选中的路径才可读。选择动作由壳里的
  `QFileDialog` 触发，这里只判「这个路径是不是被用户选过」——白名单是内存态，
  重启即清空；
- **体积 / 类型限额只此一处**：选择框与发送共用 `inspect()`；
- **发送**：`build_attachment_part()` 把已授权附件读成图 / PDF / 文本内容块，读不进时
  回一条 note 拼进正文，不假装成功。

历史说明：原版还有 `fs:paste-attachment` / `fs:dropped-entries` / `fs:attachment-image`
/ `fs:read-dir` / `fs:read-file` / `fs:write-file` / `fs:open-folder` / `fs:reveal-folder`
八条渲染层通道，它们唯一的调用方是已删除的 `DevaBridge`（QtWebChannel）。QML 壳不走
IPC：附件选择直接调 `pick_attachments()`，发送直接调 `build_attachment_part()`，
工作区文件读写走 `ToolRuntime` 自己的守卫，因此那些通道与只为它们服务的辅助函数
一并删除，而不是留成没有调用方的死代码。

能力差异要如实记：QML 壳只有一个「回形针」入口，**没有**拖入与粘贴附件（web 入口当年
有）。`allowed_dirs` 与 `[附件文件夹]` 分支保留，是因为历史消息里可能已有这类注入块，
发送侧仍需能拼出同样的提示；但当前没有任何路径会往 `allowed_dirs` 里写。
"""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from mvvm.services.image_prep import sniff_image_mime
from mvvm.services.workspace_guard import WorkspaceGuard

# ── 类型判定（与 attachments.ts 的 classify / IMAGE_MIME / TEXT_EXT 同表）────────
IMAGE_MIME = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

TEXT_EXT = frozenset(
    (
        ".txt .md .markdown .json .jsonc .yaml .yml .toml .ini .csv .tsv .log "
        ".js .jsx .ts .tsx .mjs .cjs .vue .svelte "
        ".html .htm .css .scss .less .xml .svg "
        ".py .rb .go .rs .java .kt .kts .c .h .cpp .hpp .cc .cs .php "
        ".swift .m .mm .sh .bash .zsh .ps1 .bat .sql .gradle .properties "
        ".env .r .dart .lua .pl .dockerfile .makefile .cmake"
    ).split()
)

MAX_IMAGE = 5 * 1024 * 1024
MAX_PDF = 20 * 1024 * 1024
MAX_TEXT = 512 * 1024

# 附件注入消息时的前缀标记：历史重建靠它们认出「这是附件而不是提问正文」。
ATTACH_TEXT_PREFIX = "[附件文件] "
ATTACH_FOLDER_PREFIX = "[附件文件夹] "
ATTACH_PATH_PREFIX = "[附件文件路径] "


def classify(ext: str) -> str:
    """扩展名 → image / document / text / unsupported。"""
    lowered = ext.lower()
    if lowered in IMAGE_MIME:
        return "image"
    if lowered == ".pdf":
        return "document"
    if lowered in TEXT_EXT:
        return "text"
    return "unsupported"


def format_size(size: int) -> str:
    """附件位置提示里的体积写法（与原版 buildAttachmentPart 一致）。"""
    if size < 1024 * 1024:
        return f"{max(1, round(size / 1024))} KB"
    return f"{size / 1024 / 1024:.1f} MB"


@dataclass(frozen=True)
class AttachmentPart:
    """一份附件读进消息后的结果：`part` 与 `note` 至少有一个（原版语义）。"""

    part: Optional[Any] = None
    note: Optional[str] = None


class AttachmentService:
    """附件白名单 + 发送时读取。纯 Python，Qt 不参与（缩略图由落盘消息直接给 data URI）。"""

    def __init__(
        self,
        home: Path,
        guard: Optional[WorkspaceGuard] = None,
    ) -> None:
        self.home = Path(home)
        self.guard = guard if guard is not None else WorkspaceGuard()
        # 白名单：能读进消息的 / 只给位置的。
        self.allowed: set[str] = set()
        self.allowed_files: set[str] = set()
        self.allowed_dirs: set[str] = set()
        self._dialog_files: Optional[Callable[[], Optional[list[str]]]] = None

    # ── 宿主注入的外部能力（没注入就显式报错，不假成功）─────────────────────
    def set_file_dialogs(
        self,
        *,
        pick_files: Optional[Callable[[], Optional[list[str]]]] = None,
    ) -> None:
        """注入原生选择框：Qt 实现由 QML 壳给，测试可用假回调。"""
        self._dialog_files = pick_files

    def _require(self, value: Optional[Callable[..., Any]], what: str) -> Callable[..., Any]:
        if value is None:
            raise RuntimeError(f"{what}未接线：需要宿主注入系统对话框")
        return value

    # ── 类型 / 体积判定（选择框与发送共用）───────────────────────────────────
    def inspect(self, absolute: str, size: int, by_path: bool = True) -> dict[str, Any]:
        """判一份文件能否读进消息；合规登记白名单，不合规按原版口径给原因。"""
        abspath = os.path.abspath(absolute)
        name = os.path.basename(abspath)
        ext = os.path.splitext(abspath)[1].lower()
        kind = classify(ext)
        reason: Optional[str] = None
        if kind == "unsupported":
            reason = "暂不支持的文件类型"
        elif kind == "image" and size > MAX_IMAGE:
            reason = "图片过大（>5MB）"
        elif kind == "document" and size > MAX_PDF:
            reason = "PDF 过大（>20MB）"
        elif kind == "text" and size > MAX_TEXT:
            reason = "文本过大（>512KB）"
        if reason is None:
            self.allowed.add(abspath)
            return {"path": abspath, "name": name, "ext": ext, "size": size, "kind": kind, "supported": True}
        if by_path:
            self.allowed_files.add(abspath)
            return {"path": abspath, "name": name, "ext": ext, "size": size, "kind": "file", "supported": True}
        return {
            "path": abspath,
            "name": name,
            "ext": ext,
            "size": size,
            "kind": kind,
            "supported": False,
            "reason": reason,
        }

    # ── 选择附件 ──────────────────────────────────────────────────────────
    def pick_attachments(self) -> list[dict[str, Any]]:
        picker = self._require(self._dialog_files, "选择附件对话框")
        picked = picker() or []
        out: list[dict[str, Any]] = []
        for raw in picked:
            if not isinstance(raw, str) or not raw:
                continue
            absolute = os.path.abspath(raw)
            try:
                size = Path(absolute).stat().st_size
            except OSError:
                size = 0
            out.append(self.inspect(absolute, size))
        return out

    # ── 发送：把已授权附件读成内容块 ──────────────────────────────────────
    def build_attachment_part(self, path: Any, adapter: str = "anthropic") -> AttachmentPart:
        """附件 → 内容块（图 / PDF / 文本注入 / 只给位置）；读不进时回一条 note 拼进正文。"""
        if not isinstance(path, str) or not path:
            return AttachmentPart(note="已忽略未授权文件：")
        absolute = os.path.abspath(path)
        name = os.path.basename(absolute)
        if absolute in self.allowed_dirs:
            return AttachmentPart(
                part=_text_part(
                    f"{ATTACH_FOLDER_PREFIX}{absolute}\n"
                    "（用户附上了这个文件夹的位置，内容未展开；需要时用 list_dir / glob / grep / "
                    "read_file 按绝对路径查看）"
                )
            )
        if absolute in self.allowed_files:
            target = Path(absolute)
            if not target.is_file():
                return AttachmentPart(note=f"文件已不存在：{name}")
            return AttachmentPart(
                part=_text_part(
                    f"{ATTACH_PATH_PREFIX}{absolute}\n"
                    f"（用户附上了这个文件（{format_size(target.stat().st_size)}），内容没有直接放进消息；"
                    "需要时按上面的绝对路径读取：.docx / .xlsx / .pptx 用 read_file 可读出文字，"
                    "其他格式视情况用命令或技能处理）"
                )
            )
        if absolute not in self.allowed:
            return AttachmentPart(note=f"已忽略未授权文件：{name}")
        kind = classify(os.path.splitext(absolute)[1])
        try:
            data = Path(absolute).read_bytes()
        except OSError:
            return AttachmentPart(note=f"读取失败已忽略：{name}")
        if kind == "image":
            if len(data) > MAX_IMAGE:
                return AttachmentPart(note=f"图片过大已忽略：{name}")
            mime = IMAGE_MIME.get(os.path.splitext(absolute)[1].lower()) or sniff_image_mime(data)
            if not mime:
                return AttachmentPart(note=f"已忽略不支持的文件：{name}")
            return AttachmentPart(part=_image_part(mime, data, name))
        if kind == "document":
            if adapter == "openai":
                return AttachmentPart(note=f"PDF「{name}」需使用 Anthropic 或 OpenAI Responses 协议的模型才能读取，本次已跳过")
            if len(data) > MAX_PDF:
                return AttachmentPart(note=f"PDF 过大已忽略：{name}")
            return AttachmentPart(part=_document_part("application/pdf", data, name))
        if kind == "text":
            if len(data) > MAX_TEXT:
                return AttachmentPart(note=f"文本过大已忽略：{name}")
            body = data.decode("utf-8", errors="replace")
            return AttachmentPart(part=_text_part(f"{ATTACH_TEXT_PREFIX}{name}\n```\n{body}\n```"))
        return AttachmentPart(note=f"已忽略不支持的文件：{name}")


def _text_part(text: str) -> Any:
    from mvvm.models.chat_models import TextPart

    return TextPart(text=text)


def _image_part(mime: str, data: bytes, name: str) -> Any:
    from mvvm.models.chat_models import ImagePart

    return ImagePart(mediaType=mime, data=base64.b64encode(data).decode("ascii"), name=name)


def _document_part(mime: str, data: bytes, name: str) -> Any:
    from mvvm.models.chat_models import DocumentPart

    return DocumentPart(mediaType=mime, data=base64.b64encode(data).decode("ascii"), name=name)


__all__ = [
    "ATTACH_FOLDER_PREFIX",
    "ATTACH_PATH_PREFIX",
    "ATTACH_TEXT_PREFIX",
    "AttachmentPart",
    "AttachmentService",
    "IMAGE_MIME",
    "MAX_IMAGE",
    "MAX_PDF",
    "MAX_TEXT",
    "TEXT_EXT",
    "classify",
    "format_size",
]
