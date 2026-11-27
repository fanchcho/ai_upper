"""F67：从服务商拉取模型列表（provider:list-models）。"""
from __future__ import annotations

import json, os, sys, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest


def test_provider_models_returns_real_server_list(tmp_path, monkeypatch):
    from test_qml_shell import _bridge, text_stream

    seen = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("content-length", "0"))
            body = self.rfile.read(length) if length else b""
            seen.append((self.path, body))
            payload = json.dumps({"data": [{"id": "model-a"}, {"id": "model-b"}]}).encode()
            self.send_response(200); self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
        def do_GET(self):
            self.do_POST()
        def log_message(self, *_a): pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        bridge, _store, _host = _bridge(tmp_path, monkeypatch, text_stream("x"))
        base = f"http://127.0.0.1:{server.server_port}"
        bridge._settings.set_config({"models": {"providers": [{
            "id": "p1", "adapter": "anthropic", "apiHost": base,
            "enabled": True, "models": [{"id": "model-a", "enabled": True}]}]}})
        from mvvm.services.secrets_vault import SecretsVault
        SecretsVault(tmp_path).set_secret("p1", "sk-test")
        result = bridge.providerModels("p1")
        assert result["ok"] is True, result
        assert result["models"] == ["model-a", "model-b"]
        assert seen and seen[0][0].endswith("/v1/models")
    finally:
        server.shutdown(); server.server_close(); thread.join()
