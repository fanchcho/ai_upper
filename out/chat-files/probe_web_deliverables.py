"""web 入口实证：交付卡真的接通了（不再是 0 B / 通道未接入）。

做法：在临时 HOME 里落一条带 `delivered` 边车的会话（`present_files` 两次交付：一个 png、
一个 md），再用真 QtWebEngine 打开 web 入口，点进那条会话，从 DOM 里读：
    文件名、大小文案、缩略图 img 是否加载出像素、`deliverables:inspect/thumbnail` 的返回。
最后截一张图。

不联网、不调模型：会话与边车是直接落盘的，测的是「渲染层 → 桥 → 服务」这条链。
用法：AUDIT_HOME=/tmp/chat-files-web .venv/bin/python out/chat-files/probe_web_deliverables.py
"""
from __future__ import annotations

import base64
import json
import os
import struct
import sys
import time
import zlib
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "app" / "src"
sys.path.insert(0, str(SRC))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")

HOME = Path(os.environ["AUDIT_HOME"])
HOME.mkdir(parents=True, exist_ok=True)
OUT = Path(__file__).resolve().parent


def _png(width: int, height: int, rgb: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + rgb * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def seed() -> None:
    """落一条会话：用户问了句话，助手交付 chart.png + report.md。"""
    from mvvm.models.chat_models import Message, TextPart, ToolUsePart
    from mvvm.services.chat_session_store import ChatSessionStore

    workspace = HOME / "ws"
    workspace.mkdir(parents=True, exist_ok=True)
    chart = workspace / "chart.png"
    chart.write_bytes(_png(96, 96, b"\x2f\xa3\xf7"))  # 蓝色 96x96，缩略图有真实像素
    report = workspace / "report.md"
    report.write_text("# 周报\n\n- 交付卡接通\n- 附件可见\n", encoding="utf-8")

    store = ChatSessionStore(HOME)
    store.ensure_session("chat-files-web")
    store.append_message("chat-files-web", Message(role="user", content="把周报和图表给我"))
    store.append_message(
        "chat-files-web",
        Message(
            role="assistant",
            content=[
                TextPart(text="都整理好了，见下方交付卡。"),
                ToolUsePart(
                    id="tu_present_1",
                    name="present_files",
                    input={"paths": [str(chart), str(report)]},
                ),
            ],
        ),
    )
    store.append_message(
        "chat-files-web",
        Message(
            role="user",
            content=[
                {
                    "type": "tool_result",
                    "toolUseId": "tu_present_1",
                    "content": "已交付 2 个文件，交付卡将在本轮回复结束后显示在回复末尾。",
                }
            ],
        ),
    )
    store.append_message(
        "chat-files-web", Message(role="assistant", content="需要我再补一版吗？")
    )
    # 边车：工具成功时写的就是这个形状（绝对路径、按 toolUseId）
    session = store.load_session("chat-files-web")
    session.delivered = {
        "tu_present_1": [str(chart), str(report)],
        "tu_script": [str(workspace / "run.sh")],
    }
    (workspace / "run.sh").write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    store.save("chat-files-web")
    print("== 会话文件 ==", store.session_path("chat-files-web"))
    payload = json.loads(store.session_path("chat-files-web").read_text(encoding="utf-8"))
    print("   delivered 边车 =", json.dumps(payload.get("delivered"), ensure_ascii=False))
    print("   chart.png 字节 =", chart.stat().st_size, " report.md 字节 =", report.stat().st_size)


def pump(app, seconds: float) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.02)


def js(app, view, code: str, timeout: float = 20.0):
    box: dict = {}
    view.page().runJavaScript(code, 0, lambda value: box.setdefault("v", value))
    end = time.monotonic() + timeout
    while time.monotonic() < end and "v" not in box:
        app.processEvents()
        time.sleep(0.02)
    return box.get("v")


