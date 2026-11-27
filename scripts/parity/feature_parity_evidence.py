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


def build(tmp: Path, theme: str, transport):
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
    store.ensure_session("s-1")
    session = store.load_session("s-1")
    session.title = "停止生成证据"
    store.save("s-1")
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


def main():
    feature = sys.argv[1]
    outdir = Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    app = QGuiApplication.instance() or QGuiApplication([])
    runner = {"stop": evidence_stop}[feature]
    rows = [runner(outdir, theme) for theme in ("dark", "light")]
    (outdir / f"{feature}-measurements.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
