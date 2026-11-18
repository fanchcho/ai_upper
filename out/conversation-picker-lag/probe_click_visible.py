"""真实壳上的「点一下到首帧可见」耗时：openSession 同步段 + 紧随的首帧。"""
from __future__ import annotations
import json, os, statistics, sys, tempfile, time
from pathlib import Path
ROOT = Path("/home/agent/shared_workspace/ai_upper")
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(ROOT / "out" / "conversation-picker-lag"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    label = sys.argv[4] if len(sys.argv) > 4 else "run"

    home = Path(tempfile.mkdtemp(prefix="ai-upper-vis-"))
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

    app = QApplication.instance() or QApplication([])
    settings, vault, store = SettingsService(home), SecretsVault(home), ChatSessionStore(home)
    PersonaStore(home).ensure_seeded()
    box = {}
    def emit(p): box["bridge"].emit(p)
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
    for _ in range(200): app.processEvents()

    long_id = "heavy-000"
    others = [r["id"] for r in bridge._rows() if r["id"] != long_id][-5:]
    bridge.openSession(others[0])
    for _ in range(50): app.processEvents()

    sync, first = [], []
    for i in range(rounds):
        target = long_id if i % 2 == 0 else others[i % len(others)]
        t = time.perf_counter()
        bridge.openSession(target)
        sync.append((time.perf_counter() - t) * 1000)
        t = time.perf_counter()
        app.processEvents()
        first.append((time.perf_counter() - t) * 1000)

    print("PERF " + json.dumps({
        "label": label, "sessions": count, "turns": turns, "rounds": rounds,
        "openSession_sync_ms": {"median": round(statistics.median(sync), 1),
                                "max": round(max(sync), 1)},
        "first_frame_ms": {"median": round(statistics.median(first), 1),
                           "max": round(max(first), 1)},
    }, ensure_ascii=False))
    window.close()

if __name__ == "__main__":
    main()
