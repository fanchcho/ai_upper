"""QML 默认入口的实跑取证：附件贴片 / 交付卡 / 三个动作按钮 / 回形针。

不是「把界面画出来」就算：本脚本在 offscreen 平台真起 `QApplication` + `QQmlApplicationEngine`
加载 `app/src/qml/Main.qml`，数据来自 `seed_chat_files.py` 灌进真实 `AI_UPPER_HOME` 的会话
（边车 `delivered` + 落盘附件），然后：

1. `grabWindow()` 截图，直接从 QML 控件读回文本（`delivName` / `delivSub` / `attachName`
   / `attachSize`），断言图里那几行就是**真实文件名与真实体积**（不是 `0 B`）；
2. 用真实鼠标事件（QMouseEvent 送进 QQuickWindow）按下交付卡的「打开 / 定位 / 复制路径」
   三个按钮，看后端的真实结果（`_spawn` 记录下来的命令、剪贴板内容），越权路径必须失败；
3. 用真实鼠标事件按下回形针，`QFileDialog` 真的被创建（非原生对话框，offscreen 下可脚本化），
   选中文件进 `pendingFiles`；随后走真实发送链路（离线脚本化传输）把附件读成内容块落盘，
   再截图证明待发贴片与历史贴片都在。

用法（仓库根目录）：
    QT_QPA_PLATFORM=offscreen .venv/bin/python out/chat-files/probe_qml_deliverables.py \
        /tmp/chat-files-qml <截图目录>
"""
from __future__ import annotations

import json
import os
import struct
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(ROOT / "app" / "tests"))

from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication, QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QFileDialog  # noqa: E402

from mvvm.services.chat_session_store import ChatSessionStore  # noqa: E402
from mvvm.services import deliverables as dlv  # noqa: E402
from mvvm.services.persona_store import PersonaStore  # noqa: E402
from mvvm.services.secrets_vault import SecretsVault  # noqa: E402
from mvvm.services.settings_service import SettingsService  # noqa: E402
from mvvm.services.workspace_guard import WorkspaceGuard  # noqa: E402
from mvvm.webui.assembly import build_chat_host  # noqa: E402
from qml_shell import ShellBridge  # noqa: E402
from PySide6 import QtQml  # noqa: E402
from scripted_transport import ScriptedTransport, sse  # noqa: E402

SESSION_ID = "qml-files-demo"
TOOL_USE_ID = "tu-deliver-1"


def text_stream(*chunks: str) -> ScriptedTransport:
    events = [
        sse("message_start", {"type": "message_start", "message": {"usage": {"input_tokens": 7}}}),
        sse("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
    ]
    for chunk in chunks:
        events.append(
            sse("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": chunk}})
        )
    events += [
        sse("content_block_stop", {"type": "content_block_stop", "index": 0}),
        sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 3}}),
        sse("message_stop", {"type": "message_stop"}),
    ]
    return ScriptedTransport(chunks=events)


def pump(app, predicate, timeout: float, tick=None) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if tick is not None:
            tick()
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def png_size(path: Path) -> tuple:
    head = path.read_bytes()[:33]
    assert head[:8] == b"\x89PNG\r\n\x1a\n", path
    return struct.unpack(">II", head[16:24])


def find_item(root, name):
    """按 objectName 找 QQuickItem（含 Repeater 生成的行）。"""
    stack = [root]
    while stack:
        item = stack.pop()
        if item.objectName() == name:
            return item
        stack.extend(item.childItems())
    return None


def all_items(root, name):
    out, stack = [], [root]
    while stack:
        item = stack.pop()
        if item.objectName() == name:
            out.append(item)
        stack.extend(item.childItems())
    return out


def js_list(value):
    """QML 的 `var` 属性取回可能是 QJSValue；统一成 Python 列表。"""
    if value is None:
        return []
    try:
        length = value.property("length")
    except AttributeError:
        return list(value)
    if length is None:
        return list(value)
    out = []
    for i in range(int(length.toInt() if hasattr(length, "toInt") else length)):
        item = value.property(i)
        out.append(str(item.toString()) if hasattr(item, "toString") else item)
    return out


