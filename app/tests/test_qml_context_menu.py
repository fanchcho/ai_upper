"""会话右键菜单与删除确认框：真实 QML 窗口 + ``QTest.mouseClick``。

覆盖全部菜单动作（全部走真实事件命中，不直接调槽位）：

1. 点菜单第 5 项 ``Delete`` → 确认框出现（``confirm=True``），会话仍为 120；
2. 点确认框 ``Delete`` → 会话 120 → 119、会话文件消失、当前会话按 Deva 回退到最近一条；
3. 重开菜单后点 ``Cancel`` / 点背板 → ``confirm=False``、会话数不变；
4. 点 ``Rename`` → 输入框出现且可编辑，提交后标题落盘并反映到列表；
5. 点 ``Select`` → 多选态与底部批量条出现，点行可增减选择数；
6. 点 ``Archive`` → 会话从普通列表消失、写入 ``archived``，并在归档入口里可查到。

菜单的 5 项名称、顺序、几何与项中心也在第一组里量出来并断言，坐标不是旧截图的常量。
"""
from __future__ import annotations

import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from mvvm.models.chat_models import Message
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.persona_store import PersonaStore
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.settings_service import SettingsService
from mvvm.services.skill_store import SkillStore
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.webui.assembly import build_chat_host

from qml_shell_sessions import session_rows
from test_qml_shell import MODELS, text_stream

ROOT = Path(__file__).resolve().parents[2]
MENU_LABELS = ["New chat", "Rename", "Select", "Archive", "Delete"]


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication

    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


def _seed_sessions(store: ChatSessionStore, count: int = 120) -> None:
    """120 条真实落盘会话；parity-000 最新（删除后应回退到 parity-001）。"""
    now = int(time.time() * 1000)
    for index in range(count):
        session_id = f"parity-{index:03d}"
        session = store.ensure_session(session_id)
        session.messages = [Message(role="user", content="对比用会话：一条完整回合")]
        session.title = (
            "对比用会话：一条完整回合"
            if index == 0
            else f"会话 {index:03d}：准备发布说明"
        )
        # 显式拉开 updatedAt，保证回退顺序可断言（parity-000 最大）。
        session.updatedAt = now - index * 1000
        store.save(session_id)


def _build_window(tmp_path, monkeypatch):
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine

    from qml_shell import ShellBridge, _plain_mode, _start_ticker, qml_main

    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    monkeypatch.setenv("DEVA_ASSETS_DIR", str(ROOT / "app" / "assets"))
    home = tmp_path / "home"
    home.mkdir(parents=True)
    monkeypatch.setenv("AI_UPPER_HOME", str(home))

    settings = SettingsService(home)
    settings.set_config({"models": MODELS})
    vault = SecretsVault(home)
    vault.set_secret("p1", "sk-test")
    store = ChatSessionStore(home)
    _seed_sessions(store)
    PersonaStore(home).ensure_seeded()

    box: dict = {}

    def emit(payload):
        box["bridge"].emit(payload)

    host, _gateway = build_chat_host(
        settings=settings,
        vault=vault,
        store=store,
        guard=WorkspaceGuard(),
        home=home,
        emit=emit,
        emit_sessions_changed=lambda: None,
        transport=text_stream("x"),
    )
    bridge = ShellBridge(
        host=host,
        store=store,
        plain=_plain_mode(),
        settings=settings,
        vault=vault,
        skills=SkillStore(home),
    )
    box["bridge"] = bridge

    engine = QQmlApplicationEngine()
    bridge._engine = engine
    engine.rootContext().setContextProperty("shellBridge", bridge)
    engine.load(QUrl.fromLocalFile(str(qml_main())))
    roots = engine.rootObjects()
    assert len(roots) == 1, "Main.qml 必须能独立加载"
    window = roots[0]
    bridge.bind_window(window)
    bridge.initial()
    window.setProperty("page", "ctx-menu")
    window.show()
    ticker = _start_ticker(bridge)
    return window, bridge, store, home, ticker, engine


def _find_item(root, name: str):
    """QML 的 Repeater 委托不是 QObject 子节点，必须走视觉树 ``childItems()``。"""
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


def _center(item) -> tuple[float, float]:
    from PySide6.QtCore import QPointF

    point = item.mapToScene(
        QPointF(item.property("width") / 2.0, item.property("height") / 2.0)
    )
    return point.x(), point.y()


