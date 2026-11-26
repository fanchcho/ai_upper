"""左侧会话列表：新建 / 切换 / 重命名 / 归档 / 删除。

数据来自 `ChatSessionsViewModel`（磁盘是唯一真相）；本控件只负责把投影画出来、
把用户动作转成对 ViewModel 的调用。操作结果（是否切到了别的会话）由窗口层决定，
所以这里不直接调用聊天 ViewModel。

用普通 Python 回调而不是自定义 Signal：回调在构造时注入，测试里可以直接替换成
记录器，不需要事件循环。
"""
from __future__ import annotations
from locale_runtime import tr

from typing import Any, Callable, Optional

from mvvm.view_models.chat_sessions_vm import ChatSessionsViewModel
from mvvm.views.base_view import ViewBase

NEW_BUTTON_TEXT = tr('legacy.b3e55858d9d4')
RENAME_BUTTON_TEXT = tr('legacy.1cd80fd7a8b3')
ARCHIVE_BUTTON_TEXT = tr('legacy.ddfde75bec38')
DELETE_BUTTON_TEXT = tr('legacy.3755f56f2f83')
SETTINGS_BUTTON_TEXT = tr('legacy.7debf9cb0372')
EMPTY_HINT = tr('legacy.46b23a5ba88a')


class SessionListPane(ViewBase):
    """会话列表控件。外部通过回调拿到用户动作。"""

    def __init__(
        self,
        viewmodel: ChatSessionsViewModel,
        *,
        on_select: Optional[Callable[[str], None]] = None,
        on_new: Optional[Callable[[], None]] = None,
        on_rename: Optional[Callable[[str], None]] = None,
        on_archive: Optional[Callable[[str], None]] = None,
        on_delete: Optional[Callable[[str], None]] = None,
        on_settings: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(viewmodel)
        from utils.qt_compat import QtWidgets

        self._on_select = on_select
        self._on_new = on_new
        self._on_rename = on_rename
        self._on_archive = on_archive
        self._on_delete = on_delete
        self._on_settings = on_settings
        self._rebuilding = False

        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)

        self._list = QtWidgets.QListWidget()
        self._hint = QtWidgets.QLabel((tr('legacy.46b23a5ba88a')))
        self._hint.setWordWrap(True)

        new_button = QtWidgets.QPushButton((tr('legacy.b3e55858d9d4')))
        rename_button = QtWidgets.QPushButton((tr('legacy.1cd80fd7a8b3')))
        archive_button = QtWidgets.QPushButton((tr('legacy.ddfde75bec38')))
        delete_button = QtWidgets.QPushButton((tr('legacy.3755f56f2f83')))
        settings_button = QtWidgets.QPushButton((tr('legacy.7debf9cb0372')))

        row1 = QtWidgets.QHBoxLayout()
        row1.addWidget(new_button)
        row1.addWidget(rename_button)
        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(archive_button)
        row2.addWidget(delete_button)
        row3 = QtWidgets.QHBoxLayout()
        row3.addWidget(settings_button)

        layout.addWidget(self._list, 1)
        layout.addWidget(self._hint)
        layout.addLayout(row1)
        layout.addLayout(row2)
        layout.addLayout(row3)

        self._widget = widget
        self._new_button = new_button
        self._rename_button = rename_button
        self._archive_button = archive_button
        self._delete_button = delete_button
        self._settings_button = settings_button

        self._list.currentRowChanged.connect(self._on_row_changed)
        new_button.clicked.connect(lambda _=False: self._fire(self._on_new))
        rename_button.clicked.connect(lambda _=False: self._fire_id(self._on_rename))
        archive_button.clicked.connect(lambda _=False: self._fire_id(self._on_archive))
        delete_button.clicked.connect(lambda _=False: self._fire_id(self._on_delete))
        settings_button.clicked.connect(lambda _=False: self._fire(self._on_settings))

        viewmodel.sessions_property.subscribe(self._on_sessions_changed)
        self.rebuild()

    # ── 供窗口/测试 ────────────────────────────────────────────────────────
    def widget(self) -> Any:
        return self._widget

    def list_widget(self) -> Any:
        return self._list

    def buttons(self) -> dict[str, Any]:
        """按钮名 → 控件（测试与截图脚本驱动用；界面内部不依赖这个映射）。"""
        return {
            "new": self._new_button,
            "rename": self._rename_button,
            "archive": self._archive_button,
            "delete": self._delete_button,
            "settings": self._settings_button,
        }

    def current_session_id(self) -> str:
        """当前选中的会话 id（没有选中返回空串）。"""
        row = self._list.currentRow()
        if row < 0:
            return ""
        item = self._list.item(row)
        return str(item.data(item_data_role()) or "")

    def rebuild(self) -> None:
        """按 ViewModel 的投影重建列表，并恢复选中行。"""
        from utils.qt_compat import QtWidgets

        sessions = self.viewmodel.sessions
        active = self.viewmodel.active_id
        self._rebuilding = True
        try:
            self._list.clear()
            active_row = -1
            for index, entry in enumerate(sessions):
                item = QtWidgets.QListWidgetItem(f"{entry['title']}\n{entry['subtitle']}")
                item.setData(item_data_role(), entry["id"])
                self._list.addItem(item)
                if entry["id"] == active:
                    active_row = index
            if active_row >= 0:
                self._list.setCurrentRow(active_row)
            self._show(self._list, bool(sessions))
            self._show(self._hint, not sessions)
        finally:
            self._rebuilding = False
        has_selection = bool(sessions) and self.current_session_id() != ""
        for button in (self._rename_button, self._archive_button, self._delete_button):
            button.setEnabled(has_selection)

    # ── 内部 ──────────────────────────────────────────────────────────────
    @staticmethod
    def _show(widget: Any, visible: bool) -> None:
        """`setVisible` 在不同绑定里拼写一致，但假控件只需 show/hide；统一走这两个。"""
        if visible:
            widget.show()
        else:
            widget.hide()

    def _on_sessions_changed(self, _event: Any = None) -> None:
        self.rebuild()

    def _on_row_changed(self, _row: int) -> None:
        if self._rebuilding:
            return
        session_id = self.current_session_id()
        if session_id:
            self._fire(self._on_select, session_id)

    def _fire_id(self, callback: Optional[Callable[[str], None]]) -> None:
        session_id = self.current_session_id()
        if session_id:
            self._fire(callback, session_id)

    @staticmethod
    def _fire(callback: Optional[Callable[..., None]], *args: Any) -> None:
        if callback is not None:
            callback(*args)


# QListWidgetItem 的自定义数据角色（Qt.UserRole 在 Qt5 是枚举、Qt6 是枚举成员）。
# 延迟到第一次用时再取：import 本模块不该需要 Qt（与包内其它窗口一致）。
def item_data_role() -> int:
    from utils.qt_compat import QtCore, enum_member

    return int(enum_member(QtCore.Qt, "UserRole"))


__all__ = [
    "ARCHIVE_BUTTON_TEXT",
    "DELETE_BUTTON_TEXT",
    "EMPTY_HINT",
    "NEW_BUTTON_TEXT",
    "RENAME_BUTTON_TEXT",
    "SETTINGS_BUTTON_TEXT",
    "SessionListPane",
    "item_data_role",
]