def click(window, item) -> bool:
    """把真实鼠标按下/抬起事件送进 QQuickWindow 的对应坐标。"""
    if item is None or not item.isVisible():
        return False
    center = item.mapToScene(QPointF(item.width() / 2, item.height() / 2))
    pos = QPointF(center)
    for kind, buttons in (
        (QEvent.MouseButtonPress, Qt.LeftButton),
        (QEvent.MouseButtonRelease, Qt.NoButton),
    ):
        event = QMouseEvent(
            kind, pos, window.mapToGlobal(center.toPoint()).toPointF(),
            Qt.LeftButton, buttons, Qt.NoModifier,
        )
        QCoreApplication.sendEvent(window, event)
    return True


def main() -> int:
    if len(sys.argv) < 3:
        print("用法：probe_qml_deliverables.py <home> <截图目录>", file=sys.stderr)
        return 2
    home = Path(sys.argv[1]).resolve()
    shots = Path(sys.argv[2]).resolve()
    shots.mkdir(parents=True, exist_ok=True)

    # 1) 起 QApplication（不是 QGuiApplication：QFileDialog / 剪贴板都要它）。
    app = QApplication.instance() or QApplication([])
    settings = SettingsService(home)
    vault = SecretsVault(home)
    store = ChatSessionStore(home)
    personas = PersonaStore(home)
    personas.ensure_seeded()
    guard = WorkspaceGuard()
    for root in {home, home / "ws"}:
        guard.trust_root(str(root))

    transport = text_stream("收到，附件已读取。")
    host, _gateway = build_chat_host(
        settings=settings, vault=vault, store=store, guard=guard, home=home,
        emit=lambda payload: None, emit_sessions_changed=lambda: None, transport=transport,
    )
    bridge = ShellBridge(host=host, store=store, plain=False, settings=settings, vault=vault)
    host._emit = bridge.emit

    engine = QtQml.QQmlApplicationEngine()
    bridge._engine = engine
    engine.rootContext().setContextProperty("shellBridge", bridge)
    engine.load(QUrl.fromLocalFile(str(ROOT / "app" / "src" / "qml" / "Main.qml")))
    roots = engine.rootObjects()
    if not roots:
        print("PROBE FAILED: QML loaded no root object", file=sys.stderr, flush=True)
        return 1
    window = roots[0]
    bridge.bind_window(window)
    bridge.openSession(SESSION_ID)
    bridge.initial()
    window.show()
    painted = pump(app, lambda: window.isExposed() and bridge.rendered > 0, 15.0, bridge.tick)
    pump(app, lambda: False, 0.4, bridge.tick)
    bridge.rerender()
    pump(app, lambda: False, 0.3, bridge.tick)

    # 2) QML 控件里真实显示的文件名 / 体积（不是 Python 自己算给自己看）。
    names = [item.property("text") for item in all_items(window.contentItem(), "delivName")]
    subs = [item.property("text") for item in all_items(window.contentItem(), "delivSub")]
    attach_names = [item.property("text") for item in all_items(window.contentItem(), "attachName")]
    attach_sizes = [item.property("text") for item in all_items(window.contentItem(), "attachSize")]
    print("QML 交付行文件名 =", json.dumps(names, ensure_ascii=False), flush=True)
    print("QML 交付行副标题 =", json.dumps(subs, ensure_ascii=False), flush=True)
    print("QML 附件贴片     =", json.dumps(attach_names, ensure_ascii=False),
          json.dumps(attach_sizes, ensure_ascii=False), flush=True)
    cards = find_item(window.contentItem(), "deliveryCard")
    flow = find_item(window.contentItem(), "attachFlow")
    print("QML 交付卡可见 =", bool(cards and cards.isVisible()),
          "/ 附件条可见 =", bool(flow and flow.isVisible()), flush=True)

    chart = home / "ws" / "chart.png"
    notes = home / "ws" / "notes.md"
    expect_size = {
        "chart.png": "%d B" % chart.stat().st_size,
        "notes.md": "%d B" % notes.stat().st_size,
    }
    checks = {
        "交付卡显示 chart.png": "chart.png" in names,
        "交付卡显示 notes.md": "notes.md" in names,
        "体积是真实值（chart.png）": any(expect_size["chart.png"] in s for s in subs),
        "体积是真实值（notes.md）": any(expect_size["notes.md"] in s for s in subs),
        "副标题带目录": any(str(chart.parent) in s for s in subs),
        # 逐条精确比对：体积文案不能正好是「0 B」（原版未接后端时的占位值）。
        # 不用子串判断——`740 B` 里也含 `0 B` 三个字符。
        "界面没有 0 B": not any(s == "0 B" or s.startswith("0 B ·") for s in subs),
        "附件贴片显示 photo.png": "photo.png" in attach_names,
        "附件贴片有体积": any("B" in s for s in attach_sizes),
    }

    shot = shots / "qml-chat-files.png"
    image = window.grabWindow()
    if image.isNull() or not image.save(str(shot)):
        print("PROBE FAILED: grabWindow/save", file=sys.stderr, flush=True)
        return 1
    print("截图 =", shot, png_size(shot), flush=True)

    # 3) 三个按钮走真实鼠标事件。后端把「起进程 / 调桌面服务」换成记录器，
    #    否则 offscreen 下会真的去拉 xdg-open；判据仍是 deliverables.py 的原样逻辑。
    spawned = []
    dlv._spawn = lambda argv: spawned.append(list(argv)) or True  # noqa: SLF001
    dlv._desktop_open = lambda path: False  # 强制走按平台起进程的回落分支

    # 点 chart.png 那一行：按钮属于哪一行必须影响结果（拿第一行断言等于没测）。
    chart_row = next(
        item for item in all_items(window.contentItem(), "delivName")
        if item.property("text") == "chart.png"
    ).parentItem()
    ok = {}
    for label, name in (("open", "delivOpen"), ("reveal", "delivReveal"), ("copy", "delivCopy")):
        bucket = all_items(chart_row, name)
        ok[label] = click(window, bucket[0] if bucket else None)
        pump(app, lambda: False, 0.2)
    clipboard = QGuiApplication.clipboard().text()
    print("按钮点击 open/reveal/copy =", json.dumps(ok), flush=True)
    print("后端记录到的命令 =", json.dumps(spawned, ensure_ascii=False), flush=True)
    print("剪贴板 =", json.dumps(clipboard, ensure_ascii=False), flush=True)
    checks.update(
        {
            "三个按钮都可点": all(ok.values()),
            "打开/定位各起了一次进程": len(spawned) >= 2,
            "剪贴板拿到交付路径": clipboard == str(chart),
        }
    )

    # 4) 越权入参必须失败（不经过 QML 的「只认边车」断言）。
    bad_open = bridge.openDeliverable(TOOL_USE_ID, "/etc/passwd")
    bad_reveal = bridge.revealDeliverable(TOOL_USE_ID, "/etc/passwd")
    bad_copy = bridge.copyDeliverablePath("/etc/passwd")
    bad_index = bridge.openDeliverable(TOOL_USE_ID, "/tmp/not-delivered.png")
    print("越权 open/reveal/copy/未知路径 =",
          [bad_open, bad_reveal, bad_copy, bad_index], flush=True)
    checks["越权 open 失败"] = bad_open is False
    checks["越权 reveal 失败"] = bad_reveal is False
    checks["越权 copy 失败"] = bad_copy is False
    checks["未登记路径 open 失败"] = bad_index is False

    # 5) 回形针：真按下去，QFileDialog 真被创建并选中一个文件。
    dialog_seen = {"created": 0, "native": None, "selected": []}
    real_get = QFileDialog.getOpenFileNames

    def scripted_dialog(parent=None, caption="", directory="", filter="", *args, **kwargs):
        dialog = QFileDialog(parent, caption, directory, filter)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setOption(QFileDialog.ShowDirsOnly, False)
        dialog.setFileMode(QFileDialog.ExistingFiles)
        dialog.selectFile(str(home / "ws" / "photo.png"))
        dialog_seen["created"] += 1
        dialog_seen["native"] = dialog.testOption(QFileDialog.DontUseNativeDialog)
        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, dialog.accept)
        code = dialog.exec()
        dialog_seen["selected"] = [str(p) for p in dialog.selectedFiles()]
        return dialog.selectedFiles(), filter

    QFileDialog.getOpenFileNames = staticmethod(scripted_dialog)  # type: ignore[assignment]
    try:
        clip_item = find_item(window.contentItem(), "clipBtn")
        clip_ok = click(window, clip_item)
        pump(app, lambda: js_list(window.property("pendingFiles")), 5.0)
        pending = [str(item) for item in js_list(window.property("pendingFiles"))]
    finally:
        QFileDialog.getOpenFileNames = real_get  # type: ignore[assignment]
    print("回形针点击 =", clip_ok, "/ 对话框创建次数 =", dialog_seen["created"],
          "/ 非原生 =", dialog_seen["native"], "/ 选中 =",
          json.dumps(dialog_seen["selected"], ensure_ascii=False), flush=True)
    print("QML pendingFiles =", json.dumps(pending, ensure_ascii=False), flush=True)
    checks.update(
        {
            "回形针弹出 QFileDialog": dialog_seen["created"] == 1,
            "选中文件进了待发列表": [str(home / "ws" / "photo.png")] == list(pending),
            "待发贴片可见": bool(find_item(window.contentItem(), "pendingBar") and find_item(window.contentItem(), "pendingBar").isVisible()),
        }
    )
    shot2 = shots / "qml-chat-files-pending.png"
    image2 = window.grabWindow()
    if not image2.isNull():
        image2.save(str(shot2))
        print("截图（待发附件）= ", shot2, png_size(shot2), flush=True)

    # 6) 带附件真发送：走 ChatHost.send（离线脚本化传输），落盘里必须出现图片内容块。
    sent = bridge.sendWithAttachments("把这张图也一起看下", list(pending))
    finished = pump(app, bridge.turn_finished, 15.0, bridge.tick)
    pump(app, lambda: False, 0.3, bridge.tick)
    bridge.rerender()
    pump(app, lambda: False, 0.3, bridge.tick)
    session = store.load_session(SESSION_ID)
    last_user = [m for m in session.messages if m.role == "user" and not isinstance(m.content, str)][-1]
    kinds = [getattr(part, "type", "") for part in last_user.content]
    print("带附件发送 =", sent, "/ 回合结束 =", finished,
          "/ 落盘内容块 =", kinds, flush=True)
    checks.update(
        {
            "带附件发送成功": sent is True and finished,
            "落盘含图片内容块": "image" in kinds,
            "落盘含本轮提问": any(
                getattr(part, "text", "").startswith("把这张图也一起看下") for part in last_user.content
            ),
        }
    )
    shot3 = shots / "qml-chat-files-after-send.png"
    image3 = window.grabWindow()
    if not image3.isNull():
        image3.save(str(shot3))
        print("截图（附件入历史）= ", shot3, png_size(shot3), flush=True)
    after_names = [item.property("text") for item in all_items(window.contentItem(), "attachName")]
    print("发送后附件贴片 =", json.dumps(after_names, ensure_ascii=False), flush=True)
    checks["历史里出现新附件贴片"] = after_names.count("photo.png") >= 2

    print("---- 断言 ----", flush=True)
    for key, value in checks.items():
        print(("PASS " if value else "FAIL ") + key, flush=True)
    failed = [key for key, value in checks.items() if not value]
    print("RESULT", "ALL PASS" if not failed else "FAILED: %s" % failed, flush=True)
    print("painted=%s rendered=%d" % (painted, bridge.rendered), flush=True)
    window.close()
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
