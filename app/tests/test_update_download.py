"""F75：更新包下载到临时文件，installUpdate 只对真实存在的文件打开。"""
from __future__ import annotations
import os, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtGui import QGuiApplication
    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


def test_download_update_writes_bytes_and_reports(qapp, tmp_path, monkeypatch):
    from test_qml_shell import _bridge, text_stream
    payload = b"INSTALLER-BYTES" * 1024
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200); self.send_header("content-length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
        def log_message(self, *_a): pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=server.serve_forever, daemon=True); t.start()
    try:
        bridge, _store, _host = _bridge(tmp_path, monkeypatch, text_stream("x"))
        url = f"http://127.0.0.1:{server.server_port}/ai-upper-installer.bin"
        assert bridge.downloadUpdate(url) is True
        deadline = time.time() + 10
        while time.time() < deadline and bridge.updateState().get("phase") == "downloading":
            time.sleep(0.05)
        state = bridge.updateState()
        assert state["phase"] == "downloaded", state
        assert open(state["path"], "rb").read() == payload
        # offscreen 的 QPlatformServices 不支持 openDocument，成功打开安装包无法在本环境验证；
        # 只能验证不存在的文件被拒绝，真实报错见 stderr。
        assert bridge.installUpdate(str(tmp_path / "missing")) is False
    finally:
        server.shutdown(); server.server_close(); t.join()