def _click(window, item, button=None) -> None:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    if button is None:
        button = Qt.LeftButton
    x, y = _center(item)
    QTest.mouseClick(window, button, Qt.NoModifier, QPoint(round(x), round(y)), 100)


def _pump(app, seconds: float = 0.4) -> None:
    from qml_shell import _pump as pump

    pump(app, lambda: False, seconds)


def _menu_items(window):
    return [_find_item(window.contentItem(), f"ctxMenuItem{i}") for i in range(5)]


def test_menu_geometry_and_delete_confirm_flow(qapp, tmp_path, monkeypatch):
    """第一/二组：5 项几何 → 点 Delete（菜单）→ 点 Delete（确认）→ 120→119。"""
    window, bridge, store, home, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        _pump(qapp, 0.6)
        items = _menu_items(window)
        assert all(item is not None for item in items)

        labels = []
        centers = []
        for item in items:
            labels.append(_item_label(item))
            centers.append(_center(item))

        assert labels == MENU_LABELS
        assert [round(y, 1) for _, y in centers] == [110.5, 139.5, 168.5, 197.5, 226.5]
        assert all(round(x, 1) == 234.0 for x, _ in centers)
        assert len(session_rows(store)) == 120
        assert bridge._active == "parity-000"

        # Delete 项的 hover 底色：Deva `color-mix(in srgb, #e5484d 14%, transparent)`。
        from PySide6.QtCore import QPoint
        from PySide6.QtTest import QTest

        QTest.mouseMove(window, QPoint(round(centers[4][0]), round(centers[4][1])))
        _pump(qapp, 0.2)
        hover = items[4].property("color")
        red, green, blue, alpha = hover.getRgb()
        assert (red, green, blue) == (229, 72, 77)
        assert 34 <= alpha <= 38, alpha

        _click(window, items[4])
        _pump(qapp, 0.4)
        confirm = _find_item(window.contentItem(), "confirmLayer")
        assert confirm is not None and confirm.property("visible") is True
        assert window.property("confirmOpen") is True
        assert len(session_rows(store)) == 120, "确认前不得删会话"

        _click(window, _find_item(window.contentItem(), "confirmDelete"))
        _pump(qapp, 0.6)
        assert confirm.property("visible") is False
        assert window.property("confirmOpen") is False
        assert len(session_rows(store)) == 119
        assert bridge._active == "parity-001"
        assert window.property("activeId") == "parity-001"
        assert not store.session_path("parity-000").exists()
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


def test_cancel_and_backdrop_keep_the_session(qapp, tmp_path, monkeypatch):
    """第三组：菜单 Delete → Cancel（真按钮）与背板点击都只关框，不删会话。"""
    window, bridge, store, home, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        _pump(qapp, 0.6)
        items = _menu_items(window)

        _click(window, items[4])
        _pump(qapp, 0.3)
        confirm = _find_item(window.contentItem(), "confirmLayer")
        assert confirm.property("visible") is True
        _click(window, _find_item(window.contentItem(), "confirmCancel"))
        _pump(qapp, 0.3)
        assert confirm.property("visible") is False
        assert window.property("confirmOpen") is False
        assert len(session_rows(store)) == 120
        assert bridge._active == "parity-000"
        assert store.session_path("parity-000").exists()

        # 背板：从列表行右键重新打开菜单，点卡片外的遮罩区域（100,100）也只取消。
        from PySide6.QtCore import Qt

        _click(window, _find_item(window.contentItem(), "threadRow0"), Qt.RightButton)
        _pump(qapp, 0.3)
        _click(window, _menu_items(window)[4])
        _pump(qapp, 0.3)
        assert confirm.property("visible") is True
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest

        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(100, 100), 100)
        _pump(qapp, 0.3)
        assert confirm.property("visible") is False
        assert len(session_rows(store)) == 120
        assert bridge._active == "parity-000"
        assert store.session_path("parity-000").exists()
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


def _item_label(item) -> str:
    """取菜单项里唯一那段 Text（Icon 没有 text 属性）。"""
    for child in item.childItems():
        for grandchild in child.childItems():
            text = grandchild.property("text")
            if isinstance(text, str) and text:
                return text
    raise AssertionError("菜单项缺少文字")

def _as_list(value):
    """QML 的 JS 数组属性在 PySide6 里是 QJSValue；转成 Python list 再断言。"""
    if hasattr(value, "toVariant"):
        value = value.toVariant()
    return list(value or [])


