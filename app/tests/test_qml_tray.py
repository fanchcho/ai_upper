"""托盘/通知：无托盘平台必须打印真实不可用原因，不伪造成功（deva index.ts:235-272）。"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application


def test_tray_reports_offscreen_unavailable(qapp, capsys):
    from mvvm.services.tray import TrayController

    tray = TrayController(qapp, window=None)
    assert tray.install() is False
    err = capsys.readouterr().err
    assert "TRAY UNAVAILABLE" in err
    assert "isSystemTrayAvailable=False" in err


def test_close_to_tray_setting_is_read_from_config(tmp_path, monkeypatch):
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.settings_service import SettingsService
    from mvvm.services.skill_store import SkillStore
    from mvvm.services.workspace_guard import WorkspaceGuard
    from mvvm.webui.assembly import build_chat_host
    from qml_shell import ShellBridge

    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    settings = SettingsService(tmp_path)
    host, _ = build_chat_host(settings=settings, vault=SecretsVault(tmp_path),
                              store=ChatSessionStore(tmp_path), guard=WorkspaceGuard(),
                              home=tmp_path, emit=lambda p: None,
                              emit_sessions_changed=lambda: None)
    bridge = ShellBridge(host=host, store=ChatSessionStore(tmp_path), plain=True,
                         settings=settings, skills=SkillStore(tmp_path))
    assert bridge.closeToTray() is False
    settings.set_config({"closeToTray": True})
    assert bridge.closeToTray() is True
    settings.set_config({"closeToTray": False})
    assert bridge.closeToTray() is False


def test_turn_notification_uses_injected_notifier_when_window_unfocused(tmp_path, monkeypatch):
    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.settings_service import SettingsService
    from mvvm.services.skill_store import SkillStore
    from mvvm.services.workspace_guard import WorkspaceGuard
    from mvvm.webui.assembly import build_chat_host
    from qml_shell import ShellBridge

    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    home = tmp_path
    settings = SettingsService(home)
    store = ChatSessionStore(home)
    store.ensure_session("s-1")
    session = store.load_session("s-1"); session.title = "后台会话"; store.save("s-1")
    host, _ = build_chat_host(settings=settings, vault=SecretsVault(home), store=store,
                              guard=WorkspaceGuard(), home=home, emit=lambda p: None,
                              emit_sessions_changed=lambda: None)
    bridge = ShellBridge(host=host, store=store, plain=True, settings=settings,
                         skills=SkillStore(home))
    calls = []
    bridge.set_notifier(lambda title, body: calls.append((title, body)) or True)
    bridge._window = object()
    bridge._notify_turn("s-1", "", error=False)
    assert calls == [("后台会话", "回复已完成")]
