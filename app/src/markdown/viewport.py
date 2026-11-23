"""Local viewports for overflowing code in the shared QML text document."""
from utils.qt_compat import QtCore, QtGui, QtQuick
from .document import CODE_LANGUAGE_PROPERTY


class CodeViewport(QtQuick.QQuickPaintedItem):
    contentXChanged = QtCore.Signal()

    def __init__(self, parent, document, rect, width, background):
        super().__init__(parent)
        self.setObjectName("codeViewport")
        self.document = document
        self.rect = rect
        self._content_x = 0.0
        self.content_width = rect.width()
        self.background = background
        self.setX(rect.x())
        self.setY(rect.y())
        self.setWidth(width)
        self.setHeight(rect.height())
        self.setZ(1)
        self.setAcceptedMouseButtons(QtCore.Qt.NoButton)

    @QtCore.Property(float, notify=contentXChanged)
    def contentX(self):
        return self._content_x

    @QtCore.Property(float, constant=True)
    def contentWidth(self):
        return self.content_width

    def wheelEvent(self, event):
        # Vertical wheel events retain the enclosing Flickable's behavior.
        horizontal = event.pixelDelta().x() or event.angleDelta().x()
        if not horizontal and event.modifiers() & QtCore.Qt.ShiftModifier:
            horizontal = event.pixelDelta().y() or event.angleDelta().y()
        if not horizontal:
            event.ignore()
            return
        self._content_x = max(0.0, min(self.content_width - self.width(),
                                     self._content_x - horizontal))
        self.contentXChanged.emit()
        self.update()
        event.accept()

    def paint(self, painter):
        painter.fillRect(self.boundingRect(), self.background)
        painter.setClipRect(self.boundingRect())
        painter.translate(-self.rect.x() - self._content_x, -self.rect.y())
        self.document.drawContents(painter, QtCore.QRectF(
            self.rect.x() + self._content_x, self.rect.y(), self.width(), self.height()))


def attach_code_viewports(quick_document, document, background):
    parent = quick_document.parent()
    if not isinstance(parent, QtQuick.QQuickItem):
        return []
    overlays = []
    layout = document.documentLayout()
    width = parent.width()

    def visit(frame):
        for child in frame.childFrames():
            if isinstance(child, QtGui.QTextTable) and child.columns() == 1:
                cell = child.cellAt(child.rows() - 1, 0)
                block = cell.firstCursorPosition().block()
                if block.blockFormat().hasProperty(CODE_LANGUAGE_PROPERTY):
                    rect = layout.frameBoundingRect(child)
                    if rect.width() > width + 2:
                        # Keep the language header fixed; scroll code content only.
                        if child.rows() > 1:
                            rect.setTop(layout.blockBoundingRect(block).top())
                        overlays.append(CodeViewport(parent, document, rect,
                                                     width - rect.x(), background))
            visit(child)
    visit(document.rootFrame())
    return overlays
