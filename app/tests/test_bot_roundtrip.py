"""F63：本地 Telegram API 完整入站→主会话→出站往返（非公网）。"""
from __future__ import annotations
import json, os, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_telegram_roundtrip_local(qapp, tmp_path, monkeypatch):
    from test_qml_shell import _bridge, text_stream
    calls = {"send": [], "updates": 0}
    update = {"update_id": 1, "message": {"message_id": 7, "text": "hello bot", "chat": {"id": 99, "type": "private"}, "from": {"id": 99, "is_bot": False}}}
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("content-length", "0"))) or b"{}")
            if self.path.endswith("/getMe"):
                result = {"ok": True, "result": {"id": 42, "username": "fixture_bot", "first_name": "Fixture"}}
            elif self.path.endswith("/getUpdates"):
                calls["updates"] += 1
                result = {"ok": True, "result": [update] if calls["updates"] == 1 else []}
            elif self.path.endswith("/sendMessage"):
                calls["send"].append(body); result = {"ok": True, "result": {"message_id": 100}}
            else: result = {"ok": True, "result": True}
            raw = json.dumps(result).encode(); self.send_response(200); self.send_header("content-type", "application/json"); self.send_header("content-length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def log_message(self, *_a): pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), H)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        monkeypatch.setenv("AI_UPPER_TELEGRAM_API", f"http://127.0.0.1:{server.server_port}")
        bridge, store, host = _bridge(tmp_path, monkeypatch, text_stream("LOCAL_REPLY"))
        bot = {"id": "bot1", "platform": "telegram", "name": "Fixture", "enabled": True,
               "replyMode": "final", "scope": {"mode": "all", "personas": [], "sessions": []},
               "users": [{"id": "99", "chatId": "99", "name": "User"}], "bindings": {}, "settings": {}}
        bridge._settings.set_config({"remote": {"bots": [bot]}})
        from mvvm.services.secrets_vault import SecretsVault
        bridge._vault = SecretsVault(tmp_path / "home")
        bridge._vault.set_secret("remote:bot1:botToken", "123:abcdefghijklmnopqrstuvwx")
        ctrl = bridge.botsService(); assert ctrl.start(bot) == ""
        deadline = time.time() + 8
        while time.time() < deadline and not calls["send"]:
            bridge.tick(); qapp.processEvents(); time.sleep(.05)
        assert calls["send"], "outbound sendMessage not called"
        assert calls["send"][0]["chat_id"] == "99"
        assert "LOCAL_REPLY" in calls["send"][0]["text"]
        rows = store.list_sessions()
        remote = next((r for r in rows if r.id.startswith("remote-")), None)
        assert remote is not None
        session = store.load_session(remote.id)
        assert any("LOCAL_REPLY" in str(m.content) for m in session.messages)
        ctrl.close()
    finally:
        server.shutdown(); server.server_close(); thread.join()
