"""假 Qt 控件集：给 `test_deva_app.py` 与 `test_deva_panes.py` 共用。

只实现被视图真正调用的方法（`setText`/`setEnabled`/`addItem`/信号……），
行为上尽量贴近真 Qt 的两条约定：`blockSignals(True)` 会抑制信号，
`setCurrentRow` / `setCurrentIndex` 成功后立即发信号。

用法：在测试模块里 `from fake_qt_ui import fake_qt  # noqa: F401`（pytest 把
导入到模块命名空间里的 fixture 当作本模块的 fixture 用）。
"""
from __future__ import annotations

import html as html_module
import os
import re

import pytest

from conftest import install_fake_binding


class FakeSignal:
    def __init__(self) -> None:
        self.handlers: list = []

    def connect(self, handler) -> None:
        self.handlers.append(handler)

    def emit(self, *args) -> None:
        for handler in list(self.handlers):
            handler(*args)


class FakeWindow:
    def __init__(self) -> None:
        self.visible = False
        self.title = ""
        self.central_widget = None
        self.size = None
        self.raised = False
        self.activated = False
        self.sizes = None

    def setWindowTitle(self, title: str) -> None:  # noqa: N802
        self.title = title

    def setCentralWidget(self, widget) -> None:  # noqa: N802
        self.central_widget = widget

    def resize(self, *size: int) -> None:
        self.size = size

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False

    def raise_(self) -> None:  # noqa: N802
        self.raised = True

    def activateWindow(self) -> None:  # noqa: N802
        self.activated = True

    def close(self) -> None:
        self.visible = False

    def setSizes(self, sizes) -> None:  # noqa: N802
        self.sizes = list(sizes)


class FakeLabel:
    def __init__(self, text: str = "") -> None:
        self._text = text
        self.visible = True
        self.word_wrap = False

    def setText(self, value: str) -> None:  # noqa: N802
        self._text = value

    def text(self) -> str:  # noqa: N802 - 真 Qt 是方法，不是属性
        return self._text

    def setWordWrap(self, value: bool) -> None:  # noqa: N802
        self.word_wrap = value

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False


class FakeButton:
    def __init__(self, text: str = "") -> None:
        self._text = text
        self.clicked = FakeSignal()
        self.enabled = True

    def setEnabled(self, value: bool) -> None:  # noqa: N802
        self.enabled = value

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = text

    def text(self) -> str:  # noqa: N802 - 真 Qt 是方法
        return self._text

    def isEnabled(self) -> bool:  # noqa: N802
        return self.enabled

    def click(self) -> None:
        self.clicked.emit(False)


class FakeTextDocument:
    def __init__(self) -> None:
        self.resources: list = []

    def addResource(self, resource_type, url, image) -> None:  # noqa: N802
        self.resources.append((resource_type, url, image))


class FakeTextBrowser:
    """`setPlainText` 与 `setHtml` 分开记：历史区现在走富文本，纯文本仍供测试断言。"""

    def __init__(self) -> None:
        self.plain_text = ""
        self.html = ""
        self._document = FakeTextDocument()

    def setPlainText(self, value: str) -> None:  # noqa: N802
        self.plain_text = value

    def setHtml(self, value: str) -> None:  # noqa: N802
        self.html = value
        # 真 QTextBrowser 的 toPlainText() 读得到 setHtml 的内容；这里用「去标签」近似，
        # 让按纯文本断言的旧用例仍然测的是「屏幕上有没有这句话」。
        text = re.sub(r"<br\s*/?>|</p>|</tr>|</li>", "\n", value)
        text = re.sub(r"<[^>]+>", "", text)
        self.plain_text = html_module.unescape(text)

    def toPlainText(self) -> str:  # noqa: N802
        return self.plain_text

    def document(self) -> "FakeTextDocument":  # noqa: N802
        return self._document


class FakePlainTextEdit:
    def __init__(self) -> None:
        self.plain_text = ""
        self.textChanged = FakeSignal()

    def setPlainText(self, value: str) -> None:  # noqa: N802
        self.plain_text = value
        self.textChanged.emit()

    def toPlainText(self) -> str:  # noqa: N802
        return self.plain_text

    def setPlaceholderText(self, value: str) -> None:  # noqa: N802
        self.placeholder = value

    def setFixedHeight(self, value: int) -> None:  # noqa: N802
        self.fixed_height = value


