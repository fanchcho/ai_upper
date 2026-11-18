"""attach 候选 A 正式探针：整篇替换（``setTextDocument``）vs 现行 ``insertFragment``。

三条变体，全部在真实 ``Main.qml`` + ``ShellBridge`` 里跑：

- ``insert``       现行实现：渲染进自有文档 → ``BodyDocument.attach``（remove + insertFragment）
- ``replace``      新文档先行渲染（高亮器先挂新文档，随渲染着色）→ ``QQuickTextDocument.setTextDocument``
- ``replace_nohl`` 同上但渲染时摘掉高亮器，只为量 ``setTextDocument`` 的成本下限

两个关键前提（第一次跑踩到的）：

1. 新 ``QTextDocument`` 的默认字体是 ``Sans Serif 9pt``，QML 文档是 ``DejaVu Sans 14px``；
   不 ``setDefaultFont`` 抄过去，几何整体不同（400 轮差 2400 px）。
2. ``image.convertToFormat(...).bits()`` 不能对临时对象取，否则悬空指针段错误。

等价性口径（以 ``insert`` 为基线）：
块数、高度、表格数、**着色签名**（逐块文本 + 前景色拼串后取 sha1，比「有色 run 数」精确）、
``toHtml()`` 的 sha1、``bodyScroll.contentY/contentHeight``、窗口整帧像素 sha1。

用法：``probe_attach_replace.py [会话数=40] [轮数=400] [rounds=5] [标签]``
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
    rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    label = sys.argv[4] if len(sys.argv) > 4 else "run"

    home = Path(tempfile.mkdtemp(prefix="ai-upper-attachrep-"))
    os.environ["AI_UPPER_HOME"] = str(home)
    make_home(home, count, turns)

    from PySide6.QtCore import QObject, QUrl
    from PySide6.QtGui import QTextDocument, QTextTable
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
    ui_font = body_view.property("font")
    print("UI font: %s %spx" % (ui_font.family(), ui_font.pixelSize()), flush=True)

    # ── 量具 ──────────────────────────────────────────────────────────────
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

    def colour_signature(doc):
        """逐块 (文本, 每个着色 run 的前景色) 拼串取 sha1。

        **必须读 ``block.layout().formats()``**：高亮器写的是 ``QTextLayout`` 的
        附加格式，``block.textFormats()`` 只回基础块格式，两种文档都只回一条基础色，
        拿它比对会把「代码块全灰」和「代码块着色」判成相等（第一次跑就是这么错的）。
        """
        h = hashlib.sha1()
        block = doc.begin()
        runs = 0
        while block.isValid():
            h.update(block.text().encode("utf-8"))
            layout = block.layout()
            for spec in (layout.formats() if layout is not None else []):
                fg = spec.format.foreground()
                if fg.style() != 0:
                    h.update(spec.format.foreground().color().name().encode("ascii"))
                    runs += 1
            h.update(b"\x00")
            block = block.next()
        return h.hexdigest()[:16], runs

    def snapshot(doc):
        sig, runs = colour_signature(doc)
        return {"blocks": doc.blockCount(),
                "height": round(doc.size().height(), 2),
                "tables": table_count(doc),
                "colour_runs": runs,
                "colour_sig": sig,
                "html_sig": hashlib.sha1(doc.toHtml().encode("utf-8")).hexdigest()[:16],
                "html_len": len(doc.toHtml())}

    def scroll_state():
        return {"contentY": round(float(body_scroll.property("contentY") or 0.0), 2),
                "contentHeight": round(float(body_scroll.property("contentHeight") or 0.0), 2),
                "implicitHeight": round(float(body_view.property("implicitHeight") or 0.0), 2)}

    def frame_shot(tag):
        """整帧像素 sha，但**剔掉左侧时间戳竖列**（x 289..294）。

        那一列显示「21 hr ago」这类相对时间，跨分钟会翻字；同一路径连跑两次都能差出
        一百来个像素（实测 insert r0 vs r3：34 px、r0 vs r4：136 px，全落在这一列）。
        不剔除就会把采集抖动误判成渲染差异；真正的内容差异会横跨更宽的范围
        （``replace_nohl`` 的代码块丢色是 4020 px、x 到 949），剔掉这一列照样抓得住。
        """
        image = window.grabWindow()
        shot = SHOT_DIR / ("attach_replace_%s_%s.png" % (label, tag))
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

    # ── 变体 ──────────────────────────────────────────────────────────────
    def start_fresh():
        fresh = QTextDocument()
        fresh.setDefaultFont(ui_font)
        fresh.setDocumentMargin(body.document.documentMargin())
        return fresh

    def run_segment(mode, md_text):
        """一次切换的完整同步段；三段（render / transfer / publish）分开计时。"""
        fresh = None
        if mode in ("replace", "replace_nohl"):
            fresh = start_fresh()
            if mode == "replace" and body.highlighter is not None:
                body.highlighter.setDocument(fresh)

        saved_hl = body._highlighter
        if mode == "replace_nohl":
            body._highlighter = None            # 渲染时不着色，只为量成本下限
        body._source = md_text
        body._plain = False

        t0 = time.perf_counter()
        try:
            body.render(document=fresh) if fresh is not None else body.render()
        finally:
            body._highlighter = saved_hl
        render_ms = ms(t0)

        t0 = time.perf_counter()
        error, target = None, None
        try:
            if mode == "insert":
                body.attach(quick_doc)
            else:
                quick_doc.setTextDocument(fresh)
            target = quick_doc.textDocument()
        except Exception as exc:  # noqa: BLE001
            error = "%s: %s" % (type(exc).__name__, exc)
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

    # ── 驱动 ──────────────────────────────────────────────────────────────
    rows = bridge._rows()
    long_id = "heavy-000"
    others = [r["id"] for r in rows if r["id"] != long_id]
    assert others, "need a short session to switch away to"
    back = others[-1]

    def go(session_id):
        bridge._active = session_id
        bridge._render()
        bridge._publish()
        for _ in range(30):
            app.processEvents()

    go(back)

    results, baseline, holder = [], None, {}
    modes_all = ["insert", "replace"]
    for round_index in range(rounds):
        order = list(modes_all)
        if round_index % 2:
            order.reverse()
        if round_index == rounds - 1:
            order.append("replace_nohl")     # 成本下限：只测一遍，不进等价性判定
        for mode in order:
            go(back)                          # 两侧都从同一短会话状态出发
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
                  "colour_eq": snap["colour_sig"] == baseline["colour_sig"],
                  "html_eq": snap["html_sig"] == baseline["html_sig"],
                  # 文档对不够：还要看 QML 控件是否真的换到了新文档高度、画面是否一致。
                  "view_eq": (scroll["implicitHeight"] == base_view["implicitHeight"]
                              and scroll["contentY"] == base_view["contentY"]),
                  "frame_eq": shot["sha"] == base_view["frame_sha"]}
            holder.setdefault(mode, []).append({"scroll": scroll, "shot": shot, "eq": eq})
            results.append({**seg, "round": round_index, **snap, "scroll": scroll,
                            "shot": shot, **eq, "ok": all(eq.values())})

    # 同轮跨路径对照：滚动位置与整帧像素
    cross = {}
    if all(k in holder for k in ("insert", "replace")):
        a, b = holder["insert"], holder["replace"]
        cross = {
            "pairs": min(len(a), len(b)),
            "scroll_y_equal": all(x["scroll"]["contentY"] == y["scroll"]["contentY"]
                                  for x, y in zip(a, b)),
            "content_height_equal": all(x["scroll"]["contentHeight"] == y["scroll"]["contentHeight"]
                                        for x, y in zip(a, b)),
            "frame_sha_equal": all(x["shot"]["sha"] == y["shot"]["sha"] for x, y in zip(a, b)),
            "frame_shas": {"insert": [x["shot"]["sha"] for x in a],
                           "replace": [y["shot"]["sha"] for y in b]},
            "shots": {"insert": [x["shot"]["png"] for x in a],
                      "replace": [y["shot"]["png"] for y in b]},
        }

    def agg(mode):
        sel = [r for r in results if r["mode"] == mode]
        if not sel:
            return {}
        out = {"n": len(sel), "ok": [r["ok"] for r in sel],
               "errors": [r["error"] for r in sel if r.get("error")]}
        for key in ("render_ms", "transfer_ms", "publish_ms", "settle_ms",
                    "sync_ms", "shell_ms"):
            vals = sorted(r[key] for r in sel)
            out[key] = vals
            out[key + "_median"] = round(statistics.median(vals), 1)
            out[key + "_min"] = vals[0]
        for key in ("blocks", "height", "tables", "colour_runs", "colour_sig", "html_len"):
            vals = [r.get(key) for r in sel]
            if any(v is None for v in vals):
                continue
            out[key] = vals[0] if len(set(map(str, vals))) == 1 else vals
        eqs = {k: all(r[k] for r in sel) for k in
               ("blocks_eq", "height_eq", "tables_eq", "colour_eq", "html_eq",
                "view_eq", "frame_eq")}
        out["equivalence_all_rounds"] = eqs
        return out

    out = {"label": label, "sessions": count, "turns": turns, "rounds": rounds,
           "ui_font": {"family": ui_font.family(), "pixelSize": ui_font.pixelSize()},
           "baseline": baseline, "results": results,
           "insert": agg("insert"), "replace": agg("replace"),
           "replace_nohl": agg("replace_nohl"), "cross": cross}
    print("ATTACHREP " + json.dumps(out, ensure_ascii=False))
    window.close()
    return 0 if all(r.get("ok") for r in results if r["mode"] != "replace_nohl") else 1


if __name__ == "__main__":
    raise SystemExit(main())
