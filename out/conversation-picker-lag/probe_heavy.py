"""重正文场景：点进一条长对话（多轮 + 代码块 + 表格）时的点击耗时。

真实用户的「多对话选择」卡顿通常发生在会话有长历史时：openSession 会在 GUI 线程
把整篇正文重新解析并渲染进 QTextDocument。
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

CODE = """```python
def build_report(rows):
    out = []
    for row in rows:
        out.append({"name": row.name, "total": sum(row.values)})
    return sorted(out, key=lambda r: r["total"], reverse=True)
```
"""

TABLE = """
| 文件 | 类型 | 说明 |
| --- | --- | --- |
| `README.md` | 文档 | 项目用途与运行方式 |
| `src/` | 目录 | 源代码 |
| `package.json` | 配置 | 依赖清单 |
"""


def make_home(home: Path, count: int, turns: int) -> None:
    chats = home / "data" / "chats"
    chats.mkdir(parents=True, exist_ok=True)
    base = int(time.time() * 1000) - 22 * 3600 * 1000
    index = []
    for i in range(count):
        sid = "heavy-%03d" % i
        messages = []
        rounds = turns if i == 0 else 1
        for t in range(rounds):
            messages.append({"role": "user", "content":
                             "第 %d 轮的提问：请把这一轮的结果整理成表格并给出要点。" % t})
            messages.append({"role": "assistant", "content": [{"type": "text", "text":
                             "这是第 %d 轮回复。\n\n%s\n要点：\n\n1. 先读 README\n2. 再看依赖\n\n%s" % (t, CODE, TABLE)}]})
        data = {"id": sid, "title": "会话 %03d" % i, "createdAt": base,
                "updatedAt": base + (count - i) * 1000, "personaId": "general",
                "messages": messages}
        (chats / (sid + ".json")).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        index.append({"id": sid, "title": data["title"], "createdAt": base,
                      "updatedAt": data["updatedAt"], "personaId": "general"})
    (chats / "_index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    turns = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    clicks = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    home = Path(tempfile.mkdtemp(prefix="ai-upper-heavy-"))
    os.environ["AI_UPPER_HOME"] = str(home)
    make_home(home, count, turns)

    from PySide6.QtCore import QPoint, Qt, QTimer, QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QTest
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

    frames = {"n": 0}
    window.frameSwapped.connect(lambda: frames.__setitem__("n", frames["n"] + 1))

    def pump_until(pred, timeout=60.0):
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

    def row_point(i):
        # 侧栏 x=56；ListView y=56；行高 54。行 i 的中心 = 56 + i*54 + 27。
        return QPoint(56 + 8 + 140, 56 + i * 54 + 27)

    rows = bridge._rows()
    long_ids = [r["id"] for r in rows]
    long_row = long_ids.index("heavy-000")
    short_row = long_ids.index("heavy-%03d" % (count - 1))
    print("ROWS long=%d short=%d" % (long_row, short_row), flush=True)

    samples = []
    # 交替点击：长对话 ↔ 短对话
    for k in range(clicks):
        i = long_row if k % 2 == 0 else short_row
        before = frames["n"]
        t0 = time.perf_counter()
        QTest.mouseClick(window, Qt.LeftButton, Qt.NoModifier, row_point(i))
        app.processEvents()
        got = pump_until(lambda: frames["n"] > before, timeout=30.0)
        samples.append({"row": i, "ms": round((time.perf_counter() - t0) * 1000, 2),
                        "repainted": got, "active": bridge._active})

    long_s = [s["ms"] for s in samples if s["row"] == long_row]
    short_s = [s["ms"] for s in samples if s["row"] == short_row]
    print("HEAVY-RESULT " + json.dumps({
        "sessions": count, "turns_in_long": turns,
        "long_median_ms": round(statistics.median(long_s), 2) if long_s else None,
        "long_max_ms": max(long_s) if long_s else None,
        "short_median_ms": round(statistics.median(short_s), 2) if short_s else None,
        "samples": samples, "home": str(home),
    }, ensure_ascii=False))
    ticker.stop()
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
