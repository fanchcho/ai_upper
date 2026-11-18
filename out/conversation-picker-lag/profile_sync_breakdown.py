"""把一次 §2.8 s 的同步段拆到函数级：取正文 / 解析 / 各渲染器分支 / 搬运 / 滚动 / 发布。

在真实 Main.qml + ShellBridge 壳里跑，instrument 真实函数（不做替身实现），
所以每段的耗时就是线上那条路径自己的耗时。
"""
from __future__ import annotations

import collections
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from probe_heavy import make_home  # noqa: E402


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    home = Path(tempfile.mkdtemp(prefix="ai-upper-breakdown-"))
    os.environ["AI_UPPER_HOME"] = str(home)
    make_home(home, count, turns)

    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication

    from markdown import document as mdoc
    from markdown.body import BodyDocument
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.settings_service import SettingsService
    from mvvm.services.skill_store import SkillStore
    from mvvm.services.workspace_guard import WorkspaceGuard
    from mvvm.webui.assembly import build_chat_host
    from qml_shell import ShellBridge, qml_main

    if os.environ.get("AI_UPPER_PROBE_WHOLE") == "1":
        # 同机同口径的「改动前」：把分块阈值提到无穷大，强制整篇渲染路径。
        from markdown import document as mdoc
        mdoc._CHUNK_BLOCKS = 10 ** 9

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

    phases = collections.defaultdict(list)
    counter = collections.Counter()

    def timed(owner, name, key, cls=None):
        fn = getattr(owner, name)

        def inner(*a, **k):
            t = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                phases[key].append((time.perf_counter() - t) * 1000.0)

        setattr(owner, name, inner if cls is None else cls(inner))

    # ── ShellBridge 同步段 ───────────────────────────────────────────────
    timed(bridge, "_markdown", "_markdown")
    timed(bridge, "_render", "_render_total")
    timed(bridge, "_publish", "_publish")
    timed(bridge, "_scroll_to_bottom", "_scroll")

    # ── BodyDocument / 渲染器 ────────────────────────────────────────────
    timed(BodyDocument, "render", "body_render")
    timed(BodyDocument, "attach", "attach")
    timed(mdoc, "parse_markdown", "parse_markdown", cls=None)
    timed(mdoc, "_collapse_edge_margins", "collapse_margins", cls=None)
    timed(mdoc._Renderer, "render_blocks", "render_blocks_total")
    for name in ("_heading", "_paragraph", "_list", "_quote", "_table", "_code", "_rule",
                 "_inline", "_apply_cell_borders", "_code_head", "_hairline"):
        timed(mdoc._Renderer, name, "kind" + name)

    # attach 内部：insertFragment / 图片补注册
    from markdown import body as mbody
    timed(mbody, "_image_names", "_image_names", cls=None)
    orig_copy = BodyDocument._copy_images
    timed(BodyDocument, "_copy_images", "_copy_images")

    # QTextCursor.insertFragment -- 直接包一层看它的耗时
    from PySide6.QtGui import QTextCursor
    orig_insert = QTextCursor.insertFragment
    def insert_fragment(self, fragment):
        t = time.perf_counter()
        try:
            return orig_insert(self, fragment)
        finally:
            phases["insertFragment"].append((time.perf_counter() - t) * 1000.0)
    QTextCursor.insertFragment = insert_fragment

    long_id = "heavy-000"
    others = [r["id"] for r in bridge._rows() if r["id"] != long_id][-4:]
    bridge.openSession(others[0])
    for _ in range(50):
        app.processEvents()

    # 每轮：短 → 长（长会话才是残留 2.8s 的场景）
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    report = []
    for _ in range(rounds):
        for sid in (long_id, others[0]):
            phases.clear()
            counter.clear()
            t = time.perf_counter()
            bridge.openSession(sid)
            total = (time.perf_counter() - t) * 1000.0
            for _ in range(20):
                app.processEvents()
            report.append({"sid": sid, "total_ms": round(total, 1),
                           "phase_ms": {k: round(sum(v), 1) for k, v in phases.items()}})

    # 汇总长会话的那些轮
    longs = [r for r in report if r["sid"] == long_id]
    keys = sorted({k for r in longs for k in r["phase_ms"]})
    agg = {}
    for k in keys:
        vals = [r["phase_ms"].get(k, 0.0) for r in longs]
        agg[k] = round(sum(vals) / len(vals), 1)
    print(json.dumps({"n_long_rounds": len(longs),
                      "long_total_ms": [r["total_ms"] for r in longs],
                      "long_phase_avg_ms": agg,
                      "short_total_ms": [r["total_ms"] for r in report if r["sid"] != long_id]},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
