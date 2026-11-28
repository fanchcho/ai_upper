from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from ai_upper.config import APP  # noqa: E402 - tools/ must be importable first

sys.path.insert(0, str(APP / "src"))

QT_BINDINGS = ("PySide6", "PyQt6", "PySide2", "PyQt5")


@pytest.fixture(autouse=True)
def _flush_qt_deferred_deletes():
    """Run ``deleteLater()`` while Qt is still alive.

    QML tests close their window and call ``engine.deleteLater()`` in a
    ``finally`` block, but pytest has no event loop between tests. The
    deferred C++ delete then executes during interpreter shutdown, after the
    QApplication has been destroyed, and Qt segfaults with no Python frame.
    Flushing here keeps the object lifetime inside the application lifetime.

    Only touch Qt when it is already loaded, so tests that assert the binding
    shim does not import Qt keep an untouched environment.
    """
    yield
    if "PySide6.QtCore" not in sys.modules:
        return
    from PySide6.QtCore import QCoreApplication, QEvent

    QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def install_fake_binding(monkeypatch, bindings: dict[str, dict[str, dict[str, object]]]):
    """Install fake Qt packages in sys.modules for one test.

    Every binding the caller did not fake is shadowed with ``None``: importing a
    module set to None raises ImportError, so detection lands on the fake one
    even on a machine that has a real binding installed. The shim's
    process-global cache is reset too, or the fake leaks into later tests.
    """
    from utils import qt_compat

    for name in QT_BINDINGS:
        if name not in bindings:
            monkeypatch.setitem(sys.modules, name, None)
    for name, submodules in bindings.items():
        package = types.ModuleType(name)
        package.__path__ = []
        monkeypatch.setitem(sys.modules, name, package)
        for submodule, members in submodules.items():
            module = types.ModuleType(f"{name}.{submodule}")
            for member, value in members.items():
                setattr(module, member, value)
            monkeypatch.setitem(sys.modules, f"{name}.{submodule}", module)
    monkeypatch.setattr(qt_compat, "_binding", None)
    monkeypatch.setattr(qt_compat, "_modules", {})
    return qt_compat

@pytest.fixture(autouse=True)
def _legacy_text_language(request, monkeypatch):
    """Existing application scenarios assert their original Chinese UI strings.

    Build/CLI tests retain the English host default. Dedicated i18n tests set
    their own locale and verify both languages and selection precedence.
    """
    name = request.node.fspath.basename
    chinese = ('test_qml_chat_files.py', 'test_settings_write.py', 'test_compaction.py', 'test_host_write.py', 'test_provider_headers.py', 'test_chat_vm_compaction.py', 'test_chat_vm_todos.py', 'test_chat_streaming.py', 'test_mvvm_example.py', 'test_chat_vm.py', 'test_chat_sessions_vm.py', 'test_transcript_render.py',
               'test_deva_panes.py', 'test_settings_vm.py', 'test_provider_gateway.py',
               'test_provider_setup.py', 'test_demo.py', 'test_mvvm.py')
    if name in chinese:
        monkeypatch.setenv('AI_UPPER_LANG', 'zh-CN')


@pytest.fixture(scope="session", autouse=True)
def _qt_application_lifetime():
    """Destroy native Qt state before Python tears down binding callbacks."""
    yield
    if "PySide6.QtCore" not in sys.modules:
        return
    from PySide6.QtCore import QCoreApplication, QEvent
    import shiboken6

    app = QCoreApplication.instance()
    if app is not None:
        from PySide6.QtGui import QGuiApplication
        if isinstance(app, QGuiApplication):
            # The offscreen clipboard owns test-created QMimeData. Its static
            # destructor runs after Python; release binding callbacks now.
            app.clipboard().clear()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        shiboken6.delete(app)
