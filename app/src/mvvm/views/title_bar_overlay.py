"""自绘标题栏叠加层：复刻原版（Electron `titleBarStyle:'hidden'` + `titleBarOverlay`）的三个窗口控件。

几何取自原版实拍（1280x820 客户端区右上角，逐像素量出）：
- 命中区：3 个 32x40 按钮，右对齐贴边（x = 1184 / 1216 / 1248）；
- 最小化：10x2 实心横条，x 1195..1204 / y 23..24；
- 最大化：10x10 描边方框，x 1227..1236 / y 15..24，线宽 2；
- 关闭：10x10 的 X，x 1259..1268 / y 15..24，线宽 2、抗锯齿；
- 图标色 #5F6368（浅色）/ #E8EAED（深色）。

为什么自绘：原版窗口无边框，控件由 Electron 叠加层画在内容区里。Qt 若用原生边框，
系统标题栏会多出一整条，同尺寸截图必然不同；故这里无边框 + 覆盖层，几何与原版逐像素对齐。
"""
from __future__ import annotations

from utils.qt_compat import QtCore, QtGui, QtWidgets, Signal

QPoint = QtCore.QPoint
QPointF = QtCore.QPointF
QRect = QtCore.QRect
QSize = QtCore.QSize
Qt = QtCore.Qt
QColor = QtGui.QColor
QPainter = QtGui.QPainter
QPen = QtGui.QPen
QWidget = QtWidgets.QWidget

TITLEBAR_HEIGHT = 40
BUTTON_WIDTH = 32
GLYPH_COLOR = QColor("#5F6368")
GLYPH_COLOR_DARK = QColor("#E8EAED")
# Linux 上 Electron 的 titleBarOverlay 是**实色**矩形（main/index.ts 的 overlayOptions：win32 用透明，
# linux 用 OVERLAY_BG）。它画在网页内容之上，所以设置弹框的遮罩压不暗它——这里必须照原样不透明。
OVERLAY_BG = QColor("#ffffff")
OVERLAY_BG_DARK = QColor("#1e1e20")
HOVER_BG = QColor(0, 0, 0, 18)


class TitleBarOverlay(QWidget):
    """覆盖在 WebView 右上角的三个窗口按钮。"""

    minimizeRequested = Signal()
    maximizeRequested = Signal()
    closeRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # 不透明：原版 Linux 的叠加层是一块实色，遮住其下的网页内容（含弹框遮罩）。
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self._hover = -1
        self._dark = False

    def set_dark(self, dark: bool) -> None:
        self._dark = dark
        self.update()

    # ── 几何 ──────────────────────────────────────────────────────────────
    def button_rect(self, index: int) -> QRect:
        """index: 0 = 最小化, 1 = 最大化, 2 = 关闭。右对齐贴边。"""
        width = self.width()
        return QRect(width - BUTTON_WIDTH * (3 - index), 0, BUTTON_WIDTH, TITLEBAR_HEIGHT)

    def strip_size(self) -> QSize:
        """叠加层的实色矩形：原版 Linux 上是 3 个 32px 按钮宽、40 高，右对齐。"""
        return QSize(BUTTON_WIDTH * 3, TITLEBAR_HEIGHT)

    def _index_at(self, pos: QPoint) -> int:
        for index in range(3):
            if self.button_rect(index).contains(pos):
                return index
        return -1

    def _color(self) -> QColor:
        return GLYPH_COLOR_DARK if self._dark else GLYPH_COLOR

    # ── 交互 ──────────────────────────────────────────────────────────────
    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt 接口
        index = self._index_at(event.position().toPoint())
        if index != self._hover:
            self._hover = index
            self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = -1
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        index = self._index_at(event.position().toPoint())
        if index == 0:
            self.minimizeRequested.emit()
        elif index == 1:
            self.maximizeRequested.emit()
        elif index == 2:
            self.closeRequested.emit()

    # ── 绘制 ──────────────────────────────────────────────────────────────
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), OVERLAY_BG_DARK if self._dark else OVERLAY_BG)
        if 0 <= self._hover <= 2:
            painter.fillRect(self.button_rect(self._hover), HOVER_BG)

        color = self._color()
        right = self.width()
        # 最小化：10x2 横条
        painter.fillRect(QRect(right - 85, 23, 10, 2), color)
        # 最大化：10x10 方框，四条边各 2px（fillRect 而非 drawRect：避免描边向外扩 1px）
        box = QRect(right - 53, 15, 10, 10)
        painter.fillRect(QRect(box.left(), box.top(), box.width(), 2), color)
        painter.fillRect(QRect(box.left(), box.bottom() - 1, box.width(), 2), color)
        painter.fillRect(QRect(box.left(), box.top(), 2, box.height()), color)
        painter.fillRect(QRect(box.right() - 1, box.top(), 2, box.height()), color)
        # 关闭：10x10 的 X
        painter.setRenderHint(QPainter.Antialiasing, True)
        pen = QPen(color)
        pen.setWidthF(2.1)
        pen.setCapStyle(Qt.FlatCap)
        painter.setPen(pen)
        # 端点由原版实拍拟合（中点 1.5..10.5，笔宽 2、平头），与 Electron 叠加层字形一致
        painter.drawLine(QPointF(right - 20.25, 15.75), QPointF(right - 11.75, 24.25))
        painter.drawLine(QPointF(right - 11.75, 15.75), QPointF(right - 20.25, 24.25))
        painter.end()
