"""真实壳上「点一下到首帧可见」的耗时，**长/短会话分开报**。

``probe_click_visible.py`` 按奇偶轮交替开长/短会话后合并取中位数，那个中位数是
「长会话耗时与短会话耗时的混合物」，不代表任何一次真实点击。这里拆开：

- 长会话（400 轮正文）连开 N 次，报同步段与首帧各自的中位/最小/最大；
- 短会话连开 N 次，同样报，用来确认没有回归；
- 两种会话都在同一个窗口、同一份 Main.qml 里切换，交替进行以免顺序偏差。

用法：``python probe_click_split.py [数量=120] [轮数=400] [每组次数=4] [标签]``
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path("/home/agent/shared_workspace/ai_upper")
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(ROOT / "out" / "conversation-picker-lag"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def stats(values):
    return {"median": round(statistics.median(values), 1),
            "min": round(min(values), 1), "max": round(max(values), 1),
            "all": [round(v, 1) for v in values]}


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    label = sys.argv[4] if len(sys.argv) > 4 else "run"

    home = Path(tempfile.mkdtemp(prefix="ai-upper-clicksplit-"))
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

    if os.environ.get("AI_UPPER_PROBE_WHOLE") == "1":
        # 同机同口径的「改动前」：把分块阈值提到无穷大，强制走整篇渲染路径。
        # 只动这个进程里的模块常量，不改源码、不影响其它测量。
        from markdown import document as mdoc
        mdoc._CHUNK_BLOCKS = 10 ** 9

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
    assert short_candidates, "需要至少一个短会话"
    bridge.openSession(short_candidates[0])
    for _ in range(50):
        app.processEvents()

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
        for kind, target in (("long", long_id), ("short", short_candidates[i % len(short_candidates)])):
            sync, frame = click(target)
            measured[kind]["sync"].append(sync)
            measured[kind]["frame"].append(frame)
            for _ in range(20):
                app.processEvents()

    print("PERF " + json.dumps({
        "label": label, "sessions": count, "turns": turns, "rounds_each": rounds,
        "long": {"openSession_sync_ms": stats(measured["long"]["sync"]),
                 "first_frame_ms": stats(measured["long"]["frame"])},
        "short": {"openSession_sync_ms": stats(measured["short"]["sync"]),
                  "first_frame_ms": stats(measured["short"]["frame"])},
    }, ensure_ascii=False))
    window.close()


if __name__ == "__main__":
    main()
