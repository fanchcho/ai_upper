"""逐行复刻 BodyDocument.attach，把片段构造也算进去，量「未归因」的 666 ms 在哪。"""
import json, os, sys, tempfile, time
from pathlib import Path
ROOT = Path("/home/agent/shared_workspace/ai_upper")
sys.path.insert(0, str(ROOT / "app/src")); sys.path.insert(0, str(ROOT / "out/conversation-picker-lag"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
home = Path(tempfile.mkdtemp(prefix="ai-upper-lines-")); os.environ["AI_UPPER_HOME"] = str(home)
from probe_heavy import make_home
make_home(home, 12, 400)
from PySide6.QtCore import QUrl
from PySide6.QtGui import QTextCursor, QTextDocumentFragment
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
PersonaStore(home).ensure_seeded(); box = {}
def emit(p): box["bridge"].emit(p)
host, _ = build_chat_host(settings=settings, vault=vault, store=store, guard=WorkspaceGuard(),
                          home=home, emit=emit, emit_sessions_changed=lambda: None)
bridge = ShellBridge(host=host, store=store, plain=False, settings=settings, vault=vault, skills=SkillStore(home))
box["bridge"] = bridge
engine = QQmlApplicationEngine(); engine.rootContext().setContextProperty("shellBridge", bridge)
engine.load(QUrl.fromLocalFile(str(qml_main()))); window = engine.rootObjects()[0]
bridge.bind_window(window); bridge.initial(); window.show()
for _ in range(200): app.processEvents()
body = bridge._body
bridge.openSession("heavy-000")
for _ in range(200): app.processEvents()
found = {}
for obj in window.findChildren(object):
    name = obj.objectName() if hasattr(obj, "objectName") else ""
    if name: found.setdefault(name, obj)
quick = found["bodyView"].property("textDocument")
target = quick.textDocument()
hl = body._highlighter
steps = {}
def mark(k, t0):
    dt = (time.perf_counter() - t0) * 1000.0
    steps[k] = steps.get(k, 0.0) + dt
    return time.perf_counter()
reps = 3; totals = []
for _ in range(reps):
    t0 = time.perf_counter()
    target.setDocumentMargin(body.document.documentMargin()); t = mark("setDocumentMargin", t0)
    if hl is not None and hl.document() is not target: hl.setDocument(target)
    t = mark("highlighter_rebind", t)
    cursor = QTextCursor(target); t = mark("cursor", t)
    cursor.beginEditBlock(); t = mark("beginEditBlock", t)
    cursor.select(QTextCursor.SelectionType.Document); t = mark("select", t)
    cursor.removeSelectedText(); t = mark("remove", t)
    frag = QTextDocumentFragment(body.document); t = mark("fragment_ctor", t)
    cursor.insertFragment(frag); t = mark("insertFragment", t)
    cursor.endEditBlock(); t = mark("endEditBlock", t)
    body._copy_images(target); t = mark("copy_images", t)
    totals.append((time.perf_counter() - t0) * 1000.0)
per = {k: round(v / reps, 1) for k, v in steps.items()}
print("LINES " + json.dumps({"total": [round(x,1) for x in totals], "per": per,
                             "sum": round(sum(per.values()),1)}, ensure_ascii=False))
window.close()
