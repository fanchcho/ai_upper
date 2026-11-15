"""复现：QML 的 ``TextEdit`` 渲染 ``setBorder(1.0)`` 的 ``QTextFrame`` 段错误。

用法（在仓库根目录）：
    QT_QPA_PLATFORM=offscreen .venv/bin/python out/qml-body/bordered_frame_segfault.py --case border
退出码：段错误为 139（128 + SIGSEGV 11），正常渲染为 0。

三种对照跑的是同一段 QML、同一份文档结构，只有「线的画法」不同：
  --case border   QTextFrameFormat.setBorder(1.0)      ← 崩溃（139）
  --case border0  QTextFrameFormat.setBorder(0.0)      ← 正常（0）
  --case cell     1×2 表格左列 3px 背景（引用竖线实现） ← 正常（0）

结论直接决定了 ``markdown/document.py`` 的实现：正文层任何地方都不许出现
``border > 0`` 的 ``QTextFrame``；线一律用「固定 1px 行高 + 背景」或表格单元格
逐边边框表达。``app/tests/test_markdown_document.py`` 里的
``test_no_rendered_frame_has_a_border`` 是这个结论的回归锁。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "app", "src"))

from PySide6.QtCore import QObject, QUrl, Slot
from PySide6.QtGui import QColor, QFont, QGuiApplication, QTextCharFormat, QTextCursor
from PySide6.QtGui import QTextFrameFormat, QTextLength, QTextTableCellFormat, QTextTableFormat
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickTextDocument, QQuickWindow

FONT = QFont()
FONT.setPixelSize(14)


def _char_format():
    fmt = QTextCharFormat()
    fmt.setFont(FONT)
    return fmt


def _frame_document(document, border):
    cursor = QTextCursor(document)
    cursor.insertText("before", _char_format())
    cursor.insertBlock()
    frame_format = QTextFrameFormat()
    frame_format.setBorder(border)
    frame_format.setBackground(QColor("#ff0000"))
    frame = cursor.insertFrame(frame_format)
    frame.firstCursorPosition().insertText("inside frame", _char_format())
    cursor = QTextCursor(document)
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertBlock()
    cursor.insertText("after", _char_format())


def build_bordered_frame(document):
    _frame_document(document, 1.0)


def build_borderless_frame(document):
    _frame_document(document, 0.0)


def build_quote_table(document):
    """当前实现：引用竖线是 1×2 表格的左列背景，不是 frame 边框。"""
    cursor = QTextCursor(document)
    cursor.insertText("before", _char_format())
    cursor.insertBlock()
    table_format = QTextTableFormat()
    table_format.setBorder(0.0)
    table_format.setCellSpacing(0.0)
    table_format.setCellPadding(0.0)
    table_format.setMargin(12.0)
    table_format.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100.0))
    table_format.setColumnWidthConstraints([
        QTextLength(QTextLength.Type.FixedLength, 3.0),
        QTextLength(QTextLength.Type.VariableLength, 100.0),
    ])
    table = cursor.insertTable(1, 2, table_format)
    bar_format = QTextTableCellFormat()
    bar_format.setBackground(QColor("#d5d5db"))
    table.cellAt(0, 0).setFormat(bar_format)
    body = table.cellAt(0, 1)
    body_format = QTextTableCellFormat()
    body_format.setLeftPadding(12.0)
    body.setFormat(body_format)
    body.firstCursorPosition().insertText("quoted", _char_format())


BUILDERS = {
    "border": build_bordered_frame,
    "border0": build_borderless_frame,
    "cell": build_quote_table,
}

QML = b"""
import QtQuick
import QtQuick.Controls
ApplicationWindow {
    id: win
    width: 480
    height: 200
    visible: true
    color: "white"
    TextEdit {
        id: body
        anchors.fill: parent
        readOnly: true
        Component.onCompleted: bodyBridge.attach(textDocument)
    }
}
"""


class Bridge(QObject):
    def __init__(self, builder):
        super().__init__()
        self._builder = builder

    @Slot(QQuickTextDocument, result=bool)
    def attach(self, quick_document):
        self._builder(quick_document.textDocument())
        return True


def main(argv):
    case = "border"
    if "--case" in argv:
        case = argv[argv.index("--case") + 1]
    if case not in BUILDERS:
        print("unknown case %r" % case, file=sys.stderr)
        return 2

    app = QGuiApplication(sys.argv)
    bridge = Bridge(BUILDERS[case])
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bodyBridge", bridge)
    engine.loadData(QML, QUrl(""))
    if not engine.rootObjects():
        print("QML FAILED TO LOAD", file=sys.stderr)
        return 2
    image = QQuickWindow.grabWindow(engine.rootObjects()[0])
    path = os.path.join(HERE, "frame-%s.png" % case)
    print("case=%s grabbed=%s saved=%s" % (case, image.width(), image.save(path)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
