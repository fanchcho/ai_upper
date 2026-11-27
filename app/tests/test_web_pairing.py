"""F62-F63：Web 安全配对本地入口（真实 HTTP 页面与一次性票据）。"""
from __future__ import annotations
import json, os, urllib.request
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


class Settings:
    def __init__(self, path):
        self.path = Path(path) / "settings.json"
        self.data = {"remote": {"bots": []}}
    def get(self, key, default=None):
        return self.data.get(key, default)
    def set_config(self, patch):
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(self.data.get(key), dict):
                self.data[key].update(value)
            else:
                self.data[key] = value


def test_web_pair_ticket_serves_local_page(qapp, tmp_path):
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.remote_bots import RemoteBots
    from PySide6.QtCore import QObject
    class Shell(QObject):
        def __init__(self):
            super().__init__()
            self._settings = Settings(tmp_path)
            self._vault = SecretsVault(tmp_path)
    shell = Shell()
    controller = RemoteBots(shell)
    try:
        url = controller.webPairTicket()
        assert url.startswith("http://127.0.0.1:")
        page = urllib.request.urlopen(url.split("#")[0], timeout=5).read().decode()
        assert "配对" in page or "subscribe" in page.lower()
        assert "#" in url and "secret" in url
        rows = controller.list()
        assert any(b["platform"] == "web" for b in rows)
        assert shell._settings.get("remote")["bots"]
    finally:
        controller.close()
