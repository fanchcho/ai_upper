"""A stale QML selection must not overwrite Desktop/Studio config or session state."""
import json
from test_qml_window_controls import qapp, _build_window, _pump


def test_qml_selection_rejects_external_edit(qapp, tmp_path, monkeypatch):
    window, bridge, ticker, engine = _build_window(tmp_path, monkeypatch, [('s1', 'Session')])
    try:
        bridge._active = 's1'
        old_model = bridge._store.load_session('s1').model
        old_effort = bridge._store.load_session('s1').effort
        config = bridge._settings.path
        data = json.loads(config.read_text())
        data['models']['activeModelId'] = 'external:model:variant'
        config.write_text(json.dumps(data), encoding='utf-8')
        assert bridge.setActiveModel('p1', 'claude-sonnet-5-5') is False
        assert bridge.setActiveEffort('high') is False
        assert json.loads(config.read_text()) == data
        assert bridge._store.load_session('s1').model == old_model
        assert bridge._store.load_session('s1').effort == old_effort
    finally:
        ticker.stop()
        window.close()
        _pump(qapp, 0.1)
        engine.deleteLater()
