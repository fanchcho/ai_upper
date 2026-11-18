"""验证 _render 的四个阶段，特别是「渲染自身文档」时高亮器仍挂在上一份巨大 QML 文档上。"""
from __future__ import annotations
import json, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from probe_heavy import make_home

def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 200
    home = Path(tempfile.mkdtemp(prefix="ai-upper-prh-"))
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
    host, _ = build_chat_host(settings=settings, vault=vault, store=store,
                              guard=WorkspaceGuard(), home=home,
                              emit=lambda p: box["bridge"].emit(p),
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

    body = bridge._body
    hl = body.highlighter
    # 高亮器当前挂在哪份文档上？
    print("highlighter doc is qml-doc:", hl.document() is not body.document, flush=True)

    orig_render, orig_attach, orig_set = body.render, body.attach, body.set_markdown
    orig_rh = type(hl).rehighlight
    log = {}
    def rec(key, fn):
        def inner(*a, **k):
            t = time.perf_counter()
            try: return fn(*a, **k)
            finally: log.setdefault(key, []).append(round((time.perf_counter()-t)*1000, 1))
        return inner
    body.render = rec("body_render", orig_render)
    body.attach = rec("body_attach", orig_attach)
    body.set_markdown = rec("set_markdown", orig_set)
    type(hl).rehighlight = rec("rehighlight", orig_rh)

    long_id, short_id = "heavy-000", "heavy-%03d" % (count-1)
    bridge.openSession(long_id)          # 先进入大文档
    for key in log: log[key].clear()

    rows = []
    for sid, label in ((short_id, "big->short"), (long_id, "short->big"), (short_id, "big->short")):
        for v in log.values(): v.clear()
        t = time.perf_counter(); bridge.openSession(sid); total = (time.perf_counter()-t)*1000
        rows.append({"to": label, "total_ms": round(total,1),
                     **{k: v for k, v in log.items()}})
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    print("SUMMARY " + json.dumps({"turns": turns, "rows": rows}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
