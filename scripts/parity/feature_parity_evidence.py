#!/usr/bin/env python3
"""功能补齐的真机证据：真实 QML 窗口 + 真实鼠标/键盘事件 + grabWindow 截图。

用法:
  python scripts/parity/feature_parity_evidence.py <feature> <outdir>

feature: stop | context-menu | collapse | drop
每个 feature 会产出暗/亮两套 PNG 与一份 measurements.json（按钮/菜单几何、像素颜色）。
不写真实 ~/.ai_upper：AI_UPPER_HOME 由本脚本指到临时目录。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(ROOT / "app" / "tests"))

from PySide6.QtCore import QPoint, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

from mvvm.services.chat_session_store import ChatSessionStore  # noqa: E402
from mvvm.services.persona_store import PersonaStore  # noqa: E402
from mvvm.services.secrets_vault import SecretsVault  # noqa: E402
from mvvm.services.settings_service import SettingsService  # noqa: E402
from mvvm.services.skill_store import SkillStore  # noqa: E402
from mvvm.services.workspace_guard import WorkspaceGuard  # noqa: E402
from mvvm.webui.assembly import build_chat_host  # noqa: E402
from qml_shell import ShellBridge, _plain_mode, _pump, _start_ticker, qml_main  # noqa: E402
from test_qml_shell import MODELS, gated_stream  # noqa: E402


def find_item(root, name):
    try:
        if root.objectName() == name:
            return root
    except Exception:
        pass
    for child in root.childItems():
        found = find_item(child, name)
        if found is not None:
            return found
    return None


def build(tmp: Path, theme: str, transport, sessions=("s-1",)):
    home = tmp / "home"
    home.mkdir(parents=True)
    os.environ["AI_UPPER_HOME"] = str(home)
    os.environ["DEVA_SECRETS_BACKEND"] = "file"
    os.environ["DEVA_ASSETS_DIR"] = str(ROOT / "app" / "assets")
    settings = SettingsService(home)
    settings.set_config({"models": MODELS, "theme": theme, "locale": "zh-CN"})
    vault = SecretsVault(home)
    vault.set_secret("p1", "sk-test")
    store = ChatSessionStore(home)
    for index, sid in enumerate(sessions):
        store.ensure_session(sid)
        session = store.load_session(sid)
        session.title = f"会话 {index + 1}"
        store.save(sid)
    PersonaStore(home).ensure_seeded()
    box = {}

    def emit(payload):
        box["bridge"].emit(payload)

    host, _ = build_chat_host(settings=settings, vault=vault, store=store, guard=WorkspaceGuard(),
                              home=home, emit=emit, emit_sessions_changed=lambda: None, transport=transport)
    bridge = ShellBridge(host=host, store=store, plain=_plain_mode(), settings=settings, vault=vault,
                         skills=SkillStore(home))
    box["bridge"] = bridge
    engine = QQmlApplicationEngine()
    bridge._engine = engine
    engine.rootContext().setContextProperty("shellBridge", bridge)
    engine.load(QUrl.fromLocalFile(str(qml_main())))
    window = engine.rootObjects()[0]
    bridge.bind_window(window)
    bridge.initial()
    window.setProperty("page", "chat")
    window.show()
    ticker = _start_ticker(bridge)
    _pump(QGuiApplication.instance(), lambda: False, 0.6)
    return window, bridge, store, ticker, engine, home


def shot(window, path: Path):
    img = window.grabWindow()
    path.parent.mkdir(parents=True, exist_ok=True)
    assert img.save(str(path)), f"截图保存失败 {path}"
    return img.width(), img.height()


def evidence_stop(outdir: Path, theme: str):
    gate = threading.Event()
    tmp = Path(tempfile.mkdtemp(prefix=f"ai-upper-feature-stop-{theme}-"))
    try:
        window, bridge, store, ticker, engine, home = build(tmp, theme, gated_stream("开头", gate))
        assert bridge.openSession("s-1") is True
        assert bridge.send("问题") is True
        deadline = time.time() + 10
        while time.time() < deadline and not (window.property("busy") and bridge.deltas):
            _pump(QGuiApplication.instance(), lambda: False, 0.1)
        assert window.property("busy") is True and bridge.deltas == ["开头"]
        png = outdir / f"stop-busy-{theme}.png"
        size = shot(window, png)
        send = find_item(window.contentItem(), "sendBtn")
        glyph = find_item(window.contentItem(), "stopGlyph")
        assert send is not None and glyph is not None
        data = {
            "feature": "stop", "theme": theme, "png": str(png), "size": size,
            "send": [send.property("x"), send.property("y"), send.property("width"), send.property("height")],
            "glyph_visible": bool(glyph.property("visible")),
            "busy": bool(window.property("busy")),
        }
        # 真实点击停止键，记录停止结果。
        x, y = send.mapToScene(__import__("PySide6.QtCore", fromlist=["QPointF"]).QPointF(34, 16)).toTuple()
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, QPoint(round(x), round(y)), 100)
        _pump(QGuiApplication.instance(), lambda: bridge.turn_finished(), 10)
        data["stop_reason"] = bridge.stop
        data["messages"] = [m.role for m in store.load_session("s-1").messages]
        data["after_busy"] = bool(window.property("busy"))
        ticker.stop(); window.close(); engine.deleteLater()
        return data
    finally:
        gate.set()
        shutil.rmtree(tmp, ignore_errors=True)


def evidence_collapse(outdir: Path, theme: str):
    from PySide6.QtCore import QPoint
    from test_qml_shell import text_stream

    tmp = Path(tempfile.mkdtemp(prefix=f"ai-upper-feature-collapse-{theme}-"))
    try:
        window, bridge, _store, ticker, engine, home = build(
            tmp, theme, text_stream("x"), sessions=("s-1", "s-2", "s-3"))
        side = find_item(window.contentItem(), "sessionSide")
        conv = find_item(window.contentItem(), "convColumn")
        chats = find_item(window.contentItem(), "railChats")
        QTest.keyClick(window, Qt.Key_B, Qt.ControlModifier)
        _pump(QGuiApplication.instance(), lambda: False, 0.4)
        png = outdir / f"sidebar-collapsed-{theme}.png"
        size = shot(window, png)
        rows = [{
            "feature": "collapse", "theme": theme, "state": "collapsed", "png": str(png), "size": size,
            "side_width": side.property("width"), "side_visible": bool(side.property("visible")),
            "conv_x": conv.property("x"), "collapsed": bool(window.property("sideCollapsed")),
            "config": bool(bridge.sidebarCollapsed()),
        }]
        # 先把指针移到远处再进图标，避免上一轮窗口关闭后指针已停在图标上、
        # 新窗口创建时没有 hoveredChanged 事件。
        QTest.mouseMove(window, QPoint(700, 400))
        _pump(QGuiApplication.instance(), lambda: False, 0.2)
        QTest.mouseMove(window, QPoint(28, 88))
        _pump(QGuiApplication.instance(), lambda: False, 0.4)
        png2 = outdir / f"sidebar-peek-{theme}.png"
        size2 = shot(window, png2)
        rows.append({
            "feature": "collapse", "theme": theme, "state": "peek", "png": str(png2), "size": size2,
            "side_width": side.property("width"), "side_visible": bool(side.property("visible")),
            "conv_x": conv.property("x"), "peek": bool(window.property("sidePeek")),
        })
        ticker.stop(); window.close(); engine.deleteLater()
        return rows
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def evidence_context_menu(outdir: Path, theme: str):
    from PySide6.QtCore import QObject
    from test_qml_shell import text_stream

    tmp = Path(tempfile.mkdtemp(prefix=f"ai-upper-feature-menu-{theme}-"))
    try:
        window, bridge, _store, ticker, engine, home = build(tmp, theme, text_stream("x"))
        field = find_item(window.contentItem(), "inputField")
        field.setProperty("text", "右键菜单证据文本")
        _pump(QGuiApplication.instance(), lambda: False, 0.3)
        item = field
        p = item.mapToScene(__import__("PySide6.QtCore", fromlist=["QPointF"]).QPointF(40, 40))
        QTest.mouseClick(window, Qt.RightButton, Qt.NoModifier, QPoint(round(p.x()), round(p.y())), 100)
        _pump(QGuiApplication.instance(), lambda: False, 0.4)
        menu = window.findChild(QObject, "composerMenu")
        assert menu is not None and menu.property("visible") is True
        png = outdir / f"edit-menu-{theme}.png"
        size = shot(window, png)
        rows = [{
            "feature": "context-menu", "theme": theme, "png": str(png), "size": size,
            "menu_visible": bool(menu.property("visible")),
            "menu_width": menu.property("width"), "menu_height": menu.property("height"),
            "editable": bool(menu.property("editable")),
        }]
        menu.close()
        ticker.stop(); window.close(); engine.deleteLater()
        return rows
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def evidence_attachments(outdir: Path, theme: str):
    from PySide6.QtCore import QMimeData, QPoint, QUrl, QPointF, QCoreApplication
    from PySide6.QtGui import QDragEnterEvent, QDropEvent
    from test_qml_shell import text_stream

    tmp = Path(tempfile.mkdtemp(prefix=f"ai-upper-feature-drop-{theme}-"))
    try:
        window, bridge, _store, ticker, engine, home = build(tmp, theme, text_stream("x"))
        note = tmp / "拖放证据.txt"
        note.write_text("drag evidence", encoding="utf-8")
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(note))])
        QCoreApplication.sendEvent(window, QDragEnterEvent(
            QPoint(400, 400), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
        _pump(QGuiApplication.instance(), lambda: False, 0.3)
        png = outdir / f"drop-overlay-{theme}.png"
        size = shot(window, png)
        overlay = find_item(window.contentItem(), "dropOverlay")
        rows = [{
            "feature": "attachments", "theme": theme, "state": "drag-over", "png": str(png), "size": size,
            "overlay_visible": bool(overlay.property("visible")) if overlay is not None else None,
        }]
        QCoreApplication.sendEvent(window, QDropEvent(
            QPointF(400, 400), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier))
        _pump(QGuiApplication.instance(), lambda: False, 0.4)
        pending = window.property("pendingFiles")
        if hasattr(pending, "toVariant"):
            pending = pending.toVariant()
        rows.append({
            "feature": "attachments", "theme": theme, "state": "dropped", "png": None, "size": None,
            "pending_files": pending,
        })
        ticker.stop(); window.close(); engine.deleteLater()
        return rows
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def evidence_unread(outdir: Path, theme: str):
    from test_qml_shell import text_stream

    tmp = Path(tempfile.mkdtemp(prefix=f"ai-upper-feature-unread-{theme}-"))
    try:
        window, bridge, store, ticker, engine, home = build(tmp, theme, text_stream("x"), sessions=("s-1", "s-2"))
        bridge._unread.add("s-1")
        bridge._publish()
        _pump(QGuiApplication.instance(), lambda: False, 0.4)
        png = outdir / f"unread-dot-{theme}.png"
        size = shot(window, png)
        rows = [{"feature": "unread", "theme": theme, "png": str(png), "size": size,
                 "rows": [{"id": r["id"], "unread": r["unread"]} for r in bridge._rows()]}]
        bridge.openSession("s-1"); bridge._publish()
        _pump(QGuiApplication.instance(), lambda: False, 0.2)
        rows.append({"feature": "unread", "theme": theme, "state": "opened",
                     "rows": [{"id": r["id"], "unread": r["unread"]} for r in bridge._rows()]})
        ticker.stop(); window.close(); engine.deleteLater()
        return rows
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def evidence_slash(outdir: Path, theme: str):
    from test_qml_shell import text_stream

    tmp = Path(tempfile.mkdtemp(prefix=f"ai-upper-feature-slash-{theme}-"))
    try:
        window, bridge, _store, ticker, engine, home = build(tmp, theme, text_stream("x"))
        field = find_item(window.contentItem(), "inputField")
        field.forceActiveFocus()
        QTest.keyClick(window, Qt.Key_Slash)
        _pump(QGuiApplication.instance(), lambda: False, 0.4)
        png = outdir / f"slash-menu-{theme}.png"
        size = shot(window, png)
        rows = [{"feature": "slash", "theme": theme, "png": str(png), "size": size,
                 "open": bool(window.property("slashOpen")), "rows": window.property("slashRows").toVariant() if hasattr(window.property("slashRows"), "toVariant") else window.property("slashRows")}]
        ticker.stop(); window.close(); engine.deleteLater()
        return rows
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def evidence_activity(outdir: Path, theme: str):
    from mvvm.models.chat_models import Message, TextPart, ToolResultPart, ToolUsePart
    from test_qml_shell import text_stream

    tmp = Path(tempfile.mkdtemp(prefix=f"ai-upper-feature-activity-{theme}-"))
    try:
        window, bridge, store, ticker, engine, home = build(tmp, theme, text_stream("x"))
        session = store.load_session("s-1")
        session.messages = [
            Message(role="user", content="检查文件并让子代理审查"),
            Message(role="assistant", content=[TextPart(text="先读取文件。"),
                                               ToolUsePart(id="t1", name="read_file", input={"path": "/tmp/spec.md"})]),
            Message(role="user", content=[ToolResultPart(toolUseId="t1", content="文件内容 ABC", isError=False)]),
            Message(role="assistant", content=[ToolUsePart(id="t2", name="run_subagent", input={"task": "审查 spec"})]),
            Message(role="user", content=[ToolResultPart(toolUseId="t2", content="子代理完成：无问题", isError=False)]),
            Message(role="assistant", content="审查完成。"),
        ]
        store.save("s-1")
        assert bridge.openSession("s-1") is True
        _pump(QGuiApplication.instance(), lambda: False, 0.8)
        png = outdir / f"activity-cards-{theme}.png"
        size = shot(window, png)
        body = find_item(window.contentItem(), "bodyView")
        text = body.property("textDocument").textDocument().toPlainText()
        rows = [{"feature": "activity", "theme": theme, "png": str(png), "size": size,
                 "has_tool": "read_file" in text, "has_result": "文件内容 ABC" in text,
                 "has_subagent": "run_subagent" in text}]
        ticker.stop(); window.close(); engine.deleteLater()
        return rows
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def evidence_capsules(outdir: Path, theme: str):
    from test_qml_shell import text_stream

    tmp = Path(tempfile.mkdtemp(prefix=f"ai-upper-feature-capsules-{theme}-"))
    try:
        window, bridge, store, ticker, engine, home = build(tmp, theme, text_stream("x"))
        session = store.load_session("s-1")
        session.todos = [{"listId": "L1", "title": "证据待办", "at": 1, "items": [
            {"content": "第一步", "status": "completed"},
            {"content": "第二步", "status": "in_progress"},
        ]}]
        session.background = {"tool-1": "running"}
        store.save("s-1")
        bridge.openSession("s-1")
        bridge._pending_inserts = ["排队插话"]
        bridge._publish()
        _pump(QGuiApplication.instance(), lambda: False, 0.6)
        png = outdir / f"capsules-{theme}.png"
        size = shot(window, png)
        texts = []
        def walk(item):
            try:
                txt = item.property("text")
                if txt: texts.append(str(txt))
            except Exception:
                pass
            for child in item.childItems():
                walk(child)
        walk(window.contentItem())
        rows = [{"feature": "capsules", "theme": theme, "png": str(png), "size": size,
                 "todo": any("证据待办" in t for t in texts),
                 "pending": any("待插入" in t for t in texts),
                 "background": any("后台任务" in t for t in texts)}]
        ticker.stop(); window.close(); engine.deleteLater()
        return rows
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def evidence_personas(outdir: Path, theme: str):
    from test_qml_shell import text_stream

    tmp = Path(tempfile.mkdtemp(prefix=f"ai-upper-feature-personas-{theme}-"))
    try:
        window, bridge, store, ticker, engine, home = build(tmp, theme, text_stream("x"))
        from pathlib import Path as _P
        import os as _os
        _os.environ["DEVA_ASSETS_DIR"] = str(ROOT / "app/assets")
        from mvvm.services.plugin_identity import shared_store
        shared_store().ensure_seeded()
        window.setProperty("page", "roster")
        _pump(QGuiApplication.instance(), lambda: False, 0.6)
        png = outdir / f"personas-list-{theme}.png"
        size = shot(window, png)
        rows = bridge.personaRecords()
        from PySide6.QtQml import QQmlEngine, QQmlExpression
        roster_item = find_item(window.contentItem(), "personaRoster")
        detail = {}
        if rows:
            bridge.roleMemorySave(rows[0]["id"], '{"title":"记忆证据","body":"真实角色记忆","type":"reference"}')
            QQmlExpression(QQmlEngine.contextForObject(roster_item), roster_item,
                           "openDetail('" + rows[0]["id"] + "')").evaluate()
            _pump(QGuiApplication.instance(), lambda: False, 0.4)
            png2 = outdir / f"persona-detail-{theme}.png"
            size2 = shot(window, png2)
            detail = {"id": rows[0]["id"], "name": rows[0]["name"], "png": str(png2), "size": size2}
        ticker.stop(); window.close(); engine.deleteLater()
        return [{"feature": "personas", "theme": theme, "list_png": str(png), "size": size,
                 "count": len(rows), "detail": detail}]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def evidence_git(outdir: Path, theme: str):
    import subprocess
    from test_qml_shell import text_stream

    tmp = Path(tempfile.mkdtemp(prefix=f"ai-upper-feature-git-{theme}-"))
    try:
        window, bridge, store, ticker, engine, home = build(tmp, theme, text_stream("x"))
        repo = home / "repo"; repo.mkdir()
        subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "t@e.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
        (repo / "a.txt").write_text("one\n")
        subprocess.run(["git", "add", "a.txt"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)
        (repo / "a.txt").write_text("two\n")
        session = store.load_session("s-1"); session.focusRoot = str(repo); store.save("s-1")
        bridge.openSession("s-1"); bridge._publish(); _pump(QGuiApplication.instance(), lambda: False, 0.5)
        from PySide6.QtQml import QQmlExpression, QQmlEngine
        QQmlExpression(QQmlEngine.contextForObject(window), window, "gitPanel.open()").evaluate()
        _pump(QGuiApplication.instance(), lambda: False, 0.5)
        png = outdir / f"git-panel-{theme}.png"; size = shot(window, png)
        ticker.stop(); window.close(); engine.deleteLater()
        return [{"feature": "git", "theme": theme, "png": str(png), "size": size, "status": bridge.gitStatus(str(repo))}]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def evidence_background(outdir: Path, theme: str):
    from test_qml_shell import text_stream

    tmp = Path(tempfile.mkdtemp(prefix=f"ai-upper-feature-background-{theme}-"))
    try:
        window, bridge, store, ticker, engine, home = build(tmp, theme, text_stream("x"))
        child_id = "member-bg"
        bridge._host.create_session({"sessionId": child_id, "personaId": "general"})
        session = store.load_session("s-1")
        session.members = [{"id": child_id, "sessionId": child_id, "name": "Reviewer", "personaId": "general"}]
        store.save("s-1")
        bridge.openSession("s-1"); bridge._publish(); _pump(QGuiApplication.instance(), lambda: False, 0.5)
        png = outdir / f"background-tasks-{theme}.png"
        size = shot(window, png)
        rows = [{"feature": "background", "theme": theme, "png": str(png), "size": size,
                 "tasks": bridge.backgroundTasks()}]
        ticker.stop(); window.close(); engine.deleteLater()
        return rows
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def evidence_sidebar(outdir: Path, theme: str):
    from test_qml_shell import text_stream

    tmp = Path(tempfile.mkdtemp(prefix=f"ai-upper-feature-sidebar-{theme}-"))
    try:
        window, bridge, store, ticker, engine, home = build(tmp, theme, text_stream("x"))
        bridge.setSidebarWidth(380)
        window.setProperty("sidebarWidth", 380)
        _pump(QGuiApplication.instance(), lambda: False, 0.4)
        png = outdir / f"sidebar-resize-{theme}.png"
        size = shot(window, png)
        ticker.stop(); window.close(); engine.deleteLater()
        return [{"feature": "sidebar", "theme": theme, "png": str(png), "size": size, "width": bridge.sidebarWidth()}]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def evidence_profile(outdir: Path, theme: str):
    from test_qml_shell import text_stream

    tmp = Path(tempfile.mkdtemp(prefix=f"ai-upper-feature-profile-{theme}-"))
    try:
        window, bridge, store, ticker, engine, home = build(tmp, theme, text_stream("x"))
        from PySide6.QtQml import QQmlExpression, QQmlEngine
        panel = window.findChild(__import__("PySide6.QtCore", fromlist=["QObject"]).QObject, "profilePanel")
        QQmlExpression(QQmlEngine.contextForObject(panel), panel, "open()").evaluate()
        _pump(QGuiApplication.instance(), lambda: False, 0.5)
        png = outdir / f"profile-{theme}.png"; size = shot(window, png)
        ticker.stop(); window.close(); engine.deleteLater()
        return [{"feature": "profile", "theme": theme, "png": str(png), "size": size, "profile": bridge.userProfile()}]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    feature = sys.argv[1]
    outdir = Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from PySide6.QtGui import QFontDatabase
    font = ROOT / ".tmp/theme-settings/NotoSansCJKsc-Regular.otf"
    if font.exists():
        QFontDatabase.addApplicationFont(str(font))
    runners = {"stop": evidence_stop, "collapse": evidence_collapse, "context-menu": evidence_context_menu, "attachments": evidence_attachments, "unread": evidence_unread, "slash": evidence_slash, "activity": evidence_activity, "capsules": evidence_capsules, "personas": evidence_personas, "gitpanel": evidence_git, "background": evidence_background, "sidebar": evidence_sidebar, "profile": evidence_profile}
    runner = runners[feature]
    rows = []
    for theme in ("dark", "light"):
        result = runner(outdir, theme)
        rows.extend(result if isinstance(result, list) else [result])
    (outdir / f"{feature}-measurements.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
