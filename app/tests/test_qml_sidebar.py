"""侧栏会话行：按 deva CSS/DOM 取宽高、内边距、圆角与 hover/selected/active 三态底色。

判据来源（只读 deva）：
- `redesign.css:32`：`.cf-body` 第二列 `--cf-side` 默认 300px；`:193` `.cf-rail` 右框 1px
  → `.cf-list` clientWidth 299；
- `redesign.css:741-746`：`.cf-list` 左右 padding `var(--space-2)`=8、`overflow-y:auto`；
- `styles/app.css:45-62`：WebKit 滚动条宽 8；
- 所以行内容宽 = 299 - 8×2 - 8 = 275，DOM `out/qml-shell/dom/chat.json`
  的 `threads[0].rect` 实测也是 `{x:64, y:56, w:275, h:54}`；
- `redesign.css:749-767`：`.cf-thread` padding 8px 12px、圆角 `var(--radius)`=8、上下两行 38px 头像
  → 行高 38 + 8×2 = 54；hover `var(--bg-hover)`、active `var(--bg-selected)`；
- `redesign.css:788-793`：多选 picked 态同样使用 `var(--bg-selected)`；
- `styles/tokens.css:45-47`：`--bg-hover: rgba(0,0,0,0.045)`、`--bg-selected: rgba(91,91,214,0.12)`。
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication

    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


def _pixel(image, x: int, y: int) -> tuple[int, int, int]:
    color = image.pixelColor(x, y)
    return color.red(), color.green(), color.blue()


def test_sidebar_rows_match_deva_bounds_and_states(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtTest import QTest

    import test_qml_window_controls as window_test

    sessions = [(f"s-{index:03d}", f"会话 {index:03d}") for index in range(20)]
    window, _bridge, ticker, engine = window_test._build_window(
        tmp_path, monkeypatch, sessions=sessions
    )
    try:
        window_test._pump(qapp, 0.8)

        rows = [window_test._find_item(window.contentItem(), f"threadRow{index}") for index in range(2)]
        assert all(row is not None for row in rows), "侧栏前两行必须已实例化"

        # x=64 来自 .cf-list x=56 + 左 padding 8；宽 275 来自 299-8×2-8。
        origin = rows[0].mapToScene(QPointF(0, 0))
        assert (origin.x(), origin.y()) == (64, 56)
        assert rows[0].property("width") == pytest.approx(275)
        assert rows[0].property("height") == pytest.approx(54)
        assert rows[1].mapToScene(QPointF(0, 0)).y() == 110

        image = window.grabWindow()
        # 第一行 active：rgba(91,91,214,0.12) 叠在 #f7f7f8 上 = (228,228,244)。
        assert _pixel(image, 70, 70) == (228, 228, 244)
        assert _pixel(image, 338, 70) == (228, 228, 244)
        assert _pixel(image, 339, 70) == (247, 247, 248), "行右缘必须止于 x=338"

        # chat 第 11 行：deva 原图鼠标 (200,700) 的 hover，rgba(0,0,0,0.045) → (236,236,237)。
        assert _pixel(image, 70, 660) == (236, 236, 237)
        assert _pixel(image, 338, 660) == (236, 236, 237)
        assert _pixel(image, 339, 660) == (247, 247, 248), "hover 范围同样止于 x=338"

        # 第二行 hover：真实鼠标移入后逐像素取同 token。
        # 全量顺序下 `test_qml_shell.py` 的包装用例会先把光标停在 (160,140)；
        # 若第二次 mouseMove 目标与全局光标同点，Qt 不会产生移动事件。先移开再移入，
        # 让本用例重复执行时仍能看到真实的 hover 切换。
        QTest.mouseMove(window, QPoint(20, 20))
        window_test._pump(qapp, 0.05)
        QTest.mouseMove(window, QPoint(160, 140))
        window_test._pump(qapp, 0.2)
        image = window.grabWindow()
        assert _pixel(image, 70, 140) == (236, 236, 237)
        assert _pixel(image, 338, 140) == (236, 236, 237)
        assert _pixel(image, 339, 140) == (247, 247, 248), "hover 范围同样止于 x=338"

        # 多选 picked：deva `.cf-thread.is-picked` 也用 --bg-selected，且出现勾选框。
        second_id = window.property("listedSessions")[1]["id"]
        window.setProperty("selectMode", True)
        window.setProperty("selectedSessions", [second_id])
        window_test._pump(qapp, 0.2)
        rows = [window_test._find_item(window.contentItem(), f"threadRow{index}") for index in range(2)]
        assert rows[0].property("active") is True
        assert rows[1].property("selected") is True
        check = window_test._find_item(rows[1], "threadCheck")
        assert check is not None and check.property("visible") is True
        image = window.grabWindow()
        assert _pixel(image, 70, 140) == (228, 228, 244)
        assert _pixel(image, 338, 140) == (228, 228, 244)
        assert _pixel(image, 339, 140) == (247, 247, 248), "picked 范围同样止于 x=338"
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


def test_long_mid_hover_tracks_the_visible_row_after_scrolling(qapp, tmp_path, monkeypatch):
    import test_qml_window_controls as window_test

    sessions = [(f"s-{index:03d}", f"会话 {index:03d}") for index in range(120)]
    window, _bridge, ticker, engine = window_test._build_window(
        tmp_path, monkeypatch, sessions=sessions
    )
    try:
        window.setProperty("page", "long-mid")
        window_test._pump(qapp, 0.8)
        scroller = window_test._find_item(window.contentItem(), "sessionList")
        assert scroller.property("contentY") == pytest.approx(1386)
        # 固定截图指针在窗口 y700；滚动后它落在 y668..721 的可见行。
        assert _pixel(window.grabWindow(), 70, 680) == (236, 236, 237)

        scroller.setProperty("contentY", 1406)
        window_test._pump(qapp, 0.2)
        image = window.grabWindow()
        assert _pixel(image, 70, 680) == (236, 236, 237)
        assert _pixel(image, 70, 710) == (247, 247, 248)

        window.setProperty("page", "chat")
        window_test._pump(qapp, 0.2)
        assert _pixel(window.grabWindow(), 70, 660) == (236, 236, 237)
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()
