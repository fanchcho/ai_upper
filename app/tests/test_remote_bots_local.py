"""F62-F63：机器人本地端点协议往返（真实 HTTP 请求/响应）。"""
from __future__ import annotations
import json, os, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_telegram_protocol_against_local_endpoint(monkeypatch):
    from mvvm.services.remote_bots import telegram
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("content-length", "0")))
            seen.append((self.path, body.decode()))
            payload = {"ok": True, "result": {"id": 42, "username": "fixture_bot", "first_name": "Fixture"}}
            raw = json.dumps(payload).encode()
            self.send_response(200); self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def log_message(self, *_a): pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        monkeypatch.setenv("AI_UPPER_TELEGRAM_API", f"http://127.0.0.1:{server.server_port}")
        result = telegram("123:abcdefghijklmnopqrstuvwx", "getMe", {})
        assert result["username"] == "fixture_bot"
        assert seen and "/bottoken" not in seen[0][0].lower()
        assert "/getMe".lower() in seen[0][0].lower()
    finally:
        server.shutdown(); server.server_close(); thread.join()
