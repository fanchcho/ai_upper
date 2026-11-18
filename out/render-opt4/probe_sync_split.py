"""壳内 400 轮长会话 `openSession` 同步段的构成：读盘 / 渲染 / attach / 发布。

在真实 `Main.qml` + `ShellBridge` 里跑，包真实实现（不写替身），所以每段就是线上那条
路径自己的耗时。长会话与短会话在同一轮内交替，奇数轮倒序，避免顺序漂移。

分段口径：

- ``read_body``     ``ChatSessionStore.load_session``（正文落盘读取）
- ``quote``         ``transcript_markdown``（消息 → Markdown 拼接）
- ``body_render``   ``BodyDocument.render`` → ``render_markdown``（自有文档那一次）
- ``attach_total``  ``BodyDocument.attach`` 总计（搬到 QML 文档）
  - ``attach_end``  ``endEditBlock``（QQuickTextEdit 提交时整篇排版）
  - ``frag_build``  ``QTextDocumentFragment(self.document)`` 构造
  - ``remove_old``  选择全文并删除
  - ``insert_frag`` ``QTextCursor.insertFragment``
  - ``images``      ``_copy_images`` + ``_image_names``
- ``scroll``        ``_scroll_to_bottom``
- ``publish``       ``_publish``（含 ``_rows`` / ``visible_sessions`` / 附件与交付行）
  - ``pub_rows``    ``_publish`` 内的 ``ShellBridge._rows``
- ``hl_rehighlight`` 渲染后显式 ``rehighlight``（若发生）

用法：``python probe_sync_split.py [会话数=40] [轮数=400] [rounds=3] [标签]``
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
sys.path.insert(0, str(ROOT / "out" / "conversation-picker-lag"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from probe_heavy import make_home  # noqa: E402


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    label = sys.argv[4] if len(sys.argv) > 4 else "run"

    home = Path(tempfile.mkdtemp(prefix="ai-upper-syncsplit-"))
    os.environ["AI_UPPER_HOME"] = str(home)
    make_home(home, count, turns)

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QTextCursor, QTextDocumentFragment
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication

    from markdown.body import BodyDocument
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.settings_service import SettingsService
    from mvvm.services.skill_store import SkillStore
    from mvvm.services.workspace_guard import WorkspaceGuard
    from mvvm.webui.assembly import build_chat_host
    from qml_shell import ShellBridge, qml_main
    from qml_shell_sessions import transcript_markdown

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

    # ── 采样容器 ──────────────────────────────────────────────────────────
    phases = collections.defaultdict(list)
    in_attach = {"on": False}

    def timed(owner, name, key, cls=None, only_in_attach=False):
        fn = getattr(owner, name)

        def inner(*a, **k):
            if only_in_attach and not in_attach["on"]:
                return fn(*a, **k)
            t = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                phases[key].append((time.perf_counter() - t) * 1000.0)

        setattr(owner, name, inner if cls is None else cls(inner))

    timed(bridge, "_markdown_base", "read_body")
    timed(bridge, "_render", "render_total")
    timed(bridge, "_publish", "publish")
    timed(bridge, "_scroll_to_bottom", "scroll")
    timed(bridge, "_rows", "pub_rows", only_in_attach=False)
    timed(BodyDocument, "render", "body_render")

    real_attach = BodyDocument.attach

    def attach(self, quick_document):
        in_attach["on"] = True
        t = time.perf_counter()
        try:
            return real_attach(self, quick_document)
        finally:
            in_attach["on"] = False
            phases["attach_total"].append((time.perf_counter() - t) * 1000.0)

    BodyDocument.attach = attach

    # attach 内部（只在 in_attach 时记账，避免渲染器里的游标操作混进来）
    for method, key in (("endEditBlock", "attach_end"),
                        ("beginEditBlock", "attach_begin"),
                        ("removeSelectedText", "remove_old")):
        real = getattr(QTextCursor, method)

        def wrapper(self, *a, _real=real, _key=key, **k):
            if not in_attach["on"]:
                return _real(self, *a, **k)
            t = time.perf_counter()
            try:
                return _real(self, *a, **k)
            finally:
                phases[_key].append((time.perf_counter() - t) * 1000.0)

        setattr(QTextCursor, method, wrapper)

    real_insert = QTextCursor.insertFragment

    def insert_fragment(self, fragment):
        if not in_attach["on"]:
            return real_insert(self, fragment)
        t = time.perf_counter()
        try:
            return real_insert(self, fragment)
        finally:
            phases["insert_frag"].append((time.perf_counter() - t) * 1000.0)

    QTextCursor.insertFragment = insert_fragment

    real_frag_init = QTextDocumentFragment.__init__

    def frag_init(self, *a, **k):
        if not in_attach["on"]:
            return real_frag_init(self, *a, **k)
        t = time.perf_counter()
        try:
            return real_frag_init(self, *a, **k)
        finally:
            phases["frag_build"].append((time.perf_counter() - t) * 1000.0)

    QTextDocumentFragment.__init__ = frag_init

    timed(BodyDocument, "_copy_images", "images", only_in_attach=True)

    # body_render 内部再拆一层：解析 vs 写文档
    from markdown import document as mdoc

    timed(mdoc, "parse_markdown", "parse", cls=None)
    timed(mdoc, "_collapse_edge_margins", "margins", cls=None)
    timed(mdoc._Renderer, "render_blocks", "render_blocks", only_in_attach=False)

    # transcript_markdown 是模块函数：包装后同时替换两个模块里的引用
    import qml_shell as qsh
    import qml_shell_sessions as qss

    real_quote = qss.transcript_markdown

    def quote(messages):
        t = time.perf_counter()
        try:
            return real_quote(messages)
        finally:
            phases["quote"].append((time.perf_counter() - t) * 1000.0)

    qss.transcript_markdown = quote
    qsh.transcript_markdown = quote

    # ── 采样 ──────────────────────────────────────────────────────────────
    long_id = "heavy-000"
    others = [r["id"] for r in bridge._rows() if r["id"] != long_id][-4:]
    assert others, "需要至少一个短会话"
    bridge.openSession(others[0])
    for _ in range(50):
        app.processEvents()

    rows = []
    for round_index in range(rounds):
        order = [("long", long_id), ("short", others[round_index % len(others)])]
        if round_index % 2:
            order.reverse()
        for kind, sid in order:
            phases.clear()
            t = time.perf_counter()
            bridge.openSession(sid)
            total = (time.perf_counter() - t) * 1000.0
            for _ in range(20):
                app.processEvents()
            rows.append({"kind": kind, "total_ms": round(total, 1),
                         "phase_ms": {k: round(sum(v), 1) for k, v in phases.items()},
                         "calls": {k: len(v) for k, v in phases.items()}})

    def agg(kind):
        sel = [r for r in rows if r["kind"] == kind]
        keys = sorted({k for r in sel for k in r["phase_ms"]})
        return {
            "n": len(sel),
            "total_ms": [r["total_ms"] for r in sel],
            "phase_avg_ms": {k: round(sum(r["phase_ms"].get(k, 0.0) for r in sel) / len(sel), 1)
                             for k in keys},
            "phase_all_ms": {k: [r["phase_ms"].get(k, 0.0) for r in sel] for k in keys},
            "calls": {k: max((r["calls"].get(k, 0) for r in sel), default=0) for k in keys},
        }

    out = {"label": label, "sessions": count, "turns": turns, "rounds": rounds,
           "rows": rows, "long": agg("long"), "short": agg("short")}
    print("SYNCSPLIT " + json.dumps(out, ensure_ascii=False))
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
