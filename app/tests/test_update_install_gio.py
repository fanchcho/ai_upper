"""F75：无 xdg-open 时用 GIO 默认应用真实打开安装包。"""
from __future__ import annotations
import os, stat, time
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


def test_install_update_uses_gio_handler(qapp, tmp_path, monkeypatch):
    from test_qml_shell import _bridge, text_stream
    import sys
    if not sys.platform.startswith("linux"):
        # GIO desktop files are Linux-only. Verify native URL dispatch elsewhere.
        import qml_shell
        opened = []
        monkeypatch.setattr(qml_shell.QtGui.QDesktopServices, "openUrl", lambda url: opened.append(url) or True)
        target = tmp_path / "installer.txt"
        target.write_text("installer\n", encoding="utf-8")
        bridge, _store, _host = _bridge(tmp_path, monkeypatch, text_stream("x"))
        assert bridge.installUpdate(str(target)) is True
        assert len(opened) == 1 and Path(opened[0].toLocalFile()) == target
        return
    data = tmp_path / "xdg"; (data / "applications").mkdir(parents=True)
    marker = tmp_path / "opened.txt"
    handler = tmp_path / "handler.sh"
    handler.write_text(f"#!/bin/sh\necho \"$1\" > {marker}\n", encoding="utf-8")
    handler.chmod(0o755)
    (data / "applications" / "test-open.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Test Open\n"
        f"Exec={handler} %f\nMimeType=text/plain;\nNoDisplay=true\nTerminal=false\n", encoding="utf-8")
    (data / "applications" / "mimeapps.list").write_text("[Default Applications]\ntext/plain=test-open.desktop\n", encoding="utf-8")
    target = tmp_path / "installer.txt"; target.write_text("installer\n", encoding="utf-8")
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setenv("XDG_DATA_DIRS", "/usr/share")
    bridge, _store, _host = _bridge(tmp_path, monkeypatch, text_stream("x"))
    assert bridge.installUpdate(str(target)) is True
    deadline = time.time() + 5
    while time.time() < deadline and not marker.exists():
        time.sleep(0.05)
    assert marker.exists() and str(target) in marker.read_text()
