from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from ai_upper.config import TARGETS
from ai_upper.qt_prune import QT_COMPAT_MODULE, _qt_module_of, prune, used_qt_modules


@pytest.fixture(autouse=True)
def _isolate_payload_options(monkeypatch):
    """Prune tests exercise the documented defaults, not the local app config.

    ``prune()`` reads ``[tool.ai_upper.optimize]`` for the optional payload
    cuts. The working copy deliberately enables those cuts, so without this
    isolation the expected files would depend on the machine's pyproject.toml.
    """
    from ai_upper import qt_prune

    monkeypatch.setattr(qt_prune, "optimize_config", lambda: {})
    # Same reason, one step further: the working copy ships .qml files, and a
    # prune test that inherited them would keep a QML payload its fake wheel
    # does not have. Only the tests that pass ``source_root`` see QML sources;
    # the default lookup is pinned to "no QML shipped".
    real_roots = qt_prune.qml_source_roots
    monkeypatch.setattr(
        qt_prune, "qml_source_roots", lambda root=None: () if root is None else real_roots(root)
    )


def _touch(path: Path, payload: bytes = b"\xcf\xfa\xed\xfe") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def _fake_pyside(site: Path) -> Path:
    pyside = site / "PySide6"
    for module in ("QtCore", "QtGui", "QtWidgets", "QtQml", "QtWebEngineCore"):
        _touch(pyside / f"{module}.abi3.so")
    for module in ("QtCore", "QtGui", "QtWidgets", "QtQml", "QtWebEngineCore"):
        _touch(pyside / "Qt" / "lib" / f"{module}.framework" / "Versions" / "A" / module)
    _touch(pyside / "Qt" / "plugins" / "platforms" / "libqcocoa.dylib")
    _touch(pyside / "Qt" / "plugins" / "sqldrivers" / "libqsqlite.dylib")
    _touch(pyside / "Qt" / "plugins" / "imageformats" / "libqpdf.dylib")
    _touch(pyside / "Qt" / "qml" / "QtQuick" / "libqtquickplugin.dylib")
    _touch(pyside / "Qt" / "libexec" / "QtWebEngineProcess")
    _touch(pyside / "qmlls")
    _touch(pyside / "Assistant.app" / "Contents" / "MacOS" / "Assistant")
    _touch(pyside / "libpyside6.abi3.6.11.dylib")
    _touch(pyside / "libpyside6qml.abi3.6.11.dylib")
    (pyside / "Qt" / "translations").mkdir(parents=True, exist_ok=True)
    for name in ("qtbase_zh_CN.qm", "qt_zh_CN.qm", "qt_help_zh_CN.qm", "assistant_zh_CN.qm", "qtmultimedia_zh_CN.qm"):
        (pyside / "Qt" / "translations" / name).write_text("", encoding="utf-8")
    return pyside


def _fake_windows_pyside(site: Path) -> Path:
    """A PySide6 tree with the Windows wheel layout.

    The Windows wheels keep no ``Qt`` directory: the Qt DLLs, the extension
    modules and the tooling sit in the package root, and only ``plugins``,
    ``qml``, ``translations`` and ``metatypes`` are beside them.
    """
    pyside = site / "PySide6"
    for module in ("QtCore", "QtGui", "QtWidgets", "QtQml", "QtWebEngineCore"):
        _touch(pyside / f"{module}.pyd")
    for module in ("QtCore", "QtGui", "QtWidgets", "QtQml", "QtWebEngineCore", "QtPdf", "QtSql", "QtMultimedia"):
        _touch(pyside / f"Qt6{module[2:]}.dll")
    _touch(pyside / "pyside6.abi3.dll")
    _touch(pyside / "pyside6qml.abi3.dll")
    _touch(pyside / "msvcp140.dll")
    # Loaded by name at runtime, never through an import table.
    _touch(pyside / "opengl32sw.dll")
    _touch(pyside / "plugins" / "platforms" / "qwindows.dll")
    _touch(pyside / "plugins" / "sqldrivers" / "qsqlite.dll")
    _touch(pyside / "plugins" / "imageformats" / "qpdf.dll")
    _touch(pyside / "plugins" / "imageformats" / "qsvg.dll")
    _touch(pyside / "plugins" / "multimedia" / "ffmpegmediaplugin.dll")
    _touch(pyside / "qml" / "QtQuick" / "qtquickplugin.dll")
    _touch(pyside / "QtWebEngineProcess.exe")
    _touch(pyside / "assistant.exe")
    _touch(pyside / "qmlls.exe")
    _touch(pyside / "metatypes" / "qt6core_metatypes.json")
    (pyside / "translations").mkdir(parents=True, exist_ok=True)
    for name in ("qtbase_zh_CN.qm", "qt_zh_CN.qm", "qt_help_zh_CN.qm", "assistant_zh_CN.qm", "qtmultimedia_zh_CN.qm"):
        (pyside / "translations" / name).write_text("", encoding="utf-8")
    return pyside


def _windows_dependencies(path: Path) -> list[str]:
    """The import graph of the fake Windows tree, keyed by file name."""
    return {
        "QtWidgets.pyd": ["Qt6Widgets.dll", "Qt6Gui.dll", "pyside6.abi3.dll"],
        "QtGui.pyd": ["Qt6Gui.dll", "Qt6Core.dll", "pyside6.abi3.dll"],
        "QtCore.pyd": ["Qt6Core.dll", "pyside6.abi3.dll"],
        "Qt6Widgets.dll": ["Qt6Gui.dll", "msvcp140.dll"],
        "Qt6Gui.dll": ["Qt6Core.dll", "msvcp140.dll"],
        "Qt6Core.dll": ["msvcp140.dll"],
        "qwindows.dll": ["Qt6Gui.dll", "Qt6Core.dll"],
        "qsvg.dll": ["Qt6Gui.dll", "Qt6Core.dll"],
        "qpdf.dll": ["Qt6Gui.dll", "Qt6Pdf.dll"],
        "qsqlite.dll": ["Qt6Core.dll", "Qt6Sql.dll"],
        "ffmpegmediaplugin.dll": ["Qt6Multimedia.dll"],
    }.get(path.name, [])


def test_qt_module_mapping_covers_platform_layouts():
    assert _qt_module_of("@rpath/QtGui.framework/Versions/A/QtGui") == "QtGui"
    assert _qt_module_of("@rpath/libQt6Core.6.dylib") == "QtCore"
    assert _qt_module_of("libQt6Gui.so.6.11.0") == "QtGui"
    assert _qt_module_of("Qt6Widgets.dll") == "QtWidgets"
    assert _qt_module_of("libqcocoa.dylib") is None


def test_qt_module_mapping_ignores_system_frameworks():
    """System frameworks must not look like Qt modules.

    Treating CoreVideo/IOSurface/ColorSync as Qt modules dropped the cocoa
    platform plugin, because it links system frameworks the Qt wrapper closure
    never mentions, and the packaged application then could not start.
    """
    assert _qt_module_of("/System/Library/Frameworks/CoreVideo.framework/Versions/A/CoreVideo") is None
    assert _qt_module_of("/System/Library/Frameworks/IOSurface.framework/Versions/A/IOSurface") is None
    assert _qt_module_of("/System/Library/Frameworks/AppKit.framework/Versions/C/AppKit") is None
    assert _qt_module_of("/usr/lib/libSystem.B.dylib") is None
    assert _qt_module_of("/usr/lib/libobjc.A.dylib") is None


