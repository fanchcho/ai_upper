"""Keep only the Qt payload the application actually imports.

A PySide6 install ships every Qt module, and QtWebEngineCore alone is roughly
450 MB of Chromium. Other packagers look smaller because they only bundle the Qt
modules the application imports; ai_upper does the same here:

1. read the Qt modules ``app/src`` imports, whichever binding it names and
   whether it names the binding directly or through ``utils.qt_compat``;
2. ask the target runtime which modules that pulls in transitively;
3. drop every other Qt wrapper module, Qt library and Qt plugin category.

The result is validated by the build's own Qt smoke test, which imports the
application and opens a real window in the packaged bundle.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from .config import APP, Target, host_target, optimize_config, runtime_executable, runtime_provider
from .native.deps import dependency_names

WRAPPER_SUFFIXES = {".so", ".pyd"}

# Every supported Qt binding. The pruning pipeline detects which one the
# application uses from its imports and site-packages layout, then applies the
# same module/plugin/translation policy per binding.
BINDINGS = ("PySide6", "PyQt6", "PySide2", "PyQt5")

# The binding-neutral shim the application imports Qt through. It forwards every
# ``Qt<Module>`` name it is asked for to the detected binding, so an import from
# it names a Qt module exactly as directly as a binding import does. Miss this
# and the scanner sees no Qt usage at all, which silently keeps the full 665 MB
# payload instead of failing. ``test_qt_compat_module_exists`` keeps this name
# and the application module in step.
QT_COMPAT_MODULE = "utils.qt_compat"

# A Qt submodule name: QtCore, QtWidgets, QtNetwork. Qt class names do not
# match — QtCore.Qt and QApplication are not modules.
QT_SUBMODULE = re.compile(r"^Qt[A-Za-z0-9_]+$")


def detect_binding(site: Path) -> str | None:
    """The Qt binding present in this site-packages, in preference order."""
    for binding in BINDINGS:
        if (site / binding).is_dir():
            return binding
    return None


# Handlers that turn a failed import into something the application carries on
# without. ``except ImportError`` is what the sources use; the broader names are
# included because a bare ``except:`` and ``except Exception:`` swallow the same
# failure, so the import is just as optional to the running program.
_IMPORT_ERROR_HANDLERS = {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"}


def _catches_import_error(handler: ast.ExceptHandler) -> bool:
    """Whether this handler lets a failing import go by."""
    node = handler.type
    if node is None:  # bare except
        return True
    names = []
    if isinstance(node, ast.Tuple):
        names = [elt.id for elt in node.elts if isinstance(elt, ast.Name)]
    elif isinstance(node, ast.Name):
        names = [node.id]
    return any(name in _IMPORT_ERROR_HANDLERS for name in names)


def _imported_paths(path: Path) -> tuple[set[str], set[str]]:
    """Dotted import paths in this source file, split by optionality.

    ``import a.b`` contributes ``a.b``; ``from a.b import c`` contributes both
    ``a.b`` and ``a.b.c``, because that form imports the module ``c`` when one
    exists. Reading the import statements instead of matching text keeps a
    parenthesised multi-line import from being invisible.

    An import inside a ``try`` whose handlers catch ``ImportError`` is
    *optional*: the application is written to run without it. PySide6's
    win_arm64 wheels ship no QtWebEngineCore at all, and ``web_shell_window``
    imports it exactly that way, so treating every import as mandatory made the
    packaging layer reject a payload the application itself accepts.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    except SyntaxError as exc:
        raise RuntimeError(f"Qt pruning: cannot parse {path}: {exc}") from exc

    required: set[str] = set()
    optional: set[str] = set()

    def record(node, guarded: bool) -> None:
        target = optional if guarded else required
        if isinstance(node, ast.Import):
            target.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            target.add(node.module)
            target.update("%s.%s" % (node.module, alias.name) for alias in node.names)

    def visit(node, guarded: bool) -> None:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            record(node, guarded)
            return
        if isinstance(node, ast.Try):
            # Only the try body is protected; a failing import in a handler or
            # in ``else``/``finally`` is not caught by this statement.
            protected = guarded or any(_catches_import_error(h) for h in node.handlers)
            for child in node.body:
                visit(child, protected)
            for child in node.orelse + node.finalbody:
                visit(child, guarded)
            for handler in node.handlers:
                for child in handler.body:
                    visit(child, guarded)
            return
        for child in ast.iter_child_nodes(node):
            visit(child, guarded)

    visit(tree, False)
    return required, optional


def _qt_module_of_import(dotted: str) -> str | None:
    """The Qt submodule an imported dotted path refers to, or None.

    Both shapes collapse to the same answer: ``PySide6.QtWidgets`` names the
    submodule directly, and ``utils.qt_compat.QtWidgets`` names it through the
    shim. Everything after the first match is a class or attribute, not a
    module.
    """
    parts = dotted.split(".")
    if parts[0] == QT_COMPAT_MODULE.split(".")[0] and ".".join(parts[:2]) == QT_COMPAT_MODULE:
        candidates = parts[2:]
    elif parts[0] in BINDINGS:
        candidates = parts[1:]
    else:
        return None
    for part in candidates:
        if QT_SUBMODULE.match(part):
            return part
    return None


