"""`body_render` 里「parse + render_blocks」之外那 ~170 ms 到底是谁。

`probe_sync_split.py` 把长会话同步段拆到 ``body_render``（约 700 ms）一层，
但它内部只记了 ``parse_markdown``（约 45 ms）与 ``_Renderer.render_blocks``（约 486 ms），
两者相加仍差 ~170 ms。差额只能来自 ``render_markdown`` 里的另外几句：

- ``document.clear()``：源文档上一轮仍是 13200 块，清空本身要花时间；
- ``document.setDocumentMargin(0)``；
- ``_collapse_edge_margins(document)``：整篇重新走一遍块。

本探针只做**归因**，不改任何实现：在真实壳里连续两次打开 400 轮长会话，逐项计时，
并顺带数 ``highlightBlock`` 调用次数（预期 0——高亮器接管后挂在 QML 文档上）。
高亮器计数用构造前安装的 ``highlightBlock`` 探针（PySide 的虚函数派发在构造时绑定，
构造后再改类属性拦不到已存在实例；见 ``out/render-opt2/REPORT.md`` §4.1）。

用法：``python probe_render_residual.py [turns=400] [opens=2]``
"""
from __future__ import annotations

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


def main() -> int:
    turns = int(sys.argv[1]) if len(sys.argv) > 1 else 400
    opens = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    home = Path(tempfile.mkdtemp(prefix="ai-upper-residual-"))
    os.environ["AI_UPPER_HOME"] = str(home)

    from probe_heavy import make_home
    make_home(home, 8, turns)

    import collections

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QTextDocument
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication

    from markdown import document as mdoc
    from markdown.body import BodyDocument
    from markdown.highlight import CodeHighlighter
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.settings_service import SettingsService
    from mvvm.services.skill_store import SkillStore
    from mvvm.services.workspace_guard import WorkspaceGuard
    from mvvm.webui.assembly import build_chat_host
    from qml_shell import ShellBridge, qml_main

    phases = collections.defaultdict(list)
    render_on = {"on": False}   # 整个 openSession 期间（含 attach）
    in_body = {"on": False}     # 只在 BodyDocument.render 内部
    hl_calls = collections.Counter()

    # highlightBlock 必须在高亮器**构造之前**装到类上。
    real_hl = CodeHighlighter.highlightBlock

    def hl(self, text):
        hl_calls["all"] += 1
        if in_body["on"]:
            hl_calls["during_body_render"] += 1
        return real_hl(self, text)

    CodeHighlighter.highlightBlock = hl

    def timed(owner, name, key, gate=None):
        fn = getattr(owner, name)

        def inner(*a, **k):
            if gate is not None and not gate["on"]:
                return fn(*a, **k)
            t = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                phases[key].append((time.perf_counter() - t) * 1000.0)

        setattr(owner, name, inner)

    real_body_render = BodyDocument.render

    def body_render(self, document=None):
        t = time.perf_counter()
        in_body["on"] = True
        try:
            return real_body_render(self, document)
        finally:
            in_body["on"] = False
            phases["body_render"].append((time.perf_counter() - t) * 1000.0)

    BodyDocument.render = body_render
    timed(mdoc, "parse_markdown", "parse")
    timed(mdoc, "_collapse_edge_margins", "margins")
    timed(mdoc._Renderer, "render_blocks", "render_blocks")
    timed(QTextDocument, "clear", "clear", gate=in_body)
    timed(QTextDocument, "setDocumentMargin", "set_margin", gate=in_body)
    timed(mdoc, "_render_chunked", "chunked_total")

    from PySide6.QtGui import QTextCursor

    real_insert = QTextCursor.insertFragment

    def insert_fragment(self, fragment):
        if not in_body["on"]:
            return real_insert(self, fragment)
        t = time.perf_counter()
        try:
            return real_insert(self, fragment)
        finally:
            phases["chunk_insert_frag"].append((time.perf_counter() - t) * 1000.0)

    QTextCursor.insertFragment = insert_fragment
    timed(mdoc, "_copy_resources", "chunk_copy_resources")

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
    for _ in range(150):
        app.processEvents()

    short_id = [r["id"] for r in bridge._rows() if r["id"] != "heavy-000"][-1]
    bridge.openSession(short_id)
    for _ in range(30):
        app.processEvents()

    rows = []
    for i in range(opens):
        phases.clear()
        hl_calls.clear()
        render_on["on"] = True
        t = time.perf_counter()
        bridge.openSession("heavy-000")
        total = (time.perf_counter() - t) * 1000.0
        render_on["on"] = False
        for _ in range(20):
            app.processEvents()
        rows.append({
            "open": i,
            "sync_ms": round(total, 1),
            "phase_ms": {k: round(sum(v), 1) for k, v in phases.items()},
            "calls": {k: len(v) for k, v in phases.items()},
            "highlightBlock_calls": dict(hl_calls),
            "source_blocks_after": bridge._body.document.blockCount(),
        })

    out = {"turns": turns, "opens": opens, "rows": rows}
    print("RENDERRESIDUAL " + json.dumps(out, ensure_ascii=False))
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
