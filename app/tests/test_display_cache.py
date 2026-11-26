"""Display reuse, invalidation and bounded ownership in a real QML window."""
from dataclasses import replace
import pytest
from markdown.cache import DisplayCache
from markdown.document import BodyStyle


def test_key_invalidates_each_render_input():
    args = ['session', 'body', False, BodyStyle(), 780.0]
    base = DisplayCache.key(*args)
    variants = ['other', 'edited', True, replace(args[3], scale=1.2), 600.0]
    for i, value in enumerate(variants):
        changed = args.copy()
        changed[i] = value
        assert DisplayCache.key(*changed) != base
    assert DisplayCache.key(*args) == base


class FakeDisplay:
    charge = 10
    released = False

    def release(self):
        self.released = True


def test_lru_bounds_revision_and_active_ownership():
    cache = DisplayCache(max_entries=2, max_bytes=20)
    a, b, c = FakeDisplay(), FakeDisplay(), FakeDisplay()
    cache.put(('a', 1), a)
    cache.put(('b', 1), b)
    assert cache.get(('a', 1)) is a
    cache.put(('c', 1), c)
    assert b.released and not a.released
    assert cache.bytes == 20 and len(cache.entries) == 2
    cache.current = a
    cache.invalidate_current()
    assert not a.released and cache.bytes == 10
    d = FakeDisplay()
    cache.put(('c', 2), d)
    assert c.released and cache.bytes == 10
    oversized = FakeDisplay()
    oversized.charge = 21
    cache.put(('large', 1), oversized)
    assert cache.bytes == 10 and len(cache.entries) == 1


@pytest.fixture
def qapp():
    from PySide6.QtGui import QGuiApplication
    return QGuiApplication.instance() or QGuiApplication([])


def test_window_reuses_document_invalidates_edit_and_releases_eviction(qapp, tmp_path, monkeypatch):
    import test_qml_context_menu as fixture
    import markdown.prepare as prepare
    from mvvm.models.chat_models import Message
    from test_qml_shell import _tick_until

    def seed(store):
        for i in range(3):
            s = store.ensure_session(f's-{i}')
            s.title = f'Title {i}'
            s.messages = [Message(role='assistant', content=f'Body {i}\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n```text\n' + 'wide ' * 200 + '\n```')]
            store.save(s.id)
    monkeypatch.setattr(fixture, '_seed_sessions', seed)
    calls = []
    original = prepare.prepare_document
    def counted(*args):
        calls.append(args[0])
        return original(*args)
    monkeypatch.setattr(prepare, 'prepare_document', counted)
    w, b, store, _, ticker, engine = fixture._build_window(tmp_path, monkeypatch)
    w.setProperty('page', 'chat')
    b._display_cache.max_entries = 2
    def show(sid):
        before = b.rendered
        b.openSession(sid)
        assert _tick_until(b, lambda: b.rendered > before)
        return b._document.textDocument()
    try:
        first = show('s-0')
        viewport = b._body._viewports[0]
        viewport._content_x = 20.0
        show('s-1')
        n = len(calls)
        assert show('s-0') is first
        assert len(calls) == n
        assert viewport.contentX == 0.0
        assert w.property('activeId') == 's-0'
        assert w.property('activeTitle') == 'Title 0'
        assert 'Body 0' in first.toPlainText()
        session = store.load_session('s-0')
        session.messages.append(Message(role='assistant', content='edited'))
        store.save('s-0')
        assert 'edited' in show('s-0').toPlainText()
        assert len(calls) == n + 1
        from PySide6.QtCore import QCoreApplication, QEvent
        from shiboken6 import isValid
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        assert not isValid(first), 'evicted document must release its C++ allocation'
        show('s-2')
        assert len(b._display_cache.entries) <= 2
        # Streaming/synchronous rerender cannot leave a stale cached snapshot.
        b._render()
        assert all(v[0] is not b._display_cache.current for v in b._display_cache.entries.values())
        assert b.setTextSize(2)
        show('s-1')
        assert b._body.style.scale != 1.0
        assert b._display_cache.bytes <= b._display_cache.max_bytes
        # Image syntax bypasses reuse even when the local resource is missing;
        # a file may appear/change without a Markdown revision.
        session = store.load_session('s-1')
        session.messages.append(Message(role='assistant', content='![later](missing-image.png)'))
        store.save('s-1')
        show('s-1')
        n = len(calls)
        show('s-1')
        assert len(calls) == n + 1
    finally:
        ticker.stop()
        w.close()
        engine.deleteLater()
