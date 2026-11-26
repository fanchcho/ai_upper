"""演示页 View：验证属性绑定与命令绑定。

只做渲染与绑定，不持有业务状态。Qt 名字在 __init__ 里才 import，
与 MainWindow/AboutWindow 的约定一致。
"""
from __future__ import annotations
from locale_runtime import tr

from typing import Optional

from mvvm.view_models.demo_vm import DemoViewModel
from mvvm.views.base_view import ViewBase

RESET_BUTTON_TEXT = tr('legacy.3d81345303ab')


class DemoWindow(ViewBase):
    """一个输入框 + 一行问候 + 一个重置按钮。

    三个方向都在这里：
      - UI → ViewModel：QLineEdit.textEdited 是唯一的用户输入源；
      - ViewModel → UI：bind_property 把 name 写回输入框（重置命令走这条）；
      - 派生状态：greeting 由 ViewModel 算好，View 只 display。
    """

    def __init__(self, viewmodel: Optional[DemoViewModel] = None) -> None:
        super().__init__(viewmodel or DemoViewModel())
        from utils.qt_compat import QtWidgets

        window = QtWidgets.QWidget()
        window.setWindowTitle(tr('legacy.d6c39c5ceb4c'))
        layout = QtWidgets.QVBoxLayout(window)

        line_edit = QtWidgets.QLineEdit(viewmodel.name)
        greeting_label = QtWidgets.QLabel(viewmodel.greeting)
        reset_button = QtWidgets.QPushButton((tr('legacy.3d81345303ab')))
        layout.addWidget(line_edit)
        layout.addWidget(greeting_label)
        layout.addWidget(reset_button)
        window.resize(420, 160)

        self._window = window
        self._line_edit = line_edit
        self._greeting_label = greeting_label
        self._reset_button = reset_button

        # UI → ViewModel：textEdited 只在用户输入时发，程序 setText 不会回环。
        line_edit.textEdited.connect(self._on_text_edited)

        # ViewModel → UI：attribute_name 用 setter 方法名，getter_name 显式给出
        # （Qt 的 setText/text 不同形，框架不会去猜）。
        self.bind_property("name", line_edit, "setText", getter_name="text")
        self.bind_property("greeting", greeting_label, "setText")
        self.bind_command("reset", reset_button)

    def _on_text_edited(self, text: str) -> None:
        self.viewmodel.name_property.set_value(text)

    def show(self) -> None:
        self._window.show()

    def close(self) -> None:
        self._window.close()
