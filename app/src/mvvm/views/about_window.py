"""「关于」窗口：绑定 MainViewModel，自己不做任何业务判断。"""
from __future__ import annotations
from locale_runtime import tr

from mvvm.view_models import MainViewModel
from mvvm.views.base_view import ViewBase

CLOSE_BUTTON_TEXT = tr('legacy.6c14bd7f6f9e')


class AboutWindow(ViewBase):
    """关于窗口：显示 ViewModel 里的 about_title/about_body"""

    def __init__(self, viewmodel: MainViewModel) -> None:
        super().__init__(viewmodel)
        self._dialog = None

    def _create_dialog(self):
        from utils.qt_compat import QtWidgets

        viewmodel = self.viewmodel
        dialog = QtWidgets.QDialog()
        dialog.setWindowTitle(viewmodel.about_title)
        layout = QtWidgets.QVBoxLayout(dialog)
        browser = QtWidgets.QTextBrowser()
        browser.setPlainText(viewmodel.about_body)
        close_button = QtWidgets.QPushButton((tr('legacy.6c14bd7f6f9e')))
        layout.addWidget(browser)
        layout.addWidget(close_button)
        dialog.resize(560, 320)
        self.bind_property("about_title", dialog, "setWindowTitle")
        self.bind_property("about_body", browser, "setPlainText")
        self.bind_command("hide_about", close_button)
        self.bind_command("hide_about", dialog, "finished")
        return dialog

    def show(self) -> None:
        """按 ViewModel 当前的 about_visible 显示窗口"""
        if not self.viewmodel.about_visible:
            return
        if self._dialog is None:
            self._dialog = self._create_dialog()
        self._dialog.show()

    def close(self) -> None:
        if self._dialog is not None:
            self._dialog.close()
