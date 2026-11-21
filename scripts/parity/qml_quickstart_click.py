"""空态快速开启的「真点击」验证（offscreen 真 QML 引擎 + 真鼠标事件）。

为什么不用 Xvfb + xdotool：本机 Qt 的 xcb 平台插件缺 `libxcb-cursor0`，加载即失败
（`qt.qpa.plugin: Could not load the Qt platform plugin "xcb"`），窗口起不来。offscreen
平台不影响事件分发：样式、排版、命中测试都照常走，`QApplication.sendEvent` 投进去的
`QMouseEvent` 与窗口系统送进来的是同一类事件，MouseArea 一样会接。

流程：起窗口 → 空态截图 → 往第一张卡片的头像中心投 press/release → 再截图 → 数落盘
会话并核对会话绑定的角色。输出 PNG 与判定行，退出码 0/1。

用法: scripts/parity/qml_quickstart_click.py <输出目录> [home]
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/qml-quick-click")
OUT.mkdir(parents=True, exist_ok=True)
HOME = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else tempfile.mkdtemp(prefix="quickclick-"))
(HOME / "data").mkdir(parents=True, exist_ok=True)

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["AI_UPPER_HOME"] = str(HOME)
os.environ["DEVA_ASSETS_DIR"] = str(ROOT / "app" / "assets")
os.environ["AI_UPPER_QML_PAGE"] = "empty"
# 空态要求「没有任何对话」：数据目录新建即空，不拷 config 也能正常起。
os.environ.pop("AI_UPPER_QML_SHOT", None)

from PySide6 import QtCore, QtGui, QtWidgets, QtQml  # noqa: E402

app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

from qml_shell import ShellBridge, app_home, qml_main  # noqa: E402
from mvvm.services.chat_session_store import ChatSessionStore  # noqa: E402
from mvvm.services.persona_store import PersonaStore  # noqa: E402
from mvvm.services.secrets_vault import SecretsVault  # noqa: E402
from mvvm.services.settings_service import SettingsService  # noqa: E402
from mvvm.services.skill_store import SkillStore  # noqa: E402
from mvvm.services.workspace_guard import WorkspaceGuard  # noqa: E402
from mvvm.webui.assembly import build_chat_host  # noqa: E402

home = app_home()
PersonaStore(home).ensure_seeded()
settings, vault, store = SettingsService(home), SecretsVault(home), ChatSessionStore(home)
box: dict = {}


def emit(payload):
    box["bridge"].emit(payload)


host, _ = build_chat_host(
    settings=settings,
    vault=vault,
    store=store,
    guard=WorkspaceGuard(),
    home=home,
    emit=emit,
    emit_sessions_changed=lambda: None,
)
bridge = ShellBridge(
    host=host, store=store, plain=True, settings=settings, vault=vault, skills=SkillStore(home)
)
box["bridge"] = bridge
engine = QtQml.QQmlApplicationEngine()
engine.rootContext().setContextProperty("shellBridge", bridge)
engine.load(QtCore.QUrl.fromLocalFile(str(qml_main())))
roots = engine.rootObjects()
if not roots:
    print("FAIL QML 没有根对象")
    raise SystemExit(1)
window = roots[0]
bridge.bind_window(window)
bridge.initial()
window.setProperty("page", "empty")
window.show()


def pump(sec: float) -> None:
    end = time.monotonic() + sec
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def shot(name: str) -> None:
    img = window.grabWindow()
    if img.isNull():
        print(f"FAIL grabWindow 空图 ({name})")
        raise SystemExit(1)
    img.save(str(OUT / name))


def chat_files() -> list[pathlib.Path]:
    chats = home / "data" / "chats"
    # `_index.json` 是列表用的索引，不是会话文件。
    return sorted(p for p in chats.glob("*.json") if not p.name.startswith("_")) if chats.is_dir() else []


pump(1.5)
cards = window.property("quickStartPersonas") or []
qs = window.findChild(QtCore.QObject, "quickStart")
print("QML QUICK cards", json.dumps([[c["id"], c["name"]] for c in cards], ensure_ascii=False))
print("QML QUICK quickStart.visible", bool(qs and qs.property("visible")))
if len(cards) < 2:
    print("FAIL 空态卡片不足 2 张")
    raise SystemExit(1)

# 第一张卡片（grid 第 1 列）的头像中心：与 deva 实测同一坐标（721..768 / 412..458）。
TARGET = QtCore.QPointF(744, 435)

def _hits(item, x, y):
    """点 (x,y) 下所有几何上覆盖它的后代（由浅到深）。

    `QQuickItem.childAt()` 只给最上层那一个，而 `ApplicationWindow` 的内容容器会把它
    整个挡住（实测返回的是 `ApplicationWindowContentControl`），所以按可视矩形自己往下走。
    """
    for child in item.childItems():
        if not child.isVisible():
            continue
        if not (0 <= x - child.x() <= child.width() and 0 <= y - child.y() <= child.height()):
            continue
        yield child
        yield from _hits(child, x - child.x(), y - child.y())


# 命中测试：这个点上必须有卡片的 MouseArea / 头像，否则后面的「点击生效」不算数。
hits = list(_hits(window.contentItem(), TARGET.x(), TARGET.y()))
names = [f"{h.metaObject().className()}({h.objectName() or '-'})" for h in hits]
print("QML QUICK hit-chain", " <- ".join(reversed(names)))
if not any("MouseArea" in n for n in names):
    print("FAIL 点击坐标没有落在卡片的 MouseArea 上")
    raise SystemExit(1)

shot("before.png")
before = chat_files()
print("QML QUICK sessions before", len(before))

# 第 3 个参数写 probe 时只做命中测试与空态截图（调坐标用），默认照常投点击。
if len(sys.argv) > 3 and sys.argv[3] == "probe":
    print("QML QUICK probe-only 不投事件")
    raise SystemExit(0)
for typ, btn, btns in (
    (QtCore.QEvent.MouseMove, QtCore.Qt.NoButton, QtCore.Qt.NoButton),
    (QtCore.QEvent.MouseButtonPress, QtCore.Qt.LeftButton, QtCore.Qt.LeftButton),
    (QtCore.QEvent.MouseButtonRelease, QtCore.Qt.LeftButton, QtCore.Qt.NoButton),
):
    ev = QtGui.QMouseEvent(
        typ, TARGET, window.mapToGlobal(TARGET.toPoint()), btn, btns, QtCore.Qt.NoModifier
    )
    QtWidgets.QApplication.sendEvent(window, ev)
    pump(0.2)
pump(1.0)

after = chat_files()
new_ids = [p.stem for p in after if p not in before]
print("QML QUICK sessions after", len(after), "new", new_ids)
print("QML QUICK active", repr(bridge._active))
qs2 = window.findChild(QtCore.QObject, "quickStart")
print("QML QUICK quickStart.visible after click", bool(qs2 and qs2.property("visible")))
shot("after.png")

if len(new_ids) != 1:
    print("FAIL 点击没有建出恰好一条会话")
    raise SystemExit(1)
session = store.load_session(new_ids[0])
print("QML QUICK session personaId", repr(session.personaId))
if session.personaId != cards[0]["id"]:
    print("FAIL 会话绑定的角色不是被点的那张卡")
    raise SystemExit(1)
if bridge._active != new_ids[0]:
    print("FAIL 建完会话没有切过去")
    raise SystemExit(1)
if qs2 is not None and qs2.property("visible"):
    print("FAIL 点了卡片后仍停在空态")
    raise SystemExit(1)
print("OK 点击命中第一张卡片 -> 建会话(绑定该角色) -> 切走空态")