class FakeLayout:
    def __init__(self, parent=None) -> None:
        self.widgets: list = []

    def addWidget(self, widget, *args) -> None:  # noqa: N802
        self.widgets.append(widget)

    def addLayout(self, layout) -> None:  # noqa: N802
        self.widgets.append(layout)

    def addStretch(self, value: int = 0) -> None:  # noqa: N802
        pass

    def setContentsMargins(self, *args) -> None:  # noqa: N802
        pass


class FakeFormLayout(FakeLayout):
    def addRow(self, *args) -> None:  # noqa: N802
        self.widgets.append(args)


class FakeStackedWidget(FakeWindow):
    def __init__(self) -> None:
        super().__init__()
        self._pages: list = []
        self._index = 0

    def addWidget(self, widget) -> None:  # noqa: N802
        self._pages.append(widget)

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        self._index = index

    def currentIndex(self) -> int:  # noqa: N802
        return self._index


class FakeSplitter(FakeWindow):
    def __init__(self, orientation=None) -> None:
        super().__init__()
        self.orientation = orientation
        self._widgets: list = []

    def addWidget(self, widget) -> None:  # noqa: N802
        self._widgets.append(widget)


class FakeTimer:
    """QTimer 的假实现：只记录连接，由测试决定何时触发（Qt 事件循环不在这里跑）。"""

    def __init__(self) -> None:
        self.interval = 0
        self.started = False
        self.timeout = FakeSignal()

    def setInterval(self, value: int) -> None:  # noqa: N802
        self.interval = value

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False

    def fire(self) -> None:
        self.timeout.emit()


class FakeListItem:
    def __init__(self, text: str = "") -> None:
        self._text = text
        self._data: dict = {}

    def setData(self, role, value) -> None:  # noqa: N802
        self._data[role] = value

    def data(self, role):
        return self._data.get(role)

    def text(self) -> str:
        return self._text


class FakeListWidget:
    def __init__(self) -> None:
        self._items: list = []
        self._row = -1
        self.visible = True
        self._blocked = False
        self.currentRowChanged = FakeSignal()
        self.itemDoubleClicked = FakeSignal()

    def clear(self) -> None:
        self._items = []
        self._row = -1

    def addItem(self, item) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def item(self, row):
        return self._items[row] if 0 <= row < len(self._items) else None

    def currentRow(self) -> int:  # noqa: N802
        return self._row

    def setCurrentRow(self, row: int) -> None:  # noqa: N802
        self._row = row
        if not self._blocked:
            self.currentRowChanged.emit(row)

    def blockSignals(self, value: bool) -> None:  # noqa: N802
        self._blocked = value

    def setVisible(self, value: bool) -> None:  # noqa: N802
        self.visible = value

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False


class FakeLineEdit:
    Password = "password"

    def __init__(self, text: str = "") -> None:
        self._text = text
        self.placeholder = ""
        self.echo_mode = None
        self.visible = True

    def setText(self, value: str) -> None:  # noqa: N802
        self._text = value

    def text(self) -> str:
        return self._text

    def clear(self) -> None:
        self._text = ""

    def setPlaceholderText(self, value: str) -> None:  # noqa: N802
        self.placeholder = value

    def setEchoMode(self, mode) -> None:  # noqa: N802
        self.echo_mode = mode

    def show(self) -> None:
        self.visible = True

    def hide(self) -> None:
        self.visible = False


class FakeComboBox:
    def __init__(self) -> None:
        self._items: list = []
        self._index = 0
        self._blocked = False
        self.currentIndexChanged = FakeSignal()

    def addItem(self, label: str) -> None:  # noqa: N802
        self._items.append(label)

    def count(self) -> int:
        return len(self._items)

    def itemText(self, index: int) -> str:  # noqa: N802
        return self._items[index]

    def currentIndex(self) -> int:  # noqa: N802
        return self._index

    def setCurrentIndex(self, index: int) -> None:  # noqa: N802
        self._index = index
        if not self._blocked:
            self.currentIndexChanged.emit(index)

    def blockSignals(self, value: bool) -> None:  # noqa: N802
        # 真 Qt 的 blockSignals 会抑制信号；假控件也照做，否则刷新时的程序化赋值
        # 会被当成用户操作，触发不该触发的命令。
        self._blocked = value


