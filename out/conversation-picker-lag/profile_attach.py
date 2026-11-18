"""在真实 Main.qml 环境下，把一次 _render 拆成 set_markdown/attach/rehighlight/scroll。"""
from __future__ import annotations
import json, os, sys, tempfile, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from probe_heavy import make_home

def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    home = Path(tempfile.mkdtemp(prefix="ai-upper-pattach-"))
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
    import json as J

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
    phases = {"set_markdown": [], "attach": [], "render_own": [], "render_qml": [], "rehighlight": [], "scroll": []}
    orig_set, orig_attach, orig_render, orig_scroll = body.set_markdown, body.attach, body.render, bridge._scroll_to_bottom

    def timed2(fn, key):
        def inner(*a, **k):
            t = time.perf_counter()
            try: return fn(*a, **k)
            finally: phases[key].append((time.perf_counter()-t)*1000)
        return inner
    body.set_markdown = timed2(orig_set, "set_markdown")
    body.attach = timed2(orig_attach, "attach")
    bridge._scroll_to_bottom = timed2(orig_scroll, "scroll")

    # 拆分 attach 内部：第一次 render（写自身文档）与 render(target)
    orig_body_render = body.render
    def render_split(document=None):
        t = time.perf_counter()
        r = orig_body_render(document)
        dt = (time.perf_counter()-t)*1000
        phases["render_qml" if document is not None else "render_own"].append(dt)
        return r
    body.render = render_split

    long_id, short_id = "heavy-000", "heavy-%03d" % (count-1)
    bridge.openSession(short_id)   # 预热
    out = []
    for _ in range(2):
        for sid in (long_id, short_id):
            for v in phases.values(): v.clear()
            t = time.perf_counter(); bridge.openSession(sid); total = (time.perf_counter()-t)*1000
            out.append({"to": "long" if sid == long_id else "short", "total_ms": round(total,1),
                        **{k: round(sum(v),1) for k,v in phases.items()}})
            print(json.dumps(out[-1], ensure_ascii=False), flush=True)
    md = bridge._markdown_base()
    print("SUMMARY " + json.dumps({"turns": turns, "chars": len(md), "rows": out}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
