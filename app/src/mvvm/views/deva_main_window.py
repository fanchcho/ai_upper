"""主窗口：左侧会话列表 + 右侧对话 / 设置，底部状态栏。

这是 Qt 原生三栏主窗口，由 `tests/test_deva_panes.py` 装配并驱动（它不是应用入口：
打包入口走的是 QML 壳 `qml_shell.py`）。它不直接读写
磁盘或网络：会话列表与设置各有一个 ViewModel，聊天是 `ChatViewModel`；窗口只做
三件事——把面板摆好、在用户切换会话时让聊天 ViewModel `open_session`、把跨面板的
提示写到状态栏。

三个可观察的限制都来自框架：`MVVMApplication.start()` 会显示**所有**已注册的 View，
所以会话列表与设置页做成嵌进本窗口的控件，而不是各自注册成独立 View。
"""
from __future__ import annotations
from locale_runtime import tr

import asyncio
import threading
from typing import Any, Callable, Optional

from mvvm.view_models.chat_sessions_vm import ChatSessionsViewModel
from mvvm.view_models.chat_vm import ChatViewModel
from mvvm.view_models.settings_vm import SettingsViewModel
from mvvm.views.base_view import ViewBase
from mvvm.views.chat_pane import ChatPane
from mvvm.views.session_list import SessionListPane
from mvvm.views.settings_pane import SettingsPane
from utils.paths import app_name

WINDOW_TITLE = app_name()
SPLIT_SIZES = (280, 780)
STATUS_DEFAULT = tr('legacy.b796f2d4ca85')


def notice_text(message: str, *, level: str = "info") -> str:
    """状态栏文案：错误带前缀，普通提示原样。"""
    text = str(message or "").strip()
    if not text:
        return ""
    return f"{text}" if level != "error" else tr('legacy.01dd57ee1fb5' ,p1=text)


