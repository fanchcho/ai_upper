"""F88：pin 会话在缓存淘汰中不被移除。"""
from __future__ import annotations
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_pinned_session_survives_prune(tmp_path, monkeypatch):
    from test_qml_shell import _bridge, text_stream
    bridge, store, host = _bridge(tmp_path, monkeypatch, text_stream("x"))
    for i in range(12):
        host.create_session({"sessionId": f"s-{i}", "personaId": "general"})
        store.load_session(f"s-{i}")
    assert len(store._cache) >= 12
    assert bridge.pinSession("s-5") is True
    assert "s-5" in store._cache
    assert len(store._cache) <= 8
    store.save("s-5")
    assert (store.session_path("s-5")).exists()