class FakeCheckBox:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self._checked = False

    def setChecked(self, value: bool) -> None:  # noqa: N802
        self._checked = value

    def isChecked(self) -> bool:  # noqa: N802
        return self._checked


class FakeSpinBox:
    def __init__(self) -> None:
        self._value = 0
        self.special = ""

    def setRange(self, low: int, high: int) -> None:  # noqa: N802
        self.range = (low, high)

    def setSpecialValueText(self, text: str) -> None:  # noqa: N802
        self.special = text

    def setValue(self, value: int) -> None:  # noqa: N802
        self._value = value

    def value(self) -> int:
        return self._value


class FakeMessageBox:
    # 真 Qt 里 StandardButton 是标志位，`Yes | No` 合法；假实现用整数保持同一运算。
    Yes = 0x4000
    No = 0x10000
    answer = "no"
    last: dict = {}

    @classmethod
    def question(cls, *args):
        cls.last = {"args": args}
        return cls.answer


class FakeInputDialog:
    answer = ""
    accepted = False
    last: dict = {}

    @classmethod
    def getText(cls, *args, **kwargs):
        cls.last = {"args": args, "kwargs": kwargs}
        return cls.answer, cls.accepted


class FakeApplication:
    def __init__(self, argv=None) -> None:
        self.argv = argv

    @classmethod
    def instance(cls):
        return None

    @classmethod
    def setAttribute(cls, attribute) -> None:  # noqa: N802
        pass

    def processEvents(self) -> None:  # noqa: N802
        pass

    def platformName(self) -> str:  # noqa: N802
        return os.environ.get("QT_QPA_PLATFORM", "unknown")

    def quit(self) -> None:
        pass


class FakeQt:
    """`QtCore.Qt` 的替身：`enum_member` 会按属性名找枚举成员。"""

    Horizontal = "horizontal"
    UserRole = 256


class FakeQUrl:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def toString(self) -> str:  # noqa: N802
        return self.value

    def __str__(self) -> str:
        return self.value


class FakeQImage:
    """只实现内联图片渲染用到的那几个名字（`fromData` / `isNull`）。"""

    def __init__(self, raw: bytes = b"") -> None:
        self.raw = raw

    @classmethod
    def fromData(cls, data: bytes, fmt=None):  # noqa: N802 - Qt spelling
        return cls(data or b"")

    def isNull(self) -> bool:  # noqa: N802
        return not self.raw


class FakeResourceType:
    ImageResource = "image"


class FakeTextDocumentClass:
    """`QtGui.QTextDocument` 在视图里只用于取 `ResourceType.ImageResource`。"""

    ResourceType = FakeResourceType


WIDGETS = {
    "QApplication": FakeApplication,
    "QMainWindow": FakeWindow,
    "QWidget": FakeWindow,
    "QVBoxLayout": FakeLayout,
    "QLabel": FakeLabel,
    "QPushButton": FakeButton,
    "QTextBrowser": FakeTextBrowser,
    "QPlainTextEdit": FakePlainTextEdit,
    "QHBoxLayout": FakeLayout,
    "QFormLayout": FakeFormLayout,
    "QStackedWidget": FakeStackedWidget,
    "QSplitter": FakeSplitter,
    "QListWidget": FakeListWidget,
    "QListWidgetItem": FakeListItem,
    "QLineEdit": FakeLineEdit,
    "QComboBox": FakeComboBox,
    "QCheckBox": FakeCheckBox,
    "QSpinBox": FakeSpinBox,
    "QMessageBox": FakeMessageBox,
    "QInputDialog": FakeInputDialog,
}


@pytest.fixture()
def fake_qt(monkeypatch):
    install_fake_binding(
        monkeypatch,
        {
            "PySide6": {
                "QtCore": {"Qt": FakeQt, "QTimer": FakeTimer, "QUrl": FakeQUrl},
                "QtGui": {"QImage": FakeQImage, "QTextDocument": FakeTextDocumentClass},
                "QtWidgets": WIDGETS,
            }
        },
    )
