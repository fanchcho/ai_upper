"""Ordinary sidebar switching keeps body semantics without replacing unchanged lists."""
from test_qml_context_menu import qapp, _build_window, _find_item, _click, _pump
from mvvm.models.chat_models import Message


def test_switch_preserves_lists_and_updates_body_title_and_scroll(qapp, tmp_path, monkeypatch):
    from PySide6.QtCore import QObject

    # Keep relative-time labels stable while asserting no list replacement.
    import qml_shell_sessions
    label = qml_shell_sessions.time_label
    monkeypatch.setattr(qml_shell_sessions, 'time_label',
                        lambda ms, now=None, lang='zh': label(ms, 1700000000000, lang))
    window, bridge, store, home, ticker, engine = _build_window(tmp_path, monkeypatch)
    try:
        window.setProperty('page', 'chat')
        session = store.load_session('parity-001')
        session.messages = [Message(role='assistant', content=(
            'Unique target\n\n```python\nreturn 42\n```\n\n'
            '| Key | Value |\n| --- | --- |\n| item | 42 |\n\n') * 20)]
        store.save(session.id)
        bridge._publish()
        _pump(qapp, .1)
        changed = []
        window.sessionsChanged.connect(lambda: changed.append('sessions'))
        window.archivedSessionsChanged.connect(lambda: changed.append('archive'))
        rows = window.property('sessions')
        index = next(i for i, row in enumerate(rows) if row['id'] == session.id)
        _click(window, _find_item(window.contentItem(), f'threadRow{index}'))
        _pump(qapp, .1)
        assert window.property('activeId') == session.id
        assert window.property('activeTitle') == session.title
        assert 'Unique target' in bridge._document.textDocument().toPlainText()
        assert changed == []
        assert window.property('sessions') == rows
        assert _find_item(window.contentItem(), f'threadRow{index}').property('active')
        scroller = window.findChild(QObject, 'bodyScroll')
        assert abs(scroller.property('contentY') - max(0, scroller.property('contentHeight') - scroller.property('height'))) < 2
        bridge.renameSession(session.id, 'Updated title')
        assert window.property('activeTitle') == 'Updated title'
        assert changed == ['sessions']
    finally:
        ticker.stop()
        window.close()
        engine.deleteLater()
