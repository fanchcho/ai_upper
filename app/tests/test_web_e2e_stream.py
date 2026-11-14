"""Web 承载窗口的端到端实跑：真 QtWebEngine + 真渲染层 + 真桥 + 真 provider。

和 `test_web_chat_write.py` 的区别：那边的「渲染层」是测试直接调桥；这里是真的页面，
真的 `window.deva.chat.send(...)` 从 JS 里发出来，事件走 `window.__devaEmit` 回到页面，
反馈从 DOM 里读回来。用来回答「输入框发一条消息能不能拿到流式回复」这个问题。

provider 是**真的**：`DEVA_E2E_PROVIDER=1` 时按环境里的 `ANTHROPIC_BASE_URL` /
`ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` 配一个 anthropic 适配器（本机的 Claude Code 代理）。
没设这个变量、或环境里缺这三项时整文件 skip，**skip 原因写清**——不假装跑过。

用法：`cd app && ../.venv/bin/python -m pytest -q tests/test_web_e2e_stream.py -s`
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")
os.environ.setdefault("QT_QPA_PLATFORM", "xcb" if os.environ.get("DISPLAY") else "offscreen")

pytest.importorskip("PySide6.QtWebEngineWidgets", reason="该安装没有 QtWebEngineWidgets")

_PROVIDER_ENV = os.environ.get("DEVA_E2E_PROVIDER", "").strip() == "1"
_BASE_URL = os.environ.get("DEVA_E2E_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL") or ""
_API_KEY = os.environ.get("DEVA_E2E_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or ""
_MODEL = os.environ.get("DEVA_E2E_MODEL") or os.environ.get("ANTHROPIC_MODEL") or ""

pytestmark = pytest.mark.skipif(
    not (_PROVIDER_ENV and _BASE_URL and _API_KEY and _MODEL),
    reason=(
        "端到端实跑需要真 provider：设 DEVA_E2E_PROVIDER=1 并提供 "
        "ANTHROPIC_BASE_URL / ANTHROPIC_API_KEY / ANTHROPIC_MODEL（或 DEVA_E2E_* 同名变量）"
    ),
)


def _wait(app, predicate, timeout: float, step: float = 0.05):
    """跑 Qt 事件循环直到 predicate 成立或超时（页面脚本、信号都靠事件循环推进）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.processEvents()
        value = predicate()
        if value:
            return value
        time.sleep(step)
    return predicate()


def _run_js(window, code: str, timeout: float = 5.0):
    """在页面里跑一段 JS 并把结果同步取回（runJavaScript 是异步回调）。"""
    app = _qapp()
    box: dict = {}

    def done(value):
        box["value"] = value

    window.view.page().runJavaScript(code, done)
    _wait(app, lambda: "value" in box, timeout)
    return box.get("value")


def _qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _make_home(tmp_path: Path) -> Path:
    home = tmp_path / "e2e-home"
    home.mkdir(parents=True, exist_ok=True)
    config = {
        "models": {
            "activeModelId": "e2e:primary",
            "providers": [
                {
                    "id": "e2e",
                    "adapter": "anthropic",
                    "apiHost": _BASE_URL,
                    "enabled": True,
                    "models": [{"id": _MODEL, "enabled": True, "contextWindow": 128000}],
                }
            ],
            "activeEffort": "default",
        },
        "theme": "light",
    }
    (home / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return home


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.settings_service import SettingsService
    from mvvm.views.web_shell_window import DevaWebWindow

    app = _qapp()
    home = _make_home(tmp_path_factory.mktemp("e2e"))
    settings = SettingsService(home)
    vault = SecretsVault(home, backend="file")
    vault.set_secret("e2e", _API_KEY)
    personas = PersonaStore(home)
    personas.ensure_seeded()
    win = DevaWebWindow(
        settings=settings, personas=personas, store=ChatSessionStore(home), vault=vault
    )
    win.resize(1280, 820)
    win.show()

    loaded: dict = {}
    win.view.loadFinished.connect(lambda ok: loaded.setdefault("ok", ok))
    assert _wait(app, lambda: loaded.get("ok") is True, 30.0), "渲染层没有加载完成"
    # 页面挂载后渲染层自己会拉一次配置与会话列表；等它把首帧画完。
    _wait(app, lambda: _run_js(win, "!!(window.deva && window.deva.chat)"), 10.0)
    yield win
    win.view.stop()
    win.close()


def test_chat_send_from_page_streams_reply(window):
    """在页面里发一条消息：turn_start → text_delta… → done，正文出现在 DOM 里。"""
    sid = "e2e-send"
    result = _run_js(
        window,
        """
        window.__e2eEvents = [];
        window.deva.chat.onEvent(function (payload) {
          window.__e2eEvents.push(payload);
        });
        window.deva.chat.send({
          sessionId: %s,
          text: '只回复两个字：收到',
          model: {adapter: 'anthropic', providerId: 'e2e', baseURL: %s, model: %s},
          workspaceRoot: null,
          modelRef: 'e2e:%s',
          effort: 'default'
        }).then(function (r) { window.__e2eSend = {ok: true, result: r}; })
          .catch(function (e) { window.__e2eSend = {ok: false, error: String(e && e.message || e)}; });
        'started'
        """
        % (json.dumps(sid), json.dumps(_BASE_URL), json.dumps(_MODEL), _MODEL),
    )
    assert result == "started"

    app = _qapp()
    assert _wait(
        app,
        lambda: _run_js(window, "window.__e2eSend ? JSON.stringify(window.__e2eSend) : ''"),
        15.0,
    )
    send = json.loads(_run_js(window, "JSON.stringify(window.__e2eSend)"))
    assert send["ok"] is True, send
    assert send["result"]["turnId"]

    def done_seen():
        raw = _run_js(window, "JSON.stringify(window.__e2eEvents || [])")
        events = json.loads(raw or "[]")
        return events if any(e["event"]["type"] == "done" for e in events) else None

    events = _wait(app, done_seen, 120.0, step=0.1)
    assert events, "60 秒内没有收到 done 事件"

    types = [e["event"]["type"] for e in events]
    assert types[0] == "turn_start"
    assert "text_delta" in types
    assert types[-1] == "done"
    payload = events[-1]["event"]
    assert payload["stopReason"] == "end_turn"

    text = "".join(e["event"]["text"] for e in events if e["event"]["type"] == "text_delta")
    assert "收到" in text, text

    # 正文真的进了页面 DOM（不是只在事件里转了一圈）。
    body = _run_js(window, "document.body.innerText")
    assert "收到" in (body or ""), "回复没有渲染到页面上"
