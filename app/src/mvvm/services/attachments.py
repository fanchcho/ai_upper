"""附件与工作区文件服务：`fs:*` 九条通道 + `chat:attachment-image` 的 Python 实现。

逐条对齐 Deva `apps/desktop/src/main/services/attachments.ts` 与 `workspace.ts`：

- **附件白名单**：只有用户亲手选中 / 拖入 / 粘贴的路径才可读。渲染层可以伪造任意字符串参数，
  但伪造不出「曾被 pick / drop / paste 过」这件事——白名单是内存态，重启即清空；
- **粘贴落地**：渲染层只交字节、不交路径；这里写到临时目录再走同一套白名单。白名单与临时文件
  都只活到发送前，启动时清空粘贴目录（与原版 `registerAttachmentsIpc` 的第一行同语义）；
- **体积 / 类型限额只此一处**：选择框、拖入、粘贴共用 `inspect()`；
- **工作区读写**：`read_dir` / `read_file` / `write_file` 必须过 `WorkspaceGuard`（越界抛
  `拒绝访问：路径不在已打开的项目内`），这是本工程的安全底线。

未迁移的部分照原样不假装：原生选择框与「在文件管理器里打开」通过**注入的回调**完成，
宿主没注入时抛 `BridgeError`（界面显示错误），不返回假成功。
"""
from __future__ import annotations

import base64
import hashlib
import os
import shutil
import tempfile
import time
import uuid
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

# 工作区文件读写限额（workspace.ts）。
MAX_FILE_BYTES = 2 * 1024 * 1024
BINARY_SNIFF_BYTES = 8000

DENIED = "拒绝访问：路径不在已打开的项目内"

# 缩略图（image-read.ts）：短边 240、长边 960。
THUMB_SHORT = 240
THUMB_LONG = 960


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


def looks_binary(buf: bytes) -> bool:
    """前 8000 字节里有 0 字节即判二进制（与 workspace.ts 的 looksBinary 同阈值）。"""
    return b"\x00" in buf[:BINARY_SNIFF_BYTES]


def paste_name(raw: str, mime: str) -> str:
    """粘贴文件名清洗：剥路径与 Windows 非法字符；无名 / image.xxx 按本地时间戳重命名。"""
    clean = os.path.basename(raw or "")
    for ch in '<>:"/|?*' + "".join(chr(c) for c in range(0x20)):
        clean = clean.replace(ch, "_")
    clean = clean.strip()
    if clean and not set(clean) <= {"."} and not _is_generic_image_name(clean):
        return clean
    ext = os.path.splitext(clean)[1] or (
        "." + mime[6:].replace("jpeg", "jpg") if mime.startswith("image/") else ""
    )
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
    return f"粘贴-{stamp}{ext}"


def _is_generic_image_name(name: str) -> bool:
    stem, ext = os.path.splitext(name)
    return stem.lower() == "image" and bool(ext)


def thumbnail_data_url(buf: bytes, mime: str) -> str:
    """图片 → 缩略图 data URI；解不开或原图已够小则原样返回（同 image-read.ts）。"""
    original = f"data:{mime};base64,{base64.b64encode(buf).decode('ascii')}"
    try:
        from utils.qt_compat import QtCore, QtGui

        image = QtGui.QImage.fromData(buf)
    except Exception:  # noqa: BLE001 - 无 Qt / 解码器缺失按「原样返回」处理
        return original
    if image is None or image.isNull():
        return original
    width, height = image.width(), image.height()
    if width <= 0 or height <= 0:
        return original
    scale = min(1.0, THUMB_SHORT / min(width, height), THUMB_LONG / max(width, height))
    if scale >= 1:
        return original
    scaled = image.scaled(
        max(1, round(width * scale)),
        max(1, round(height * scale)),
        QtCore.Qt.AspectRatioMode.KeepAspectRatio,
        QtCore.Qt.TransformationMode.SmoothTransformation,
    )
    if mime == "image/jpeg":
        data = _encode(scaled, "JPEG", 85)
        return "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")
    data = _encode(scaled, "PNG")
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def _encode(image: Any, fmt: str, quality: int = -1) -> bytes:
    from utils.qt_compat import QtCore

    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    if quality >= 0:
        image.save(buffer, fmt, quality)
    else:
        image.save(buffer, fmt)
    return bytes(buffer.data())


