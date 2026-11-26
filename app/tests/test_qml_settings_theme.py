"""Settings controls must switch on the existing window, including system changes."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from test_qml_window_controls import qapp, _build_window, _find_item, _pump


def test_settings_live_theme_and_system(qapp, tmp_path, monkeypatch):
    w, bridge, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        w.setProperty('page', 'settings-general')
        _pump(qapp)
        choice = _find_item(w.contentItem(), 'settingsThemeChoice')
        for theme, index in [('dark', 2), ('light', 1), ('system', 0)]:
            bridge.setTheme(theme)
            _pump(qapp, .1)
            assert choice.property('current') == index
        w.setProperty('page', 'settings-mcp')
        _pump(qapp)
        field = _find_item(w.contentItem(), 'pluginBaseUrl')
        field.setProperty('text', 'https://example.test/mcp')
        for theme, color in [('dark', '#e4e4e7'), ('light', '#1f1f24')]:
            assert bridge.setTheme(theme)
            _pump(qapp, .1)
            assert field.property('color').name() == color
            assert field.property('text') == 'https://example.test/mcp'
            assert field.property('placeholderTextColor').name() != color
        # offscreen does not implement native scheme changes: supply the real
        # QStyleHints signal with a controlled getter to verify the connection.
        hints = QGuiApplication.styleHints()
        scheme = [Qt.ColorScheme.Dark]
        monkeypatch.setattr(hints, 'colorScheme', lambda: scheme[0])
        bridge.setTheme('system')
        _pump(qapp, .1)
        assert field.property('color').name() == '#e4e4e7'
        scheme[0] = Qt.ColorScheme.Light
        hints.colorSchemeChanged.emit(scheme[0])
        _pump(qapp, .1)
        assert field.property('color').name() == '#1f1f24'
        bridge.setTheme('dark')
        hints.colorSchemeChanged.emit(Qt.ColorScheme.Light)
        assert field.property('color').name() == '#e4e4e7'
    finally:
        ticker.stop()
        w.close()
        engine.deleteLater()