class DevaMainWindow(ViewBase):
    """装配后的主窗口。构造参数都是已就绪的 ViewModel（由装配处提供）。"""

    def __init__(
        self,
        chat: ChatViewModel,
        sessions: ChatSessionsViewModel,
        settings: SettingsViewModel,
        *,
        fetch_models: Optional[Callable[[str], Any]] = None,
    ) -> None:
        super().__init__(chat)
        from utils.qt_compat import QtCore, QtWidgets, enum_member

        self._chat = chat
        self._sessions = sessions
        self._settings = settings
        self._fetch_models = fetch_models
        self._fetch_thread: Optional[threading.Thread] = None

        window = QtWidgets.QMainWindow()
        window.setWindowTitle(WINDOW_TITLE)
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QtWidgets.QSplitter(enum_member(QtCore.Qt, "Horizontal"))
        # 状态栏先建：设置页构造时会触发 `_refresh_header` -> 下拉框 `setCurrentIndex`
        # -> `_on_effort_changed` -> `on_notice` -> `_set_status`，此时 `_status` 必须已存在。
        # 布局顺序仍在最后加入（代码下方 `layout.addWidget(self._status)`）。
        self._status = QtWidgets.QLabel((tr('legacy.b796f2d4ca85')))
        self._session_pane = SessionListPane(
            sessions,
            on_select=self._switch_session,
            on_new=self._new_session,
            on_rename=self._rename_session,
            on_archive=self._archive_session,
            on_delete=self._delete_session,
            on_settings=self._show_settings,
        )
        self._chat_pane = ChatPane(chat)
        self._settings_pane = SettingsPane(
            settings,
            on_back=self._back_to_chat,
            on_notice=self._set_status,
            on_fetch=self._fetch_models_async,
        )
        # 布局是「左：会话列表 / 右：内容区」，内容区在对话与设置之间切换。
        # 设置是内容区的一页，不是第四列（Deva 的 `ChatFirstShell` 把设置渲染在
        # `section === 'models'` 的内容位置，独占整块内容区）。
        self._stack = QtWidgets.QStackedWidget()
        self._stack.addWidget(self._chat_pane.widget())
        self._stack.addWidget(self._settings_pane.widget())
        splitter.addWidget(self._session_pane.widget())
        splitter.addWidget(self._stack)
        splitter.setSizes(list(SPLIT_SIZES))

        layout.addWidget(splitter, 1)
        layout.addWidget(self._status)
        window.setCentralWidget(central)
        window.resize(1080, 720)

        self._window = window
        self._splitter = splitter
        self._settings_visible = False
        self._chat_pane.widget().hide()

        qapp = QtWidgets.QApplication.instance()
        if qapp is not None:
            qapp.aboutToQuit.connect(self.close)

        sessions.set_active(chat.session_id)
        self._show_chat()

    # ── 供窗口层/测试/截图脚本 ─────────────────────────────────────────────
    def chat_pane(self) -> ChatPane:
        return self._chat_pane

    def session_pane(self) -> SessionListPane:
        return self._session_pane

    def settings_pane(self) -> SettingsPane:
        return self._settings_pane

    @property
    def status_text(self) -> str:
        return self._status.text()

    @property
    def settings_visible(self) -> bool:
        return self._settings_visible

    # ── 会话切换 ──────────────────────────────────────────────────────────
    def _show_chat(self) -> None:
        self._settings_visible = False
        self._stack.setCurrentIndex(0)
        self._settings_pane.widget().hide()
        self._chat_pane.widget().show()

    def _back_to_chat(self) -> None:
        self._show_chat()
        self._set_status((tr('legacy.b796f2d4ca85')))

    def _show_settings(self) -> None:
        self._settings_visible = True
        self._stack.setCurrentIndex(1)
        self._chat_pane.widget().hide()
        self._settings_pane.widget().show()
        self._set_status(tr('legacy.7debf9cb0372'))

    def _switch_session(self, session_id: str) -> None:
        if not session_id or session_id == self._chat.session_id:
            return
        if self._chat.busy:
            self._set_status(tr('legacy.f6a9dcdaa966'))
            self._session_pane.rebuild()
            return
        self._open(session_id)

    def _open(self, session_id: str) -> None:
        self._chat.open_session(session_id)
        self._sessions.set_active(session_id)
        self._sessions.refresh()
        self._session_pane.rebuild()
        self._show_chat()
        self._set_status((tr('legacy.b796f2d4ca85')))

    def _new_session(self) -> None:
        # 惰性建档：新会话要等第一条消息落盘才出现在列表里（与 Deva 一致）。
        session_id = self._sessions.new_session()
        self._chat.open_session(session_id)
        self._sessions.refresh()
        self._session_pane.rebuild()
        self._show_chat()
        self._set_status(tr('legacy.1b7abf96f8bc'))

    def _rename_session(self, session_id: str) -> None:
        from utils.qt_compat import QtWidgets

        current = next((s for s in self._sessions.sessions if s["id"] == session_id), None)
        title, ok = QtWidgets.QInputDialog.getText(
            self._window, tr('legacy.23543b7d1ae2'), tr('legacy.65234c1d4f77'), text=(current or {}).get("title", "")
        )
        if not ok:
            return
        title = str(title or "").strip()
        if not title:
            self._set_status(tr('legacy.f2d8d992fe5c'))
            return
        self._sessions.rename(session_id, title)
        if session_id == self._chat.session_id:
            self._chat.title_property.set_value(title)
        self._session_pane.rebuild()
        self._set_status(tr('legacy.dc9fe43fb71e'))

    def _archive_session(self, session_id: str) -> None:
        self._sessions.archive(session_id, True)
        self._session_pane.rebuild()
        if session_id == self._chat.session_id:
            remaining = self._sessions.sessions
            if remaining:
                self._open(remaining[0]["id"])
            else:
                self._new_session()
        self._set_status(tr('legacy.f5bc1155fbff'))

    def _delete_session(self, session_id: str) -> None:
        from utils.qt_compat import QtWidgets, enum_member

        yes = enum_member(QtWidgets.QMessageBox, "Yes")
        no = enum_member(QtWidgets.QMessageBox, "No")
        answer = QtWidgets.QMessageBox.question(
            self._window, tr('legacy.3559dc2da370'), tr('legacy.6279db526363'), yes | no, no
        )
        if answer != yes:
            return
        deleted = self._sessions.delete(session_id)
        self._session_pane.rebuild()
        if deleted and session_id == self._chat.session_id:
            remaining = self._sessions.sessions
            if remaining:
                self._open(remaining[0]["id"])
            else:
                self._new_session()
        self._set_status(tr('legacy.fb5fe1e266c6') if deleted else tr('legacy.a597340b1005'))

    # ── 拉模型清单（后台线程）──────────────────────────────────────────────
    def _fetch_models_async(self, provider_id: str) -> None:
        if self._fetch_models is None:
            self._set_status(tr('legacy.ca9f571a40a9'))
            return
        if self._fetch_thread is not None and self._fetch_thread.is_alive():
            self._set_status(tr('legacy.bb113e28a86b'))
            return

        def runner() -> None:
            try:
                result = asyncio.run(_await_maybe(self._fetch_models(provider_id)))
                if result is None:
                    self._post(tr('legacy.a19c2d6d29e3'))
                elif getattr(result, "ok", False):
                    self._post(tr('legacy.70c9d64d3c44' ,p1=len(result.models)))
                else:
                    self._post(tr('legacy.4f27d4a2784d' ,p1=getattr(result, 'message', '')))
            except Exception as exc:  # noqa: BLE001 - 线程边界，错误要显示到状态栏
                self._post(tr('legacy.4f27d4a2784d' ,p1=exc))
            finally:
                self._fetch_thread = None

        self._fetch_thread = threading.Thread(target=runner, name="models-fetch", daemon=True)
        self._fetch_thread.start()

    def _post(self, message: str) -> None:
        """后台线程 → UI 线程：排队一次状态栏更新，由聊天面板的 drain 定时器顺带执行。"""

        def apply() -> None:
            self._set_status(message)

        self._chat._ui(apply)

    # ── 状态栏 ────────────────────────────────────────────────────────────
    def _set_status(self, message: str) -> None:
        self._status.setText(notice_text(message))

    # ── 生命周期 ──────────────────────────────────────────────────────────
    def show(self) -> None:
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def close(self) -> None:
        self._chat_pane.close()
        self._window.close()


async def _await_maybe(value: Any) -> Any:
    """`fetch_models` 可能是协程也可能是同步返回值（测试里给假的）。"""
    if hasattr(value, "__await__"):
        return await value
    return value


__all__ = ["DevaMainWindow", "STATUS_DEFAULT", "WINDOW_TITLE", "notice_text"]
