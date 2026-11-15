"""交付卡（`present_files`）的后端：查看文件信息 / 缩略图 / 用默认应用打开 / 在文件夹中显示。

## 安全不变式（先读这段）

渲染层只能给「会话 id + 工具调用 id + 序号」，**不能给路径**。路径一律由这里按该会话的
`StoredSession.delivered` 边车取——边车由 Agent 循环在 `present_files` 成功时写入
（`chat_vm._agent_loop` → `tool_results.record_delivered`），内容是工具已解析、已去重、
已过工作区守卫的绝对路径。这几个入口因此只能作用于模型明确交付给用户的文件，
不会变成任意路径的读取 / 打开口子。与原版 `deliverables.ts:9-12` 同一条不变式。

原版在边车缺失时会回落历史里 `tool_use.input.paths` 的绝对路径（兼容早期版本）。这里
**故意不做这条回落**：那是模型原样发出的参数，未经工具解析与时序校验，放开就等于把
「历史里的字符串」当成可打开路径。旧会话（边车写入之前产生的）因此没有交付卡——
显式缺失好过开一个路径口子。

## 与 Qt 的关系

缩略图要 `QImage` / `QFileIconProvider`，所以 Qt 在函数内惰性导入：本模块可以在没有 Qt 的
环境里被纯逻辑测试导入。`open` 走 `QDesktopServices.openUrl`（等价原版 `shell.openPath`），
`reveal` 走子进程调系统文件管理器——参数用列表传、`shell=False`，路径里带引号/分号也
不会被解释成命令。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# 允许「用默认应用打开」的扩展名：成品类文件。可执行 / 脚本类（exe、bat、ps1、js、py、lnk …）
# 用默认应用打开就等于运行，一律不放行，只能在文件夹中显示。逐项照抄原版
# `deva/apps/desktop/src/main/services/deliverables.ts:17-34`。
OPENABLE = frozenset(
    {
        # 网页 / 文本 / 数据
        ".html", ".htm", ".md", ".markdown", ".txt", ".log", ".csv", ".tsv", ".json",
        ".xml", ".yaml", ".yml",
        # 文档
        ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".odt", ".ods",
        ".odp", ".rtf", ".epub",
        # 图片
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg", ".ico", ".tif",
        ".tiff", ".avif", ".heic",
        # 视频
        ".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v",
        # 音频
        ".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".opus",
        # 压缩包（系统打开即浏览内容）
        ".zip",
    }
)

# 与原版同值：缩略图长边上限。
THUMB_SIZE = 128


# ── 边车取路径 ────────────────────────────────────────────────────────────
def delivered_paths(session: Any, tool_use_id: Any) -> List[str]:
    """该会话那次工具调用交付的文件（绝对路径，按交付顺序）；没有则空列表。

    只认边车：`session.delivered[toolUseId]`。非绝对路径的条目丢弃（边车理应全是绝对路径，
    真出现相对路径说明被外部改过，不能拿它去打开文件）。
    """
    if not isinstance(tool_use_id, str) or not tool_use_id:
        return []
    sidecar = getattr(session, "delivered", None)
    if not isinstance(sidecar, dict):
        return []
    recorded = sidecar.get(tool_use_id)
    if not isinstance(recorded, list):
        return []
    return [
        str(item)
        for item in recorded
        if isinstance(item, str) and item and os.path.isabs(item)
    ]


def delivered_path(session: Any, tool_use_id: Any, index: Any) -> Optional[str]:
    """第 index 个交付文件；序号不是非负整数或越界返回 None（原版同口径）。"""
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
        return None
    paths = delivered_paths(session, tool_use_id)
    if index >= len(paths):
        return None
    return paths[index]


def is_openable(path: str) -> bool:
    """扩展名是否在白名单里（大小写不敏感，与原版 `extname().toLowerCase()` 一致）。"""
    return os.path.splitext(path)[1].lower() in OPENABLE


# ── 四个操作 ──────────────────────────────────────────────────────────────
def inspect(session: Any, tool_use_id: Any) -> List[Dict[str, Any]]:
    """`deliverables:inspect`：交付卡每一行的信息。

    返回 `[{path, name, dir, size, openable}]`（契约见原版 `shared/deliverables.ts`）。
    `size` 为 None = 文件已不存在（被移走或删除），界面据此标「已不存在」并跳过缩略图。
    """
    rows: List[Dict[str, Any]] = []
    for path in delivered_paths(session, tool_use_id):
        try:
            stat = os.stat(path)
            size: Optional[int] = stat.st_size if os.path.isfile(path) else None
        except OSError:
            size = None
        rows.append(
            {
                "path": path,
                "name": os.path.basename(path),
                "dir": os.path.dirname(path),
                "size": size,
                "openable": is_openable(path),
            }
        )
    return rows


def thumbnail(session: Any, tool_use_id: Any, index: Any) -> Optional[str]:
    """`deliverables:thumbnail`：交付文件缩略图的 data URI；取不到返回 None。

    先按图像解码并缩到 `THUMB_SIZE` 见方（等比），解不开再回落系统文件类型图标
    （原版顺序：`createThumbnailFromPath` → `app.getFileIcon`）。文件已不存在则 None。
    """
    path = delivered_path(session, tool_use_id, index)
    if not path or not os.path.isfile(path):
        return None
    data_url = _image_data_url(path)
    if data_url is not None:
        return data_url
    return _icon_data_url(path)


def open_item(session: Any, tool_use_id: Any, index: Any) -> Dict[str, bool]:
    """`deliverables:open`：用默认应用打开；仅白名单扩展名且文件存在。

    脚本/可执行类在这里就被挡掉，连尝试都不会发生（同原版）。
    """
    path = delivered_path(session, tool_use_id, index)
    if not path or not is_openable(path) or not os.path.isfile(path):
        return {"ok": False}
    return {"ok": _open_with_desktop(path)}


def reveal(session: Any, tool_use_id: Any, index: Any) -> Dict[str, bool]:
    """`deliverables:reveal`：在系统文件管理器里定位该文件；文件不存在则 false。"""
    path = delivered_path(session, tool_use_id, index)
    if not path or not os.path.isfile(path):
        return {"ok": False}
    return {"ok": _reveal_in_file_manager(path)}


# ── Qt / 系统调用（测试可替换）─────────────────────────────────────────────
def _image_data_url(path: str) -> Optional[str]:
    """图片缩略图 data URI；不是可解码图片返回 None。"""
    try:
        from utils.qt_compat import QtCore, QtGui

        image = QtGui.QImage(path)
        if image.isNull():
            return None
        width, height = image.width(), image.height()
        if width <= 0 or height <= 0:
            return None
        # 小图不放大：THUMB_SIZE 是上限语义（原版 createThumbnailFromPath 同）。
        if width <= THUMB_SIZE and height <= THUMB_SIZE:
            return _pixmap_data_url(image)
        scaled = image.scaled(
            THUMB_SIZE,
            THUMB_SIZE,
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
        if scaled.isNull():
            return None
        return _pixmap_data_url(scaled)
    except Exception:  # noqa: BLE001 - 与原版 catch 同语义：取不到缩略图回落文件图标
        return None


def _has_widget_app() -> bool:
    """进程里是否有真 `QApplication`（`QFileIconProvider` 的硬前提，见 `_icon_data_url`）。"""
    try:
        from utils.qt_compat import QtWidgets

        application = QtWidgets.QApplication.instance()
    except Exception:  # noqa: BLE001 - 没有 QtWidgets / 没有 Qt 绑定：按「没有」处理
        return False
    return application is not None and isinstance(application, QtWidgets.QApplication)


def _icon_data_url(path: str) -> Optional[str]:
    """系统文件类型图标 data URI；取不到返回 None。

    `QFileIconProvider` 属于 QtWidgets，且**要求进程里是真 `QApplication`**：只建了
    `QGuiApplication` 时（QML 入口，见 `qml_shell.py:687`）`provider.icon(...)` 会段错误崩进程
    （实测 PySide6 6.11.2 / offscreen）。所以先探进程类型，不是 QApplication 就直接给 None——
    渲染层对 null 缩略图本来就有占位图，宁可显示占位也不崩。
    """
    if not _has_widget_app():
        return None
    try:
        from utils.qt_compat import QtCore, QtWidgets

        provider = QtWidgets.QFileIconProvider()
        icon = provider.icon(QtCore.QFileInfo(path))
        if icon.isNull():
            return None
        pixmap = icon.pixmap(THUMB_SIZE, THUMB_SIZE)
        if pixmap.isNull():
            return None
        return _pixmap_data_url(pixmap)
    except Exception:  # noqa: BLE001 - 无图标主题 / 无 QtWidgets 时显式给 None（界面显示占位）
        return None


def _pixmap_data_url(pixmap: Any) -> Optional[str]:
    """QPixmap / QImage → PNG data URI。"""
    from utils.qt_compat import QtCore, QtGui

    buffer = QtCore.QBuffer()
    if not buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly):
        return None
    try:
        image = pixmap if isinstance(pixmap, QtGui.QImage) else pixmap.toImage()
        if not image.save(buffer, "PNG"):
            return None
    finally:
        buffer.close()
    encoded = bytes(buffer.data().toBase64()).decode("ascii")
    return "data:image/png;base64," + encoded


def _open_with_desktop(path: str) -> bool:
    """用系统默认应用打开（原版 `shell.openPath` 成功返回空串）。"""
    try:
        from utils.qt_compat import QtCore, QtGui

        return bool(QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path)))
    except Exception:  # noqa: BLE001 - 没有桌面环境时打开失败，显式返回 false
        return False


def reveal_command(path: str) -> List[str]:
    """「在文件夹中显示」的命令行（列表形式；不经 shell，路径里的元字符不会被解释）。

    Linux：`xdg-open <目录>`；macOS：`open -R <文件>`（选中该文件）；
    Windows：`explorer /select,<文件>`（explorer 的 /select 要求紧跟逗号）。
    """
    if sys.platform == "darwin":
        return ["open", "-R", path]
    if sys.platform == "win32":
        return ["explorer", "/select," + os.path.normpath(path)]
    return ["xdg-open", os.path.dirname(path) or "."]


# 测试替换点：默认真的拉起文件管理器。
_spawn: Callable[[List[str]], bool] = lambda argv: _spawn_detached(argv)


def _spawn_detached(argv: List[str]) -> bool:
    try:
        subprocess.Popen(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError:
        return False
    return True


def _reveal_in_file_manager(path: str) -> bool:
    return bool(_spawn(reveal_command(path)))


__all__ = [
    "OPENABLE",
    "THUMB_SIZE",
    "delivered_path",
    "delivered_paths",
    "inspect",
    "is_openable",
    "open_item",
    "reveal",
    "reveal_command",
    "thumbnail",
]
