"""壳内分组标定：自适应 vs 固定 24 / 固定 50，长/短会话分开报。

微基准（``probe_group_sweep.py`` / ``probe_group_calib.py``）给的是渲染器口径；这里在
真实 ``Main.qml`` 壳里用同一份 ``openSession`` 路径复核，确认「自适应选中的分组」在
端到端点击里也不输给另外两档。

每个模式都在**独立进程**里跑（同一台机器、同一份 40×400 会话数据），避免进程内残留的
文档/字体缓存互相影响；长会话与短会话分别取中位/最小/最大，不做奇偶混合采样。

用法：``python probe_shell_groups.py <mode> [数量=40] [轮数=400] [每组次数=4]``
其中 mode ∈ {plan, g24, g50, whole}。
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
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def stats(values):
    return {"median": round(statistics.median(values), 1),
            "min": round(min(values), 1), "max": round(max(values), 1),
            "all": [round(v, 1) for v in values]}


def apply_mode(mode):
    from markdown import document as mdoc

    if mode == "plan":
        return
    if mode == "whole":
        mdoc._chunk_plan = lambda blocks: 0
    else:
        fixed = int(mode[1:])
        mdoc._chunk_plan = lambda blocks: fixed


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "plan"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    turns = int(sys.argv[3]) if len(sys.argv) > 3 else 400
    rounds = int(sys.argv[4]) if len(sys.argv) > 4 else 4

    home = Path(tempfile.mkdtemp(prefix="ai-upper-shellgrp-"))
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

    print("SHELLGRP " + json.dumps({
        "mode": mode, "sessions": count, "turns": turns, "rounds_each": rounds,
        "long": {"openSession_sync_ms": stats(measured["long"]["sync"]),
                 "first_frame_ms": stats(measured["long"]["frame"])},
        "short": {"openSession_sync_ms": stats(measured["short"]["sync"]),
                  "first_frame_ms": stats(measured["short"]["frame"])},
    }, ensure_ascii=False))
    window.close()


if __name__ == "__main__":
    main()
