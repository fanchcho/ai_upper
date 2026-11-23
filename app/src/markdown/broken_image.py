"""Deva's Chromium broken-image resource, used by its default ReactMarkdown img.

Extracted without changing deva/node_modules/electron/dist/chrome_100_percent.pak,
resource 48871 (14 x 16 PNG), MD5 6e211e3f7fce75eec8847e5ba76431a5.
Chromium lays it out in a 16 x 16 inline slot, followed immediately by the alt.
See out/ab-closeout/deva-image-live.json and deva-icon-match.log for provenance.
"""
import base64
from functools import lru_cache
from utils.qt_compat import QtCore, QtGui

_PNG = (
    b"iVBORw0KGgoAAAANSUhEUgAAAA4AAAAQCAYAAAAmlE46AAABh0lEQVQoU42QSS9DURiGv7VfhKWEnyA2WFizsLci"
    b"JGrowDVU55VIjE3sxFhB1ZDiVlUapYYguLRor9f5DrdRuaJv8izOOc+zORQIBFAKRFRGP+f3B6BlP/CYMecpo0NR"
    b"FLBXFPt8fpzf6ThO50xJ3rzLkMduIfZ6vTi51hE5fZMYM85q6rUQ8tiXsdvtQfxKx3biFb/Hd0citNlsRXBDLpdb"
    b"hmbbimcRiWu4uMvhXstL+D+4IadzDPFLHRvHL6aETzLYT2ZxcPZF6lYHNzQ66kQsnUdIfS4Jdrmh4eERqOKwdqiV"
    b"BLuiIVKUIagXeaxEtQLL0UfMRKII7sSK7hnhckM0OKjgSISLew8ST2getePlqJuskDTPNWI2rBrvJFxuiByOARye"
    b"57Gw+wDbklfIlYXIoH6yChObERIOCVc2ZLc7ZOhaDZpG31DDVDXNhRMcghuyWu1YT6TROF3zZ2TQEmxCNPUObqi/"
    b"34q2hdZ/I+Oud60HvdY+UGdnF9rbO8ygHxS9dVss+AQqZY47NSC2iwAAAABJRU5ErkJggg=="
)


@lru_cache(maxsize=128)
def broken_image(alt_width, line_height):
    """Rasterize the native icon under the original img's 6px border radius.

    The replacement box includes the alt, so its right corners are beyond the
    icon. Clipping a standalone 16px rounded square would cut the wrong edges.
    """
    native = QtGui.QImage.fromData(base64.b64decode(_PNG), "PNG")
    image = QtGui.QImage(16, 16, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(image)
    painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform)
    clip = QtGui.QPainterPath()
    clip.addRoundedRect(QtCore.QRectF(0, 0, 16 + alt_width, max(16, line_height)), 6, 6)
    painter.setClipPath(clip)
    painter.drawImage(QtCore.QRectF(0, 0, 16, 16), native)
    painter.end()
    encoded = QtCore.QByteArray()
    buffer = QtCore.QBuffer(encoded)
    buffer.open(QtCore.QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return "data:image/png;base64," + bytes(encoded.toBase64()).decode("ascii"), image
