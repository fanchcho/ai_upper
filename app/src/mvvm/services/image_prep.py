"""工具结果里的图片整形：按魔数识别、必要时缩放 / 转码到可发送的 ImagePart。

逐条对齐 Deva `apps/desktop/src/main/services/image-read.ts`：

- **media_type 必须与实际字节一致**：服务商会校验，不一致直接 400；扩展名不可信，按魔数识别；
- **体积 / 尺寸有上限**：Anthropic 单图 base64 上限 5MB（原始字节约 3.75MB）；长边超过
  1568px 服务端也会先缩小再看。故超限就地缩放 / 转码再发。

缩放用 Qt 的 `QImage`（PySide6 已是本工程依赖，Deva 用的是 Electron 自带的 `nativeImage`，
两边都是「不给应用额外装原生图像库」的思路）。Qt 能解的格式（PNG/JPEG/GIF/WebP/BMP 等）
都会缩；解不开又超限时如实报错，不假装成功。

Qt 由调用方在真正需要时 import：本模块在无 Qt 的测试环境里照样可导入，
`prepare_image` 会捕获导入失败并按「该格式无法在本地压缩」处理。
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Optional

from mvvm.models.chat_models import ImagePart

IMAGE_MIME = ("image/png", "image/jpeg", "image/gif", "image/webp")

# 长边上限：与服务端内部缩放阈值对齐，约 1600 token/张。
MAX_EDGE = 1568
# 发送体积上限（原始字节）：base64 膨胀 4/3 后恰在 Anthropic 的 5MB 之内。
MAX_SEND_BYTES = int(3.75 * 1024 * 1024)
# 可接受的源文件上限：再大的图缩放也能压下来，但读盘解码本身已不划算。
MAX_IMAGE_SOURCE_BYTES = 20 * 1024 * 1024
# 超限回退 JPEG 时的质量阶梯。
JPEG_QUALITIES = (85, 70, 50)


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{round(n / 1024)} KB"
    return f"{n / 1024 / 1024:.1f} MB"


def sniff_image_mime(buf: bytes) -> Optional[str]:
    """按魔数识别图片格式；不是这四种之一返回 None。"""
    if buf[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(buf) >= 3 and buf[0] == 0xFF and buf[1] == 0xD8 and buf[2] == 0xFF:
        return "image/jpeg"
    if buf[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if len(buf) >= 12 and buf[:4] == b"RIFF" and buf[8:12] == b"WEBP":
        return "image/webp"
    return None


@dataclass(frozen=True)
class PreparedImage:
    """整形结果：成功时带可直接发送的 ImagePart 与尺寸 / 体积。"""

    part: Optional[ImagePart] = None
    width: Optional[int] = None
    height: Optional[int] = None
    sent_width: Optional[int] = None
    sent_height: Optional[int] = None
    sent_bytes: int = 0
    resized: bool = False
    reason: str = ""

    @property
    def ok(self) -> bool:
        return self.part is not None


def _encode_qt_image(image: object, fmt: str, quality: int = -1) -> bytes:
    """QImage → 指定格式的字节。Qt 的 QBuffer 在 QtCore 下，不在 QtGui。"""
    from utils.qt_compat import QtCore

    buffer = QtCore.QBuffer()
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    if quality >= 0:
        image.save(buffer, fmt, quality)
    else:
        image.save(buffer, fmt)
    return bytes(buffer.data())


def prepare_image(buf: bytes, mime: str, name: Optional[str] = None) -> PreparedImage:
    """把一张图整形成可发送的 ImagePart。`mime` 应来自 sniff_image_mime（而非扩展名）。

    不超限则原样发送（字节不动）；超限则缩放到长边 MAX_EDGE，PNG 优先保持 PNG
    （保透明与文字锐度），仍超限再逐级降质回退 JPEG。永不抛错。
    """

    def make(data: bytes, media_type: str) -> ImagePart:
        return ImagePart(
            mediaType=media_type,
            data=base64.b64encode(data).decode("ascii"),
            name=name,
        )

    try:
        from utils.qt_compat import QtCore, QtGui

        image = QtGui.QImage.fromData(buf)
    except Exception:  # noqa: BLE001 - 无 Qt / 解码器缺失都按「解不开」处理
        image = None
        QtCore = None  # type: ignore[assignment]

    if image is None or image.isNull():
        if len(buf) > MAX_SEND_BYTES:
            return PreparedImage(
                reason=(
                    f"图片过大（{format_bytes(len(buf))}），且该格式无法在本地压缩；"
                    f"上限 {format_bytes(MAX_SEND_BYTES)}"
                )
            )
        return PreparedImage(part=make(buf, mime), sent_bytes=len(buf))

    width, height = image.width(), image.height()
    long_edge = max(width, height)
    if long_edge <= MAX_EDGE and len(buf) <= MAX_SEND_BYTES:
        return PreparedImage(
            part=make(buf, mime),
            width=width,
            height=height,
            sent_width=width,
            sent_height=height,
            sent_bytes=len(buf),
        )

    scaled = image
    if long_edge > MAX_EDGE:
        scale = MAX_EDGE / long_edge
        scaled = image.scaled(
            max(1, round(width * scale)),
            max(1, round(height * scale)),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
    sent_width, sent_height = scaled.width(), scaled.height()

    def done(data: bytes, media_type: str) -> PreparedImage:
        return PreparedImage(
            part=make(data, media_type),
            width=width,
            height=height,
            sent_width=sent_width,
            sent_height=sent_height,
            sent_bytes=len(data),
            resized=True,
        )

    # 源为 JPEG（照片居多）直接出 JPEG；其余先试 PNG。
    if mime != "image/jpeg":
        png = _encode_qt_image(scaled, "PNG")
        if len(png) <= MAX_SEND_BYTES:
            return done(png, "image/png")
    for quality in JPEG_QUALITIES:
        jpg = _encode_qt_image(scaled, "JPEG", quality)
        if len(jpg) <= MAX_SEND_BYTES:
            return done(jpg, "image/jpeg")
    return PreparedImage(reason=f"图片压缩后仍超过 {format_bytes(MAX_SEND_BYTES)}，无法发送")


__all__ = [
    "IMAGE_MIME",
    "JPEG_QUALITIES",
    "MAX_EDGE",
    "MAX_IMAGE_SOURCE_BYTES",
    "MAX_SEND_BYTES",
    "PreparedImage",
    "format_bytes",
    "prepare_image",
    "sniff_image_mime",
]
