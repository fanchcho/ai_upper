"""上下文圆环与容量卡片：真实点击 + QML 属性断言。

对应只读原版 `redesign/ContextRing.tsx` / `redesign/model-panel.css:20-75`：
28×28 贴片、16×16 圆环、卡片 260 宽、居圆环、越窗留 8px；读数缺失（used=None）不渲染。
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from test_qml_context_menu import _build_window, _click, _find_item, _pump


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication

    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


def _build_chat_window(tmp_path, monkeypatch):
    window, bridge, store, home, ticker, engine = _build_window(tmp_path, monkeypatch)
    window.setProperty("page", "chat")
    return window, bridge, store, home, ticker, engine


def _texts(item):
    chunks = []

    def walk(node):
        for child in node.childItems():
            value = child.property("text")
            if isinstance(value, str) and value:
                chunks.append(value)
            walk(child)

    walk(item)
    return chunks


def test_context_ring_geometry_and_card_toggle(qapp, tmp_path, monkeypatch):
    window, bridge, store, home, ticker, engine = _build_chat_window(tmp_path, monkeypatch)
    try:
        _pump(qapp, 0.6)
        content = window.contentItem()
        ring = _find_item(content, "contextRing")
        model_chip = _find_item(content, "modelChip")
        assert ring is not None and model_chip is not None
        assert ring.property("visible") is True
        assert round(ring.property("width"), 1) == 28
        assert round(ring.property("height"), 1) == 28
        # 贴片紧贴模型贴片左侧（原版 ModelPanel.tsx:71-74 顺序：ring 在 model-pick 前）。
        ring_right = ring.mapToItem(content, 0, 0).x() + ring.property("width")
        assert round(ring_right, 1) == round(model_chip.mapToItem(content, 0, 0).x(), 1)

        card = _find_item(content, "contextCard")
        assert card.property("visible") is False

        _click(window, ring)
        _pump(qapp, 0.4)
        assert window.property("contextOpen") is True
        assert card.property("visible") is True
        assert round(card.property("width"), 1) == 260
        assert round(card.property("height"), 1) == 53
        texts = _texts(card)
        assert "Context" in texts
        assert "~16 / 1M (<0.1%)" in texts
        # 卡片以圆环为中心，左右各留 ≥8px（窗口 1280）。
        card_x = card.mapToItem(content, 0, 0).x()
        assert card_x >= 8
        assert card_x + 260 <= window.width() - 8

        _click(window, ring)
        _pump(qapp, 0.3)
        assert window.property("contextOpen") is False
        assert card.property("visible") is False
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


def test_context_card_and_model_menu_are_mutually_exclusive(qapp, tmp_path, monkeypatch):
    window, bridge, store, home, ticker, engine = _build_chat_window(tmp_path, monkeypatch)
    try:
        _pump(qapp, 0.6)
        content = window.contentItem()
        ring = _find_item(content, "contextRing")
        model_chip = _find_item(content, "modelChip")
        card = _find_item(content, "contextCard")

        _click(window, ring)
        _pump(qapp, 0.3)
        assert window.property("contextOpen") is True

        # 点模型贴片：容量卡片收起，模型菜单打开。
        _click(window, model_chip)
        _pump(qapp, 0.3)
        assert window.property("contextOpen") is False
        assert card.property("visible") is False
        assert window.property("pickerMode") == "model"

        # 点圆环：模型菜单收起，容量卡片打开。
        _click(window, ring)
        _pump(qapp, 0.3)
        assert window.property("modelPickerOpen") is False
        assert window.property("contextOpen") is True
        assert card.property("visible") is True
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


def test_context_ring_collapses_without_reading(qapp, tmp_path, monkeypatch):
    window, bridge, store, home, ticker, engine = _build_chat_window(tmp_path, monkeypatch)
    try:
        _pump(qapp, 0.6)
        window.setProperty("contextUsage", {"used": None, "estimated": False, "window": 1000000, "trigger": 955000})
        _pump(qapp, 0.2)
        ring = _find_item(window.contentItem(), "contextRing")
        assert ring.property("visible") is False
        assert round(ring.property("width"), 1) == 0
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
