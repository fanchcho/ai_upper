"""设置浮层：背景保持可见 + 左导航图标与只读原版逐项一致。

原版依据：
  - redesign.css:3135-3142 `.cf-modal__backdrop` 是 rgba(0,0,0,.42) 全屏遮罩；
  - SettingsPane.tsx:45-47 遮罩层不响应点击，只由右上角关闭按钮关闭；
  - SettingsPane.tsx:48-51 导航图标依次为 Cog / Brain / Puzzle / Info（size=15）。
"""
from __future__ import annotations

import os
import re
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from test_qml_context_menu import _build_window, _find_item, _pump


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication

    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


def _icon_paths():
    text = Path(__file__).resolve().parents[1] / "src/qml/IconData.qml"
    source = text.read_text()
    names = {}
    for key in ("cog", "brain", "puzzle", "info"):
        match = re.search(r"readonly property string %s: \"([^\"]*)\"" % key, source)
        assert match is not None, key
        names[key] = match.group(1)
    return names


def test_settings_keeps_live_page_under_backdrop(qapp, tmp_path, monkeypatch):
    window, bridge, store, home, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        window.setProperty("page", "settings-general")
        _pump(qapp, 0.6)
        assert window.property("settingsOpen") is True
        body = _find_item(window.contentItem(), "bodyScroll")
        composer = _find_item(window.contentItem(), "composer")
        modal = _find_item(window.contentItem(), "settingsModal")
        assert body is not None and composer is not None and modal is not None
        # 遮罩是覆盖层，不是把对话页 visibility 关掉；否则截出来只剩一块灰。
        assert body.property("visible") is True
        assert composer.property("visible") is True
        assert round(modal.property("width"), 1) == 720
        assert round(modal.property("height"), 1) == 560
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


def test_settings_nav_icons_match_deva(qapp, tmp_path, monkeypatch):
    window, bridge, store, home, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        window.setProperty("page", "settings-general")
        _pump(qapp, 0.6)
        paths = _icon_paths()
        for key in ("general", "models", "extensions", "about"):
            icon = _find_item(window.contentItem(), "settingsNavIcon_" + key)
            assert icon is not None, key
        assert _find_item(window.contentItem(), "settingsNavIcon_general").property("name") == paths["cog"]
        assert _find_item(window.contentItem(), "settingsNavIcon_models").property("name") == paths["brain"]
        assert _find_item(window.contentItem(), "settingsNavIcon_extensions").property("name") == paths["puzzle"]
        assert _find_item(window.contentItem(), "settingsNavIcon_about").property("name") == paths["info"]
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


def test_about_pane_includes_its_content_heading(qapp, tmp_path, monkeypatch):
    window, bridge, store, home, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        window.setProperty("page", "settings-about")
        _pump(qapp, 0.6)
        heading = _find_item(window.contentItem(), "aboutPaneHeading")
        assert heading is not None
        assert heading.property("visible") is True
        assert heading.property("text") == "About"
        # 标题属于右侧内容面板，而非左侧已有的导航标签。
        assert heading.parentItem().objectName() == "aboutPaneRoot"
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
