"""编辑区右键菜单：deva 主进程 index.ts:183-217 的原生 edit 菜单（剪切/复制/粘贴/全选）。

QML 的 TextArea/TextEdit 默认没有右键菜单；本测试真实右键打开、点击「全选」，
断言目标控件真的全选，而不是只弹出一个空壳。
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication

    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


def _find_item(root, name):
    try:
        if root.objectName() == name:
            return root
    except Exception:
        pass
    for child in root.childItems():
        found = _find_item(child, name)
        if found is not None:
            return found
    return None


def _build(tmp_path, monkeypatch):
    from test_qml_sidebar_collapse import _build as base
    return base(tmp_path, monkeypatch)


def _scene_center(item):
    from PySide6.QtCore import QPointF

    p = item.mapToScene(QPointF(item.property("width") / 2, item.property("height") / 2))
    return p.x(), p.y()


def test_right_click_opens_edit_menu_and_select_all_works(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QObject, QPoint, Qt
    from PySide6.QtTest import QTest
    from qml_shell import _pump

    window, _bridge, _settings, ticker, engine = _build(tmp_path, monkeypatch)
    try:
        field = _find_item(window.contentItem(), "inputField")
        assert field is not None
        field.setProperty("text", "第一行 第二行")
        _pump(qapp, lambda: False, 0.2)
        x, y = _scene_center(field)
        QTest.mouseClick(window, Qt.RightButton, Qt.NoModifier, QPoint(round(x), round(y)), 100)
        _pump(qapp, lambda: False, 0.3)
        menu = window.findChild(QObject, "composerMenu")
        assert menu is not None and menu.property("visible") is True

        # 菜单项「全选」是 QQuickMenuItem：点击其 contentItem 中心。
        item = window.findChild(QObject, "editMenuSelectAll")
        assert item is not None
        content = item.property("contentItem")
        cx, cy = _scene_center(content)
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(cx), round(cy)), 100)
        _pump(qapp, lambda: False, 0.2)
        assert field.property("selectedText") == "第一行 第二行"

        # 正文（只读）菜单不应有剪切/粘贴项。
        body = _find_item(window.contentItem(), "bodyView")
        bx, by = _scene_center(body)
        QTest.mouseClick(window, Qt.RightButton, Qt.NoModifier, QPoint(round(bx), round(by)), 100)
        _pump(qapp, lambda: False, 0.3)
        body_menu = window.findChild(QObject, "bodyMenu")
        assert body_menu is not None and body_menu.property("visible") is True
        assert body_menu.property("editable") is False
    finally:
        ticker.stop(); window.close(); engine.deleteLater()
