"""输入区两个贴片的下拉：模型列表 / 思考等级（真实 ``QTest.mouseClick``）。

判据全部走真实事件命中，不直接置位 ``pickerMode`` 造态：

1. 点模型贴片 → ``modelPickerOpen`` 打开且 ``pickerMode == "model"``；面板里只有模型列表
   （``modelList`` 可见、``thinkingList`` 不可见），分组标题是 provider 名、唯一一行是
   当前模型且文字为 accent 色、带 14px 勾选位；
2. 再点同一贴片 → 收起；点思考等级贴片 → ``pickerMode == "thinking"``，列表档位随模型能力
   收敛（``effortMenu`` 投影：Default + 该模型支持的档位），点 ``High`` 行 → 落盘生效档位、菜单收起；
3. 点模型行 → ``setActiveModel`` 生效、菜单收起；
4. 菜单打开时输入卡片四边都是 ``Theme.accent``（原版 ``.cf-box:focus-within``，
   实测 ``(91,91,214)``）——用真实渲染像素断言，不看绑定表达式。
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtQml import QQmlProperty

from test_qml_context_menu import _build_window, _center, _click, _find_item, _pump


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication

    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


def _build_chat_window(tmp_path, monkeypatch):
    """`_build_window` 默认落在 ctx-menu 页（整窗有一层点击遮罩），这里切回 chat 页。"""
    window, bridge, store, home, ticker, engine = _build_window(tmp_path, monkeypatch)
    window.setProperty("page", "chat")
    return window, bridge, store, home, ticker, engine


def _visible(window, name):
    item = _find_item(window.contentItem(), name)
    assert item is not None, f"缺少 {name}"
    return bool(item.property("visible"))


def _picker(window, name):
    """两个 ModelPicker 实例内部同名，必须从实例根往下找。"""
    root = _find_item(window.contentItem(), name)
    assert root is not None, f"缺少 {name}"
    return root


def _texts(item):
    """递归取视觉树里所有 Text 的 text（行文本没有 objectName）。"""
    chunks = []

    def walk(node):
        for child in node.childItems():
            value = child.property("text")
            if isinstance(value, str) and value:
                chunks.append(value)
            walk(child)

    walk(item)
    return chunks


def test_model_chip_opens_model_menu(qapp, tmp_path, monkeypatch):
    """点模型贴片：模型列表（不是 THINKING LEVEL），选中行 accent + 勾。"""
    window, bridge, store, home, ticker, engine = _build_chat_window(tmp_path, monkeypatch)
    try:
        _pump(qapp, 0.6)
        chip = _find_item(window.contentItem(), "modelChip")
        assert chip is not None
        _click(window, chip)
        _pump(qapp, 0.4)

        assert window.property("modelPickerOpen") is True
        assert window.property("pickerMode") == "model"

        picker = _picker(window, "modelPicker")
        assert picker.property("visible") is True
        assert _visible(window, "thinkingPicker") is False
        assert _find_item(picker, "modelList").property("visible") is True
        assert _find_item(picker, "thinkingList").property("visible") is False

        panel = _find_item(picker, "pickerPanel")
        # 原版 min-width 248 / 内容自适应上限 360（styles/app.css:3390-3392）
        assert 248 <= panel.property("width") <= 360
        assert panel.property("radius") == 12
        assert QQmlProperty.read(panel, "border.width") == 1

        head = _find_item(picker, "groupHead0")
        assert head is not None and head.property("text") == "p1"
        # 分组标题：`model-panel.css:116` 的 11.5px 在 Qt 侧只能落整数字号（取 12），
        # y=6 时墨迹 y700..712 与 deva 逐行相同（见 §4.9）。
        assert head.property("font").pixelSize() == 12
        assert head.property("y") == 6

        row = _find_item(picker, "modelRow0_0")
        assert row is not None
        assert _texts(row) == ["claude-sonnet-5-5"]
        text = next(c for c in row.childItems() if c.property("text"))
        assert text.property("color").name() == "#5b5bd6"
        assert text.property("font").weight() == 600
        assert row.property("height") == 27

        # 四边：菜单打开时输入卡片按聚焦态上色。
        from PySide6.QtGui import QColor

        composer = _find_item(window.contentItem(), "composer")
        assert QColor(QQmlProperty.read(composer, "border.color")).name() == "#5b5bd6"

        _pump(qapp, 0.2)
        image = window.grabWindow()
        for key, (x, y) in (("top", (700, 658)), ("bottom", (700, 803)),
                            ("left", (428, 720)), ("right", (1207, 720))):
            color = image.pixelColor(x, y)
            assert (color.red(), color.green(), color.blue()) == (91, 91, 214), key
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


def test_effort_chip_opens_thinking_menu_and_picks(qapp, tmp_path, monkeypatch):
    """点思考等级贴片：档位列表随模型能力；点 High → 生效档位写回且菜单收起。"""
    window, bridge, store, home, ticker, engine = _build_chat_window(tmp_path, monkeypatch)
    try:
        _pump(qapp, 0.6)
        chip = _find_item(window.contentItem(), "effortChip")
        assert chip is not None
        _click(window, chip)
        _pump(qapp, 0.4)

        assert window.property("modelPickerOpen") is True
        assert window.property("pickerMode") == "thinking"

        thinking = _picker(window, "thinkingPicker")
        assert thinking.property("visible") is True
        assert _picker(window, "modelPicker").property("visible") is False
        rows = [_find_item(thinking, "efRow%d" % i) for i in range(6)]
        assert all(row is not None for row in rows)
        assert [round(_center(row)[1], 1) for row in rows] == sorted(
            round(_center(row)[1], 1) for row in rows
        )
        names = [_texts(row)[0] for row in rows]
        # 档位随模型能力收敛：fixture 的 claude-sonnet-5-5 支持 5 档 + 默认。
        menu = window.property("effortMenu")
        assert [option["name"] for option in menu["options"]] == names
        assert names == ["Default", "Low", "Medium", "High", "Extra high", "Max"]

        _click(window, rows[3])
        _pump(qapp, 0.5)
        assert window.property("modelPickerOpen") is False
        assert window.property("activeEffort") == "high"
        assert window.property("effortLabel") == "High"
        assert window.property("pickerMode") == ""
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


def test_clicking_model_row_activates_it(qapp, tmp_path, monkeypatch):
    """点模型行：``setActiveModel`` 生效（引用不变时为幂等），菜单收起。"""
    window, bridge, store, home, ticker, engine = _build_chat_window(tmp_path, monkeypatch)
    try:
        _pump(qapp, 0.6)
        chip = _find_item(window.contentItem(), "modelChip")
        _click(window, chip)
        _pump(qapp, 0.4)

        picker = _picker(window, "modelPicker")
        row = _find_item(picker, "modelRow0_0")
        assert row is not None
        before = window.property("activeModelRef")
        _click(window, row)
        _pump(qapp, 0.5)
        assert window.property("modelPickerOpen") is False
        assert window.property("activeModelRef") == before == "p1:claude-sonnet-5-5"
        assert window.property("modelLabel") == "claude-sonnet-5-5"
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