def main() -> int:
    seed()

    from utils.qt_compat import QtWidgets

    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.settings_service import SettingsService
    from mvvm.views.web_shell_window import DevaWebWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    settings = SettingsService(HOME)
    personas = PersonaStore(HOME)
    personas.ensure_seeded()
    window = DevaWebWindow(
        settings=settings,
        personas=personas,
        store=ChatSessionStore(HOME),
        vault=SecretsVault(HOME),
    )
    window.show()
    pump(app, 9.0)

    print("== 打开会话 ==")
    print(
        js(
            app,
            window.view,
            """
            (() => {
              const els = Array.from(document.querySelectorAll('*'));
              for (const el of els) {
                const t = (el.innerText || '').trim();
                if (t.indexOf('把周报和图表给我') >= 0 && t.length < 40 && el.children.length <= 2) {
                  const row = el.closest('button') || el.closest('[role="button"]') || el.parentElement;
                  row.click();
                  return 'clicked ' + row.tagName;
                }
              }
              return 'not-found';
            })()
            """,
        )
    )
    pump(app, 4.0)

    print("== 交付卡 DOM ==")
    card = js(
        app,
        window.view,
        """
        (() => {
          const card = document.querySelector('.deliv');
          if (!card) return JSON.stringify({found: false});
          const rows = Array.from(card.querySelectorAll('.deliv__list > *')).map(function (row) {
            const img = row.querySelector('img');
            const path = (row.innerText || '').trim();
            return {
              text: path.replace(/\\s+/g, ' ').slice(0, 120),
              img: img ? {srcHead: (img.src || '').slice(0, 30), w: img.naturalWidth, h: img.naturalHeight} : null
            };
          });
          return JSON.stringify({found: true, text: (card.innerText || '').replace(/\\s+/g, ' ').slice(0, 300), rows: rows});
        })()
        """,
    )
    print(card)
    parsed = json.loads(card) if card else {"found": False}
    card_text = parsed.get("text", "")
    print("== 断言 ==")
    print("   卡片出现 =", parsed.get("found"))
    print("   不含 0 B =", "0 B" not in card_text)
    print("   含真实文件名 chart.png =", "chart.png" in card_text)
    print("   含真实文件名 report.md =", "report.md" in card_text)
    chart_size = (HOME / "ws" / "chart.png").stat().st_size
    report_size = (HOME / "ws" / "report.md").stat().st_size
    print("   含 chart.png 真实大小 %d B =" % chart_size, ("%d B" % chart_size) in card_text)
    print("   含 report.md 真实大小 %d B =" % report_size, ("%d B" % report_size) in card_text)

    print("== 缩略图（data URI 解码后的像素）==")
    for row in parsed.get("rows", []):
        print("   ", row["text"][:60], "->", row["img"])

    print("== 直接调桥：inspect（渲染层同一条通道）==")
    out = js(
        app,
        window.view,
        """
        (() => {
          window.__inspect = 'pending';
          window.deva.deliverables.inspect('chat-files-web', 'tu_present_1')
            .then(function (r) { window.__inspect = 'OK:' + JSON.stringify(r); })
            .catch(function (e) { window.__inspect = 'REJECT:' + (e && e.message); });
          return 'fired';
        })()
        """,
    )
    pump(app, 3.0)
    inspect = js(app, window.view, "String(window.__inspect)")
    print("   ", inspect)

    print("== 直接调桥：thumbnail / open / reveal ==")
    js(
        app,
        window.view,
        """
        (() => {
          window.__thumb = 'pending';
          window.__openGood = 'pending';
          window.__openScript = 'pending';
          window.__revealBad = 'pending';
          window.__revealGood = 'pending';
          window.deva.deliverables.thumbnail('chat-files-web', 'tu_present_1', 0)
            .then(function (u) { window.__thumb = 'OK:' + (u ? u.slice(0, 30) : String(u)); })
            .catch(function (e) { window.__thumb = 'REJECT:' + (e && e.message); });
          window.deva.deliverables.open('chat-files-web', 'tu_present_1', 1)
            .then(function (r) { window.__openGood = 'OK:' + JSON.stringify(r); })
            .catch(function (e) { window.__openGood = 'REJECT:' + (e && e.message); });
          // 边车里塞进来的脚本（工具确实可能交付它）：可在卡片上看到，但不许用默认应用打开
          window.deva.deliverables.open('chat-files-web', 'tu_script', 0)
            .then(function (r) { window.__openScript = 'OK:' + JSON.stringify(r); })
            .catch(function (e) { window.__openScript = 'REJECT:' + (e && e.message); });
          window.deva.deliverables.reveal('chat-files-web', 'tu_present_1', 99)
            .then(function (r) { window.__revealBad = 'OK:' + JSON.stringify(r); })
            .catch(function (e) { window.__revealBad = 'REJECT:' + (e && e.message); });
          window.deva.deliverables.reveal('chat-files-web', 'tu_present_1', 1)
            .then(function (r) { window.__revealGood = 'OK:' + JSON.stringify(r); })
            .catch(function (e) { window.__revealGood = 'REJECT:' + (e && e.message); });
          return 'fired';
        })()
        """,
    )
    pump(app, 3.5)
    print("   thumbnail =", js(app, window.view, "String(window.__thumb)"))
    print("   open(idx=1 report.md，白名单内) =", js(app, window.view, "String(window.__openGood)"))
    print("   open(tu_script 里的 run.sh，白名单外) =", js(app, window.view, "String(window.__openScript)"))
    print("   reveal(idx=99 越界) =", js(app, window.view, "String(window.__revealBad)"))
    print("   reveal(idx=1 report.md) =", js(app, window.view, "String(window.__revealGood)"))

    shot = OUT / "web-deliverables-live.png"
    window.grab().save(str(shot))
    print("== 截图 ==", shot, shot.exists())
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
