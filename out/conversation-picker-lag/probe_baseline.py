"""基线/回归共用的点击耗时测量：直接调用与 QML 点击等价的两条路径。

路径 A（点击会话行）= ShellBridge.openSession(sid)  —— 同步渲染正文 + 整表重投影
路径 B（仅重投影）  = ShellBridge._publish()          —— 每次点击都会跑一遍

两项都在真实 QML 壳（Main.qml + ShellBridge）上测，数据来自 /tmp 下的临时 home。
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
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from probe_heavy import make_home  # noqa: E402


def pct(v, q):
    v = sorted(v)
    return round(v[min(len(v) - 1, int(len(v) * q))], 2)


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    label = sys.argv[4] if len(sys.argv) > 4 else "run"

    home = Path(tempfile.mkdtemp(prefix="ai-upper-base-"))
    os.environ["AI_UPPER_HOME"] = str(home)
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
    others = [r["id"] for r in bridge._rows() if r["id"] != long_id][-5:]

    # 预热一次，让索引/缓存进入稳定态（模拟用户已在用这个应用）
    bridge.openSession(others[0])
    for _ in range(50):
        app.processEvents()

    open_ms, publish_ms = [], []
    for i in range(rounds):
        target = long_id if i % 2 == 0 else others[i % len(others)]
        t = time.perf_counter()
        bridge.openSession(target)
        open_ms.append((time.perf_counter() - t) * 1000)
        app.processEvents()
        t = time.perf_counter()
        bridge._publish()
        publish_ms.append((time.perf_counter() - t) * 1000)

    print("PERF " + json.dumps({
        "label": label, "sessions": count, "turns": turns, "rounds": rounds,
        "openSession_ms": {"median": round(statistics.median(open_ms), 2),
                           "p90": pct(open_ms, 0.9), "max": round(max(open_ms), 2)},
        "publish_ms": {"median": round(statistics.median(publish_ms), 2),
                       "p90": pct(publish_ms, 0.9), "max": round(max(publish_ms), 2)},
        "home": str(home),
    }, ensure_ascii=False))
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
