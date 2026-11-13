"""演示 ViewModel：一个可双向绑定的字符串属性 + 一个派生属性 + 一个命令。

只用于验证 py_upper 的 MVVM 骨架能否承载新页面，不含业务逻辑。
"""
from __future__ import annotations

from typing import Any, Optional

from mvvm.core import BaseViewModel, PropertyChangedEvent, PropertyFactory, RelayCommand

DEFAULT_NAME = "py_upper"
EMPTY_HINT = "（请输入名字）"


class DemoViewModel(BaseViewModel):
    """演示页的状态：name 由 QLineEdit 双向绑定，greeting 是派生显示值。"""

    def __init__(self) -> None:
        super().__init__()

    def _initialize_properties(self) -> None:
        self.name_property = PropertyFactory.create(DEFAULT_NAME, "name")
        self._register_property("name", self.name_property)

        self.greeting_property = PropertyFactory.create(self._greeting_for(DEFAULT_NAME), "greeting")
        self._register_property("greeting", self.greeting_property)

        self.reset_command = RelayCommand(execute=self.reset)

    @property
    def name(self) -> str:
        return str(self.name_property.get_value() or "")

    @property
    def greeting(self) -> str:
        return str(self.greeting_property.get_value() or "")

    def reset(self, parameter: Any = None) -> None:
        """命令 → 属性：应通过绑定把新值推回 QLineEdit。"""
        self.name_property.set_value(DEFAULT_NAME)

    def on_property_changed(self, event: PropertyChangedEvent) -> None:
        # 派生值只在这一个地方算：View 不拼字符串。
        if event.property_name == "name":
            self.greeting_property.set_value(self._greeting_for(str(event.new_value or "")))

    @staticmethod
    def _greeting_for(name: str) -> str:
        cleaned = name.strip()
        return f"你好，{cleaned}！" if cleaned else EMPTY_HINT
