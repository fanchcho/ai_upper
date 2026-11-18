"""把高亮从 contentsChange 驱动改成「搬完一次性重高亮」，是否更快且逐项等价。

三种顺序，目标都是 QML 的 QQuickTextDocument：

- ``A_current``  —— 现状：先 ``setDocument(target)``，再 insertFragment，
                   内容变更逐块驱动高亮（``endEditBlock`` 里跑）；
- ``B_after``    —— 搬运时目标没有高亮器，搬完 ``setDocument(target)`` 后显式
                   ``rehighlight()`` 一次；
- ``B_no_rh``    —— 搬运时目标没有高亮器，搬完只 ``setDocument(target)``（不显式重跑），
                   看是不是仍然要靠 contentsChange 才着色。

等价性比对（A 与 B 各自产出的文档）：
块数、块格式、每个块的布局格式区间（``block.layout().formats()`` 的颜色/长度）、
``toHtml()``、文档尺寸。布局格式才是着色真正落点，必须逐区间相等。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path("/home/agent/shared_workspace/ai_upper")
sys.path.insert(0, str(ROOT / "app" / "src"))
sys.path.insert(0, str(ROOT / "out" / "conversation-picker-lag"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def layout_sig(doc):
    """逐块记录块文本与布局格式区间（起点/长度/前景色）。"""
    out, block = [], doc.begin()
    while block.isValid():
        layout = block.layout()
        ranges = ()
        if layout is not None:
            ranges = tuple((r.start, r.length,
                            r.format.foreground().color().name()
                            if r.format.foreground().style() else None,
                            r.format.font().italic())
                           for r in layout.formats())
        out.append((block.text(), ranges))
        block = block.next()
    return out


def block_fmt_sig(doc):
    out, block = [], doc.begin()
    while block.isValid():
        f = block.blockFormat()
        out.append((block.text(), round(f.topMargin(), 4), round(f.bottomMargin(), 4),
                    round(f.leftMargin(), 4), round(f.lineHeight(), 4), f.alignment(),
                    f.indent(), tuple(sorted((p, str(f.property(p))) for p in f.properties()
                                             if p >= 0x100000))))
        block = block.next()
    return out


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    home = Path(tempfile.mkdtemp(prefix="ai-upper-reorder-"))
    os.environ["AI_UPPER_HOME"] = str(home)

    from probe_heavy import make_home
    make_home(home, count, turns)

    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QTextCursor, QTextDocumentFragment
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtWidgets import QApplication

    from markdown.highlight import CodeHighlighter

    calls = {"n": 0, "ms": 0.0}
    orig_block = CodeHighlighter.highlightBlock

    def counted(self, text):
        t = time.perf_counter()
        try:
            return orig_block(self, text)
        finally:
            calls["n"] += 1
            calls["ms"] += (time.perf_counter() - t) * 1000.0

    CodeHighlighter.highlightBlock = counted

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

    body = bridge._body
    bridge.openSession("heavy-000")
    for _ in range(200):
        app.processEvents()

    found = {}
    for obj in window.findChildren(object):
        name = obj.objectName() if hasattr(obj, "objectName") else ""
        if name:
            found.setdefault(name, obj)
    quick = found["bodyView"].property("textDocument")
    qdoc = quick.textDocument()
    src = body.document
    hl = body._highlighter

    def move(target):
        target.setDocumentMargin(0)
        cursor = QTextCursor(target)
        cursor.beginEditBlock()
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.removeSelectedText()
        cursor.insertFragment(QTextDocumentFragment(src))
        cursor.endEditBlock()

    def run(kind):
        calls["n"] = calls["ms"] = 0
        t = time.perf_counter()
        if kind == "A_current":
            if hl.document() is not qdoc:
                hl.setDocument(qdoc)
            move(qdoc)
        elif kind == "B_after":
            if hl.document() is qdoc:
                hl.setDocument(src)
            move(qdoc)
            t_mid = time.perf_counter()
            hl.setDocument(qdoc)
            hl.rehighlight()
        else:
            if hl.document() is qdoc:
                hl.setDocument(src)
            move(qdoc)
            hl.setDocument(qdoc)
        total = (time.perf_counter() - t) * 1000.0
        row = {"total_ms": round(total, 1), "hl_calls": calls["n"],
               "hl_ms": round(calls["ms"], 1)}
        if kind == "B_after":
            row["rehighlight_and_rebind_ms"] = round((time.perf_counter() - t_mid) * 1000.0, 1)
        return row

    def best(kind, reps=3):
        rows = [run(kind) for _ in range(reps)]
        return min(rows, key=lambda r: r["total_ms"])

    a = best("A_current")
    a_layout, a_blocks, a_html = layout_sig(qdoc), block_fmt_sig(qdoc), qdoc.toHtml()
    a_size = (qdoc.size().width(), qdoc.size().height())
    a_count = (qdoc.blockCount(), qdoc.characterCount())

    b = best("B_after")
    b_layout, b_blocks, b_html = layout_sig(qdoc), block_fmt_sig(qdoc), qdoc.toHtml()
    b_size = (qdoc.size().width(), qdoc.size().height())
    b_count = (qdoc.blockCount(), qdoc.characterCount())

    d_layout = [i for i, (x, y) in enumerate(zip(a_layout, b_layout)) if x != y]
    d_blocks = [i for i, (x, y) in enumerate(zip(a_blocks, b_blocks)) if x != y]

    c = best("B_no_rh", reps=1)
    c_layout = layout_sig(qdoc)

    print("REORDER " + json.dumps({
        "turns": turns,
        "A_current": a,
        "B_after": b,
        "B_no_rh": c,
        "counts": [a_count, b_count],
        "layout_diffs": len(d_layout), "layout_diff_indexes": d_layout[:5],
        "block_fmt_diffs": len(d_blocks), "block_fmt_diff_indexes": d_blocks[:5],
        "html_eq": a_html == b_html,
        "size_eq": a_size == b_size,
        "size": [a_size, b_size],
        "no_rh_equals_A": c_layout == a_layout,
        "no_rh_colored_blocks": sum(1 for _, r in c_layout if r),
        "A_colored_blocks": sum(1 for _, r in a_layout if r),
        "A_total_ranges": sum(len(r) for _, r in a_layout),
    }, ensure_ascii=False))
    window.close()


if __name__ == "__main__":
    main()
