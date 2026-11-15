"""§1.13 四项实跑：真窗口 + 真渲染层 + 真 provider，一次跑一个场景。

为什么单独成脚本而不是写成 pytest：这四项要的是**真实环境下的原始输出**（真实代理、
真实模型吐出的流），把结果原样贴进 `docs/BUILD-PROGRESS.md` §1.13。用 pytest 断言成败，
失败时反而看不到中间态。脚本只打印事实（`EVIDENCE {...}` 一行一条），判定留给读者。

四个场景：
- `model`  ：建会话 → 首发（模型 A）→ `chat:set-model` 换成 B → 再发一轮，抓请求体里的
             model 字段与落盘会话的 `model`；
- `tools`  ：同一会话里让模型读工作区内文件（放行 → 真实读到内容），再读工作区外文件
             （判定层放行、执行期守卫拒绝，与 Deva 的零弹框语义一致）；
- `abort`  ：发一个长输出请求，收到正文后 `chat:abort`，看 done.stopReason 与半截正文落盘；
- `reload` ：**新进程**读同一个 DEVA_HOME，`chat:load-session` 后打印历史条数与模型。

用法（在 Xvfb 里）：
    xvfb-run -a -s "-screen 0 1400x900x24" .venv/bin/python scripts/parity/live_scenarios.py \
        --scenario model --home /tmp/live-home --workspace /tmp/live-work --shots out/e2e-live

环境：`ANTHROPIC_BASE_URL` / `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` 由本机代理提供；
密钥只从环境读取后写进这次运行的临时密钥库，**不打印、不打进日志**。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")
os.environ.setdefault("QT_QPA_PLATFORM", "xcb" if os.environ.get("DISPLAY") else "offscreen")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app" / "src"))

PRIMARY = os.environ.get("ANTHROPIC_MODEL") or ""
ALT = "alt-model-7b"  # 代理不校验模型名；用别名钉住「请求体里的 model 真的换了」
BASE = os.environ.get("ANTHROPIC_BASE_URL") or ""
KEY = os.environ.get("ANTHROPIC_API_KEY") or ""


def evidence(tag: str, **fields: Any) -> None:
    print("EVIDENCE " + json.dumps({"tag": tag, **fields}, ensure_ascii=False), flush=True)


# ── 请求体记录：只记事实，不改行为 ────────────────────────────────────────
class RecordingTransport:
    """包住真实 httpx 传输，记录每次请求体里的 model / 工具名 / 消息条数。

    这不是替身：请求照样打在真代理上、响应照样逐块喂给真解析器，只是旁路留一份请求体。
    没有它，「切模型后下一轮真的用了新模型」就只能靠界面文案，那不是证据。
    """

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.calls: list[dict[str, Any]] = []

    async def post(self, url: str, *, headers: Any, body: bytes, cancel: Any = None):
        try:
            parsed = json.loads(body)
            # 只记「打到 /v1/messages」这一事实：完整 URL 里有本机代理的会话路径，
            # 属于运行时凭据的一部分，不进日志、不进文档。
            self.calls.append(
                {
                    "path": "/".join(url.split("/")[-2:]),
                    "model": parsed.get("model"),
                    "stream": bool(parsed.get("stream")),
                    "messages": len(parsed.get("messages") or []),
                    "tools": [t.get("name") for t in (parsed.get("tools") or [])],
                }
            )
            evidence("request", **self.calls[-1])
        except Exception as exc:  # noqa: BLE001 - 记录失败不该影响请求
            evidence("request-parse-failed", error=str(exc))
        return await self.inner.post(url, headers=headers, body=body, cancel=cancel)


def _install_recorder() -> RecordingTransport | None:
    from mvvm.services import provider_setup
    from mvvm.services.transport import HttpxTransport

    recorder = RecordingTransport(HttpxTransport())

    def build(proxy_url=None):  # noqa: ANN001 - 与 build_transport 同签名
        recorder.inner = HttpxTransport(proxy_url)
        return recorder

    provider_setup.build_transport = build
    return recorder


# ── 窗口与页面驱动 ────────────────────────────────────────────────────────
def _qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _wait(app, predicate: Callable[[], Any], timeout: float, step: float = 0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        value = predicate()
        if value:
            return value
        time.sleep(step)
    return predicate()


def _run_js(window, code: str, timeout: float = 5.0):
    app = _qapp()
    box: dict = {}
    window.view.page().runJavaScript(code, lambda value: box.setdefault("value", value))
    _wait(app, lambda: "value" in box, timeout)
    return box.get("value")


def _wait_send(window, name: str, timeout: float = 15.0):
    """等页面侧 `window.__live.*` 出现某个键（send 的 Promise 结果 / 出错）。"""
    raw = _wait(_qapp(), lambda: _run_js(window, f"window.__live.{name} ? JSON.stringify(window.__live.{name}) : ''"), timeout)
    return json.loads(raw) if raw else None


def _wait_done(window, timeout: float = 120.0) -> list[dict[str, Any]]:
    def done_seen():
        raw = _run_js(window, "JSON.stringify(window.__live.events || [])")
        events = json.loads(raw or "[]")
        return events if any(e["event"]["type"] == "done" for e in events) else None

    return _wait(_qapp(), done_seen, timeout, step=0.1) or []


def _reset_events(window) -> None:
    _run_js(window, "window.__live.events = []; 'ok'")


def _send(window, session_id: str, text: str, *, model_ref: str, extra: str = "") -> dict | None:
    _run_js(
        window,
        """
        window.__live.send = null;
        window.deva.chat.send({
          sessionId: %s,
          text: %s,
          model: {adapter: 'anthropic', providerId: 'e2e', baseURL: %s, model: %s},
          workspaceRoot: %s,
          modelRef: %s,
          effort: 'default'%s
        }).then(function (r) { window.__live.send = {ok: true, result: r}; })
          .catch(function (e) { window.__live.send = {ok: false, error: String(e && e.message || e)}; });
        'started'
        """
        % (
            json.dumps(session_id),
            json.dumps(text),
            json.dumps(BASE),
            json.dumps(model_ref.split(":", 1)[1]),
            json.dumps(WORKSPACE or "null"),
            json.dumps(model_ref),
            extra,
        ),
    )
    return _wait_send(window, "send")


def _call(window, channel_call: str) -> Any:
    """在页面里跑一个 window.deva.* 调用并同步取回结果（渲染层同一入口，不经 Python 直调）。"""
    _run_js(
        window,
        "window.__live.call = null; Promise.resolve(%s)"
        ".then(function (r) { window.__live.call = {ok: true, result: r}; })"
        ".catch(function (e) { window.__live.call = {ok: false, error: String(e && e.message || e)}; }); 'go'"
        % channel_call,
    )
    return _wait_send(window, "call")


SCREENSHOT_DIR: Path | None = None
WORKSPACE: str | None = None


def _shot(window, name: str) -> None:
    if SCREENSHOT_DIR is None:
        return
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    target = SCREENSHOT_DIR / f"{name}.png"
    if os.environ.get("DISPLAY"):
        subprocess.run(["import", "-window", "root", str(target)], check=False)
    else:
        window.grab().save(str(target))
    evidence("screenshot", path=str(target.resolve()))


def _open_first_session(window) -> None:
    """点会话列表第一行（新建的会话排在最前）。

    渲染层的 `chat:create-session` 只落盘、不切换选中项；不点一下的话截图还是上一段对话，
    「中断后的界面」就成了空口无凭。Xvfb 里窗口固定在 (0,0)，首行坐标是稳定值。
    """
    if not os.environ.get("DISPLAY"):
        return
    subprocess.run(["xdotool", "mousemove", "160", "80", "click", "1"], check=False)
    _wait(_qapp(), lambda: False, 1.5)  # 等界面切换并稳定


def _open_model_menu(window) -> None:
    """点输入框里的模型 chip，让弹层真的渲染出来（按钮在 DOM 里，弹层才是证据）。"""
    ok = _run_js(
        window,
        "(function () { var b = document.querySelector('.model-pick .chip');"
        " if (!b) return false; b.click(); return true; })()",
    )
    if not ok and os.environ.get("DISPLAY"):
        subprocess.run(["xdotool", "mousemove", "963", "775", "click", "1"], check=False)
    _wait(_qapp(), lambda: _run_js(window, "!!document.querySelector('.model-pick__item')"), 5.0)
    _wait(_qapp(), lambda: False, 0.3)


def _close_model_menu(window) -> None:
    _run_js(
        window,
        "(function () { var b = document.querySelector('.model-pick__backdrop');"
        " if (!b) return false; b.click(); return true; })()",
    )
    _wait(_qapp(), lambda: False, 0.3)


def _click_send_button(window) -> bool:
    """点输入框右侧的发送按钮（真界面的那条路，不走 JS 直调通道）。"""
    return bool(
        _run_js(
            window,
            "(function () { var b = document.querySelector('button.cf-send');"
            " if (!b || b.disabled) return false; b.click(); return true; })()",
        )
    )


def _type_and_send(window, text: str, *, use_button: bool = False) -> bool:
    """往输入框里写文本并按渲染层的路径提交。

    `use_button` 时用真按钮提交：只有这条路能证明「输入框 → 发送按钮 → chat:send」整条链通，
    JS 直调通道证明的是桥，不是界面。输入框是 Lexical 富文本，直接设 `textContent` 会被
    编辑器覆盖，所以走 `execCommand('insertText')` 让编辑器自己接住这次输入。
    """
    _run_js(
        window,
        "(function () {"
        " var box = document.querySelector('[contenteditable=true]');"
        " if (!box) return false;"
        " box.focus();"
        " var sel = window.getSelection(); var range = document.createRange();"
        " range.selectNodeContents(box); range.collapse(false);"
        " sel.removeAllRanges(); sel.addRange(range);"
        " document.execCommand('insertText', false, %s);"
        " return true; })()" % json.dumps(text),
    )
    if not use_button:
        return True
    _wait(_qapp(), lambda: _run_js(window, "!document.querySelector('button.cf-send')?.disabled"), 3.0)
    return _click_send_button(window)


def _open_window(home: Path):
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.settings_service import SettingsService
    from mvvm.views.web_shell_window import DevaWebWindow

    app = _qapp()
    settings = SettingsService(home)
    vault = SecretsVault(home, backend="file")
    vault.set_secret("e2e", KEY)
    personas = PersonaStore(home)
    personas.ensure_seeded()
    win = DevaWebWindow(
        settings=settings,
        personas=personas,
        store=ChatSessionStore(home),
        vault=vault,
    )
    win.resize(1280, 820)
    win.show()
    if os.environ.get("DISPLAY"):
        subprocess.run(
            ["xdotool", "search", "--name", "^Deva$"], capture_output=True, text=True, check=False
        )
        found = subprocess.run(
            ["xdotool", "search", "--class", "python3"], capture_output=True, text=True, check=False
        ).stdout.split()
        if found:
            subprocess.run(["xdotool", "windowmove", found[0], "0", "0"], check=False)
            subprocess.run(["xdotool", "windowsize", found[0], "1280", "820"], check=False)

    loaded: dict = {}
    win.view.loadFinished.connect(lambda ok: loaded.setdefault("ok", ok))
    assert _wait(app, lambda: loaded.get("ok") is True, 30.0), "渲染层没有加载完成"
    _wait(app, lambda: _run_js(win, "!!(window.deva && window.deva.chat)"), 10.0)
    _run_js(
        win,
        "window.__live = {events: []};"
        "window.deva.chat.onEvent(function (p) { window.__live.events.push(p); }); 'ok'",
    )
    return app, win


def _pick_model(window, label: str) -> dict[str, Any]:
    """点开模型菜单、点中目标模型、等菜单收起，并回报屏幕上的 chip 文案。

    这条路径是渲染层自己的 `setSessionModel` → `chat:set-model` → `refreshSessions()`；
    比直接调 `window.deva.chat.setModel` 多证一步：界面上的点击真的能改掉会话模型。
    """
    _open_model_menu(window)
    clicked = _run_js(
        window,
        "(function () { var items = Array.from(document.querySelectorAll('.model-pick__item'));"
        " var hit = items.find(function (b) { return b.textContent.trim() === %s; });"
        " if (!hit) return false; hit.click(); return true; })()" % json.dumps(label),
    )
    _wait(_qapp(), lambda: _run_js(window, "!document.querySelector('.model-pick__item')"), 5.0)
    _wait(_qapp(), lambda: False, 1.5)
    return {
        "clicked": bool(clicked),
        "label": _run_js(window, "(document.querySelector('.model-pick .chip__label')||{}).textContent || ''"),
    }


# ── 场景 ──────────────────────────────────────────────────────────────────
def scenario_model(window) -> None:
    sid = "live-model"
    _run_js(window, "window.__live.create = null;")
    created = _call(window, "window.deva.chat.createSession({sessionId: %s})" % json.dumps(sid))
    evidence("create-session", result=created)
    _open_first_session(window)

    _reset_events(window)
    first = _send(window, sid, "只回复两个字：甲一", model_ref="e2e:" + PRIMARY)
    evidence("send-1", result=first)
    _wait_done(window)
    _shot(window, "01-model-before")

    # ① 界面切模型：点输入框里的 chip → 弹层 → 点另一项。走的是渲染层的 setSessionModel。
    picked = _pick_model(window, ALT)
    evidence("picker-switch", **picked)
    _reset_events(window)
    second = _send(window, sid, "只回复两个字：乙二", model_ref="e2e:" + ALT)
    evidence("send-2", result=second)
    _wait_done(window)
    _wait(_qapp(), lambda: False, 2.0)  # 等渲染层把最后一段正文与「正在输出」收尾
    evidence(
        "composer-picker",
        label=_run_js(window, "(document.querySelector('.model-pick .chip__label')||{}).textContent || ''"),
    )
    _shot(window, "02-model-after")

    # ② 再从输入框打字 + 点发送按钮：渲染层自己的 submit → chat:send，界面那条路。
    _reset_events(window)
    typed = _type_and_send(window, "只回复两个字：丙三", use_button=True)
    evidence("ui-send", clicked=typed)
    if typed:
        ui_events = _wait_done(window)
        ui_done = [e["event"] for e in ui_events if e["event"]["type"] == "done"]
        ui_text = "".join(
            e["event"]["text"] for e in ui_events if e["event"]["type"] == "text_delta"
        )
        evidence("ui-send-result", done=ui_done, delta_chars=len(ui_text), text=ui_text[:40])
        _wait(_qapp(), lambda: False, 1.5)
        _shot(window, "02c-ui-send")
    stored = json.loads(
        (Path(os.environ["DEVA_HOME"]) / "data" / "chats" / f"{sid}.json").read_text("utf-8")
    )
    evidence(
        "session-file",
        model=stored.get("model"),
        messages=len(stored.get("messages") or []),
        roles=[m.get("role") for m in stored.get("messages") or []],
    )


def scenario_tools(window) -> None:
    sid = "live-tools"
    note = Path(WORKSPACE) / "note.txt"
    note.write_text("live-run-note-42\n", encoding="utf-8")
    _call(window, "window.deva.chat.createSession({sessionId: %s})" % json.dumps(sid))
    _open_first_session(window)

    # ① 工作区内：判定放行 → 执行期守卫也在根内 → 工具真的读到内容
    _reset_events(window)
    _send(
        window,
        sid,
        "请调用 read_file 工具读取绝对路径 %s，然后只回复文件里的那一行内容。" % note,
        model_ref="e2e:" + PRIMARY,
        extra=", focusRoot: %s" % json.dumps(str(Path(WORKSPACE))),
    )
    events = _wait_done(window)
    _summarise_tools(events, label="inside")
    _shot(window, "03-tool-inside")

    # ② 工作区外：Deva 语义是零弹框全放行；本工程在执行期由 WorkspaceGuard 拒绝
    _reset_events(window)
    _send(
        window,
        sid,
        "请调用 read_file 工具读取绝对路径 /etc/hostname，然后告诉我结果。",
        model_ref="e2e:" + PRIMARY,
        extra=", focusRoot: %s" % json.dumps(str(Path(WORKSPACE))),
    )
    events = _wait_done(window)
    _summarise_tools(events, label="outside")
    _shot(window, "04-tool-outside")

    stored = json.loads(
        (Path(os.environ["DEVA_HOME"]) / "data" / "chats" / f"{sid}.json").read_text("utf-8")
    )
    tool_parts = [
        part
        for message in stored.get("messages") or []
        for part in message.get("content") or []
        if part.get("type") == "tool_use"
    ]
    evidence(
        "tool-uses-in-store",
        count=len(tool_parts),
        names=[p.get("name") for p in tool_parts],
        inputs=[p.get("input") for p in tool_parts],
    )


def _summarise_tools(events: list[dict[str, Any]], *, label: str) -> None:
    calls = [e["event"] for e in events if e["event"]["type"] == "tool_call"]
    results = [e["event"] for e in events if e["event"]["type"] == "tool_result"]
    evidence(
        f"tool-{label}",
        calls=calls,
        results=results,
        done=[e["event"] for e in events if e["event"]["type"] == "done"],
    )


def scenario_abort(window) -> None:
    sid = "live-abort"
    _call(window, "window.deva.chat.createSession({sessionId: %s})" % json.dumps(sid))
    _open_first_session(window)
    _reset_events(window)
    sent = _send(
        window,
        sid,
        "请从 1 开始逐行输出数字，每行一个，一直输出到 500，不要省略。",
        model_ref="e2e:" + PRIMARY,
    )
    evidence("send", result=sent)
    turn_id = (sent or {}).get("result", {}).get("turnId")
    evidence("turn-id", turnId=turn_id)

    # 等正文真的开始流出来再停：停得太早只能测到「请求还没发」。
    def deltas_seen():
        raw = _run_js(
            window,
            "JSON.stringify((window.__live.events || []).filter(function (e) "
            "{ return e.event.type === 'text_delta'; }).slice(0, 3).map(function (e) "
            "{ return e.event.text; }))",
        )
        values = json.loads(raw or "[]")
        # 空数组是「还没开始流」，不是证据：必须等到正文真的吐出来再停。
        return raw if values else None

    first_delta = _wait(_qapp(), deltas_seen, 120.0, step=0.05)
    evidence("first-deltas", deltas=json.loads(first_delta or "[]"))
    _shot(window, "05-abort-streaming")

    aborted = _call(window, "window.deva.chat.abort(%s)" % json.dumps(turn_id))
    evidence("abort-call", result=aborted)

    events = _wait_done(window, timeout=60.0)
    done = [e["event"] for e in events if e["event"]["type"] == "done"]
    text = "".join(e["event"]["text"] for e in events if e["event"]["type"] == "text_delta")
    evidence(
        "abort-done",
        done=done,
        delta_chars=len(text),
        tail_text=text[-80:],
    )

    stored = json.loads(
        (Path(os.environ["DEVA_HOME"]) / "data" / "chats" / f"{sid}.json").read_text("utf-8")
    )
    roles = [m.get("role") for m in stored.get("messages") or []]
    last = (stored.get("messages") or [{}])[-1]
    last_text = "".join(
        part.get("text") or "" for part in last.get("content") or [] if part.get("type") == "text"
    )
    evidence("abort-store", roles=roles, last_role=last.get("role"), last_chars=len(last_text))
    _shot(window, "06-abort-just-done")
    # done 之后界面要把「正在输出」收掉：再等 2 秒取一张，能区分「收了」和「一直转」。
    _wait(_qapp(), lambda: False, 2.0)
    status = _run_js(
        window,
        "JSON.stringify({responding: /Responding/.test(document.body.innerText),"
        " stopped: /已停止|Stopped/.test(document.body.innerText)})",
    )
    evidence("abort-ui-after-2s", state=json.loads(status or "{}"))
    _shot(window, "07-abort-settled")


def scenario_reload(window) -> None:
    chats = Path(os.environ["DEVA_HOME"]) / "data" / "chats"
    for sid in ("live-model", "live-tools", "live-abort"):
        loaded = _call(window, "window.deva.chat.loadSession(%s)" % json.dumps(sid))
        if not loaded or not loaded.get("ok"):
            evidence("reload", session=sid, result=loaded, ok=False)
            continue
        messages = loaded["result"]
        evidence(
            "reload",
            session=sid,
            ok=True,
            count=len(messages),
            roles=[m.get("role") for m in messages],
            first_text=_text_of(messages[0]) if messages else "",
            last_text=_text_of(messages[-1])[-60:] if messages else "",
        )
    index = json.loads((chats / "_index.json").read_text("utf-8"))
    evidence("reload-index", ids=sorted(entry.get("id") for entry in index))
    stored = json.loads((chats / "live-model.json").read_text("utf-8"))
    evidence("reload-model", model=stored.get("model"))
    _shot(window, "08-reload")


def _text_of(message: dict[str, Any]) -> str:
    """`chat:load-session` 回的是 `DisplayMessage`：正文在 `text`（user）或 `blocks[].text`（assistant）。"""
    if message.get("role") == "user":
        return message.get("text") or ""
    return "".join(
        block.get("text") or "" for block in message.get("blocks") or [] if block.get("kind") == "text"
    )


# ── 入口 ──────────────────────────────────────────────────────────────────
def main(argv: list[str]) -> int:
    global SCREENSHOT_DIR, WORKSPACE
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", required=True, choices=("model", "tools", "abort", "reload"))
    parser.add_argument("--home", required=True, help="DEVA_HOME（本次实跑的临时家目录）")
    parser.add_argument("--workspace", help="受信工作区（tools 场景必填，其余可省）")
    parser.add_argument("--shots", help="截图输出目录")
    args = parser.parse_args(argv[1:])

    if not (BASE and KEY and PRIMARY):
        print("缺少 ANTHROPIC_BASE_URL / ANTHROPIC_API_KEY / ANTHROPIC_MODEL，实跑无法进行", file=sys.stderr)
        return 2
    home = Path(args.home).resolve()
    home.mkdir(parents=True, exist_ok=True)
    os.environ["DEVA_HOME"] = str(home)
    os.environ["DEVA_SECRETS_BACKEND"] = "file"
    WORKSPACE = str(Path(args.workspace).resolve()) if args.workspace else None
    if WORKSPACE:
        os.environ["DEVA_APP_WORKSPACE"] = WORKSPACE
        Path(WORKSPACE).mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR = Path(args.shots).resolve() if args.shots else None

    config_path = home / "config.json"
    if not config_path.exists():
        config = {
            "models": {
                "activeModelId": "e2e:" + PRIMARY,
                "providers": [
                    {
                        "id": "e2e",
                        "adapter": "anthropic",
                        "apiHost": BASE,
                        "enabled": True,
                        "models": [
                            {"id": PRIMARY, "enabled": True},
                            {"id": ALT, "enabled": True},
                        ],
                    }
                ],
                "activeEffort": "default",
            },
            "theme": "light",
        }
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

    recorder = _install_recorder()
    app, window = _open_window(home)
    try:
        {"model": scenario_model, "tools": scenario_tools, "abort": scenario_abort,
         "reload": scenario_reload}[args.scenario](window)
        if recorder is not None:
            evidence("requests-total", count=len(recorder.calls))
    finally:
        window.view.stop()
        window.close()
        app.processEvents()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