# ── QML 源码：静态 import 扫描看不见的第二条依赖来源 ───────────────────────
# 应用既可能通过 Python 的 ``QmlElement``/``QQmlApplicationEngine`` 使用 QML，
# 也可能只把 ``.qml`` 当资源加载；后者在 ``app/src`` 的 Python import 里一行都
# 看不见。不读 ``.qml`` 的 import 就会把整棵 Qt QML 运行时裁掉，产物启动时
# QML 引擎「module is not installed」。所以 QML 的存在与依赖都要单独扫。
QML_SUFFIX = ".qml"
QML_IMPORT = re.compile(r"^\s*import\s+([A-Za-z_][A-Za-z0-9_.]*)", re.MULTILINE)
# QML 模块名 → 它加载的 Qt 库模块名。两者并不总同名：``import QtQuick.Controls``
# 的真实插件链接的是 Qt6QuickControls2 + Qt6QuickTemplates2，而 ``QtQuick.Window``
# 只是 ``QtQuick`` 的一部分。映射错了库仍会被裁掉，QML 引擎照样加载失败。
QML_MODULE_LIBRARIES: dict[str, tuple[str, ...]] = {
    "QtQuick": ("QtQuick", "QtQml"),
    "QtQuick.Window": ("QtQuick", "QtQml"),
    "QtQuick.Layouts": ("QtQuickLayouts", "QtQuick", "QtQml"),
    "QtQuick.Templates": ("QtQuickTemplates2", "QtQuick", "QtQml"),
    "QtQuick.Controls": ("QtQuickControls2", "QtQuickTemplates2", "QtQuickControls2Impl", "QtQuick", "QtQml"),
    "QtQuick.Controls.Basic": ("QtQuickControls2Basic", "QtQuickControls2Impl", "QtQuickTemplates2", "QtQuick", "QtQml"),
    "QtQuick.Controls.Fusion": ("QtQuickControls2Fusion", "QtQuickControls2Impl", "QtQuickTemplates2", "QtQuick", "QtQml"),
    "QtQuick.Controls.Material": ("QtQuickControls2Material", "QtQuickControls2Impl", "QtQuickTemplates2", "QtQuick", "QtQml"),
    "QtQuick.Controls.Universal": ("QtQuickControls2Universal", "QtQuickControls2Impl", "QtQuickTemplates2", "QtQuick", "QtQml"),
    "QtQuick.Dialogs": ("QtQuickDialogs2", "QtQuickTemplates2", "QtQuick", "QtQml"),
    "QtQuick.Shapes": ("QtQuickShapes", "QtQuick", "QtQml"),
    "QtQuick.Effects": ("QtQuickEffects", "QtQuick", "QtQml"),
    "QtQuick.Particles": ("QtQuickParticles", "QtQuick", "QtQml"),
    "QtQuick.Timeline": ("QtQuickTimeline", "QtQuick", "QtQml"),
    "QtQuick.VectorImage": ("QtQuickVectorImage", "QtQuick", "QtQml"),
    "QtQuick.LocalStorage": ("QtQmlLocalStorage", "QtQuick", "QtQml"),
    "QtQuick.Pdf": ("QtPdfQuick", "QtPdf", "QtQuick", "QtQml"),
    "QtQml": ("QtQml",),
    "QtQml.Models": ("QtQmlModels", "QtQml"),
    "QtQml.WorkerScript": ("QtQmlWorkerScript", "QtQml"),
    "QtQml.StateMachine": ("QtQmlStateMachine", "QtQml"),
    "QtTest": ("QtTest", "QtQuick", "QtQml"),
}


def qml_source_roots(source_root: Path | None = None) -> tuple[Path, ...]:
    """Directories that may hold the application's own ``.qml`` files.

    ``app/src`` catches QML compiled into the Python tree; ``app/assets/qml``
    and ``app/resources`` are the two trees ``package.py`` copies into the
    bundle, so a resource-only QML application is covered too.
    """
    root = source_root or (APP / "src")
    app = root.parent
    candidates = (root, app / "assets" / "qml", app / "resources")
    return tuple(path for path in candidates if path.is_dir())


def qml_sources(source_root: Path | None = None) -> list[Path]:
    """Every ``.qml`` file the application ships."""
    found: list[Path] = []
    for base in qml_source_roots(source_root):
        found.extend(sorted(base.rglob(f"*{QML_SUFFIX}")))
    return found


def qml_sources_present(source_root: Path | None = None) -> bool:
    """Whether the application ships QML at all (the QML runtime is then needed)."""
    return bool(qml_sources(source_root))


