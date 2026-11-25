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


class TableGridOverlay(QtQuick.QQuickPaintedItem):
    """Crisp 1-px grid painted over a QML table at integer device pixels.

    ``QQuickTextEdit`` only paints the *table-level* border (cell borders are not
    drawn at all, verified with ``setBorder(0)`` → no grid).  That frame border
    sits on a half-pixel document position, so a 1px border rasterises into two
    solid rows (measured y217/y218 vs deva's single y224).  This overlay keeps
    the document layout untouched and repaints the grid with ``fillRect`` on
    rounded coordinates, one physical row/column per line.
    """

    def __init__(self, parent, rect, row_lines, col_lines, color):
        super().__init__(parent)
        self.setObjectName("tableGrid")
        self._rect = rect
        self._row_lines = list(row_lines)
        self._col_lines = list(col_lines)
        self._color = color
        # Integer origin: the table frame itself lands on x.5; drawing from a
        # rounded origin keeps every line on whole pixels.
        self.setX(round(rect.x()))
        self.setY(round(rect.y()))
        self.setWidth(max(1, round(rect.width())))
        self.setHeight(max(1, round(rect.height())))
        self.setZ(0.5)
        self.setAcceptedMouseButtons(QtCore.Qt.NoButton)

    def paint(self, painter):
        painter.setRenderHint(QtGui.QPainter.Antialiasing, False)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(self._color)
        ox = self.x()
        oy = self.y()
        width = self.width()
        height = self.height()
        for y in self._row_lines:
            local = min(max(round(y) - oy, 0), height - 1)
            painter.fillRect(QtCore.QRectF(0, local, width, 1), self._color)
        for x in self._col_lines:
            local = round(x) - ox
            if 0 <= local <= width - 1:
                painter.fillRect(QtCore.QRectF(local, 0, 1, height), self._color)


def _iter_tables(frame):
    for child in frame.childFrames():
        if isinstance(child, QtGui.QTextTable):
            yield child
        yield from _iter_tables(child)


def _is_code_table(table):
    """Code blocks are single-column tables whose last cell carries the language."""
    if table.columns() != 1:
        return False
    block = table.cellAt(table.rows() - 1, 0).firstCursorPosition().block()
    return block.blockFormat().hasProperty(CODE_LANGUAGE_PROPERTY)


def attach_table_grids(quick_document, document, color):
    """Strip the QML copy's table frame border and paint a pixel-exact grid.

    Only the *attached* copy is touched: the renderer's own document keeps its
    ``QTextTableFormat`` border for non-QML consumers (tests / drawContents).

    Geometry comes from cell block rects, not ``frameBoundingRect``: the latter
    includes the table tail block (measured 156px for a 4Ã—35px table), while
    the rendered grid is exactly ``row_height * rows`` tall.
    """
    parent = quick_document.parent()
    if not isinstance(parent, QtQuick.QQuickItem):
        return []
    layout = document.documentLayout()
    overlays = []
    for table in _iter_tables(document.rootFrame()):
        if _is_code_table(table):
            continue
        rows = table.rows()
        columns = table.columns()
        if rows <= 0 or columns <= 0:
            continue
        first = layout.blockBoundingRect(table.cellAt(0, 0).firstCursorPosition().block())
        if rows > 1:
            second = layout.blockBoundingRect(table.cellAt(1, 0).firstCursorPosition().block())
            row_height = second.y() - first.y()
        else:
            row_height = first.height()
        if row_height <= 1:
            continue
        top = first.y()
        bottom = layout.blockBoundingRect(
            table.cellAt(rows - 1, 0).firstCursorPosition().block()).y() + row_height
        left = first.x()
        col_lines = []
        right = left
        for column in range(columns):
            block_rect = layout.blockBoundingRect(
                table.cellAt(0, column).firstCursorPosition().block())
            col_lines.append(block_rect.x())
            right = max(right, block_rect.x() + block_rect.width())
        if right - left <= 1 or bottom - top <= 1:
            continue
        # Remove the engine-drawn frame only in the QML document copy.
        stripped = QtGui.QTextTableFormat(table.format())
        stripped.setBorder(0.0)
        table.setFormat(stripped)
        row_lines = [top + index * row_height for index in range(rows + 1)]
        col_lines.append(right)
        rect = QtCore.QRectF(left, top, right - left, bottom - top)
        overlays.append(TableGridOverlay(parent, rect, row_lines, col_lines, color))
    return overlays
