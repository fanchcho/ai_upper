"""直接测「点进长对话」的同步开销构成（不经 QTest，避免坐标/事件循环干扰）。"""
from __future__ import annotations
import json, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from probe_heavy import make_home  # noqa: E402


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    home = Path(tempfile.mkdtemp(prefix="ai-upper-plong-"))
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
    from qml_shell_sessions import transcript_markdown

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
    for _ in range(300):
        app.processEvents()

    long_id = "heavy-000"
    short_id = "heavy-%03d" % (count - 1)
    marks = {}
    orig_md_base = bridge._markdown_base
    orig_md = bridge._markdown
    orig_render = bridge._render
    orig_publish = bridge._publish

    def timed(fn, key):
        def inner(*a, **k):
            t = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                marks.setdefault(key, []).append((time.perf_counter() - t) * 1000)
        return inner

    bridge._markdown_base = timed(orig_md_base, "markdown_base")
    bridge._markdown = timed(orig_md, "markdown")
    bridge._render = timed(orig_render, "render")
    bridge._publish = timed(orig_publish, "publish")

    def click_once(sid):
        for k in ("markdown_base", "markdown", "render", "publish"):
            marks.pop(k, None)
        before = {k: len(v) for k, v in marks.items()}
        t0 = time.perf_counter()
        bridge.openSession(sid)
        total = (time.perf_counter() - t0) * 1000
        detail = {k: round(sum(v[before.get(k, 0):]), 2) for k, v in marks.items()}
        return round(total, 2), detail

    # 预热：先点一次短会话（缓存建立）
    click_once(short_id)
    results = []
    for i in range(4):
        results.append({"to": "long", **dict(zip(("total_ms", "detail"), click_once(long_id)))})
        results.append({"to": "short", **dict(zip(("total_ms", "detail"), click_once(short_id)))})

    sess = store.load_session(long_id)
    md = transcript_markdown(sess.messages)
    print("LONG-PROFILE " + json.dumps({
        "turns": turns, "markdown_chars": len(md), "markdown_lines": md.count("\n"),
        "results": results, "home": str(home),
    }, ensure_ascii=False))
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