def _type_text(window, text: str) -> None:
    """把 ASCII 文本逐键送进当前焦点项；QTest.keyClicks 只接受 QWidget，QQuickWindow 需逐键发送。"""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    for char in text:
        if char == " ":
            QTest.keyClick(window, Qt.Key_Space, Qt.NoModifier)
        elif char.isupper():
            QTest.keyClick(window, getattr(Qt, "Key_" + char), Qt.ShiftModifier)
        else:
            QTest.keyClick(window, getattr(Qt, "Key_" + char.upper()), Qt.NoModifier)


def test_rename_menu_opens_editable_input_and_updates_title(qapp, tmp_path, monkeypatch):
    """第 4 组：Rename 是居中输入框（不是行内编辑），真实键入后标题落盘并刷新列表。"""
    window, bridge, store, home, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        _pump(qapp, 0.6)
        items = _menu_items(window)
        assert all(item is not None for item in items)

        _click(window, items[1])
        _pump(qapp, 0.4)
        dialog = _find_item(window.contentItem(), "renameDialog")
        field = _find_item(window.contentItem(), "renameInput")
        assert dialog is not None and dialog.property("visible") is True
        assert field is not None
        assert field.property("readOnly") is False
        assert field.property("text") == "对比用会话：一条完整回合"

        # 真实鼠标点进输入框，Ctrl+A 后键入新标题，再点确认按钮。
        _click(window, field)
        _pump(qapp, 0.2)
        assert field.property("activeFocus") is True
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        QTest.keyClick(window, Qt.Key_A, Qt.ControlModifier)
        _type_text(window, "renamed by click")
        _pump(qapp, 0.2)
        assert field.property("text") == "renamed by click"

        _click(window, _find_item(window.contentItem(), "renameConfirm"))
        _pump(qapp, 0.5)
        assert dialog.property("visible") is False
        assert window.property("renameOpen") is False
        assert store.load_session("parity-000").title == "renamed by click"
        assert window.property("activeTitle") == "renamed by click"
        row0 = _find_item(window.contentItem(), "threadRow0")
        assert row0 is not None and row0.property("title") == "renamed by click"
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


def test_select_menu_enters_multi_select_with_batch_bar(qapp, tmp_path, monkeypatch):
    """第 5 组：Select 立即选中被右键会话，底部批量条可见；点另一行增加选择数。"""
    window, bridge, store, home, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        _pump(qapp, 0.6)
        _click(window, _menu_items(window)[2])
        _pump(qapp, 0.4)

        bar = _find_item(window.contentItem(), "selectionBar")
        count = _find_item(window.contentItem(), "selectionCount")
        assert bar is not None and bar.property("visible") is True
        assert count is not None and count.property("text") == "1 selected"
        assert window.property("selectMode") is True
        assert _as_list(window.property("selectedSessions")) == ["parity-000"]

        _click(window, _find_item(window.contentItem(), "threadRow1"))
        _pump(qapp, 0.3)
        assert count.property("text") == "2 selected"
        assert _as_list(window.property("selectedSessions")) == ["parity-000", "parity-001"]

        _click(window, _find_item(window.contentItem(), "selectionExit"))
        _pump(qapp, 0.3)
        assert bar.property("visible") is False
        assert window.property("selectMode") is False
        assert _as_list(window.property("selectedSessions")) == []
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


def test_archive_menu_moves_session_and_archive_entry_lists_it(qapp, tmp_path, monkeypatch):
    """第 6 组：Archive 从普通列表移除并落盘，归档入口打开后能查到同一条会话。"""
    window, bridge, store, home, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        _pump(qapp, 0.6)
        _click(window, _menu_items(window)[3])
        _pump(qapp, 0.6)

        assert len(session_rows(store)) == 119
        assert len(window.property("sessions")) == 119
        assert store.load_session("parity-000").archived is True
        assert bridge._active == "parity-001"
        assert window.property("activeId") == "parity-001"
        archived = window.property("archivedSessions")
        assert len(archived) == 1 and archived[0]["id"] == "parity-000"

        entry = _find_item(window.contentItem(), "archiveEntry")
        assert entry is not None and entry.property("visible") is True
        _click(window, entry)
        _pump(qapp, 0.4)
        assert window.property("archiveView") is True
        header = _find_item(window.contentItem(), "archiveHeader")
        assert header is not None and header.property("visible") is True
        archived_row = _find_item(window.contentItem(), "threadRow0")
        assert archived_row is not None
        assert archived_row.property("title") == "对比用会话：一条完整回合"
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()
