"""attach 候选 B：排版预算 / 延迟提交，能否削减同步段。

``endEditBlock`` 里的整篇排版是同步段最大单块（render-opt4 实测 723.5 ms）。这里测三种手法，
全部在真实 ``Main.qml`` + ``ShellBridge`` 里、同一进程内交替（奇数轮倒序）：

- ``base``      现行 ``BodyDocument.attach``
- ``nolayout``  ``target.setLayoutEnabled(False)`` 包住搬运，``endEditBlock`` 之后再打开
- ``nosignal``  ``target.blockSignals(True/False)`` 包住搬运

``defer``（把搬运推迟到事件循环）单独一步测：同步段少了多少，以及推迟之后到画面稳定还要多少；
两者相加不变就说明只改顺序不改总和。

每种都做等价性判定：块数 / 高度 / 着色 run（读 ``layout().formats()``）/ ``toHtml()`` sha /
``bodyScroll.contentY`` / 整帧像素 sha。像素不同即判 ``ok=false``——不拿「渲染成功」当等价。

用法：``probe_attach_defer.py [会话数=40] [轮数=400] [rounds=3] [标签]``
"""
from __future__ import annotations

import hashlib
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

from probe_heavy import make_home  # noqa: E402

SHOT_DIR = ROOT / "out" / "render-opt4"


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    label = sys.argv[4] if len(sys.argv) > 4 else "run"

    home = Path(tempfile.mkdtemp(prefix="ai-upper-defer-"))
    os.environ["AI_UPPER_HOME"] = str(home)
    make_home(home, count, turns)

    from PySide6.QtCore import QObject, QTimer, QUrl
    from PySide6.QtGui import QTextCursor, QTextDocumentFragment, QTextTable
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
    for _ in range(300):
        app.processEvents()

    quick_doc = bridge._document
    body = bridge._body
    body_view = window.findChild(QObject, "bodyView")
    body_scroll = window.findChild(QObject, "bodyScroll")
    assert body_view is not None and body_scroll is not None
    print("UI font: %s %spx" % (body_view.property("font").family(),
                                body_view.property("font").pixelSize()), flush=True)

    def table_count(doc):
        found, stack = 0, [doc.rootFrame()]
        while stack:
            frame = stack.pop()
            if isinstance(frame, QTextTable):
                found += 1
            it = frame.begin()
            while not it.atEnd():
                child = it.currentFrame()
                if child is not None:
                    stack.append(child)
                it += 1
        return found

    def colour_runs(doc):
        """高亮器的着色在 ``QTextLayout`` 的附加格式里，不在 ``textFormats()``。"""
        n, block = 0, doc.begin()
        while block.isValid():
            layout = block.layout()
            for spec in (layout.formats() if layout is not None else []):
                if spec.format.foreground().style() != 0:
                    n += 1
            block = block.next()
        return n

    def snapshot(doc):
        html = doc.toHtml()
        return {"blocks": doc.blockCount(), "height": round(doc.size().height(), 2),
                "tables": table_count(doc), "colour_runs": colour_runs(doc),
                "html_sig": hashlib.sha1(html.encode("utf-8")).hexdigest()[:16],
                "html_len": len(html)}

    def scroll_state():
        return {"contentY": round(float(body_scroll.property("contentY") or 0.0), 2),
                "contentHeight": round(float(body_scroll.property("contentHeight") or 0.0), 2),
                "implicitHeight": round(float(body_view.property("implicitHeight") or 0.0), 2)}

    def frame_shot(tag):
        """整帧像素 sha，剔除左侧时间戳竖列（x 289..294）——那一列跨分钟会翻字，
        同一路径连跑两次都能差几十到上百像素，不剔除会把采集抖动当渲染差异。"""
        image = window.grabWindow()
        shot = SHOT_DIR / ("attach_defer_%s_%s.png" % (label, tag))
        image.save(str(shot))
        flat = image.convertToFormat(image.Format.Format_RGB32)   # 必须留住引用
        h = hashlib.sha1()
        stride = flat.bytesPerLine()
        for y in range(flat.height()):
            row = bytes(flat.scanLine(y))[:stride]
            h.update(row[:289 * 4])
            h.update(row[295 * 4:])
        return {"sha": h.hexdigest()[:16], "png": shot.name}

    def ms(t0):
        return round((time.perf_counter() - t0) * 1000.0, 1)

    def transport(mode):
        """只做「把自有文档搬进 QML 文档」这一步，三种手法只差包裹。"""
        target = quick_doc.textDocument()
        if mode == "nolayout":
            target.setLayoutEnabled(False)
        elif mode == "nosignal":
            target.blockSignals(True)
        try:
            cursor = QTextCursor(target)
            cursor.beginEditBlock()
            try:
                cursor.select(QTextCursor.SelectionType.Document)
                cursor.removeSelectedText()
                cursor.insertFragment(QTextDocumentFragment(body.document))
            finally:
                cursor.endEditBlock()
            body._copy_images(target)
        finally:
            if mode == "nolayout":
                target.setLayoutEnabled(True)
            elif mode == "nosignal":
                target.blockSignals(False)
        return target

    def run_segment(mode, md_text):
        body._source = md_text
        body._plain = False
        t0 = time.perf_counter()
        body.render()
        render_ms = ms(t0)

        t0 = time.perf_counter()
        error = None
        try:
            if mode == "base":
                body.attach(quick_doc)
                target = quick_doc.textDocument()
            else:
                target = transport(mode)
        except Exception as exc:  # noqa: BLE001
            error, target = "%s: %s" % (type(exc).__name__, exc), None
        transfer_ms = ms(t0)

        t0 = time.perf_counter()
        bridge._publish()
        publish_ms = ms(t0)

        t0 = time.perf_counter()
        for _ in range(30):
            app.processEvents()
        settle_ms = ms(t0)

        return {"mode": mode, "render_ms": render_ms, "transfer_ms": transfer_ms,
                "publish_ms": publish_ms, "settle_ms": settle_ms,
                "sync_ms": round(render_ms + transfer_ms + publish_ms, 1),
                "shell_ms": round(render_ms + transfer_ms + publish_ms + settle_ms, 1),
                "error": error}, target

    rows = bridge._rows()
    long_id = "heavy-000"
    others = [r["id"] for r in rows if r["id"] != long_id]
    assert others
    back = others[-1]

    def go(session_id):
        bridge._active = session_id
        bridge._render()
        bridge._publish()
        for _ in range(30):
            app.processEvents()

    go(back)

    modes_all = ["base", "nolayout", "nosignal"]
    results, baseline = [], None
    for round_index in range(rounds):
        order = list(modes_all)
        if round_index % 2:
            order.reverse()
        for mode in order:
            go(back)
            bridge._active = long_id
            md_text = bridge._markdown_base()
            seg, target = run_segment(mode, md_text)
            bridge._scroll_to_bottom()
            for _ in range(2):
                app.processEvents()
            scroll = scroll_state()
            shot = frame_shot("r%d_%s" % (round_index, mode))
            if target is None:
                results.append({**seg, "round": round_index, "ok": False,
                                "scroll": scroll, "shot": shot})
                continue
            snap = snapshot(target)
            if baseline is None:
                baseline = snap
                base_view = {"implicitHeight": scroll["implicitHeight"],
                             "contentY": scroll["contentY"],
                             "frame_sha": shot["sha"]}
            eq = {"blocks_eq": snap["blocks"] == baseline["blocks"],
                  "height_eq": snap["height"] == baseline["height"],
                  "tables_eq": snap["tables"] == baseline["tables"],
                  "colour_eq": snap["colour_runs"] == baseline["colour_runs"],
                  "html_eq": snap["html_sig"] == baseline["html_sig"],
                  # 文档几何相等不够：QML 控件的 implicitHeight 不更新时视口还停在旧文档，
                  # 文档本身却已经是对的。第一次跑就是漏了这一项，把「控件没刷新」判成了等价。
                  "view_eq": (scroll["implicitHeight"] == base_view["implicitHeight"]
                              and scroll["contentY"] == base_view["contentY"]),
                  "frame_eq": shot["sha"] == base_view["frame_sha"]}
            results.append({**seg, "round": round_index, **snap, "scroll": scroll,
                            "shot": shot, **eq, "ok": all(eq.values())})

    # ── defer：同步段 vs 推迟后补齐 ────────────────────────────────────────
    defer = []
    for _ in range(2):
        go(back)
        bridge._active = long_id
        md_text = bridge._markdown_base()
        body._source = md_text
        body._plain = False
        t0 = time.perf_counter()
        body.render()
        render_ms = ms(t0)
        pending = {}
        t0 = time.perf_counter()
        QTimer.singleShot(0, lambda: pending.setdefault("t", time.perf_counter()))
        QTimer.singleShot(0, lambda: body.attach(quick_doc))
        sync_ms = ms(t0)
        for _ in range(60):
            app.processEvents()
        total_ms = ms(t0)
        d = bridge._document.textDocument()
        defer.append({"render_ms": render_ms, "sync_ms": sync_ms,
                      "settle_to_stable_ms": round(total_ms - sync_ms, 1),
                      "total_ms": total_ms,
                      "blocks": d.blockCount(),
                      "height": round(d.size().height(), 2),
                      "colour_runs": colour_runs(d)})

    def agg(mode):
        sel = [r for r in results if r["mode"] == mode]
        out = {"n": len(sel), "ok": [r["ok"] for r in sel],
               "errors": [r["error"] for r in sel if r.get("error")]}
        for key in ("render_ms", "transfer_ms", "publish_ms", "settle_ms", "sync_ms", "shell_ms"):
            vals = sorted(r[key] for r in sel)
            out[key] = vals
            out[key + "_median"] = round(statistics.median(vals), 1)
        for key in ("blocks", "height", "tables", "colour_runs", "html_sig", "html_len"):
            vals = [r.get(key) for r in sel]
            if any(v is None for v in vals):
                continue
            out[key] = vals[0] if len(set(map(str, vals))) == 1 else vals
        out["equivalence_all_rounds"] = {
            k: all(r[k] for r in sel)
            for k in ("blocks_eq", "height_eq", "tables_eq", "colour_eq", "html_eq",
                      "view_eq", "frame_eq")}
        return out

    out = {"label": label, "sessions": count, "turns": turns, "rounds": rounds,
           "baseline": baseline, "results": results, "defer": defer,
           "base": agg("base"), "nolayout": agg("nolayout"), "nosignal": agg("nosignal")}
    print("ATTACHDEFER " + json.dumps(out, ensure_ascii=False))
    window.close()
    return 0 if all(r.get("ok") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
