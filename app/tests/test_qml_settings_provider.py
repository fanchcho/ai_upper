"""设置 › Models：服务商详情顶栏「删除」与其确认卡片的交互测试。

判据来源：Deva `features/settings/ModelSettings.tsx:195-207`（`onDeleteProvider`：
`dialog.confirm` → `removeProvider` → `setView('list')`）、`app.css:4905`
（`.provider-detail__del` 常态 `--fg-subtle`、hover `--danger`）。

这里只测 QML 侧的接线与几何——数据投影的规则在 `test_qml_settings_models.py` 里锁。
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


def _click(window, item) -> None:
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    x, y = _center(item)
    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(x), round(y)), 100)


def _pump(app, seconds: float = 0.4) -> None:
    from qml_shell import _pump as pump

    pump(app, lambda: False, seconds)


def _providers(section) -> list:
    return [
        str(p.get("id"))
        for p in (section.get("providers") or [])
        if isinstance(p, dict)
    ]


def _build_window(tmp_path, monkeypatch, page: str = "settings-models-provider"):
    """和 ``test_qml_context_menu`` 同一套装配，只把初始页钉到 Models 的某一子视图。"""
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine

    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.settings_service import SettingsService
    from mvvm.services.skill_store import SkillStore
    from mvvm.services.workspace_guard import WorkspaceGuard
    from mvvm.webui.assembly import build_chat_host

    from qml_shell import ShellBridge, _plain_mode, _start_ticker, qml_main
    from test_qml_shell import MODELS, text_stream

    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    monkeypatch.setenv("DEVA_ASSETS_DIR", os.path.join(root, "app", "assets"))
    home = tmp_path / "home"
    home.mkdir(parents=True)
    monkeypatch.setenv("AI_UPPER_HOME", str(home))

    settings = SettingsService(home)
    settings.set_config({"models": MODELS})
    vault = SecretsVault(home)
    vault.set_secret("p1", "sk-test")
    store = ChatSessionStore(home)
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
    window.setProperty("page", page)
    window.show()
    ticker = _start_ticker(bridge)
    return window, bridge, settings, vault, ticker, engine


def test_provider_delete_confirm_flow(qapp, tmp_path, monkeypatch):
    """删除按钮 → 确认卡片 → 点「删除」→ 服务商与其密钥一起消失，界面回列表。"""
    window, bridge, settings, vault, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        _pump(qapp, 0.6)
        assert _providers(settings.models_section()) == ["p1"]

        delete_btn = _find_item(window.contentItem(), "providerDelete")
        assert delete_btn is not None and delete_btn.property("visible") is True
        # `app.css:4905-4910`：30×30 图标按钮。
        assert (delete_btn.property("width"), delete_btn.property("height")) == (30, 30)

        layer = _find_item(window.contentItem(), "providerDeleteLayer")
        assert layer is not None and layer.property("visible") is False, "未点前不得挂确认框"

        _click(window, delete_btn)
        _pump(qapp, 0.4)
        assert layer.property("visible") is True
        assert _providers(settings.models_section()) == ["p1"], "确认前不得删"

        # 卡片几何沿用实测 Modal：420×186 居中、按钮 70/69 × 30。
        card = _find_item(window.contentItem(), "providerDeleteCard")
        assert (card.property("width"), card.property("height")) == (420, 186)
        cancel = _find_item(window.contentItem(), "providerDeleteCancel")
        confirm = _find_item(window.contentItem(), "providerDeleteConfirm")
        assert (cancel.property("width"), cancel.property("height")) == (70, 30)
        assert (confirm.property("width"), confirm.property("height")) == (69, 30)

        _click(window, confirm)
        _pump(qapp, 0.6)
        assert layer.property("visible") is False
        assert _providers(settings.models_section()) == [], "确认后服务商必须被删除"
        assert vault.get_secret("p1") is None, "密钥要一起删（原版 removeProvider）"
        # 删除后退回列表（`setView('list')`）。
        pane = _find_item(window.contentItem(), "providerDelete")
        assert pane is None or pane.property("visible") is False
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


def test_provider_delete_cancel_keeps_provider(qapp, tmp_path, monkeypatch):
    """取消按钮与背板都只关卡片，服务商与密钥原样保留。"""
    window, bridge, settings, vault, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        _pump(qapp, 0.6)
        layer = _find_item(window.contentItem(), "providerDeleteLayer")

        _click(window, _find_item(window.contentItem(), "providerDelete"))
        _pump(qapp, 0.3)
        assert layer.property("visible") is True
        _click(window, _find_item(window.contentItem(), "providerDeleteCancel"))
        _pump(qapp, 0.3)
        assert layer.property("visible") is False
        assert _providers(settings.models_section()) == ["p1"]
        assert vault.get_secret("p1") is not None

        # 背板：点卡片外的遮罩区域也只取消。
        _click(window, _find_item(window.contentItem(), "providerDelete"))
        _pump(qapp, 0.3)
        assert layer.property("visible") is True
        from PySide6.QtCore import QPoint, Qt
        from PySide6.QtTest import QTest

        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(100, 100), 100)
        _pump(qapp, 0.3)
        assert layer.property("visible") is False
        assert _providers(settings.models_section()) == ["p1"]
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()


def test_add_provider_button_creates_and_opens_custom(qapp, tmp_path, monkeypatch):
    """列表态右上角 28×28 加号：新建自定义服务商并直接进它的详情。"""
    window, bridge, settings, vault, ticker, engine = _build_window(
        tmp_path, monkeypatch, page="settings-models"
    )
    try:
        _pump(qapp, 0.6)
        add_btn = _find_item(window.contentItem(), "modelsAddProvider")
        assert add_btn is not None
        # `.models__add-btn`（`app.css:4493`）：28×28。
        assert (add_btn.property("width"), add_btn.property("height")) == (28, 28)
        assert _providers(settings.models_section()) == ["p1"]

        _click(window, add_btn)
        _pump(qapp, 0.6)
        ids = _providers(settings.models_section())
        assert len(ids) == 2, ids
        new_id = [i for i in ids if i != "p1"][0]
        # 新建的是 custom 对话模型（原版 `addCustomProvider(name, 'llm')`）。
        created = [p for p in settings.models_section()["providers"] if p.get("id") == new_id][0]
        assert created.get("kind") == "custom" and created.get("purpose") in (None, "llm")
        # 新建后直接进详情：详情态才有的删除按钮此时可见。
        delete_btn = _find_item(window.contentItem(), "providerDelete")
        assert delete_btn is not None and delete_btn.property("visible") is True
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()
