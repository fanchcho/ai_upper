"""壳内 A/B：同一份 Main.qml、同一个窗口，量「改动前」与「改动后」的 openSession。

长会话（400 轮）与短会话分开计时，各自取中位/最小/最大（不做奇偶混合采样）。

- **before**：分块计划恒为 50（旧口径），颜色/字体/行高每次都重新构造；
- **after**：自适应分组 + 三张缓存表（当前源码）。

用法：``python probe_shell_ab.py [数量=40] [轮数=400] [每组次数=4] [mode]``
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(ROOT / "out" / "conversation-picker-lag"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def stats(values):
    return {"median": round(statistics.median(values), 1),
            "min": round(min(values), 1), "max": round(max(values), 1),
            "all": [round(v, 1) for v in values]}


def apply_mode(mode):
    from probe_old_opt3 import install_before

    if mode == "before":
        install_before()


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    mode = sys.argv[4] if len(sys.argv) > 4 else "after"

    home = Path(tempfile.mkdtemp(prefix="ai-upper-shellab-"))
    os.environ["AI_UPPER_HOME"] = str(home)

    from probe_heavy import make_home
    make_home(home, count, turns)

    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication

    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.settings_service import SettingsService
    from mvvm.services.skill_store import SkillStore
    from mvvm.services.workspace_guard import WorkspaceGuard
    from mvvm.webui.assembly import build_chat_host
    from qml_shell import ShellBridge, qml_main

    apply_mode(mode)

    app = QApplication.instance() or QApplication([])
    settings, vault, store = SettingsService(home), SecretsVault(home), ChatSessionStore(home)
    PersonaStore(home).ensure_seeded()
    box = {}

    def emit(p):
        box["bridge"].emit(p)

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

    long_id = "heavy-000"
    short_candidates = [r["id"] for r in bridge._rows() if r["id"] != long_id][-3:]
    assert short_candidates

    def click(session_id):
        start = time.perf_counter()
        bridge.openSession(session_id)
        sync = (time.perf_counter() - start) * 1000.0
        start = time.perf_counter()
        app.processEvents()
        frame = (time.perf_counter() - start) * 1000.0
        return sync, frame

    measured = {"long": {"sync": [], "frame": []}, "short": {"sync": [], "frame": []}}
    for i in range(rounds):
        for kind, target in (("long", long_id),
                             ("short", short_candidates[i % len(short_candidates)])):
            sync, frame = click(target)
            measured[kind]["sync"].append(sync)
            measured[kind]["frame"].append(frame)
            for _ in range(20):
                app.processEvents()

    print("SHELLAB " + json.dumps({
        "mode": mode, "sessions": count, "turns": turns, "rounds_each": rounds,
        "long": {"openSession_sync_ms": stats(measured["long"]["sync"]),
                 "first_frame_ms": stats(measured["long"]["frame"])},
        "short": {"openSession_sync_ms": stats(measured["short"]["sync"]),
                  "first_frame_ms": stats(measured["short"]["frame"])},
    }, ensure_ascii=False))
    window.close()


if __name__ == "__main__":
    main()