def qml_imports(source_root: Path | None = None) -> set[str]:
    """QML modules the application's ``.qml`` files import."""
    modules: set[str] = set()
    for path in qml_sources(source_root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in QML_IMPORT.finditer(text):
            name = match.group(1)
            if name.startswith("Qt"):
                modules.add(name)
    return modules


def qml_required_modules(source_root: Path | None = None) -> set[str]:
    """Qt library modules the application's QML imports need at runtime.

    An import the mapping does not know keeps its own top-level name: a QML
    module ``QtQuick3D`` is served by ``QtQuick3D``, and guessing a rename for
    it would drop the library it actually links.
    """
    required: set[str] = set()
    for name in qml_imports(source_root):
        required.update(QML_MODULE_LIBRARIES.get(name, (name.split(".")[0],)))
    return required


# QML 运行时是按 import 名 **动态** 加载模块的：`.qml` 里写的是模块名，真正
# dlopen 的是 `qml/<dir>/lib<plugin>.so`，两者靠 `qmldir` 里的
# ``module``/``plugin``/``linktarget`` 对上号。所以「保住哪些 QML 模块」只能
# 从 `qmldir` 的依赖声明和模块内 `.qml` 的 import 推出来，不能靠库名猜。
QML_TOOLING_DIRECTORIES = frozenset({"designer", "tooling"})
QML_QMLDIR_MODULE = re.compile(r"^\s*module\s+([A-Za-z_][A-Za-z0-9_.]*)\s*$", re.MULTILINE)
# ``import X`` / ``depends X`` 是运行期真实依赖；``optional import`` 是 Qt 只在
# 应用显式选中该样式时才加载的变体（QtQuick.Controls 的 Fusion/Material/…），
# 跟着 optional 走就一个样式都裁不掉，FluentWinUI3 一个就有 8 MB。
QML_QMLDIR_IMPORT = re.compile(
    r"^\s*(?:(optional|default)\s+)?(?:import|depends)\s+([A-Za-z_][A-Za-z0-9_.]*)",
    re.MULTILINE,
)
QML_BINARY_SUFFIXES = (".so", ".dylib", ".dll")


def qml_module_directories(layout: "_QtLayout") -> dict[str, Path]:
    """``module name -> directory`` for the QML modules the installed Qt ships.

    ``designer`` and ``tooling`` subtrees carry a ``qmldir`` too, but only Qt
    Design Studio and the QML linter load them; an application never does.
    """
    index: dict[str, Path] = {}
    root = layout.qml
    if not root.is_dir():
        return index
    for qmldir in sorted(root.rglob("qmldir")):
        if QML_TOOLING_DIRECTORIES & set(qmldir.relative_to(root).parts[:-1]):
            continue
        try:
            text = qmldir.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        match = QML_QMLDIR_MODULE.search(text)
        if match:
            index.setdefault(match.group(1), qmldir.parent)
    return index


def _qml_imports_in(directory: Path) -> set[str]:
    """Qt module names the ``.qml`` files under ``directory`` import.

    Tooling subtrees (``designer``/``tooling``) are skipped: they import modules
    only the Designer previewer loads, and following them would keep the whole
    Controls designer alongside the runtime styles.
    """
    names: set[str] = set()
    for path in sorted(directory.rglob(f"*{QML_SUFFIX}")):
        if QML_TOOLING_DIRECTORIES & set(path.relative_to(directory).parts[:-1]):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in QML_IMPORT.finditer(text):
            if match.group(1).startswith("Qt"):
                names.add(match.group(1))
    return names


def qml_shipped_modules(layout: "_QtLayout", imported: set[str]) -> dict[str, Path]:
    """QML module directories a running application needs for ``imported``.

    The closure follows ``qmldir`` dependencies and the imports of each module's
    own ``.qml`` files. ``optional import`` is skipped: Qt loads those only when
    the application selects the style variant, so following them keeps every
    Controls style (8 MB of FluentWinUI3 alone) alive.
    """
    tree = qml_module_directories(layout)
    keep: dict[str, Path] = {}
    queue = [name for name in imported if name in tree]
    while queue:
        name = queue.pop()
        if name in keep:
            continue
        directory = tree[name]
        keep[name] = directory
        try:
            text = (directory / "qmldir").read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        needed = {
            dependency
            for keyword, dependency in QML_QMLDIR_IMPORT.findall(text)
            if keyword != "optional"
        }
        needed |= _qml_imports_in(directory)
        queue.extend(sorted(needed - set(keep)))
    return keep


def prune_qml_tree(layout: "_QtLayout", imported: set[str], drop) -> set[Path]:
    """Drop QML modules nothing imports; return the module directories kept.

    Returns an empty set (and drops nothing) when the tree ships none of the
    imported modules, so the caller can decide to drop the tree as a whole.

    A directory is a QML module exactly when it holds a ``qmldir``; the module
    directories nest (``QtQuick/Controls`` contains the ``Basic``, ``Fusion``,
    ``Material`` … styles as child modules), so each level is judged on its own
    and a kept module does not keep the styles beside it. Directories that only
    group modules (``QtQuick``) survive because a kept module is still inside
    them; they are dropped once they hold nothing.
    """
    keep = set(qml_shipped_modules(layout, imported).values())
    root = layout.qml
    if not keep or not root.is_dir():
        return keep
    for directory in sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        if directory in keep:
            continue
        if directory.name in QML_TOOLING_DIRECTORIES or (directory / "qmldir").is_file():
            drop(directory)
    # Namespace directories whose modules all went are dead weight; empty them
    # out from the leaves up so no half-pruned skeleton is left behind.
    for directory in sorted(
        (path for path in root.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        if directory not in keep and not any(directory.iterdir()):
            drop(directory)
    return keep


def qml_plugin_binaries(directories) -> list[Path]:
    """Native QML plugin libraries inside the kept module directories."""
    found: list[Path] = []
    for directory in sorted(directories):
        for path in sorted(directory.rglob("*")):
            if path.is_file() and (path.suffix in QML_BINARY_SUFFIXES or ".so." in path.name):
                found.append(path)
    return found


# Plugin categories every Qt application needs at runtime.
BASE_PLUGIN_CATEGORIES = {
    "platforms", "styles", "imageformats", "iconengines",
    "platforminputcontexts", "generic", "networkinformation",
}
# Plugin categories that only matter for specific Qt modules.
MODULE_PLUGIN_CATEGORIES = {
    "QtNetwork": {"tls"},
    "QtSql": {"sqldrivers"},
    "QtMultimedia": {"multimedia"},
    "QtLocation": {"position", "geoservices"},
    "QtSerialBus": {"canbus"},
    "QtSensors": {"sensors"},
    "QtTextToSpeech": {"texttospeech"},
    "QtScxml": {"scxmldatamodel"},
    "QtDesigner": {"designer"},
    "QtWebEngineCore": {"webview"},
    "QtQuick": {"renderplugins"},
    "Qt3DRender": {"sceneparsers", "geometryloaders", "renderers", "assetimporters"},
    "QtQuick3DRuntimeRender": {"sceneparsers", "geometryloaders", "renderers", "assetimporters"},
}
# Developer tooling that is never part of a runtime payload. Missing entries
# are ignored, so the list covers the union of the supported platforms.
TOOLING_ENTRIES = {
    "Assistant.app", "Designer.app", "Linguist.app",
    "assistant", "designer", "linguist",
    "qmlls", "qmllint", "qmlformat", "qmlimportscanner", "qmltyperegistrar",
    "qmlcachegen", "qmlscene", "qmltestrunner", "qmlprofiler", "qmlpreview",
    "qmlplugindump", "lupdate", "lrelease", "lconvert",
    "balsam", "balsamui", "qsb", "svgtoqml", "uic", "rcc", "qtdiag", "qtpaths",
    "typesystems",
}
QML_MODULE_PREFIXES = ("QtQml", "QtQuick")
# Plugins worth keeping even though they pull in an extra Qt module: SVG icons
# are ubiquitous in modern applications.
PLUGIN_KEEP_EXCEPTIONS = ("qsvg", "qsvgicon")
# Translation families that belong to developer tooling, never to a running app.
TOOLING_TRANSLATION_PREFIXES = ("assistant_", "designer_", "linguist_", "qt_help_")
# Chromium's own UI strings live in ``translations/qtwebengine_locales``. They
# do not match the ``qt_``/``qtbase_`` shape of Qt's translations, so the
# translation sweep treated the whole directory as tooling and removed it from
# every bundle that shipped QtWebEngineCore. It belongs to that module the same
# way ``resources`` does: a bundle without it still renders a page, but its
# helper process cannot find the pack for the user's locale and every launch
# logs the failure.
WEBENGINE_LOCALES_DIR = "qtwebengine_locales"
# Chromium falls back to this pack when the requested locale is absent, so it
# survives any locale allowlist.
WEBENGINE_FALLBACK_LOCALE = "en-US"
# Images Qt loads by name rather than through an import. The dependency closure
# can never see them, so the reachability rule would delete them: the software
# OpenGL fallback is the one that matters, because a machine without a usable
# GL driver still has to be able to start the application.
# The software OpenGL fallback is loaded by name at runtime, never through an
# import table, so the reachability rule can never see it. A machine without a
# usable GL driver needs it to start the GUI; an application that does not want
# to carry the ~20 MB DLL can opt out with ``qt_software_opengl = false``.
SOFTWARE_OPENGL_DLL = "opengl32sw.dll"
PAYLOAD_KEEP_NAMES = frozenset({SOFTWARE_OPENGL_DLL})

# Platform plugins a desktop application may need, named by Qt's plugin base
# name (the leading ``q``/``lib`` and the extension are ignored when matching).
# One list covers every supported host: a wheel only ships the plugins for its
# own platform, so this keeps Windows, Linux and macOS payloads correct without
# host-specific rules. ``offscreen`` is the plugin the headless smoke test uses.
DEFAULT_PLATFORM_PLUGINS = ("windows", "cocoa", "xcb", "wayland", "offscreen")

# MSVC runtime DLLs shipped by the shiboken wheel for its C++ tooling. No Python
# extension in the bundle links them (they only reference each other), and the
# reference deployment omits them.
REDUNDANT_MSVC_RUNTIME = frozenset({"vcamp140.dll", "concrt140.dll", "vcomp140.dll"})

# Directories inside a binding package that belong to its development tooling,
# not to the runtime payload. PySide2 spells the documentation directory
# ``docs``; the PySide6 wheels ship ``doc`` on every platform. Headers and the
# CMake package files are build inputs too: no import, plugin or translation
# can load them at runtime.
BINDING_TOOLING_DIRECTORIES = ("docs", "doc", "scripts", "support")
BINDING_BUILD_DIRECTORIES = ("include", "lib")
SHIBOKEN_PACKAGES = {"PySide2": "shiboken2", "PySide6": "shiboken6"}


@dataclass(frozen=True)
class _QtLayout:
    """Where a Qt binding wheel keeps the parts of the Qt payload.

    The wheel flavours disagree, and every consumer of the payload has to agree
    with them:

    * POSIX PySide wheels (Linux, macOS) nest everything under ``PySide6/Qt``
      -- the libraries in ``Qt/lib``, plus ``plugins``, ``qml``,
      ``translations``, ``metatypes`` and ``libexec``.
    * PyQt wheels nest the same payload under ``PyQt6/Qt6`` (or
      ``PyQt5/Qt5``) on every platform, so the directory name follows the Qt
      major version rather than the host.
    * Windows PySide wheels put the Qt DLLs, the Python extension modules and
      the tooling directly in the package root and keep only ``plugins``,
      ``qml``, ``translations`` and ``metatypes`` beside them. There is no
      ``Qt`` directory at all, so the POSIX paths silently match nothing and
      pruning becomes a no-op.
    """

    root: Path
    """The directory holding ``plugins``, ``qml`` and the Qt libraries."""

    libraries: tuple[Path, ...]
    """Directories the reachability lookup indexes."""

    library_names: str | None
    """fnmatch pattern selecting the entries the reachability rule may delete.

    ``None`` means every entry, which is what the POSIX ``Qt/lib`` and
    ``Qt/bin`` directories hold. The Windows package root is not a library
    directory: it also contains the importable extension modules, the launcher
    helper and the packaging metadata, so only its DLLs are eligible.
    """

    tooling_suffixes: tuple[str, ...]
    """Suffixes the platform appends to the names in ``TOOLING_ENTRIES``."""

    plugins: Path
    qml: Path
    translations: Path
    metatypes: Path | None
    helpers: tuple[Path, ...]
    """Directories (POSIX ``Qt/libexec``) or files (Windows package root) that
    hold helper executables. They mix tooling with module helpers, so the
    reachability rule is applied per entry, not to the directory as a whole:
    see ``MODULE_HELPERS``."""

    qml_helpers: tuple[str, ...]
    """Glob patterns for shiboken's QML bridge library."""


# Helper executables that a *runtime* module runs as a separate process, and
# therefore has to ship beside it. ``QtWebEngineProcess`` is dlopen'd by
# QtWebEngineCore when the view attaches: a bundle that keeps the module but
# drops the helper starts, loads the page, and then renders nothing at all.
# Every other entry in ``libexec`` (rcc, uic, qmlcachegen, …) is build tooling
# and always goes.
MODULE_HELPERS = {"QtWebEngineProcess": "QtWebEngineCore"}


def _helper_owner(name: str) -> str | None:
    """The Qt module a helper executable serves, or None for plain tooling."""
    stem = Path(name).stem
    return MODULE_HELPERS.get(stem)


def _qt_payload_root(package: Path) -> Path | None:
    """The directory a binding keeps its Qt payload in, or None for the flat
    Windows PySide layout.

    PySide POSIX wheels use ``Qt``; PyQt wheels use ``Qt5``/``Qt6`` on every
    platform. Treating only ``Qt`` as nested made a PyQt POSIX tree look like a
    Windows one, so the plugin, QML and translation paths all pointed at
    directories that do not exist and pruning silently removed nothing.
    """
    for name in ("Qt", "Qt5", "Qt6"):
        candidate = package / name
        if candidate.is_dir():
            return candidate
    return None


def _qt_layout(pyside: Path, binding: str) -> _QtLayout:
    # The QML bridge helper name follows the binding: pyside6qml / pyside2qml
    # for the official bindings, qmlpy / qmlpy3 style for PyQt.
    if binding == "PySide2":
        qml_helpers = ("libpyside2qml*",)
    elif binding == "PyQt5":
        qml_helpers = ("qmlpy*",)
    elif binding == "PyQt6":
        qml_helpers = ("qmlpy*",)
    else:
        qml_helpers = ("libpyside6qml*",)
    nested = _qt_payload_root(pyside)
    if nested is not None:
        return _QtLayout(
            root=nested,
            libraries=tuple(path for path in (nested / "lib", nested / "bin") if path.is_dir()),
            library_names=None,
            tooling_suffixes=("",),
            plugins=nested / "plugins",
            qml=nested / "qml",
            translations=nested / "translations",
            metatypes=nested / "metatypes",
            helpers=(nested / "libexec",),
            qml_helpers=qml_helpers,
        )
    return _QtLayout(
        root=pyside,
        libraries=(pyside,),
        library_names="*.dll",
        tooling_suffixes=("", ".exe"),
        plugins=pyside / "plugins",
        qml=pyside / "qml",
        translations=pyside / "translations",
        metatypes=pyside / "metatypes",
        helpers=(pyside / "QtWebEngineProcess.exe",),
        qml_helpers=("pyside6qml.abi3.dll", "pyside6qml.abi3.lib") if binding == "PySide6" else qml_helpers,
    )


@dataclass(frozen=True)
class _QtPayloadOptions:
    """Optional Qt payload cuts, all opt-in through ``[tool.ai_upper.optimize]``.

    ``None`` in an allowlist means "keep everything", which keeps every default
    build byte-for-byte compatible with the previous policy. ``qt = "all"``
    still disables pruning entirely; these options refine what a pruned payload
    keeps.
    """

    software_opengl: bool = True
    locales: frozenset[str] | None = None
    image_formats: frozenset[str] | None = None
    platforms: frozenset[str] | None = frozenset(DEFAULT_PLATFORM_PLUGINS)

    @property
    def keep_names(self) -> frozenset[str]:
        return PAYLOAD_KEEP_NAMES if self.software_opengl else frozenset()


def _qt_option_list(value, name: str, default: tuple[str, ...] | None) -> frozenset[str] | None:
    """Parse ``"all"`` or an allowlist of names; ``None`` keeps everything."""
    if value is None:
        return frozenset(default) if default is not None else None
    if isinstance(value, str):
        text = value.strip()
        if text.lower() in {"all", "*"}:
            return None
        if not text:
            raise RuntimeError(f"[tool.ai_upper.optimize].{name} must not be empty")
        return frozenset({text})
    if isinstance(value, (list, tuple)):
        if not value or any(not isinstance(item, str) or not item.strip() for item in value):
            raise RuntimeError(
                f"[tool.ai_upper.optimize].{name} must be a non-empty array of strings"
            )
        return frozenset(item.strip() for item in value)
    raise RuntimeError(
        f"[tool.ai_upper.optimize].{name} must be 'all' or an array of strings"
    )


def _qt_option_bool(value, name: str, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise RuntimeError(f"[tool.ai_upper.optimize].{name} must be true or false")


def _payload_options() -> _QtPayloadOptions:
    """The configured optional Qt cuts, validated before a single file goes."""
    cfg = optimize_config()
    return _QtPayloadOptions(
        software_opengl=_qt_option_bool(cfg.get("qt_software_opengl"), "qt_software_opengl", True),
        locales=_qt_option_list(cfg.get("qt_locales"), "qt_locales", None),
        image_formats=_qt_option_list(cfg.get("qt_image_formats"), "qt_image_formats", None),
        platforms=_qt_option_list(cfg.get("qt_platforms"), "qt_platforms", DEFAULT_PLATFORM_PLUGINS),
    )


def _allowed_webengine_locale(name: str, allowed: frozenset[str] | None) -> bool:
    """Whether a Chromium locale pack (``en-US.pak``) serves a configured locale.

    Chromium spells locales ``zh-CN`` where Qt spells them ``zh_CN``, and the
    same allowlist has to cover both. A bare language (``zh``) keeps its
    regional variants, matching ``_allowed_locale``.
    """
    if allowed is None:
        return True
    locale = Path(name).stem
    if locale == WEBENGINE_FALLBACK_LOCALE:
        return True
    for pattern in allowed:
        token = pattern.strip().replace("-", "_")
        if any(char in token for char in "*?["):
            if fnmatch(locale, token.replace("_", "-")):
                return True
        elif locale.replace("-", "_") == token or locale.replace("-", "_").startswith(token + "_"):
            return True
    return False


def _plugin_name(name: str) -> str:
    """A Qt plugin name without its path, extension, ``lib`` prefix or ``q``.

    Qt spells the same plugin ``qwindows.dll`` on Windows, ``libqcocoa.dylib``
    on macOS and ``libqxcb.so`` on Linux. Normalizing all three shapes lets one
    allowlist drive every platform.
    """
    stem = Path(name).name
    lowered = stem.lower()
    for suffix in (".dll", ".dylib", ".so", ".pyd"):
        if lowered.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    lowered = stem.lower()
    if lowered.startswith("lib"):
        stem = stem[3:]
        lowered = lowered[3:]
    if lowered.startswith("q"):
        stem = stem[1:]
    return stem.lower()


def _allowed_plugin(name: str, allowed: frozenset[str] | None) -> bool:
    """Whether ``name`` matches an allowlist entry, with prefix matching.

    Prefix matching is what lets ``wayland`` cover ``qwayland-egl`` and
    ``qwayland-generic`` while still keeping the list readable. A glob entry is
    accepted as-is, so ``qt_image_formats = ["jp*"]`` also works.
    """
    if allowed is None:
        return True
    key = _plugin_name(name)
    for pattern in allowed:
        token = _plugin_name(pattern)
        if token and (fnmatch(key, token) or fnmatch(key, token + "*")):
            return True
    return False


def _translation_locale(name: str) -> str | None:
    """The locale part of ``qtbase_zh_CN.qm`` / ``qt_zh_CN.qm``."""
    stem = Path(name).stem
    for prefix in ("qtbase_", "qt_"):
        if stem.startswith(prefix):
            return stem[len(prefix):]
    return None


def _allowed_locale(name: str, allowed: frozenset[str] | None) -> bool:
    """Whether a translation file serves one of the configured locales.

    An exact locale (``zh_CN``) keeps only that variant; a bare language
    (``zh``) also keeps ``zh_TW`` and the other regional variants. A glob entry
    is matched against the locale itself.
    """
    if allowed is None:
        return True
    locale = _translation_locale(name)
    if not locale:
        return False
    for pattern in allowed:
        token = pattern.strip()
        if any(char in token for char in "*?["):
            if fnmatch(locale, token):
                return True
        elif locale == token or locale.startswith(token + "_"):
            return True
    return False


def qt_module_usage(source_root: Path | None = None) -> tuple[set[str], set[str]]:
    """Qt modules the application sources name, split into required and optional.

    "Optional" means every import of that module sits in a ``try`` that catches
    ``ImportError``: the application is written to start without it. A module
    imported unconditionally somewhere is required, whatever else guards it.
    """
    root = source_root or (APP / "src")
    required: set[str] = set()
    optional: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        hard, soft = _imported_paths(path)
        for dotted in hard:
            module = _qt_module_of_import(dotted)
            if module:
                required.add(module)
        for dotted in soft:
            module = _qt_module_of_import(dotted)
            if module:
                optional.add(module)
    return required, optional - required


def used_qt_modules(source_root: Path | None = None) -> set[str]:
    """Every Qt module referenced by the application's own Python sources."""
    required, optional = qt_module_usage(source_root)
    return required | optional


def _runtime_closure(site: Path, target: Target, modules: set[str], optional=()) -> set[str] | None:
    """Import the modules with the target runtime and return what it loaded.

    ``modules`` are required: a failure is an error. ``optional`` are the ones
    the application imports behind ``except ImportError``; each is imported
    best-effort -- when the wheel has it, its transitive closure is kept like
    any other module, and when the wheel does not (PySide6 ships no
    QtWebEngineCore for win_arm64), it is reported and skipped instead of
    failing a build whose product code already runs without it.

    ``None`` means the target interpreter cannot run on this host, so the
    closure is unknown and the caller keeps its requested modules untouched
    rather than guessing.

    An interpreter that does start and still fails a required import is
    reported as an error. Its partial closure is a trap: importing QtWidgets
    alone never mentions QtCore and QtGui, so the payload those two provide is
    deleted and the bundle only breaks in the packaged smoke run, far away from
    the cause.
    """
    python = _native_runtime_python(target)
    if python is None:
        return None
    binding = detect_binding(site) or "PySide6"
    script = (
        "import importlib, json, sys\n"
        f"result = {{'loaded': [], 'absent': []}}\n"
        f"for name in {sorted(modules)!r}:\n"
        f"    importlib.import_module('{binding}.' + name)\n"
        f"for name in {sorted(optional)!r}:\n"
        "    try:\n"
        f"        importlib.import_module('{binding}.' + name)\n"
        "    except ImportError:\n"
        "        result['absent'].append(name)\n"
        f"result['loaded'] = sorted(m for m in sys.modules if m.startswith('{binding}.'))\n"
        "print(json.dumps(result))\n"
    )
    # The probe has to import from the staged payload, and nothing else about
    # the child environment is this function's business. A hand-built
    # environment block is not a smaller version of the host's: on Windows the
    # target interpreter dies in preinit without SystemRoot
    # ("_Py_HashRandomization_Init: failed to get random numbers to initialize
    # Python"), so every Windows host build with qt = "imports" failed here
    # before the launcher was even configured. Inherit the host environment and
    # override only the two variables the probe actually needs, the way every
    # other subprocess in the build tool does.
    env = dict(os.environ)
    env["PYTHONPATH"] = str(site)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    probe = subprocess.run([str(python), "-c", script], capture_output=True, text=True, check=False, env=env)
    requested = ", ".join(sorted(modules)) or "(none)"
    if probe.returncode != 0:
        detail = probe.stderr.strip() or probe.stdout.strip() or "(no output)"
        raise RuntimeError(f"Qt pruning: {python} cannot import {requested}:\n{detail}")
    try:
        result = json.loads(probe.stdout.strip().splitlines()[-1])
        loaded = result["loaded"]
        absent = result["absent"]
    except (ValueError, IndexError, KeyError, TypeError):
        raise RuntimeError(f"Qt pruning: {python} printed no {binding} module list for {requested}")
    if absent:
        # Say it out loud. An optional module the wheel lacks is a platform gap
        # the bundle carries, not something to discover at runtime.
        print(
            "Qt pruning: %s has no %s; the application imports %s behind "
            "ImportError and starts without" % (binding, ", ".join(sorted(absent)), "it" if len(absent) == 1 else "them")
        )
    return {name.split(".", 1)[1] for name in loaded if name.count(".") == 1}


def _native_runtime_python(target: Target) -> Path | None:
    """The target interpreter, when this host can execute it."""
    if target != host_target():
        return None
    if target.os == "windows" and runtime_provider() == "pbs":
        # python.org's embed _pth ignores PYTHONPATH. Use the PBS SDK's
        # full interpreter only for this build-time import-closure probe.
        from .runtime import sdk_info

        return Path(sdk_info(target)["python_executable"])
    try:
        return runtime_executable(target)
    except RuntimeError:
        return None


def configured_modules(target: Target, site: Path) -> set[str] | None:
    """Qt modules to keep, or None when the whole payload stays."""
    value = optimize_config().get("qt", "all")
    if isinstance(value, str):
        setting = value.strip().lower()
        if setting in {"all", ""}:
            return None
        if setting != "imports":
            raise RuntimeError("[tool.ai_upper.optimize].qt must be 'all', 'imports', or an array of Qt module names")
        requested, optional = qt_module_usage()
        if not requested and not optional:
            print("Qt pruning: app/src does not reference a Qt binding, keeping the full Qt payload")
            return None
    elif isinstance(value, list):
        # An explicit list is a statement about what to keep, not a reading of
        # the sources, so nothing in it is optional.
        requested = {str(item).strip() for item in value if str(item).strip()}
        optional = set()
        if not requested:
            raise RuntimeError("[tool.ai_upper.optimize].qt must not be an empty array")
    else:
        raise RuntimeError("[tool.ai_upper.optimize].qt must be 'all', 'imports', or an array of Qt module names")

    closure = _runtime_closure(site, target, requested, optional)
    if closure is None:
        # Without the target interpreter the closure cannot be computed, and a
        # guessed subset is what deletes the Qt libraries the application loads
        # indirectly. Keeping the payload whole costs size, never correctness.
        print(f"Qt pruning: cannot run the {target.key} runtime on this host, keeping the full Qt payload")
        return None
    return closure


def _wrapper_modules(pyside: Path) -> dict[str, Path]:
    return {
        path.name.split(".", 1)[0]: path
        for path in sorted(pyside.iterdir())
        if path.is_file() and path.suffix in WRAPPER_SUFFIXES and path.name.startswith("Qt")
    }


def _framework_binary(entry: Path) -> Path | None:
    if not entry.is_dir() or not entry.name.endswith(".framework"):
        return None
    binary = entry / "Versions" / "A" / entry.name[: -len(".framework")]
    return binary if binary.exists() else None


def _library_index(layout: _QtLayout) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for directory in layout.libraries:
        for entry in sorted(directory.iterdir()):
            binary = _framework_binary(entry)
            if binary is not None:
                index.setdefault(binary.name.lower(), []).append(binary)
                continue
            if not (entry.is_file() or entry.is_symlink()):
                continue
            if layout.library_names and not fnmatch(entry.name, layout.library_names):
                continue
            index.setdefault(entry.name.lower(), []).append(entry)
    return index


def _qt_module_of(dependency: str) -> str | None:
    """Map a load path back to its Qt module name, or None when it is not Qt.

    System frameworks such as ``CoreVideo.framework`` or ``IOSurface.framework``
    are not Qt modules: treating them as such would drop plugins (for example
    the cocoa platform plugin) merely because they link a system framework the
    wrapper closure never mentions.
    """
    if ".framework/" in dependency:
        name = dependency.split(".framework/", 1)[0].rsplit("/", 1)[-1]
        return name if name.startswith("Qt") else None
    base = Path(dependency).name
    match = re.match(r"^(?:lib)?(Qt[56]?[A-Za-z0-9_]+?)(?:\.[0-9.]+)?(?:\.so.*|\.dylib|\.dll)?$", base)
    if not match:
        return None
    name = match.group(1)
    if name.startswith("Qt6") or name.startswith("Qt5"):
        return "Qt" + name[3:]
    return name if name.startswith("Qt") else None


def _reachable_libraries(layout: _QtLayout, roots: list[Path]) -> tuple[set[Path], set[str]]:
    """Qt libraries reachable from ``roots``, plus the modules they belong to."""
    index = _library_index(layout)
    kept: set[Path] = set()
    modules: set[str] = set()
    queue = list(roots)
    while queue:
        current = queue.pop()
        for name in dependency_names(current):
            module = _qt_module_of(name)
            if module:
                modules.add(module)
            for candidate in index.get(Path(name).name.lower(), ()):
                if candidate not in kept:
                    kept.add(candidate)
                    queue.append(candidate)
    return kept, modules


def prune(
    site: Path,
    target: Target,
    modules: set[str] | None = None,
    source_root: Path | None = None,
) -> dict[str, int] | None:
    """Drop Qt payload the application does not need; returns removal counters.

    ``modules`` defaults to the configured policy (``[tool.ai_upper.optimize].qt``).
    ``source_root`` is where the application's own ``.qml`` files are scanned
    from; it defaults to ``app/src`` plus the resource trees.
    """
    binding = detect_binding(site)
    if binding is None:
        return None
    pyside = site / binding
    if modules is None:
        modules = configured_modules(target, site)
    if modules is None:
        return None

    counters = {"files": 0, "dirs": 0, "bytes": 0}
    layout = _qt_layout(pyside, binding)
    qt_root = layout.root
    options = _payload_options()

    def size_of(path: Path) -> int:
        if path.is_file() or path.is_symlink():
            try:
                return path.stat().st_size
            except OSError:
                return 0
        return sum(child.stat().st_size for child in path.rglob("*") if child.is_file())

    def drop(path: Path) -> None:
        if not path.exists() and not path.is_symlink():
            return
        counters["bytes"] += size_of(path)
        counters["dirs" if path.is_dir() and not path.is_symlink() else "files"] += 1
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)

    # QML is a second dependency source the Python import scan cannot see: the
    # ``.qml`` files only name QML modules, and the engine resolves those to
    # native plugins under ``Qt/qml`` at load time. Their libraries are not in
    # the native closure of any wrapper the application imports, so both the
    # tree and those libraries have to be derived from the QML sources. Miss
    # either one and the packaged application starts with an empty window and
    # "module is not installed" on stderr.
    qml_present = qml_sources_present(source_root)
    qml_imported = qml_imports(source_root) if qml_present else set()
    qml_modules = prune_qml_tree(layout, qml_imported, drop) if qml_present else set()
    qml_plugins = qml_plugin_binaries(qml_modules)
    if qml_present:
        # The QML modules also select payload outside the ``qml`` tree: a
        # ``import QtQuick`` application needs the scenegraph render plugins,
        # which are chosen by module name when the plugin categories are
        # pruned. Without folding them in, a QML-only application keeps
        # QtQuick's libraries and loses the renderer it drives.
        modules = modules | qml_required_modules(source_root)

    # PySide ships each non-importable tool twice: once bare and once under a
    # binding-prefixed name. PySide2 comes with ``lupdate.exe`` beside
    # ``pyside2-lupdate.exe``, and PySide6 spells the same pair with its prefix.
    # The prefixed copy is a full build of the same tool, and it links the Qt
    # modules that tool needs rather than the ones the application imports
    # (lupdate reads Qt5Xml), so the reachability sweep would remove those
    # libraries while leaving this executable behind: the native dependency
    # closure then refuses the whole bundle over a dangling Qt5Xml.dll. The bare
    # name is not enough, and a toolkit tool is never runtime payload.
    tooling_prefix = binding.lower() + "-"
    for name in TOOLING_ENTRIES:
        for suffix in layout.tooling_suffixes:
            drop(pyside / f"{name}{suffix}")
            drop(pyside / f"{tooling_prefix}{name}{suffix}")
    if layout.metatypes is not None:
        drop(layout.metatypes)
    # `libexec` holds both module helpers and build tooling. Dropping the
    # whole directory took `QtWebEngineProcess` with it, so a bundle that kept
    # QtWebEngineCore shipped without the process it spawns to render a page:
    # the window opened and stayed blank. Each entry is judged by the module it
    # serves instead; an entry with no owner is tooling.
    for helper_root in layout.helpers:
        entries = sorted(helper_root.iterdir()) if helper_root.is_dir() else [helper_root]
        for entry in entries:
            owner = _helper_owner(entry.name)
            if owner is None or owner not in modules:
                drop(entry)
        if helper_root.is_dir() and not any(helper_root.iterdir()):
            drop(helper_root)

    # Build-time material that ships beside the runtime payload: C++
    # documentation, the genpyi/tool wrappers and the import libraries. None of
    # it is imported, dlopen'd or read by a running application.
    for name in BINDING_TOOLING_DIRECTORIES + BINDING_BUILD_DIRECTORIES:
        drop(pyside / name)
    for entry in sorted(pyside.glob("*.lib")):
        drop(entry)
    shiboken_name = SHIBOKEN_PACKAGES.get(binding)
    if shiboken_name:
        shiboken = site / shiboken_name
        if shiboken.is_dir():
            for name in BINDING_TOOLING_DIRECTORIES + BINDING_BUILD_DIRECTORIES:
                drop(shiboken / name)
            for entry in sorted(shiboken.glob("*.lib")):
                drop(entry)
            # Only the MSVC runtime the extension modules actually link stays;
            # the OpenMP/AMP/Concurrency runtimes are tooling leftovers.
            for entry in sorted(shiboken.iterdir()):
                if entry.is_file() and entry.name.lower() in REDUNDANT_MSVC_RUNTIME:
                    drop(entry)

    # C++ headers and the example tree are build/documentation payload: no
    # import, plugin or translation can load them at runtime. The WebEngine
    # resources (ICU data and .pak files, ~15 MB on Windows) belong to
    # QtWebEngineCore alone, so they go whenever that module is not imported.
    for name in ("examples", "include"):
        drop(pyside / name)
        drop(qt_root / name)
    if "QtWebEngineCore" not in modules:
        drop(qt_root / "resources")

    wrappers = _wrapper_modules(pyside)
    keep_wrappers = [path for name, path in wrappers.items() if name in modules]
    for name, path in wrappers.items():
        if name not in modules:
            drop(path)
            # The type stub describes a wrapper that is no longer shipped.
            drop(pyside / f"{name}.pyi")

    keep_categories = set(BASE_PLUGIN_CATEGORIES)
    for name in modules:
        keep_categories.update(MODULE_PLUGIN_CATEGORIES.get(name, set()))
    plugins = layout.plugins
    if plugins.is_dir():
        for category in sorted(plugins.iterdir()):
            if category.name not in keep_categories:
                drop(category)

    # A plugin is only usable when every Qt module it links is still present.
    # This drops the virtual-keyboard input context (QtQml/QtQuick) and the PDF
    # image format (QtPdf) without guessing categories by hand.
    wrapper_libraries, allowed_modules = _reachable_libraries(layout, keep_wrappers)
    keep_plugins: list[Path] = []
    if plugins.is_dir():
        for plugin in sorted(path for path in plugins.rglob("*") if path.is_file()):
            needed = {name for dep in dependency_names(plugin) if (name := _qt_module_of(dep))}
            category = plugin.parent.name
            # Image formats and the SVG icon engine are chosen explicitly: Qt
            # loads them by MIME type, so an import never names them. Keeping
            # only the formats the application can display is the difference
            # between the full ~1.6 MB set and a few hundred kilobytes.
            if category in {"imageformats", "iconengines"} and not _allowed_plugin(
                plugin.name, options.image_formats
            ):
                drop(plugin)
            # Platform plugins decide whether the application starts at all, so
            # their category is kept regardless of extra dependencies. The
            # allowlist drops the non-desktop and streaming platforms:
            # ``qdirect2d``/``qminimal`` are fallbacks nothing selects, and
            # qwebgl drags QtQuick/QtQml (and their DLLs) into the payload.
            # ``qoffscreen`` stays because the headless smoke test needs it.
            elif "platforms" in plugin.parts:
                if "qwebgl" in plugin.name.lower() or not _allowed_plugin(
                    plugin.name, options.platforms
                ):
                    drop(plugin)
                else:
                    keep_plugins.append(plugin)
            elif needed <= allowed_modules or any(
                token in plugin.name for token in PLUGIN_KEEP_EXCEPTIONS
            ):
                keep_plugins.append(plugin)
            else:
                drop(plugin)

    # The QML plugins are the only thing that loads QtQuick's own libraries
    # when the application has no Python-side ``import QtQuick``; they are
    # roots of the same sweep, not extra weight on top of it.
    qml_libraries, _ = _reachable_libraries(layout, qml_plugins)
    plugin_libraries, _ = _reachable_libraries(layout, keep_plugins)
    reachable = wrapper_libraries | plugin_libraries | qml_libraries
    for directory in layout.libraries:
        for entry in sorted(directory.iterdir()):
            binary = _framework_binary(entry)
            if binary is not None:
                if binary not in reachable:
                    drop(entry)
                continue
            if layout.library_names and not fnmatch(entry.name, layout.library_names):
                continue
            if entry.name.lower() in options.keep_names:
                continue
            if entry not in reachable:
                drop(entry)

    # A QML-only application imports none of the QML wrappers from Python, so
    # ``modules`` has been folded with the modules its ``.qml`` files name
    # above; the tree is pruned module by module from those same imports.
    if not any(name.startswith(QML_MODULE_PREFIXES) for name in modules):
        drop(layout.qml)
        # shiboken's QML helper library is only used by the QML wrapper modules.
        for pattern in layout.qml_helpers:
            for helper in sorted(pyside.glob(pattern)):
                drop(helper)

    # Only Qt's own widget strings are useful to a running application; tooling
    # and unused-module translations are dead weight. Chromium's locale packs
    # are a module payload rather than a translation of Qt, so they are judged
    # by the module that loads them and by their own allowlist.
    translations = layout.translations
    if translations.is_dir():
        for entry in sorted(translations.iterdir()):
            name = entry.name
            if name == WEBENGINE_LOCALES_DIR:
                if "QtWebEngineCore" not in modules:
                    drop(entry)
                    continue
                for pack in sorted(entry.iterdir()):
                    if pack.is_dir() or not _allowed_webengine_locale(pack.name, options.locales):
                        drop(pack)
                continue
            # Only Qt's own widget strings are useful to a running application.
            # Tooling translations are always dead weight; a locale allowlist
            # then keeps just the languages the application ships with, turning
            # the ~4.7 MB wheel translation set into one or two files.
            keep = (
                (name.startswith("qtbase_") or name.startswith("qt_"))
                and not name.startswith(TOOLING_TRANSLATION_PREFIXES)
                and _allowed_locale(name, options.locales)
            )
            if not keep:
                drop(entry)

    return counters
