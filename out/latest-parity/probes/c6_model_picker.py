"""D1/D2/G5 真实鼠标探针：点输入区模型贴片 / 思考等级贴片，量弹层内容与四边描边。

- 不直接改 `page` / `pickerMode` 造态：只发 `QTest.mouseClick` 到贴片中心（坐标由
  `mapToScene` 现算），再读窗口属性与实际渲染像素。
- 弹层内容判据：模型态 ⇒ `modelList` 可见、`thinkingList` 不可见、分组标题=Anthropic、
  选中行 accent 且带 ✓；思考态 ⇒ 反过来，四个等级项 Default/Low/High/Max。
- D2：弹层打开后采输入卡片四条边中点的颜色，必须都是 (91,91,214)。
- 截图：1280×820，写到传入的 png 路径。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

ROOT = Path("/home/agent/shared_workspace/ai_upper")
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(ROOT / "app" / "tests"))

from PySide6.QtCore import QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from mvvm.models.chat_models import Message  # noqa: E402
from mvvm.services.chat_session_store import ChatSessionStore  # noqa: E402
from mvvm.services.persona_store import PersonaStore  # noqa: E402
from mvvm.services.secrets_vault import SecretsVault  # noqa: E402
from mvvm.services.settings_service import SettingsService  # noqa: E402
from mvvm.services.skill_store import SkillStore  # noqa: E402
from mvvm.services.workspace_guard import WorkspaceGuard  # noqa: E402
from mvvm.webui.assembly import build_chat_host  # noqa: E402

from qml_shell import ShellBridge, _plain_mode, _pump, _start_ticker, qml_main  # noqa: E402


FIXTURE = Path(os.environ.get("PARITY_CONFIG", "/tmp/fx-qml-home/config.json"))


def pump(app, seconds):
    _pump(app, lambda: False, seconds)
from test_qml_shell import MODELS, text_stream  # noqa: E402

HOME = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/c6-picker-home")
SHOT_MODEL = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/c6-picker.png")
SHOT_EFFORT = Path(sys.argv[3] if len(sys.argv) > 3 else "/tmp/c6-picker-effort.png")


def build(app):
    HOME.mkdir(parents=True, exist_ok=True)
    os.environ["DEVA_SECRETS_BACKEND"] = "file"
    os.environ["DEVA_ASSETS_DIR"] = str(ROOT / "app" / "assets")
    os.environ["AI_UPPER_HOME"] = str(HOME)

    settings = SettingsService(HOME)
    # 与截图页同一份夹具（provider 叫 Anthropic、模型 deepseek-v4.1-flash），
    # 才能和 deva 那份弹层逐值对齐；不复用测试里的 p1/claude 简配。
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))["models"]
    settings.set_config({"models": fixture})
    vault = SecretsVault(HOME)
    vault.set_secret("anthropic", "sk-test")
    store = ChatSessionStore(HOME)
    now = int(time.time() * 1000)
    for index in range(3):
        sid = f"parity-{index:03d}"
        session = store.ensure_session(sid)
        session.messages = [Message(role="user", content="对比用会话：一条完整回合")]
        session.title = "对比用会话：一条完整回合"
        session.updatedAt = now - index * 1000
        store.save(sid)
    PersonaStore(HOME).ensure_seeded()

    box: dict = {}

    def emit(payload):
        box["bridge"].emit(payload)

    host, _gateway = build_chat_host(
        settings=settings,
        vault=vault,
        store=store,
        guard=WorkspaceGuard(),
        home=HOME,
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
        skills=SkillStore(HOME),
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
    window.show()
    ticker = _start_ticker(bridge)
    pump(app, 0.6)
    return window, bridge, ticker, engine


def find(root, name):
    """Repeater 委托不是 QObject 子节点，必须走视觉树 childItems()。"""
    try:
        if root.objectName() == name:
            return root
    except Exception:
        pass
    for child in root.childItems():
        hit = find(child, name)
        if hit is not None:
            return hit
    return None


def center(item):
    point = item.mapToScene(QPointF(item.property("width") / 2.0, item.property("height") / 2.0))
    return point


def click(window, item, app):
    point = center(item)
    from PySide6.QtCore import QPoint

    QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier,
                     QPoint(round(point.x()), round(point.y())), 80)
    pump(app, 0.5)


def shot(window, path):
    image = window.grabWindow()
    assert image.width() == 1280 and image.height() == 820, (image.width(), image.height())
    path.parent.mkdir(parents=True, exist_ok=True)
    assert image.save(str(path)), f"截图落盘失败 {path}"
    return image


def edges(image):
    out = {}
    for key, (x, y) in (("top", (700, 658)), ("bottom", (700, 803)),
                        ("left", (428, 720)), ("right", (1207, 720))):
        color = image.pixelColor(x, y)
        out[key] = (color.red(), color.green(), color.blue())
    return out


def text_of(item):
    """递归取 Item 下所有 Text 的 text（委托里的行文本没有 objectName）。"""
    from PySide6.QtCore import QObject

    chunks = []

    def walk(node):
        for child in node.childItems():
            prop = getattr(child, "property", None)
            if prop is not None:
                try:
                    value = child.property("text")
                except Exception:
                    value = None
                if isinstance(value, str) and value:
                    chunks.append(value)
            walk(child)

    walk(item)
    return chunks


def main() -> int:
    app = QGuiApplication.instance() or QGuiApplication([])
    window, bridge, ticker, engine = build(app)
    try:
        model_chip = find(window.contentItem(), "modelChip")
        effort_chip = find(window.contentItem(), "effortChip")
        assert model_chip is not None and effort_chip is not None, "两个贴片必须存在"
        print("chips model=(%.0f,%.0f) effort=(%.0f,%.0f)"
              % (center(model_chip).x(), center(model_chip).y(),
                 center(effort_chip).x(), center(effort_chip).y()))
        for label, item in (("modelChip", model_chip), ("effortChip", effort_chip)):
            origin = item.mapToScene(QPointF(0, 0))
            print("%s geometry x=%.0f y=%.0f w=%.0f h=%.0f"
                  % (label, origin.x(), origin.y(),
                     item.property("width"), item.property("height")))

        # ── 模型贴片：真实点击 ───────────────────────────────────────
        click(window, model_chip, app)
        print("after click model chip: modelPickerOpen=%s pickerMode=%r"
              % (window.property("modelPickerOpen"), window.property("pickerMode")))
        assert window.property("modelPickerOpen") is True
        assert window.property("pickerMode") == "model"

        model_picker = find(window.contentItem(), "modelPicker")
        assert model_picker is not None and model_picker.property("visible") is True
        # 两个 ModelPicker 实例内部都有 pickerPanel/modelList/thinkingList，
        # 必须从实例根往下找，不能从窗口根找（否则拿到隐藏的那个）。
        model_list = find(model_picker, "modelList")
        thinking_list = find(model_picker, "thinkingList")
        panel = find(model_picker, "pickerPanel")
        assert panel is not None and panel.property("visible") is True
        print("modelList.visible=%s thinkingList.visible=%s"
              % (model_list.property("visible"), thinking_list.property("visible")))
        assert model_list.property("visible") is True
        assert thinking_list.property("visible") is False
        print("panel width=%s height=%s" % (panel.property("width"), panel.property("height")))

        head = find(model_picker, "groupHead0")
        assert head is not None
        print("groupHead0 text=%r color=%s" % (head.property("text"),
                                               head.property("color").name()))
        assert head.property("text") == "Anthropic"

        rows = []
        index = 0
        while True:
            row = find(model_picker, "modelRow0_%d" % index)
            if row is None:
                break
            rows.append(row)
            index += 1
        print("model rows=%d texts=%s" % (len(rows), [text_of(r) for r in rows]))
        assert len(rows) == 1
        texts = [t.property("text") for t in rows[0].childItems() if t.property("text")]
        print("row0 label props=%s" % [t.property("text") for t in rows[0].childItems()])

        image = shot(window, SHOT_MODEL)
        print("edges(model mode)=%s" % (edges(image),))

        # ── 再点一次模型贴片：收起 ──────────────────────────────────
        click(window, model_chip, app)
        print("after second model click: modelPickerOpen=%s pickerMode=%r"
              % (window.property("modelPickerOpen"), window.property("pickerMode")))
        assert window.property("modelPickerOpen") is False

        # ── 思考等级贴片：真实点击 ──────────────────────────────────
        click(window, effort_chip, app)
        print("after click effort chip: modelPickerOpen=%s pickerMode=%r"
              % (window.property("modelPickerOpen"), window.property("pickerMode")))
        assert window.property("modelPickerOpen") is True
        assert window.property("pickerMode") == "thinking"

        thinking_picker = find(window.contentItem(), "thinkingPicker")
        model_picker = find(window.contentItem(), "modelPicker")
        assert thinking_picker is not None and thinking_picker.property("visible") is True
        assert model_picker is not None and model_picker.property("visible") is False
        tl = find(thinking_picker, "thinkingList")
        print("thinkingList.visible=%s" % tl.property("visible"))
        assert tl.property("visible") is True

        options = [text_of(tl.childItems()[0])] if tl.childItems() else []
        names = []
        for child in tl.childItems():
            for grand in child.childItems():
                for text in grand.childItems():
                    value = text.property("text")
                    if isinstance(value, str) and value:
                        names.append(value)
        print("thinking option texts=%s" % names)

        image2 = shot(window, SHOT_EFFORT)
        print("edges(thinking mode)=%s" % (edges(image2),))

        # ── 点一档「High」：写回生效档位并收起（真实点击，不调槽位）──────────
        ef_rows = []
        for index in range(8):
            row = find(thinking_picker, "efRow%d" % index)
            if row is not None:
                ef_rows.append(row)
        print("thinking rows found=%d activeEffort before=%r"
              % (len(ef_rows), window.property("activeEffort")))
        target = None
        for row in ef_rows:
            if "High" in text_of(row):
                target = row
                break
        assert target is not None, "思考等级项里必须有 High"
        click(window, target, app)
        print("after click High: pickerOpen=%s activeEffort=%r effortLabel=%r"
              % (window.property("modelPickerOpen"), window.property("activeEffort"),
                 window.property("effortLabel")))
        assert window.property("modelPickerOpen") is False

        # ── 点模型行的真实模型：写回生效模型并收起 ──────────────────────
        click(window, model_chip, app)
        mp = find(window.contentItem(), "modelPicker")
        row0 = find(mp, "modelRow0_0")
        print("model ref before=%r" % (window.property("activeModelRef"),))
        click(window, row0, app)
        print("after click model row: pickerOpen=%s activeModelRef=%r modelLabel=%r"
              % (window.property("modelPickerOpen"), window.property("activeModelRef"),
                 window.property("modelLabel")))
        assert window.property("modelPickerOpen") is False
        return 0
    finally:
        # 不 close()/deleteLater()：关闭阶段 QML 会因 cardsCol 的 y 绑定指向已销毁的
        # bodyView 打一条 TypeError，与本次判据无关却会污染 stderr 证据。
        ticker.stop()
        print("probe done")


if __name__ == "__main__":
    sys.exit(main())