def test_used_qt_modules_reads_application_sources(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    (source / "application.py").write_text(
        "from PySide6.QtWidgets import QApplication\nimport PySide6.QtCore\n", encoding="utf-8"
    )
    (source / "main.py").write_text("print('no qt here')\n", encoding="utf-8")
    assert used_qt_modules(source) == {"QtWidgets", "QtCore"}


def test_used_qt_modules_reads_the_compat_shim(tmp_path):
    """The shim names Qt modules exactly as directly as a binding import.

    The application imports Qt from the shim, so a scanner that only knew
    binding prefixes would report no Qt usage, configured_modules() would keep
    the whole 665 MB payload, and the build would still pass — a silent
    regression rather than a visible failure.
    """
    source = tmp_path / "src"
    shim = source / Path(*QT_COMPAT_MODULE.split(".")).with_suffix(".py")
    shim.parent.mkdir(parents=True)
    shim.write_text("# binding-neutral shim, no import of its own\n", encoding="utf-8")
    (source / "window.py").write_text(
        f"from {QT_COMPAT_MODULE} import (\n    QtWidgets,\n    QtCore,\n)\n", encoding="utf-8"
    )
    (source / "main.py").write_text(
        f"from {QT_COMPAT_MODULE} import QtWidgets, Signal\nimport {QT_COMPAT_MODULE}\n", encoding="utf-8"
    )
    # Signal is a factory, not a module: only names that could be a Qt
    # submodule count, and a bare shim import names no module.
    assert used_qt_modules(source) == {"QtWidgets", "QtCore"}


def test_used_qt_modules_reports_a_source_it_cannot_parse(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    (source / "broken.py").write_text("def f(:\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="broken.py"):
        used_qt_modules(source)


def test_qt_compat_module_names_a_real_shim():
    """The constant Qt pruning scans for must point at the application's shim.

    Rotting on either side is invisible: the scanner finds nothing and keeps the
    whole payload instead of failing.
    """
    from ai_upper.config import APP
    from ai_upper.qt_prune import QT_COMPAT_MODULE

    path = APP / "src" / Path(*QT_COMPAT_MODULE.split(".")).with_suffix(".py")
    assert path.is_file(), f"{QT_COMPAT_MODULE} names no module under {APP / 'src'}"
    assert "QtWidgets" in used_qt_modules(), "application sources name no Qt module through the shim"


def test_prune_keeps_only_the_imported_qt_payload(tmp_path, monkeypatch):
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = _fake_pyside(site)

    def fake_dependencies(path: Path) -> list[str]:
        name = path.name
        if name == "QtWidgets.abi3.so":
            return ["@rpath/QtWidgets.framework/Versions/A/QtWidgets", "@rpath/QtGui.framework/Versions/A/QtGui"]
        if name == "QtGui.abi3.so":
            return ["@rpath/QtGui.framework/Versions/A/QtGui", "@rpath/QtCore.framework/Versions/A/QtCore"]
        if name == "libqcocoa.dylib":
            # A platform plugin links system frameworks and may even reference
            # an extra Qt module; it must still be kept.
            return [
                "@rpath/QtGui.framework/Versions/A/QtGui",
                "@rpath/QtCore.framework/Versions/A/QtCore",
                "@rpath/QtPdf.framework/Versions/A/QtPdf",
                "/System/Library/Frameworks/CoreVideo.framework/Versions/A/CoreVideo",
                "/System/Library/Frameworks/IOSurface.framework/Versions/A/IOSurface",
            ]
        if name == "libqsqlite.dylib":
            return ["@rpath/QtCore.framework/Versions/A/QtCore"]
        if name == "libqpdf.dylib":
            return ["@rpath/QtGui.framework/Versions/A/QtGui", "@rpath/QtPdf.framework/Versions/A/QtPdf"]
        if name == "QtCore.framework":
            return ["/usr/lib/libSystem.B.dylib"]
        if name == "QtGui.framework":
            return ["@rpath/QtCore.framework/Versions/A/QtCore"]
        if name == "QtWidgets.framework":
            return ["@rpath/QtGui.framework/Versions/A/QtGui"]
        if name == "QtWebEngineCore.framework":
            return ["@rpath/QtQml.framework/Versions/A/QtQml"]
        return []

    monkeypatch.setattr(qt_prune, "dependency_names", fake_dependencies)
    # prune() receives the expanded module set, exactly as configured_modules()
    # hands it over after resolving the runtime closure.
    counters = prune(site, TARGETS["macos-arm64"], {"QtWidgets", "QtGui", "QtCore"})

    assert counters and counters["bytes"] > 0
    # kept: the imported module and its native closure
    assert (pyside / "QtWidgets.abi3.so").exists()
    assert (pyside / "QtGui.abi3.so").exists()
    assert (pyside / "QtCore.abi3.so").exists()
    assert (pyside / "Qt" / "lib" / "QtWidgets.framework").exists()
    assert (pyside / "Qt" / "plugins" / "platforms" / "libqcocoa.dylib").exists()
    # dropped: unimported modules, their libraries, plugins and tooling
    assert not (pyside / "QtWebEngineCore.abi3.so").exists()
    assert not (pyside / "QtQml.abi3.so").exists()
    assert not (pyside / "Qt" / "lib" / "QtWebEngineCore.framework").exists()
    assert not (pyside / "Qt" / "lib" / "QtQml.framework").exists()
    assert not (pyside / "Qt" / "plugins" / "sqldrivers").exists()
    # an image format that needs a Qt module the app never imports goes too
    assert not (pyside / "Qt" / "plugins" / "imageformats" / "libqpdf.dylib").exists()
    assert (pyside / "Qt" / "plugins" / "imageformats").exists()
    assert not (pyside / "Qt" / "qml").exists()
    assert not (pyside / "Qt" / "libexec").exists()
    assert not (pyside / "libpyside6qml.abi3.6.11.dylib").exists()
    assert (pyside / "libpyside6.abi3.6.11.dylib").exists()
    assert not (pyside / "qmlls").exists()
    assert not (pyside / "Assistant.app").exists()
    # translations: Qt's own strings stay, tooling and unused modules go
    assert (pyside / "Qt" / "translations" / "qtbase_zh_CN.qm").exists()
    assert (pyside / "Qt" / "translations" / "qt_zh_CN.qm").exists()
    assert not (pyside / "Qt" / "translations" / "qt_help_zh_CN.qm").exists()
    assert not (pyside / "Qt" / "translations" / "assistant_zh_CN.qm").exists()
    assert not (pyside / "Qt" / "translations" / "qtmultimedia_zh_CN.qm").exists()


def test_prune_keeps_only_the_imported_qt_payload_on_windows(tmp_path, monkeypatch):
    """The Windows wheel has no Qt/ directory, so every path has to be derived.

    Reading only the POSIX layout left the whole Windows payload in place: the
    Qt DLLs, the SQL drivers, the multimedia stack and the QML tree all stayed
    in the bundle, and the native closure then failed on the optional payload
    those extra modules link (the database clients, the ffmpeg libraries).
    """
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = _fake_windows_pyside(site)
    monkeypatch.setattr(qt_prune, "dependency_names", _windows_dependencies)

    counters = prune(site, TARGETS["windows-x86_64"], {"QtWidgets", "QtGui", "QtCore"})

    assert counters and counters["bytes"] > 0
    # kept: the imported modules, the Qt libraries they link and the runtime
    # images that closure needs
    assert (pyside / "QtCore.pyd").exists()
    assert (pyside / "QtGui.pyd").exists()
    assert (pyside / "QtWidgets.pyd").exists()
    assert (pyside / "Qt6Core.dll").exists()
    assert (pyside / "Qt6Gui.dll").exists()
    assert (pyside / "Qt6Widgets.dll").exists()
    assert (pyside / "pyside6.abi3.dll").exists()
    assert (pyside / "msvcp140.dll").exists()
    assert (pyside / "plugins" / "platforms" / "qwindows.dll").exists()
    assert (pyside / "plugins" / "imageformats" / "qsvg.dll").exists()
    # kept although nothing imports it: QtGui loads it by name
    assert (pyside / "opengl32sw.dll").exists()
    # dropped: unimported modules and everything that belongs to them
    assert not (pyside / "QtQml.pyd").exists()
    assert not (pyside / "QtWebEngineCore.pyd").exists()
    assert not (pyside / "Qt6Qml.dll").exists()
    assert not (pyside / "Qt6WebEngineCore.dll").exists()
    assert not (pyside / "Qt6Sql.dll").exists()
    assert not (pyside / "Qt6Multimedia.dll").exists()
    assert not (pyside / "plugins" / "sqldrivers").exists()
    assert not (pyside / "plugins" / "multimedia").exists()
    # an image format that needs a Qt module the app never imports goes too
    assert not (pyside / "plugins" / "imageformats" / "qpdf.dll").exists()
    assert not (pyside / "Qt6Pdf.dll").exists()
    assert not (pyside / "qml").exists()
    assert not (pyside / "pyside6qml.abi3.dll").exists()
    assert not (pyside / "metatypes").exists()
    # tooling: the Windows wheels append .exe to every name
    assert not (pyside / "assistant.exe").exists()
    assert not (pyside / "qmlls.exe").exists()
    # the WebEngine helper process follows the payload it belongs to
    assert not (pyside / "QtWebEngineProcess.exe").exists()
    # translations: Qt's own strings stay, tooling and unused modules go
    assert (pyside / "translations" / "qtbase_zh_CN.qm").exists()
    assert (pyside / "translations" / "qt_zh_CN.qm").exists()
    assert not (pyside / "translations" / "qt_help_zh_CN.qm").exists()
    assert not (pyside / "translations" / "assistant_zh_CN.qm").exists()
    assert not (pyside / "translations" / "qtmultimedia_zh_CN.qm").exists()


def test_windows_pruning_never_touches_the_package_itself(tmp_path, monkeypatch):
    """Only DLLs are payload; the package's own files must survive the sweep.

    On Windows the Qt libraries live in the package root next to the importable
    extension modules and the packaging metadata, so a reachability sweep that
    treated every entry as a library would delete the modules it just kept.
    """
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = _fake_windows_pyside(site)
    (pyside / "__init__.py").write_text("", encoding="utf-8")
    (pyside / "QtCore.pyi").write_text("", encoding="utf-8")
    (pyside / "helper").mkdir()
    (pyside / "helper" / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(qt_prune, "dependency_names", _windows_dependencies)

    prune(site, TARGETS["windows-x86_64"], {"QtWidgets", "QtGui", "QtCore"})

    assert (pyside / "__init__.py").exists()
    assert (pyside / "QtCore.pyi").exists()
    assert (pyside / "helper" / "__init__.py").exists()


def test_windows_pruning_drops_the_binding_prefixed_tool_copy(tmp_path, monkeypatch):
    """PySide ships lupdate twice, and the prefixed copy is the one that leaks.

    The Windows wheels carry ``pyside2-lupdate.exe`` beside ``lupdate.exe``. Only
    the bare name was listed as tooling, so the prefixed executable survived the
    sweep while the Qt5Xml.dll it links did not (the application never imports
    QtXml) and the build stopped at "Unresolved native dependencies:
    site-packages/PySide2/pyside2-lupdate.exe: Qt5Xml.dll" -- over a translation
    tool that is developer tooling, not runtime payload.
    """
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = site / "PySide2"
    _touch(pyside / "QtCore.pyd")
    _touch(pyside / "Qt5Core.dll")
    _touch(pyside / "pyside2.abi3.dll")
    _touch(pyside / "lupdate.exe")
    _touch(pyside / "pyside2-lupdate.exe")

    def dependencies(path: Path) -> list[str]:
        return {
            "QtCore.pyd": ["Qt5Core.dll", "pyside2.abi3.dll"],
            "pyside2-lupdate.exe": ["Qt5Xml.dll"],
        }.get(path.name, [])

    monkeypatch.setattr(qt_prune, "dependency_names", dependencies)

    counters = prune(site, TARGETS["windows-x86_64"], {"QtCore"})

    assert counters and counters["files"] >= 2
    assert not (pyside / "lupdate.exe").exists()
    assert not (pyside / "pyside2-lupdate.exe").exists()
    # The payload the application does import is untouched.
    assert (pyside / "QtCore.pyd").exists()
    assert (pyside / "Qt5Core.dll").exists()
    assert (pyside / "pyside2.abi3.dll").exists()


def test_configured_modules_expands_explicit_lists_through_the_closure(tmp_path, monkeypatch):
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    _fake_pyside(site)
    monkeypatch.setattr(qt_prune, "optimize_config", lambda: {"qt": ["QtWidgets"]})
    monkeypatch.setattr(
        qt_prune, "_runtime_closure", lambda site, target, modules, optional=None: modules | {"QtGui", "QtCore"}
    )
    assert qt_prune.configured_modules(TARGETS["macos-arm64"], site) == {"QtWidgets", "QtGui", "QtCore"}


def test_configured_modules_rejects_unknown_settings(tmp_path, monkeypatch):
    from ai_upper import qt_prune

    monkeypatch.setattr(qt_prune, "optimize_config", lambda: {"qt": "everything"})
    try:
        qt_prune.configured_modules(TARGETS["macos-arm64"], tmp_path)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected a rejection of an unknown qt setting")


def test_configured_modules_reports_a_runtime_that_cannot_import_the_payload(tmp_path, monkeypatch):
    """A failed closure probe is an error, never a narrower payload.

    Falling back to the requested modules deletes everything they link
    indirectly, because importing QtWidgets alone never mentions QtCore and
    QtGui; the bundle then only breaks in the packaged smoke run.
    """
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    _fake_pyside(site)
    # A real wheel ships PySide6/__init__.py. Without it the probe would import
    # whichever PySide6 the test interpreter happens to have installed instead
    # of the staged payload.
    (site / "PySide6" / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(qt_prune, "optimize_config", lambda: {"qt": "imports"})
    monkeypatch.setattr(qt_prune, "qt_module_usage", lambda *args, **kwargs: ({"QtWidgets"}, set()))
    monkeypatch.setattr(qt_prune, "_native_runtime_python", lambda target: Path(sys.executable))
    with pytest.raises(RuntimeError, match="QtWidgets"):
        qt_prune.configured_modules(TARGETS["macos-arm64"], site)


def test_configured_modules_keeps_the_payload_when_the_target_cannot_run(tmp_path, monkeypatch):
    """Without the target interpreter the closure is unknown, so nothing goes."""
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    _fake_pyside(site)
    monkeypatch.setattr(qt_prune, "optimize_config", lambda: {"qt": "imports"})
    monkeypatch.setattr(qt_prune, "qt_module_usage", lambda *args, **kwargs: ({"QtWidgets"}, set()))
    monkeypatch.setattr(qt_prune, "_native_runtime_python", lambda target: None)
    assert qt_prune.configured_modules(TARGETS["macos-arm64"], site) is None


def test_prune_ignores_a_site_without_a_qt_payload(tmp_path, monkeypatch):
    """A staged site without PySide6 has nothing to prune, so nothing is probed."""
    from ai_upper import qt_prune

    monkeypatch.setattr(qt_prune, "optimize_config", lambda: {"qt": "imports"})

    def fail(*args, **kwargs):
        raise AssertionError("the module closure must not be probed without a Qt payload")

    monkeypatch.setattr(qt_prune, "_runtime_closure", fail)
    assert prune(tmp_path / "site-packages", TARGETS["macos-arm64"]) is None


def test_prune_is_disabled_by_default(tmp_path, monkeypatch):
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = _fake_pyside(site)
    monkeypatch.setattr(qt_prune, "optimize_config", lambda: {})
    monkeypatch.setattr(qt_prune, "dependency_names", lambda path: [])
    assert prune(site, TARGETS["macos-arm64"]) is None
    assert (pyside / "QtWebEngineCore.abi3.so").exists()


def test_runtime_closure_probe_inherits_the_host_environment(tmp_path, monkeypatch):
    """The closure probe must not hand the target interpreter a built environment.

    It needs PYTHONPATH (the staged payload) and PYTHONDONTWRITEBYTECODE, but
    everything else has to come from the host. A block containing only those two
    plus a POSIX PATH is not a smaller host environment: on Windows the target
    interpreter dies during preinit without SystemRoot, reporting
    "_Py_HashRandomization_Init: failed to get random numbers to initialize
    Python", which failed every Windows host build with qt = "imports" before
    the launcher step.
    """
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    site.mkdir()
    recorded: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        recorded["cmd"] = cmd
        recorded["env"] = kwargs["env"]
        loaded = {"loaded": ["PySide6.QtWidgets", "PySide6.QtCore"], "absent": []}
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(loaded) + "\n", stderr="")

    monkeypatch.setattr(qt_prune, "_native_runtime_python", lambda target: Path(sys.executable))
    monkeypatch.setattr(qt_prune.subprocess, "run", fake_run)

    closure = qt_prune._runtime_closure(site, TARGETS["macos-arm64"], {"QtWidgets"})

    assert closure == {"QtWidgets", "QtCore"}
    env = recorded["env"]
    assert env["PYTHONPATH"] == str(site)
    assert env["PYTHONDONTWRITEBYTECODE"] == "1"
    dropped = {name: value for name, value in os.environ.items() if env.get(name) != value}
    assert not dropped, f"the probe dropped host variables: {sorted(dropped)}"


def test_prune_drops_build_payload_and_webengine_resources(tmp_path, monkeypatch):
    """Headers, examples, WebEngine resources and the WebGL platform plugin.

    None of these can be reached from an import: the C++ headers and example
    tree are build payload, ``resources`` belongs to QtWebEngineCore, and
    ``qwebgl`` is Qt's streaming platform plugin rather than a desktop one.
    ``qoffscreen`` has to stay because the headless smoke test opens a window
    through it.
    """
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = _fake_windows_pyside(site)
    _touch(pyside / "examples" / "widgets" / "demo.py")
    _touch(pyside / "include" / "QtWidgets" / "qwidget.h")
    _touch(pyside / "resources" / "icudtl.dat")
    _touch(pyside / "plugins" / "platforms" / "qwebgl.dll")
    _touch(pyside / "plugins" / "platforms" / "qoffscreen.dll")
    monkeypatch.setattr(qt_prune, "dependency_names", _windows_dependencies)

    counters = prune(site, TARGETS["windows-x86_64"], {"QtCore"})

    assert counters and counters["bytes"] > 0
    assert not (pyside / "examples").exists()
    assert not (pyside / "include").exists()
    assert not (pyside / "resources").exists()
    assert not (pyside / "plugins" / "platforms" / "qwebgl.dll").exists()
    assert (pyside / "plugins" / "platforms" / "qoffscreen.dll").exists()
    # The platform category itself survives, so a real desktop plugin would too.
    assert (pyside / "plugins" / "platforms").is_dir()


def test_prune_keeps_webengine_resources_when_the_module_is_used(tmp_path, monkeypatch):
    """``resources`` is WebEngine payload, not unconditional build output."""
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = _fake_windows_pyside(site)
    _touch(pyside / "resources" / "qtwebengine_resources.pak")
    _touch(pyside / "include" / "QtCore" / "qobject.h")
    monkeypatch.setattr(qt_prune, "dependency_names", _windows_dependencies)

    prune(site, TARGETS["windows-x86_64"], {"QtCore", "QtWebEngineCore"})

    assert (pyside / "resources" / "qtwebengine_resources.pak").exists()
    assert not (pyside / "include").exists()


@pytest.mark.parametrize(("binding", "qt_dir"), [
    ("PySide2", "Qt"),
    ("PySide6", "Qt"),
    ("PyQt5", "Qt5"),
    ("PyQt6", "Qt6"),
])
def test_qt_layout_reads_each_bindings_payload_directory(tmp_path, binding, qt_dir):
    """PySide POSIX uses ``Qt``; PyQt uses ``Qt<major>`` on every platform.

    Recognising only ``Qt`` made a PyQt POSIX tree look like the flat Windows
    layout: ``plugins``, ``qml`` and ``translations`` were then read from the
    package root, where they do not exist, and pruning became a no-op.
    """
    from ai_upper import qt_prune

    package = tmp_path / "site-packages" / binding
    plugins = package / qt_dir / "plugins"
    plugins.mkdir(parents=True)
    (package / qt_dir / "bin").mkdir()
    (package / qt_dir / "translations").mkdir()

    layout = qt_prune._qt_layout(package, binding)

    assert layout.root == package / qt_dir
    assert layout.plugins == plugins
    assert layout.translations == package / qt_dir / "translations"
    assert package / qt_dir / "bin" in layout.libraries
    assert layout.library_names is None


def test_qt_layout_falls_back_to_the_flat_windows_pyside_root(tmp_path):
    from ai_upper import qt_prune

    package = tmp_path / "site-packages" / "PySide2"
    (package / "plugins" / "platforms").mkdir(parents=True)

    layout = qt_prune._qt_layout(package, "PySide2")

    assert layout.root == package
    assert layout.plugins == package / "plugins"
    assert layout.library_names == "*.dll"


def test_prune_reads_the_pyqt_payload_directory(tmp_path, monkeypatch):
    """The payload root is not hard-coded to ``Qt``.

    A PyQt6 tree keeps its libraries, plugins and translations under ``Qt6``.
    ``prune()`` used to derive that root from ``pyside / "Qt"`` alone, so on
    PyQt it treated the package root as the payload root and left examples,
    headers and unused translations in the bundle.
    """
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    package = site / "PyQt6"
    _touch(package / "QtCore.pyd")
    _touch(package / "Qt6" / "bin" / "Qt6Core.dll")
    _touch(package / "Qt6" / "plugins" / "platforms" / "qwindows.dll")
    _touch(package / "Qt6" / "translations" / "qtbase_zh_CN.qm")
    _touch(package / "Qt6" / "translations" / "qtmultimedia_zh_CN.qm")
    _touch(package / "Qt6" / "examples" / "widgets" / "main.cpp")
    _touch(package / "Qt6" / "include" / "QtCore" / "qobject.h")

    def dependencies(path: Path) -> list[str]:
        return {
            "QtCore.pyd": ["Qt6Core.dll"],
            "qwindows.dll": ["Qt6Core.dll"],
        }.get(path.name, [])

    monkeypatch.setattr(qt_prune, "dependency_names", dependencies)

    counters = prune(site, TARGETS["windows-x86_64"], {"QtCore"})

    assert counters and counters["bytes"] > 0
    assert (package / "Qt6" / "bin" / "Qt6Core.dll").exists()
    assert (package / "Qt6" / "plugins" / "platforms" / "qwindows.dll").exists()
    assert (package / "Qt6" / "translations" / "qtbase_zh_CN.qm").exists()
    assert not (package / "Qt6" / "translations" / "qtmultimedia_zh_CN.qm").exists()
    assert not (package / "Qt6" / "examples").exists()
    assert not (package / "Qt6" / "include").exists()

def test_prune_drops_binding_tooling_docs_and_link_libraries(tmp_path, monkeypatch):
    """Wheel docs, .lib import libraries and unused MSVC runtimes are dead weight.

    The reference PySide2 deployment keeps only the runtime DLLs and the
    shiboken signature directory. ``docs`` alone is ~1.9 MB, and ``.lib`` files
    are link-time inputs no frozen application can use.
    """
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = _fake_windows_pyside(site)
    _touch(pyside / "docs" / "index.html")
    _touch(pyside / "pyside6.abi3.lib")
    shiboken = site / "shiboken6"
    _touch(shiboken / "docs" / "index.html")
    _touch(shiboken / "shiboken6.abi3.lib")
    _touch(shiboken / "msvcp140.dll")
    _touch(shiboken / "vcruntime140.dll")
    _touch(shiboken / "vcamp140.dll")
    _touch(shiboken / "concrt140.dll")
    _touch(shiboken / "vcomp140.dll")
    monkeypatch.setattr(qt_prune, "dependency_names", _windows_dependencies)

    prune(site, TARGETS["windows-x86_64"], {"QtCore"})

    assert not (pyside / "docs").exists()
    assert not (pyside / "pyside6.abi3.lib").exists()
    assert not (shiboken / "docs").exists()
    assert not (shiboken / "shiboken6.abi3.lib").exists()
    # The runtimes the extension modules link stay; tooling-only ones go.
    assert (shiboken / "msvcp140.dll").exists()
    assert (shiboken / "vcruntime140.dll").exists()
    assert not (shiboken / "vcamp140.dll").exists()
    assert not (shiboken / "concrt140.dll").exists()
    assert not (shiboken / "vcomp140.dll").exists()


def test_prune_drops_posix_docs_headers_cmake_and_stale_stubs(tmp_path, monkeypatch):
    """The POSIX wheel uses ``doc``/``include``/``lib``, not only ``docs``/``.lib``.

    PySide6 ships the documentation as ``doc`` on every platform, and the
    headers plus CMake package files sit beside the binding on POSIX too. The
    type stubs of pruned wrappers describe modules that are no longer shipped.
    """
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = _fake_pyside(site)
    _touch(pyside / "doc" / "qtcore.rst")
    _touch(pyside / "include" / "QtCore" / "qobject.h")
    _touch(pyside / "lib" / "cmake" / "PySide6" / "PySide6Config.cmake")
    _touch(pyside / "QtWebEngineCore.pyi")
    _touch(pyside / "QtCore.pyi")
    shiboken = site / "shiboken6"
    _touch(shiboken / "doc" / "index.rst")
    _touch(shiboken / "include" / "basewrapper.h")
    _touch(shiboken / "lib" / "cmake" / "Shiboken6" / "Shiboken6Config.cmake")
    monkeypatch.setattr(qt_prune, "dependency_names", lambda path: [])

    prune(site, TARGETS["macos-arm64"], {"QtCore"})

    assert not (pyside / "doc").exists()
    assert not (pyside / "include").exists()
    assert not (pyside / "lib").exists()
    assert not (shiboken / "doc").exists()
    assert not (shiboken / "include").exists()
    assert not (shiboken / "lib").exists()
    assert not (pyside / "QtWebEngineCore.pyi").exists()
    assert (pyside / "QtCore.pyi").exists()


def test_prune_platform_allowlist_spans_every_desktop_layout(tmp_path, monkeypatch):
    """One policy keeps the desktop plugin for each host and drops fallbacks.

    Qt names the plugin ``qwindows.dll`` on Windows, ``libqcocoa.dylib`` on
    macOS and ``libqxcb.so``/``libqwayland-*.so`` on Linux. The allowlist is
    matched after normalizing those spellings, so a Windows build does not need
    a different configuration from a Linux or macOS build.
    """
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = _fake_windows_pyside(site)
    platforms = pyside / "plugins" / "platforms"
    _touch(platforms / "qoffscreen.dll")
    for name in (
        "libqcocoa.dylib",
        "libqxcb.so",
        "libqwayland-egl.so",
        "libqwayland-generic.so",
        "qminimal.dll",
        "qdirect2d.dll",
        "qwebgl.dll",
    ):
        _touch(platforms / name)
    monkeypatch.setattr(qt_prune, "dependency_names", _windows_dependencies)

    prune(site, TARGETS["windows-x86_64"], {"QtCore"})

    assert (platforms / "qwindows.dll").exists()
    assert (platforms / "qoffscreen.dll").exists()
    assert (platforms / "libqcocoa.dylib").exists()
    assert (platforms / "libqxcb.so").exists()
    assert (platforms / "libqwayland-egl.so").exists()
    assert (platforms / "libqwayland-generic.so").exists()
    assert not (platforms / "qminimal.dll").exists()
    assert not (platforms / "qdirect2d.dll").exists()
    assert not (platforms / "qwebgl.dll").exists()


def test_prune_image_format_allowlist_drops_svg_and_unused_formats(tmp_path, monkeypatch):
    """Image plugins are loaded by MIME type, so an allowlist has to name them.

    Dropping the SVG image plugin also drops the SVG icon engine and Qt5Svg:
    nothing else in a widgets-only application reaches that library.
    """
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = _fake_windows_pyside(site)
    formats = pyside / "plugins" / "imageformats"
    icons = pyside / "plugins" / "iconengines"
    for name in ("qgif.dll", "qico.dll", "qjpeg.dll", "qsvg.dll", "qwebp.dll", "qtiff.dll", "qwbmp.dll"):
        _touch(formats / name)
    _touch(icons / "qsvgicon.dll")
    _touch(pyside / "Qt5Svg.dll")
    monkeypatch.setattr(qt_prune, "optimize_config", lambda: {"qt_image_formats": ["gif", "ico", "jpeg"]})
    monkeypatch.setattr(qt_prune, "dependency_names", _windows_dependencies)

    prune(site, TARGETS["windows-x86_64"], {"QtCore", "QtGui"})

    assert (formats / "qgif.dll").exists()
    assert (formats / "qico.dll").exists()
    assert (formats / "qjpeg.dll").exists()
    assert not (formats / "qsvg.dll").exists()
    assert not (formats / "qwebp.dll").exists()
    assert not (formats / "qtiff.dll").exists()
    assert not (formats / "qwbmp.dll").exists()
    assert not (icons / "qsvgicon.dll").exists()
    # Qt5Svg was only reachable through the plugins that just went away.
    assert not (pyside / "Qt5Svg.dll").exists()


@pytest.mark.parametrize(
    ("locales", "kept", "dropped"),
    [
        (["zh_CN"], {"qtbase_zh_CN.qm", "qt_zh_CN.qm"}, {"qtbase_zh_TW.qm", "qtbase_de.qm"}),
        (["zh"], {"qtbase_zh_CN.qm", "qt_zh_CN.qm", "qtbase_zh_TW.qm"}, {"qtbase_de.qm"}),
        (["de"], {"qtbase_de.qm"}, {"qtbase_zh_CN.qm", "qt_zh_CN.qm", "qtbase_zh_TW.qm"}),
    ],
)
def test_prune_locale_allowlist_keeps_the_requested_translations(
    tmp_path, monkeypatch, locales, kept, dropped
):
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = _fake_windows_pyside(site)
    for name in ("qtbase_zh_TW.qm", "qtbase_de.qm"):
        (pyside / "translations" / name).write_text("", encoding="utf-8")
    monkeypatch.setattr(qt_prune, "optimize_config", lambda: {"qt_locales": locales})
    monkeypatch.setattr(qt_prune, "dependency_names", _windows_dependencies)

    prune(site, TARGETS["windows-x86_64"], {"QtCore"})

    translations = pyside / "translations"
    for name in kept:
        assert (translations / name).exists(), name
    for name in dropped:
        assert not (translations / name).exists(), name
    # Tooling translations stay out regardless of the locale list.
    assert not (translations / "qt_help_zh_CN.qm").exists()
    assert not (translations / "assistant_zh_CN.qm").exists()


def test_prune_can_drop_the_software_opengl_fallback(tmp_path, monkeypatch):
    """``qt_software_opengl = false`` removes the ~20 MB DLL."""
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = _fake_windows_pyside(site)
    monkeypatch.setattr(qt_prune, "optimize_config", lambda: {"qt_software_opengl": False})
    monkeypatch.setattr(qt_prune, "dependency_names", _windows_dependencies)

    prune(site, TARGETS["windows-x86_64"], {"QtCore"})

    assert not (pyside / "opengl32sw.dll").exists()


def test_prune_rejects_malformed_payload_options(tmp_path, monkeypatch):
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    _fake_windows_pyside(site)
    monkeypatch.setattr(qt_prune, "dependency_names", _windows_dependencies)

    for config, name in (
        ({"qt_image_formats": []}, "qt_image_formats"),
        ({"qt_locales": ["zh_CN", ""]}, "qt_locales"),
        ({"qt_platforms": 3}, "qt_platforms"),
        ({"qt_software_opengl": "no"}, "qt_software_opengl"),
    ):
        monkeypatch.setattr(qt_prune, "optimize_config", lambda cfg=config: cfg)
        with pytest.raises(RuntimeError, match=name):
            prune(site, TARGETS["windows-x86_64"], {"QtCore"})


def test_prune_keeps_the_webengine_helper_process_with_its_module(tmp_path, monkeypatch):
    """A kept QtWebEngineCore without its helper process renders nothing.

    ``QtWebEngineProcess`` is spawned by QtWebEngineCore when a view attaches,
    and it ships in the same ``libexec`` directory as rcc/uic/qmlcachegen.
    Dropping that directory wholesale deleted the runtime helper together with
    the build tooling: the packaged window opened, loaded the page, and stayed
    blank with no error. The helper has to follow its module; plain tooling
    still goes.
    """
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = _fake_pyside(site)
    _touch(pyside / "Qt" / "libexec" / "rcc")
    _touch(pyside / "Qt" / "libexec" / "uic")
    _touch(pyside / "Qt" / "libexec" / "qmlcachegen")

    def fake_dependencies(path):
        name = Path(path).name
        if name.startswith("QtWebEngineCore"):
            return ["@rpath/QtCore.framework/Versions/A/QtCore"]
        if name.startswith("QtCore"):
            return ["/usr/lib/libSystem.B.dylib"]
        return []

    monkeypatch.setattr(qt_prune, "dependency_names", fake_dependencies)

    prune(site, TARGETS["macos-arm64"], {"QtCore", "QtWebEngineCore"})

    helper = pyside / "Qt" / "libexec" / "QtWebEngineProcess"
    assert helper.exists(), "QtWebEngineCore ships without the process it spawns"
    # Everything else in libexec is build tooling, not runtime payload.
    assert not (pyside / "Qt" / "libexec" / "rcc").exists()
    assert not (pyside / "Qt" / "libexec" / "uic").exists()
    assert not (pyside / "Qt" / "libexec" / "qmlcachegen").exists()


def test_prune_drops_the_webengine_helper_with_its_module(tmp_path, monkeypatch):
    """The helper is dead weight once QtWebEngineCore itself is gone."""
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = _fake_pyside(site)

    monkeypatch.setattr(qt_prune, "dependency_names", lambda path: [])

    prune(site, TARGETS["macos-arm64"], {"QtCore"})

    assert not (pyside / "Qt" / "libexec").exists()


def test_prune_keeps_the_webengine_locale_packs_with_its_module(tmp_path, monkeypatch):
    """Chromium's locale packs belong to QtWebEngineCore, not to Qt translations.

    They live in ``translations/qtwebengine_locales`` and are spelled
    ``en-US.pak``, so the rule that keeps ``qtbase_*.qm`` treated the whole
    directory as tooling and removed it from the bundle. Every launch then
    logged ``could not find the translation file for the current locale``.
    """
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = _fake_pyside(site)
    locales = pyside / "Qt" / "translations" / qt_prune.WEBENGINE_LOCALES_DIR
    for name in ("en-US.pak", "zh-CN.pak", "de.pak"):
        (locales / name).parent.mkdir(parents=True, exist_ok=True)
        (locales / name).write_bytes(b"pak")

    monkeypatch.setattr(qt_prune, "dependency_names", lambda path: [])

    prune(site, TARGETS["macos-arm64"], {"QtCore", "QtWebEngineCore"})

    assert (locales / "en-US.pak").exists()
    assert (locales / "zh-CN.pak").exists()
    assert (locales / "de.pak").exists()


def test_webengine_locale_allowlist_matches_chromium_spelling(tmp_path, monkeypatch):
    """One allowlist covers Qt's ``zh_CN`` and Chromium's ``zh-CN``."""
    from ai_upper import qt_prune

    monkeypatch.setattr(
        qt_prune,
        "optimize_config",
        lambda: {"qt_locales": ["zh_CN"]},
    )
    site = tmp_path / "site-packages"
    pyside = _fake_pyside(site)
    locales = pyside / "Qt" / "translations" / qt_prune.WEBENGINE_LOCALES_DIR
    locales.mkdir(parents=True, exist_ok=True)
    for name in ("en-US.pak", "zh-CN.pak", "zh-TW.pak", "de.pak"):
        (locales / name).write_bytes(b"pak")

    monkeypatch.setattr(qt_prune, "dependency_names", lambda path: [])

    prune(site, TARGETS["macos-arm64"], {"QtCore", "QtWebEngineCore"})

    assert (locales / "en-US.pak").exists(), "the fallback pack must survive any allowlist"
    assert (locales / "zh-CN.pak").exists()
    assert not (locales / "zh-TW.pak").exists()
    assert not (locales / "de.pak").exists()
    # Qt's own translations still follow the same allowlist.
    assert (pyside / "Qt" / "translations" / "qtbase_zh_CN.qm").exists()
    assert (pyside / "Qt" / "translations" / "qt_zh_CN.qm").exists()
    assert not (pyside / "Qt" / "translations" / "qtmultimedia_zh_CN.qm").exists()


def test_prune_drops_the_webengine_locale_packs_with_its_module(tmp_path, monkeypatch):
    """No QtWebEngineCore, no Chromium locale packs."""
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = _fake_pyside(site)
    locales = pyside / "Qt" / "translations" / qt_prune.WEBENGINE_LOCALES_DIR
    locales.mkdir(parents=True, exist_ok=True)
    (locales / "en-US.pak").write_bytes(b"pak")

    monkeypatch.setattr(qt_prune, "dependency_names", lambda path: [])

    prune(site, TARGETS["macos-arm64"], {"QtCore"})

    assert not locales.exists()


def test_an_import_guarded_by_importerror_is_optional(tmp_path):
    """The application runs without it, so the packaging layer must not demand it.

    PySide6's win_arm64 wheels ship no QtWebEngineCore at all. When the web
    fallback still existed, ``web_shell_window`` imported it behind
    ``except ImportError`` precisely so the application started on such a
    binding; scanning every import as mandatory made the build fail on a payload
    the product code accepted. The guard is gone with the web entry, but the
    scanner contract it forced is what keeps any future optional import usable.
    """
    from ai_upper import qt_prune

    source = tmp_path / "src"
    source.mkdir()
    (source / "window.py").write_text(
        "try:\n"
        f"    from {QT_COMPAT_MODULE} import QtWebEngineCore, QtWebEngineWidgets\n"
        "except ImportError:\n"
        "    QtWebEngineCore = None\n"
        "    QtWebEngineWidgets = None\n"
        f"from {QT_COMPAT_MODULE} import QtWidgets\n",
        encoding="utf-8",
    )

    required, optional = qt_prune.qt_module_usage(source)

    assert required == {"QtWidgets"}
    assert optional == {"QtWebEngineCore", "QtWebEngineWidgets"}


def test_an_unconditional_import_wins_over_a_guarded_one(tmp_path):
    """One hard import anywhere makes the module required, whatever else guards it."""
    from ai_upper import qt_prune

    source = tmp_path / "src"
    source.mkdir()
    (source / "optional.py").write_text(
        "try:\n"
        f"    from {QT_COMPAT_MODULE} import QtGui\n"
        "except ImportError:\n"
        "    QtGui = None\n",
        encoding="utf-8",
    )
    (source / "required.py").write_text(f"from {QT_COMPAT_MODULE} import QtGui\n", encoding="utf-8")

    required, optional = qt_prune.qt_module_usage(source)

    assert required == {"QtGui"}
    assert optional == set()


def test_a_bare_except_hides_a_failed_import_just_as_well(tmp_path):
    """``except:`` and ``except Exception:`` protect the import too.

    Only the try body is protected: an import in the handler body runs when the
    try body failed, and is not caught by the same statement.
    """
    from ai_upper import qt_prune

    source = tmp_path / "src"
    source.mkdir()
    (source / "window.py").write_text(
        "try:\n"
        f"    from {QT_COMPAT_MODULE} import QtGui\n"
        "except Exception:\n"
        f"    from {QT_COMPAT_MODULE} import QtCore\n",
        encoding="utf-8",
    )

    required, optional = qt_prune.qt_module_usage(source)

    assert required == {"QtCore"}
    assert optional == {"QtGui"}


def test_the_application_no_longer_names_qt_webengine():
    """Pin the product contract this scanner has to agree with.

    The only UI is the QML shell + ``QTextDocument``, so nothing under
    ``app/src`` may import a WebEngine module any more — neither hard nor
    guarded. ``QtWebChannel`` must not be required either: it was pulled in by
    the deleted QWebChannel bridge, ``PySide6-Essentials`` does not ship it, and
    the pinned dependency is Essentials. The QML modules the shell really uses
    stay pinned in the same assertion, so this cannot quietly become vacuous.
    """
    from ai_upper import qt_prune

    required, optional = qt_prune.qt_module_usage()

    webengine = {"QtWebEngineCore", "QtWebEngineWidgets", "QtWebEngineQuick"}
    assert not (webengine & required)
    assert not (webengine & optional)
    assert "QtWebChannel" not in required
    assert {"QtCore", "QtGui", "QtQml", "QtQuick"} <= required


def test_runtime_closure_skips_only_the_optional_module_the_wheel_lacks(tmp_path, monkeypatch, capsys):
    """Required modules are still hard; a missing optional one is reported.

    Both halves matter. Failing on the optional module reproduces the arm64
    failure; silently ignoring a missing *required* module would prune the
    payload down to modules that are not there and only break at runtime.
    """
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = site / "PySide6"
    pyside.mkdir(parents=True)
    (pyside / "__init__.py").write_text("", encoding="utf-8")
    (pyside / "QtCore.py").write_text("", encoding="utf-8")
    (pyside / "QtWidgets.py").write_text("import PySide6.QtCore\n", encoding="utf-8")
    (pyside / "QtWebChannel.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(qt_prune, "_native_runtime_python", lambda target: Path(sys.executable))

    closure = qt_prune._runtime_closure(
        site,
        TARGETS["macos-arm64"],
        {"QtWidgets"},
        {"QtWebChannel", "QtWebEngineCore"},
    )

    assert closure == {"QtWidgets", "QtCore", "QtWebChannel"}
    out = capsys.readouterr().out
    assert "QtWebEngineCore" in out, "an optional module missing from the wheel must be reported"
    assert "QtWebChannel" not in out.split("has no", 1)[1].split(";", 1)[0]


def test_runtime_closure_still_errors_for_a_missing_required_module(tmp_path, monkeypatch):
    from ai_upper import qt_prune

    site = tmp_path / "site-packages"
    pyside = site / "PySide6"
    pyside.mkdir(parents=True)
    (pyside / "__init__.py").write_text("", encoding="utf-8")
    (pyside / "QtCore.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(qt_prune, "_native_runtime_python", lambda target: Path(sys.executable))

    with pytest.raises(RuntimeError, match="QtWebEngineCore"):
        qt_prune._runtime_closure(site, TARGETS["macos-arm64"], {"QtWebEngineCore"})


# ── QML 保留 ──────────────────────────────────────────────────────────────
# 应用只把 ``.qml`` 当资源加载时，``app/src`` 的 Python import 里没有一行
# ``QtQml``/``QtQuick``；旧判定只看那个集合，于是整棵 ``qml`` 树、qml 插件的
# 原生库和 shiboken 的 QML bridge 全被删掉，产物启动时 QML 引擎报
# "module is not installed"，窗口空白。下面的用例把这条判定锁住。

QMLDIR = """module {module}
linktarget Qt6::{plugin}
plugin {plugin}
{extra}depends QtQuick auto
"""


def _write_qml_module(root: Path, module: str, plugin: str, extra: str = "") -> Path:
    directory = root.joinpath(*module.split("."))
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "qmldir").write_text(
        QMLDIR.format(module=module, plugin=plugin, extra=extra), encoding="utf-8"
    )
    _touch(directory / ("lib%s.so" % plugin))
    return directory


def _fake_qml_tree(pyside: Path) -> None:
    """A QtQuick + QtQuick.Controls tree shipping styles and tooling nobody imports."""
    root = pyside / "Qt" / "qml"
    _write_qml_module(root, "QtQuick", "qtquick2plugin")
    _write_qml_module(root, "QtQuick.Templates", "qtquicktemplates2plugin")
    _write_qml_module(
        root,
        "QtQuick.Controls",
        "qtquickcontrols2plugin",
        extra=(
            "import QtQuick.Controls.Basic auto\n"
            "optional import QtQuick.Controls.Material auto\n"
            "optional import QtQuick.Controls.Fusion auto\n"
        ),
    )
    _write_qml_module(
        root,
        "QtQuick.Controls.Basic",
        "qtquickcontrols2basicstyleplugin",
        extra="depends QtQuick.Templates auto\n",
    )
    # optional import: only a QML file that names it may pull it in.
    _write_qml_module(root, "QtQuick.Controls.Material", "qtquickcontrols2materialstyleplugin")
    _write_qml_module(root, "QtQuick.Controls.Fusion", "qtquickcontrols2fusionstyleplugin")
    # Windows only: the platform default style there. Present in the tree on
    # every platform so the "kept only where the platform picks it" case is real.
    _write_qml_module(root, "QtQuick.Controls.Windows", "qtquickcontrols2windowsstyleplugin")
    # tooling: never loaded by a running application.
    _write_qml_module(root, "QtQuick.Shapes", "qmlshapesplugin")
    _touch(root / "QtQuick" / "tooling" / "libquicktoolingplugin.so")
    (root / "QtQuick" / "tooling" / "Inspector.qml").write_text(
        "import QtQuick\nimport QtQuick.Shapes\nItem { }\n", encoding="utf-8"
    )


def _qml_dependencies(path: Path) -> list[str]:
    return {
        "libqtquick2plugin.so": ["libQt6Quick.so.6", "libQt6Qml.so.6"],
        "libqtquicktemplates2plugin.so": ["libQt6QuickTemplates2.so.6", "libQt6Qml.so.6"],
        "libqtquickcontrols2plugin.so": ["libQt6QuickControls2.so.6", "libQt6QuickTemplates2.so.6"],
        "libqtquickcontrols2basicstyleplugin.so": ["libQt6QuickControls2Basic.so.6"],
        "QtQml.abi3.so": ["libQt6Qml.so.6"],
    }.get(path.name, [])


def _qml_wheel(tmp_path: Path) -> tuple[Path, Path]:
    site = tmp_path / "site-packages"
    pyside = site / "PySide6"
    _touch(pyside / "QtQml.abi3.so")
    for name in ("Quick", "Qml", "QuickControls2", "QuickTemplates2", "QuickControls2Basic"):
        _touch(pyside / "Qt" / "lib" / ("libQt6%s.so.6" % name))
    _touch(pyside / "libpyside6qml.abi3.6.11.dylib")
    _touch(pyside / "Qt" / "plugins" / "platforms" / "libqoffscreen.dylib")
    return site, pyside


def _qml_source(tmp_path: Path, text: str) -> Path:
    source = tmp_path / "src"
    source.mkdir(parents=True, exist_ok=True)
    (source / "Main.qml").write_text(text, encoding="utf-8")
    return source


MAIN_QML = "import QtQuick\nimport QtQuick.Controls\nApplicationWindow { }\n"


def test_qml_sources_are_scanned_from_the_application_tree(tmp_path):
    from ai_upper import qt_prune

    source = _qml_source(tmp_path, MAIN_QML)
    assert qt_prune.qml_sources_present(source) is True
    assert qt_prune.qml_imports(source) == {"QtQuick", "QtQuick.Controls"}
    # QtQuick.Controls 由 Qt6QuickControls2 提供，QtQuick 由 Qt6Quick 提供。
    assert {"QtQuick", "QtQml", "QtQuickControls2"} <= qt_prune.qml_required_modules(source)
    # 没有 .qml 的应用照旧不保留 QML 运行时。
    empty = tmp_path / "empty"
    empty.mkdir()
    assert qt_prune.qml_sources_present(empty) is False
    assert qt_prune.qml_required_modules(empty) == set()


def test_prune_keeps_the_qml_runtime_for_a_resource_only_qml_app(tmp_path, monkeypatch):
    from ai_upper import qt_prune

    site, pyside = _qml_wheel(tmp_path)
    _fake_qml_tree(pyside)
    monkeypatch.setattr(qt_prune, "dependency_names", _qml_dependencies)
    source = _qml_source(tmp_path, MAIN_QML)

    # Python 源码只 import 了 QtCore，QML 用到的模块一个都没写进 Python。
    counters = prune(site, TARGETS["macos-arm64"], {"QtCore"}, source_root=source)

    assert counters and counters["bytes"] > 0
    tree = pyside / "Qt" / "qml"
    # 保住：应用 import 的模块、它的传递依赖，以及加载它们所需的本机库
    for module in ("QtQuick", "QtQuick.Templates", "QtQuick.Controls", "QtQuick.Controls.Basic"):
        assert tree.joinpath(*module.split(".")).is_dir(), module
    assert (pyside / "Qt" / "lib" / "libQt6Quick.so.6").exists()
    assert (pyside / "Qt" / "lib" / "libQt6QuickControls2.so.6").exists()
    assert (pyside / "Qt" / "lib" / "libQt6QuickTemplates2.so.6").exists()
    assert (pyside / "Qt" / "lib" / "libQt6QuickControls2Basic.so.6").exists()
    # shiboken 的 QML bridge 是 QML 包装模块的运行时依赖
    assert (pyside / "libpyside6qml.abi3.6.11.dylib").exists()
    # QtQml 包装模块也只由 .qml 的 import 推出来，Python 侧没有 import 过它
    assert (pyside / "QtQml.abi3.so").exists()
    # 删掉：没被 import 的样式和 tooling 插件
    assert not (tree / "QtQuick" / "Controls" / "Fusion").exists()
    assert not (tree / "QtQuick" / "Controls" / "Material").exists()
    assert not (tree / "QtQuick" / "tooling").exists()
    # tooling 里的 .qml 写了 Shapes，但只有 Designer 会加载它：不能因此保留
    assert not (tree / "QtQuick" / "Shapes").exists()


def test_prune_still_drops_the_qml_tree_without_qml_sources(tmp_path, monkeypatch):
    """反向：没有 ``.qml`` 的应用不许因为 QML 的存在而变大。"""
    from ai_upper import qt_prune

    site, pyside = _qml_wheel(tmp_path)
    _fake_qml_tree(pyside)
    monkeypatch.setattr(qt_prune, "dependency_names", _qml_dependencies)
    empty = tmp_path / "src"
    empty.mkdir()

    prune(site, TARGETS["macos-arm64"], {"QtCore"}, source_root=empty)

    assert not (pyside / "Qt" / "qml").exists()
    assert not (pyside / "libpyside6qml.abi3.6.11.dylib").exists()


def test_prune_drops_the_qml_tree_when_the_python_import_is_absent_too(tmp_path, monkeypatch):
    """反向：既没有 ``.qml`` 也没有 QML 包装模块时，树整个消失。"""
    from ai_upper import qt_prune

    site, pyside = _qml_wheel(tmp_path)
    _fake_qml_tree(pyside)
    monkeypatch.setattr(qt_prune, "dependency_names", _qml_dependencies)
    empty = tmp_path / "src"
    empty.mkdir()

    prune(site, TARGETS["macos-arm64"], {"QtCore"}, source_root=empty)

    assert not (pyside / "Qt" / "qml").exists()
    assert not (pyside / "Qt" / "lib" / "libQt6Quick.so.6").exists()


def test_qml_optional_imports_are_only_kept_when_used(tmp_path, monkeypatch):
    """``optional import`` 只在应用的 ``.qml`` 真的写了那个模块时才保留。"""
    from ai_upper import qt_prune

    site, pyside = _qml_wheel(tmp_path)
    _fake_qml_tree(pyside)
    monkeypatch.setattr(qt_prune, "dependency_names", _qml_dependencies)
    source = _qml_source(
        tmp_path,
        "import QtQuick\nimport QtQuick.Controls\nimport QtQuick.Controls.Material\nItem { }\n",
    )

    prune(site, TARGETS["macos-arm64"], {"QtQml"}, source_root=source)

    assert (pyside / "Qt" / "qml" / "QtQuick" / "Controls" / "Material").is_dir()
    assert not (pyside / "Qt" / "qml" / "QtQuick" / "Controls" / "Fusion").exists()


def test_the_platform_default_controls_style_is_not_optional(tmp_path, monkeypatch):
    """引擎自己挑的样式模块必须保留——它不在任何 ``.qml`` 的 import 里。

    Qt 6 的 Controls 按平台挑样式（Qt 文档：Linux → Fusion、Windows →
    Windows），应用只写 ``import QtQuick.Controls``。只跟 ``.qml`` 的 import
    走，Linux 产物加载根组件时就会因 ``module "QtQuick.Controls.Fusion" is
    not installed`` 得到空窗口；这是真实 wheel 上实测到的失败。
    """
    from ai_upper import qt_prune

    site, pyside = _qml_wheel(tmp_path)
    _fake_qml_tree(pyside)
    monkeypatch.setattr(qt_prune, "dependency_names", _qml_dependencies)
    source = _qml_source(tmp_path, MAIN_QML)

    prune(site, TARGETS["linux-arm64"], {"QtCore"}, source_root=source)

    controls = pyside / "Qt" / "qml" / "QtQuick" / "Controls"
    assert (controls / "Fusion").is_dir()
    assert (controls / "Fusion" / "libqtquickcontrols2fusionstyleplugin.so").is_file()
    # Windows 的默认样式不因 Linux 构建而保留，其余 optional 样式照旧裁掉。
    assert not (controls / "Windows").exists()
    assert not (controls / "Material").exists()


def test_the_windows_default_style_follows_the_target(tmp_path, monkeypatch):
    """同一份源码按 Windows 打包时，保留的是 Windows 样式而不是 Fusion。"""
    from ai_upper import qt_prune

    site, pyside = _qml_wheel(tmp_path)
    _fake_qml_tree(pyside)
    monkeypatch.setattr(qt_prune, "dependency_names", _qml_dependencies)
    source = _qml_source(tmp_path, MAIN_QML)

    prune(site, TARGETS["windows-x86_64"], {"QtCore"}, source_root=source)

    controls = pyside / "Qt" / "qml" / "QtQuick" / "Controls"
    assert (controls / "Windows").is_dir()
    assert not (controls / "Fusion").exists()


def test_an_app_without_controls_keeps_no_style(tmp_path):
    """只 ``import QtQuick`` 的应用不会实例化样式：不能顺手牵一个进来。"""
    from ai_upper import qt_prune

    assert qt_prune.qml_implicit_modules(set(), TARGETS["linux-arm64"]) == set()
    assert qt_prune.qml_implicit_modules({"QtQuick"}, TARGETS["linux-arm64"]) == set()
    assert qt_prune.qml_implicit_modules({"QtQuick.Controls"}, TARGETS["linux-arm64"]) == {
        "QtQuick.Controls.Fusion"
    }
    # macOS 的默认样式编在 Controls 插件里，没有模块目录可留。
    assert qt_prune.qml_implicit_modules({"QtQuick.Controls"}, TARGETS["macos-arm64"]) == set()
