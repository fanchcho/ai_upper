"""设置页（模型与服务商）：列表态 / 服务商详情态 / 模型详情态。

口径来自 Deva `features/settings/ModelSettings.tsx`：钻取式导航（先列服务商，点进去
看详情，详情里每个模型还能再进模型详情），同一时刻只显示一列。功能范围按本工程的
`SettingsViewModel` 提供的能力来——服务商增删改、模型增删启用、默认模型与思考等级、
密钥写入（明文不回显）、从服务端拉模型清单。

密钥输入框每次进入详情都清空：密钥库不回读明文，界面也不缓存上一次输入。
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from mvvm.view_models.settings_vm import ADAPTER_LABELS, ADAPTERS, EFFORT_LEVELS, SettingsViewModel
from mvvm.views.base_view import ViewBase

TITLE = "设置"
BACK_TEXT = "返回"
ADD_PROVIDER_TEXT = "新增服务商"
REMOVE_PROVIDER_TEXT = "删除服务商"
SAVE_PROVIDER_TEXT = "保存"
FETCH_MODELS_TEXT = "拉取模型清单"
ADD_MODEL_TEXT = "添加模型"
REMOVE_MODEL_TEXT = "删除模型"
EDIT_MODEL_TEXT = "编辑模型"
SET_DEFAULT_TEXT = "设为默认"
ENABLE_TEXT = "启用"
DISABLE_TEXT = "停用"
KEY_PLACEHOLDER = "API 密钥（保存后不回显）"
SAVE_KEY_TEXT = "保存密钥"
CLEAR_KEY_TEXT = "清除密钥"
KEY_SET_HINT = "已配置密钥"
KEY_MISSING_HINT = "未配置密钥"
FETCH_FAILED_HINT = "拉取模型清单失败："
RESTORE_AUTO_TEXT = "恢复自动"
EFFORT_LABELS = {
    "default": "默认",
    "low": "低",
    "medium": "中",
    "high": "高",
    "xhigh": "很高",
    "max": "最高",
}


def key_status_text(has_key: bool) -> str:
    return KEY_SET_HINT if has_key else KEY_MISSING_HINT


def effort_labels() -> list[str]:
    """思考等级下拉的显示文案（与 EFFORT_LEVELS 一一对应）。"""
    return [EFFORT_LABELS.get(level, level) for level in EFFORT_LEVELS]


class SettingsPane(ViewBase):
    """设置页。`on_back` 由窗口层提供（回到对话）。

    所有改动都经 `SettingsViewModel` 落到 `config.json` / 密钥库；控件不直接读写文件。
    """

    def __init__(
        self,
        viewmodel: SettingsViewModel,
        *,
        on_back: Optional[Callable[[], None]] = None,
        on_notice: Optional[Callable[[str], None]] = None,
        on_fetch: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(viewmodel)
        from utils.qt_compat import QtWidgets, enum_member

        self._enum_member = enum_member

        self._on_back = on_back
        self._on_notice = on_notice
        # 拉模型清单是网络 I/O：由窗口层在后台线程跑，结果回来再写入界面。
        self._on_fetch = on_fetch
        self._page = "list"  # list | provider | model
        self._provider_id = ""
        self._model_id = ""

        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QtWidgets.QHBoxLayout()
        self._back_button = QtWidgets.QPushButton(BACK_TEXT)
        self._title = QtWidgets.QLabel(TITLE)
        header.addWidget(self._title)
        header.addStretch(1)
        header.addWidget(self._back_button)
        layout.addLayout(header)

        # 顶部固定项：默认模型与思考等级（与具体服务商无关）
        self._active_label = QtWidgets.QLabel("")
        self._effort_combo = QtWidgets.QComboBox()
        for label in effort_labels():
            self._effort_combo.addItem(label)
        effort_row = QtWidgets.QHBoxLayout()
        effort_row.addWidget(QtWidgets.QLabel("思考等级"))
        effort_row.addWidget(self._effort_combo)
        effort_row.addStretch(1)
        layout.addWidget(self._active_label)
        layout.addLayout(effort_row)

        self._message = QtWidgets.QLabel("")
        self._message.setWordWrap(True)
        layout.addWidget(self._message)

        # 三页：服务商列表 / 服务商详情 / 模型详情
        self._pages = QtWidgets.QStackedWidget()
        layout.addWidget(self._pages, 1)
        self._pages.addWidget(self._build_list_page())
        self._pages.addWidget(self._build_provider_page())
        self._pages.addWidget(self._build_model_page())

        self._widget = widget
        self._back_button.clicked.connect(lambda _=False: self._back())
        self._effort_combo.currentIndexChanged.connect(self._on_effort_changed)
        viewmodel.subscribe_property_changed(self._on_vm_changed)
        self._refresh()

    # ── 构造三页 ──────────────────────────────────────────────────────────
    def _build_list_page(self) -> Any:
        from utils.qt_compat import QtWidgets

        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        self._provider_list = QtWidgets.QListWidget()
        self._provider_list.itemDoubleClicked.connect(lambda _item: self._open_provider())
        self._provider_list.currentRowChanged.connect(lambda _row: self._sync_list_buttons())
        buttons = QtWidgets.QHBoxLayout()
        self._open_button = QtWidgets.QPushButton("配置")
        self._add_provider_button = QtWidgets.QPushButton(ADD_PROVIDER_TEXT)
        buttons.addWidget(self._open_button)
        buttons.addWidget(self._add_provider_button)
        buttons.addStretch(1)
        layout.addWidget(self._provider_list, 1)
        layout.addLayout(buttons)
        self._open_button.clicked.connect(lambda _=False: self._open_provider())
        self._add_provider_button.clicked.connect(lambda _=False: self._add_provider())
        return page

    def _build_provider_page(self) -> Any:
        from utils.qt_compat import QtWidgets

        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)

        form = QtWidgets.QFormLayout()
        self._name_edit = QtWidgets.QLineEdit()
        self._base_edit = QtWidgets.QLineEdit()
        self._adapter_combo = QtWidgets.QComboBox()
        for adapter in ADAPTERS:
            self._adapter_combo.addItem(ADAPTER_LABELS[adapter])
        self._enabled_box = QtWidgets.QCheckBox("启用该服务商")
        form.addRow("名称", self._name_edit)
        form.addRow("服务地址", self._base_edit)
        form.addRow("协议", self._adapter_combo)
        form.addRow("", self._enabled_box)
        layout.addLayout(form)

        key_row = QtWidgets.QHBoxLayout()
        self._key_edit = QtWidgets.QLineEdit()
        self._key_edit.setPlaceholderText(KEY_PLACEHOLDER)
        self._key_edit.setEchoMode(self._enum_member(QtWidgets.QLineEdit, "Password"))
        self._save_key_button = QtWidgets.QPushButton(SAVE_KEY_TEXT)
        self._clear_key_button = QtWidgets.QPushButton(CLEAR_KEY_TEXT)
        key_row.addWidget(self._key_edit, 1)
        key_row.addWidget(self._save_key_button)
        key_row.addWidget(self._clear_key_button)
        layout.addLayout(key_row)
        self._key_status = QtWidgets.QLabel("")
        layout.addWidget(self._key_status)

        model_buttons = QtWidgets.QHBoxLayout()
        self._model_list = QtWidgets.QListWidget()
        self._fetch_button = QtWidgets.QPushButton(FETCH_MODELS_TEXT)
        self._new_model_edit = QtWidgets.QLineEdit()
        self._new_model_edit.setPlaceholderText("模型 id")
        self._add_model_button = QtWidgets.QPushButton(ADD_MODEL_TEXT)
        model_buttons.addWidget(self._new_model_edit, 1)
        model_buttons.addWidget(self._add_model_button)
        layout.addWidget(self._model_list, 1)
        layout.addLayout(model_buttons)

        actions = QtWidgets.QHBoxLayout()
        self._edit_model_button = QtWidgets.QPushButton(EDIT_MODEL_TEXT)
        self._toggle_model_button = QtWidgets.QPushButton(ENABLE_TEXT)
        self._set_default_button = QtWidgets.QPushButton(SET_DEFAULT_TEXT)
        self._remove_model_button = QtWidgets.QPushButton(REMOVE_MODEL_TEXT)
        self._remove_provider_button = QtWidgets.QPushButton(REMOVE_PROVIDER_TEXT)
        self._save_provider_button = QtWidgets.QPushButton(SAVE_PROVIDER_TEXT)
        self._fetch_button.clicked.connect(lambda _=False: self._fetch_models())
        for button in (self._edit_model_button, self._toggle_model_button,
                       self._set_default_button, self._remove_model_button):
            actions.addWidget(button)
        actions.addStretch(1)
        actions.addWidget(self._remove_provider_button)
        actions.addWidget(self._save_provider_button)
        layout.addLayout(actions)

        self._model_list.currentRowChanged.connect(lambda _row: self._sync_model_buttons())
        self._save_provider_button.clicked.connect(lambda _=False: self._save_provider())
        self._remove_provider_button.clicked.connect(lambda _=False: self._remove_provider())
        self._save_key_button.clicked.connect(lambda _=False: self._save_key())
        self._clear_key_button.clicked.connect(lambda _=False: self._clear_key())
        self._add_model_button.clicked.connect(lambda _=False: self._add_model())
        self._edit_model_button.clicked.connect(lambda _=False: self._open_model())
        self._toggle_model_button.clicked.connect(lambda _=False: self._toggle_model())
        self._set_default_button.clicked.connect(lambda _=False: self._set_default())
        self._remove_model_button.clicked.connect(lambda _=False: self._remove_model())
        return page

    def _build_model_page(self) -> Any:
        from utils.qt_compat import QtWidgets

        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        form = QtWidgets.QFormLayout()
        self._model_name_edit = QtWidgets.QLineEdit()
        self._context_spin = QtWidgets.QSpinBox()
        self._context_spin.setRange(0, 10_000_000)
        self._context_spin.setSpecialValueText("自动")
        self._output_spin = QtWidgets.QSpinBox()
        self._output_spin.setRange(0, 1_000_000)
        self._output_spin.setSpecialValueText("自动")
        form.addRow("显示名", self._model_name_edit)
        form.addRow("上下文窗口", self._context_spin)
        form.addRow("最大输出", self._output_spin)
        layout.addLayout(form)
        buttons = QtWidgets.QHBoxLayout()
        self._restore_button = QtWidgets.QPushButton(RESTORE_AUTO_TEXT)
        self._save_model_button = QtWidgets.QPushButton(SAVE_PROVIDER_TEXT)
        buttons.addWidget(self._restore_button)
        buttons.addStretch(1)
        buttons.addWidget(self._save_model_button)
        layout.addLayout(buttons)
        layout.addStretch(1)
        self._restore_button.clicked.connect(lambda _=False: self._save_model(clear=True))
        self._save_model_button.clicked.connect(lambda _=False: self._save_model())
        return page

    # ── 查询与刷新 ────────────────────────────────────────────────────────
    def page(self) -> str:
        """当前页：list / provider / model（测试与截图脚本用）。"""
        return self._page

    def current_provider_id(self) -> str:
        return self._provider_id

    def current_model_id(self) -> str:
        return self._model_id

    def widget(self) -> Any:
        return self._widget

    def widgets(self) -> dict[str, Any]:
        """命名控件（测试与截图脚本驱动用；界面内部不依赖这个映射）。"""
        return {
            "back": self._back_button,
            "effort": self._effort_combo,
            "message": self._message,
            "active_label": self._active_label,
            "provider_list": self._provider_list,
            "open_provider": self._open_button,
            "add_provider": self._add_provider_button,
            "name": self._name_edit,
            "base_url": self._base_edit,
            "adapter": self._adapter_combo,
            "enabled": self._enabled_box,
            "key": self._key_edit,
            "save_key": self._save_key_button,
            "clear_key": self._clear_key_button,
            "key_status": self._key_status,
            "model_list": self._model_list,
            "new_model": self._new_model_edit,
            "add_model": self._add_model_button,
            "fetch_models": self._fetch_button,
            "edit_model": self._edit_model_button,
            "toggle_model": self._toggle_model_button,
            "set_default": self._set_default_button,
            "remove_model": self._remove_model_button,
            "remove_provider": self._remove_provider_button,
            "save_provider": self._save_provider_button,
            "model_name": self._model_name_edit,
            "context_window": self._context_spin,
            "max_output": self._output_spin,
            "restore_auto": self._restore_button,
            "save_model": self._save_model_button,
        }

    def _refresh(self) -> None:
        provider = self.viewmodel.provider(self._provider_id) if self._provider_id else None
        if self._page == "provider" and provider is None:
            self._page = "list"
        if self._page == "model" and provider is None:
            self._page = "list"
        self._refresh_header()
        self._refresh_list()
        if self._page == "provider":
            self._refresh_provider(provider)
        elif self._page == "model":
            self._refresh_model(provider)
        index = {"list": 0, "provider": 1, "model": 2}[self._page]
        self._pages.setCurrentIndex(index)
        self._back_button.setText(BACK_TEXT if self._page != "list" else "关闭")

    def _refresh_header(self) -> None:
        self._active_label.setText(f"默认模型：{self.viewmodel.active_model or '未选择'}")
        level = self.viewmodel.active_effort
        if level in EFFORT_LEVELS:
            self._effort_combo.blockSignals(True)
            self._effort_combo.setCurrentIndex(EFFORT_LEVELS.index(level))
            self._effort_combo.blockSignals(False)
        self._message.setText(self.viewmodel.message or "")

    def _refresh_list(self) -> None:
        from utils.qt_compat import QtWidgets

        providers = self.viewmodel.providers
        current = self._provider_id
        self._provider_list.blockSignals(True)
        self._provider_list.clear()
        select_row = -1
        for row, entry in enumerate(providers):
            state = "已启用" if entry["enabled"] else "未启用"
            models = len(entry["models"])
            item = QtWidgets.QListWidgetItem(
                f"{entry['name']} · {entry['adapter_label']} · {state} · {models} 个模型"
            )
            self._provider_list.addItem(item)
            if entry["id"] == current:
                select_row = row
        if select_row >= 0:
            self._provider_list.setCurrentRow(select_row)
        self._provider_list.blockSignals(False)
        self._sync_list_buttons()

    def _refresh_provider(self, provider: Optional[dict[str, Any]]) -> None:
        if provider is None:
            return
        self._name_edit.setText(provider["name"])
        self._base_edit.setText(provider["base_url"])
        self._adapter_combo.setCurrentIndex(ADAPTERS.index(provider["adapter"]))
        self._enabled_box.setChecked(bool(provider["enabled"]))
        self._key_edit.clear()
        self._key_status.setText(key_status_text(self.viewmodel.has_key(provider["id"])))
        self._refresh_models(provider)

    def _refresh_models(self, provider: dict[str, Any]) -> None:
        from utils.qt_compat import QtWidgets

        active = self.viewmodel.active_model
        # 重建会清空选中行；记下来再恢复，否则「停用」一次后按钮全部变灰，用户得重新点选。
        previous = self._model_list.currentRow()
        self._model_list.clear()
        for model in provider["models"]:
            mark = "✓" if model["enabled"] else "○"
            default = "（默认）" if active == f"{provider['id']}:{model['id']}" else ""
            self._model_list.addItem(QtWidgets.QListWidgetItem(f"{mark} {model['name']}{default}"))
        if 0 <= previous < len(provider["models"]):
            self._model_list.setCurrentRow(previous)
        self._sync_model_buttons()

    def _refresh_model(self, provider: Optional[dict[str, Any]]) -> None:
        if provider is None:
            return
        model = next((m for m in provider["models"] if m["id"] == self._model_id), None)
        if model is None:
            return
        self._model_name_edit.setText(model["name"])
        self._context_spin.setValue(int(model["context_window"] or 0))
        self._output_spin.setValue(int(model["max_output"] or 0))

    # ── 动作 ──────────────────────────────────────────────────────────────
    def _back(self) -> None:
        if self._page == "model":
            self._page = "provider"
            self._model_id = ""
        elif self._page == "provider":
            self._page = "list"
            self._provider_id = ""
            self._notify("设置已更新，下一轮对话生效")
        else:
            self._fire(self._on_back)
            return
        self._refresh()

    def _selected_provider_id(self) -> str:
        row = self._provider_list.currentRow()
        if row < 0:
            return ""
        entry = self.viewmodel.providers[row] if row < len(self.viewmodel.providers) else None
        return entry["id"] if entry else ""

    def _open_provider(self) -> None:
        provider_id = self._selected_provider_id()
        if not provider_id:
            return
        self._provider_id = provider_id
        self._page = "provider"
        self._refresh()

    def _add_provider(self) -> None:
        provider_id = self.viewmodel.add_provider("自定义服务商")
        self._provider_id = provider_id
        self._page = "provider"
        self._notify("已新增服务商：填写地址、密钥与模型后即可使用")
        self._refresh()

    def _save_provider(self) -> None:
        if not self._provider_id:
            return
        adapter = ADAPTERS[self._adapter_combo.currentIndex()]
        self.viewmodel.update_provider(
            self._provider_id,
            name=self._name_edit.text().strip() or self._provider_id,
            base_url=self._base_edit.text().strip(),
            adapter=adapter,
            enabled=self._enabled_box.isChecked(),
        )
        self._notify("服务商已保存")
        self._refresh()

    def _remove_provider(self) -> None:
        if not self._provider_id:
            return
        removed = self.viewmodel.remove_provider(self._provider_id)
        self._provider_id = ""
        self._page = "list"
        self._notify("服务商已删除" if removed else "服务商删除失败")
        self._refresh()

    def _save_key(self) -> None:
        if not self._provider_id:
            return
        key = self._key_edit.text()
        ok = self.viewmodel.set_api_key(self._provider_id, key)
        self._key_edit.clear()
        self._notify("密钥已保存" if ok else "密钥保存失败")
        self._refresh()

    def _clear_key(self) -> None:
        if not self._provider_id:
            return
        self.viewmodel.set_api_key(self._provider_id, "")
        self._notify("密钥已清除")
        self._refresh()

    def _add_model(self) -> None:
        if not self._provider_id:
            return
        model_id = self._new_model_edit.text().strip()
        added = self.viewmodel.add_model(self._provider_id, model_id)
        self._new_model_edit.clear()
        self._notify("模型已添加" if added else "模型未添加（id 为空或已存在）")
        self._refresh()

    def _fetch_models(self) -> None:
        """拉清单是异步的：交给窗口层的 runnable，结果回来后写进输入框供勾选/添加。"""
        if not self._provider_id:
            return
        self._notify("正在拉取模型清单…")
        self._fire(self._on_fetch, self._provider_id)

    def _selected_model_id(self) -> str:
        provider = self.viewmodel.provider(self._provider_id) if self._provider_id else None
        if provider is None:
            return ""
        row = self._model_list.currentRow()
        if row < 0 or row >= len(provider["models"]):
            return ""
        return provider["models"][row]["id"]

    def _toggle_model(self) -> None:
        model_id = self._selected_model_id()
        if model_id:
            self.viewmodel.toggle_model(self._provider_id, model_id)
            self._refresh()

    def _set_default(self) -> None:
        model_id = self._selected_model_id()
        if model_id:
            self.viewmodel.set_active_model(self._provider_id, model_id)
            self._notify("已设为默认模型")
            self._refresh()

    def _remove_model(self) -> None:
        model_id = self._selected_model_id()
        if model_id:
            self.viewmodel.remove_model(self._provider_id, model_id)
            self._notify("模型已删除")
            self._refresh()

    def _open_model(self) -> None:
        model_id = self._selected_model_id()
        if not model_id:
            return
        self._model_id = model_id
        self._page = "model"
        self._refresh()

    def _save_model(self, clear: bool = False) -> None:
        if not self._provider_id or not self._model_id:
            return
        self.viewmodel.update_model(
            self._provider_id,
            self._model_id,
            name=self._model_name_edit.text().strip() or self._model_id,
            context_window=None if clear else (self._context_spin.value() or None),
            max_output=None if clear else (self._output_spin.value() or None),
            clear=clear,
        )
        self._notify("模型已保存")
        self._refresh()

    def _on_effort_changed(self, index: int) -> None:
        if 0 <= index < len(EFFORT_LEVELS):
            self.viewmodel.set_active_effort(EFFORT_LEVELS[index])
            self._notify("思考等级已更新，下一轮对话生效")
            self._refresh_header()

    # ── 按钮可用性 ────────────────────────────────────────────────────────
    def _sync_list_buttons(self) -> None:
        self._open_button.setEnabled(bool(self._selected_provider_id()))

    def _sync_model_buttons(self) -> None:
        has_selection = bool(self._selected_model_id())
        for button in (self._edit_model_button, self._toggle_model_button,
                       self._set_default_button, self._remove_model_button):
            button.setEnabled(has_selection)
        self._toggle_model_button.setText(DISABLE_TEXT if has_selection else ENABLE_TEXT)

    # ── 通知 ──────────────────────────────────────────────────────────────
    def _notify(self, message: str) -> None:
        if self._on_notice is not None:
            self._on_notice(message)

    def _on_vm_changed(self, _event: Any = None) -> None:
        self._refresh()

    @staticmethod
    def _fire(callback: Optional[Callable[..., None]], *args: Any) -> None:
        if callback is not None:
            callback(*args)

    def close(self) -> None:
        pass


__all__ = [
    "ADD_MODEL_TEXT",
    "ADD_PROVIDER_TEXT",
    "BACK_TEXT",
    "CLEAR_KEY_TEXT",
    "EFFORT_LABELS",
    "FETCH_MODELS_TEXT",
    "KEY_MISSING_HINT",
    "KEY_SET_HINT",
    "REMOVE_MODEL_TEXT",
    "REMOVE_PROVIDER_TEXT",
    "SAVE_KEY_TEXT",
    "SAVE_PROVIDER_TEXT",
    "SET_DEFAULT_TEXT",
    "SettingsPane",
    "TITLE",
    "effort_labels",
    "key_status_text",
]