@dataclass(frozen=True)
class AttachmentPart:
    """一份附件读进消息后的结果：`part` 与 `note` 至少有一个（原版语义）。"""

    part: Optional[Any] = None
    note: Optional[str] = None


class AttachmentService:
    """附件白名单 + 工作区文件读写。纯 Python，Qt 只在需要缩略图 / 图标时惰性导入。"""

    def __init__(
        self,
        home: Path,
        guard: Optional[WorkspaceGuard] = None,
        *,
        paste_dir: Optional[Path] = None,
    ) -> None:
        self.home = Path(home)
        self.guard = guard if guard is not None else WorkspaceGuard()
        self.paste_dir = Path(paste_dir) if paste_dir else Path(tempfile.gettempdir()) / "deva-paste"
        # 白名单：能读进消息的 / 只给位置的 / 拖入的文件夹。
        self.allowed: set[str] = set()
        self.allowed_files: set[str] = set()
        self.allowed_dirs: set[str] = set()
        self.pasted: dict[str, dict[str, Any]] = {}
        # 用户亲手拖入的目录同时登记为受信根（与 fs-guard.trustRoot 同语义）。
        self._dialog_open: Optional[Callable[[], Optional[str]]] = None
        self._dialog_files: Optional[Callable[[], Optional[list[str]]]] = None
        self._open_path: Optional[Callable[[str], str]] = None
        # 启动即清空上一轮遗留的粘贴文件（原版在 registerAttachmentsIpc 里做同一件事）。
        shutil.rmtree(self.paste_dir, ignore_errors=True)

    # ── 宿主注入的外部能力（没注入就显式报错，不假成功）─────────────────────
    def set_file_dialogs(
        self,
        *,
        open_folder: Optional[Callable[[], Optional[str]]] = None,
        pick_files: Optional[Callable[[], Optional[list[str]]]] = None,
        open_path: Optional[Callable[[str], str]] = None,
    ) -> None:
        """注入原生选择框与「用系统程序打开」：Qt 实现由承载窗口给，测试可用假回调。"""
        self._dialog_open = open_folder
        self._dialog_files = pick_files
        self._open_path = open_path

    def _require(self, value: Optional[Callable[..., Any]], what: str) -> Callable[..., Any]:
        if value is None:
            raise RuntimeError(f"{what}未接线：需要宿主注入系统对话框")
        return value

    # ── 类型 / 体积判定（选择框、拖入、粘贴共用）─────────────────────────────
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

    # ── fs:paste-attachment ───────────────────────────────────────────────
    def paste_attachment(self, file: Any) -> dict[str, Any]:
        """渲染层交 {name,mime,size,data(Uint8Array|null)}；落盘到临时目录后按同一规则判定。

        `data` 在本工程里经 JSON 传输，是 0..255 的整数数组（QtWebChannel 没有二进制通道）。
        """
        payload = file if isinstance(file, dict) else {}
        raw = payload.get("data")
        data: Optional[bytes] = None
        if isinstance(raw, (bytes, bytearray)):
            data = bytes(raw)
        elif isinstance(raw, list):
            data = bytes(int(b) & 0xFF for b in raw if isinstance(b, int))
        name = paste_name(str(payload.get("name") or ""), str(payload.get("mime") or ""))
        size = data and len(data) or int(payload.get("size") or 0)
        key = hashlib.sha256(data).hexdigest() if data is not None else f"big:{name}:{size}"
        hit = self.pasted.get(key)
        if hit is not None:
            return hit
        absolute = str(self.paste_dir / str(uuid.uuid4()) / name)
        pre = self.inspect(absolute, size, by_path=data is not None)
        self.pasted[key] = pre
        if data is None or not pre.get("supported"):
            return pre
        try:
            Path(absolute).parent.mkdir(parents=True, exist_ok=True)
            Path(absolute).write_bytes(data)
        except OSError:
            self.pasted.pop(key, None)
            self.allowed.discard(os.path.abspath(absolute))
            raise
        return pre

    # ── fs:dropped-entries ────────────────────────────────────────────────
    def dropped_entries(self, paths: Any) -> list[Any]:
        """拖入条目：文件夹登记受信根并回位置，文件按同一规则判定，取不到路径的为 null。"""
        if not isinstance(paths, list):
            return []
        out: list[Any] = []
        for raw in paths:
            if not isinstance(raw, str) or not raw:
                out.append(None)
                continue
            absolute = os.path.abspath(raw)
            path = Path(absolute)
            if path.is_dir():
                self.allowed_dirs.add(absolute)
                self.guard.trust_root(absolute)
                out.append({"folder": {"path": absolute, "name": os.path.basename(absolute) or absolute}})
            elif path.is_file():
                out.append({"file": self.inspect(absolute, path.stat().st_size)})
            else:
                out.append(None)
        return out

    # ── fs:attachment-image ───────────────────────────────────────────────
    def attachment_image(self, path: Any, full: Any = False) -> Optional[str]:
        """输入框里的图片附件：缩略图或原图 data URI；未授权 / 非图片 / 读失败一律 null。"""
        if not isinstance(path, str) or not path:
            return None
        absolute = os.path.abspath(path)
        if absolute not in self.allowed or classify(os.path.splitext(absolute)[1]) != "image":
            return None
        try:
            buf = Path(absolute).read_bytes()
        except OSError:
            return None
        if len(buf) > MAX_IMAGE:
            return None
        mime = sniff_image_mime(buf) or IMAGE_MIME.get(os.path.splitext(absolute)[1].lower())
        if not mime:
            return None
        encoded = base64.b64encode(buf).decode("ascii")
        if full is True:
            return f"data:{mime};base64,{encoded}"
        return thumbnail_data_url(buf, mime)

    # ── fs:pick-attachments / fs:open-folder / fs:reveal-folder ────────────
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

    def open_folder(self) -> Optional[dict[str, str]]:
        chooser = self._require(self._dialog_open, "打开文件夹对话框")
        picked = chooser()
        if not picked:
            return None
        absolute = os.path.abspath(picked)
        self.guard.trust_root(absolute)
        return {"path": absolute, "name": os.path.basename(absolute) or absolute}

    def reveal_folder(self, dir_path: Any) -> dict[str, bool]:
        """只接受受信根内的目录：打开文件等于双击执行，绝不能给渲染层这个口子。"""
        if not isinstance(dir_path, str) or not dir_path:
            return {"ok": False}
        if not self.guard.is_inside_root(dir_path):
            return {"ok": False}
        absolute = os.path.abspath(dir_path)
        if not Path(absolute).is_dir():
            return {"ok": False}
        opener = self._require(self._open_path, "系统文件管理器")
        return {"ok": opener(absolute) == ""}

    # ── fs:read-dir / read-file / write-file ──────────────────────────────
    def read_dir(self, dir_path: Any) -> list[dict[str, str]]:
        if not isinstance(dir_path, str) or not dir_path:
            raise PermissionError(DENIED)
        absolute = str(self.guard.assert_inside(dir_path))
        entries: list[dict[str, str]] = []
        with os.scandir(absolute) as it:
            for entry in it:
                if entry.is_symlink():
                    continue
                if entry.is_dir():
                    kind = "dir"
                elif entry.is_file():
                    kind = "file"
                else:
                    continue
                entries.append({"name": entry.name, "path": os.path.join(absolute, entry.name), "type": kind})
        entries.sort(key=lambda e: (0 if e["type"] == "dir" else 1, e["name"].casefold()))
        return entries

    def read_file(self, file_path: Any) -> dict[str, Any]:
        if not isinstance(file_path, str) or not file_path:
            raise PermissionError(DENIED)
        absolute = str(self.guard.assert_inside(file_path))
        path = Path(absolute)
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            return {"path": absolute, "content": "", "tooLarge": True}
        buf = path.read_bytes()
        if looks_binary(buf):
            return {"path": absolute, "content": "", "binary": True}
        # Node 的 Buffer.toString('utf8') 对坏字节替换成 U+FFFD，不在中途抛错。
        return {"path": absolute, "content": buf.decode("utf-8", errors="replace")}

    def write_file(self, file_path: Any, content: Any) -> dict[str, bool]:
        if not isinstance(file_path, str) or not file_path:
            raise PermissionError(DENIED)
        absolute = str(self.guard.assert_inside(file_path))
        text = content if isinstance(content, str) else ""
        # 原版直接 writeFile：不预建父目录，写失败原样抛出。
        Path(absolute).write_text(text, encoding="utf-8")
        return {"ok": True}

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
    "MAX_FILE_BYTES",
    "MAX_IMAGE",
    "MAX_PDF",
    "MAX_TEXT",
    "TEXT_EXT",
    "classify",
    "format_size",
    "looks_binary",
    "paste_name",
    "thumbnail_data_url",
]
