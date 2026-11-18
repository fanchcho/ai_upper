"""把一次点击拆成：openSession（渲染）+ _publish（列表投影/整表 setProperty）。"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).parent))
from probe_click import make_home  # noqa: E402


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    home = Path(tempfile.mkdtemp(prefix="ai-upper-prof-"))
    os.environ["AI_UPPER_HOME"] = str(home)
    make_home(home, count)

    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication

    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.settings_service import SettingsService
    from mvvm.services.skill_store import SkillStore
    from mvvm.services.workspace_guard import WorkspaceGuard
    from mvvm.services.persona_store import PersonaStore
    from mvvm.webui.assembly import build_chat_host
    from qml_shell import ShellBridge, qml_main

    app = QApplication.instance() or QApplication([])
    settings, vault, store = SettingsService(home), SecretsVault(home), ChatSessionStore(home)
    PersonaStore(home).ensure_seeded()
    box = {}

    def emit(payload):
        box["bridge"].emit(payload)

    host, _ = build_chat_host(settings=settings, vault=vault, store=store,
                              guard=WorkspaceGuard(), home=home, emit=emit,
                              emit_sessions_changed=lambda: None)
    bridge = ShellBridge(host=host, store=store, plain=False, settings=settings,
                         vault=vault, skills=SkillStore(home))
    box["bridge"] = bridge
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("shellBridge", bridge)
    engine.load(QUrl.fromLocalFile(str(qml_main())))
    window = engine.rootObjects()[0]
    bridge.bind_window(window)
    bridge.initial()
    window.show()
    for _ in range(200):
        app.processEvents()

    # 逐段计时（不改代码，用 monkeypatch 包一层）
    timings = {"rows": [], "render": [], "publish": [], "setProperty": []}
    orig_rows = bridge._rows
    def rows():
        t = time.perf_counter()
        out = orig_rows()
        timings["rows"].append((time.perf_counter() - t) * 1000)
        return out
    bridge._rows = rows
    orig_render = bridge._render
    def render():
        t = time.perf_counter()
        orig_render()
        timings["render"].append((time.perf_counter() - t) * 1000)
    bridge._render = render
    orig_set = window.setProperty
    def setp(name, value):
        if name == "sessions":
            t = time.perf_counter()
            orig_set(name, value)
            timings["setProperty"].append((time.perf_counter() - t) * 1000)
        else:
            orig_set(name, value)
    window.setProperty = setp

    ids = [r["id"] for r in bridge._rows() if r["id"]][1:6]
    # 先测「只渲染」与「只投影」的纯 Python 成本
    for sid in ids:
        t = time.perf_counter()
        bridge._render()
        timings.setdefault("render_only", []).append((time.perf_counter() - t) * 1000)
    for sid in ids:
        t = time.perf_counter()
        bridge._publish()
        timings.setdefault("publish_only", []).append((time.perf_counter() - t) * 1000)
    # 再测整条点击路径
    first = None
    for sid in ids:
        t = time.perf_counter()
        bridge.openSession(sid)
        app.processEvents()
        total = (time.perf_counter() - t) * 1000
        timings.setdefault("click_total", []).append(total)
    for _ in range(5):
        app.processEvents()

    def stat(v):
        return {"n": len(v), "median": round(sorted(v)[len(v)//2], 2) if v else None,
                "max": round(max(v), 2) if v else None}

    print("PROFILE " + json.dumps({k: stat(v) for k, v in timings.items()}, ensure_ascii=False))
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
