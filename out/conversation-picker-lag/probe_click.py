"""点击会话行 → 界面响应的真实耗时（offscreen 实跑，不依赖网络）。

用真 QML 壳（ShellBridge + Main.qml），在 /tmp 的 AI_UPPER_HOME 上放 N 条会话，
用 QTest.mouseClick 点第 i 行，测「点击派发 → 界面处理完并画出新帧」的墙钟耗时。
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def make_home(home: Path, count: int) -> None:
    chats = home / "data" / "chats"
    chats.mkdir(parents=True, exist_ok=True)
    base = int(time.time() * 1000) - 22 * 3600 * 1000
    index = []
    body = "\n\n".join(
        "第 %d 段正文，用来让 QTextDocument 有真实体量。" % i for i in range(60)
    )
    for i in range(count):
        sid = "probe-%03d" % i
        data = {
            "id": sid,
            "title": "会话 %03d：准备发布说明" % i,
            "createdAt": base,
            "updatedAt": base + (count - i) * 1000,
            "personaId": "general",
            "messages": [
                {"role": "user", "content": "请说明第 %d 条会话。" % i},
                {"role": "assistant", "content": [{"type": "text", "text": body}]},
            ],
        }
        (chats / (sid + ".json")).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        index.append({"id": sid, "title": data["title"], "createdAt": base,
                      "updatedAt": data["updatedAt"], "personaId": "general"})
    (chats / "_index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    clicks = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    home = Path(tempfile.mkdtemp(prefix="ai-upper-click-"))
    os.environ["AI_UPPER_HOME"] = str(home)
    make_home(home, count)

    from PySide6.QtCore import QCoreApplication, QObject, QPoint, Qt, QTimer, QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication

    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.settings_service import SettingsService
    from mvvm.services.skill_store import SkillStore
    from mvvm.services.workspace_guard import WorkspaceGuard
    from mvvm.services.persona_store import PersonaStore
    from mvvm.webui.assembly import build_chat_host
    from qml_shell import ShellBridge, qml_main
    from utils.paths import module_file  # noqa: F401

    app = QApplication.instance() or QApplication([])
    settings = SettingsService(home)
    vault = SecretsVault(home)
    store = ChatSessionStore(home)
    PersonaStore(home).ensure_seeded()
    guard = WorkspaceGuard()
    emit_box = {}

    def emit(payload):
        emit_box["bridge"].emit(payload)

    host, _gw = build_chat_host(
        settings=settings, vault=vault, store=store, guard=guard, home=home,
        emit=emit, emit_sessions_changed=lambda: None,
    )
    bridge = ShellBridge(host=host, store=store, plain=False, settings=settings,
                         vault=vault, skills=SkillStore(home))
    emit_box["bridge"] = bridge

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("shellBridge", bridge)
    engine.load(QUrl.fromLocalFile(str(qml_main())))
    window = engine.rootObjects()[0]
    bridge.bind_window(window)
    bridge.initial()
    window.show()

    frames = {"n": 0}
    window.frameSwapped.connect(lambda: frames.__setitem__("n", frames["n"] + 1))

    def pump_until(pred, timeout=30.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            app.processEvents()
            if pred():
                return True
            time.sleep(0.005)
        return False

    pump_until(lambda: frames["n"] > 2)

    ticker = QTimer()
    ticker.setInterval(30)
    ticker.timeout.connect(bridge.tick)
    ticker.start()

    # 侧栏 x=56；ListView x=8/y=56；行高 54。
    def row_point(i: int) -> QPoint:
        return QPoint(56 + 8 + 140, 56 + 56 + i * 54 + 27)

    samples = []
    for k in range(1, clicks + 1):
        i = k % min(count, 8)
        before = frames["n"]
        t0 = time.perf_counter()
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, row_point(i))
        app.processEvents()
        got = pump_until(lambda: frames["n"] > before, timeout=10.0)
        elapsed = (time.perf_counter() - t0) * 1000.0
        samples.append({"row": i, "ms": round(elapsed, 2), "repainted": got,
                        "active": bridge._active})

    ticker.stop()
    # 只统计确实换了会话的点击
    switched = [s for s in samples if s["active"] not in ("", None)]
    result = {
        "sessions": count,
        "clicks": len(samples),
        "home": str(home),
        "median_ms": round(statistics.median(s["ms"] for s in samples), 2),
        "max_ms": max(s["ms"] for s in samples),
        "min_ms": min(s["ms"] for s in samples),
        "samples": samples,
    }
    print("CLICK-RESULT " + json.dumps(result, ensure_ascii=False))
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
