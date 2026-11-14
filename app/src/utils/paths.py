from __future__ import annotations

import os
import sys
from pathlib import Path

# Exported by the packaged launcher: the directory that holds `runtime/`,
# `site-packages/` and the entry script. Counting parent directories only works
# for the layout of the day; the launcher knows the real answer.
BUNDLE_HOME_ENV = "AI_UPPER_HOME"
# Pre-rename spellings, still honoured so a bundle built by the old launcher and
# an environment set up before the rename both keep working.
LEGACY_BUNDLE_HOME_ENV = ("PY_UPPER_HOME",)

# Exported by the packaged launcher: the application name compiled in at
# packaging time. The launcher cannot read it from its own filename, because
# renaming the executable is supported.
APP_NAME_ENV = "AI_UPPER_APP_NAME"
LEGACY_APP_NAME_ENV = ("PY_UPPER_APP_NAME",)

_APP_NAME_SECTION = "tool.ai_upper.app"
# Sections a working copy may still carry from before the rename; the current
# one wins when both exist.
_LEGACY_APP_NAME_SECTIONS = ("tool.py_upper.app",)
# Mirrors the packager's own fallback, for the case where neither a launcher nor
# a pyproject.toml is reachable.
_DEFAULT_APP_NAME = "ai_upper"


def _environment(name: str, legacy: tuple[str, ...] = ()) -> str:
    """Read ``name``, falling back to the pre-rename spellings."""
    value = os.environ.get(name)
    if value:
        return value
    for old in legacy:
        value = os.environ.get(old)
        if value:
            return value
    return ""


def bundle_home() -> Path | None:
    value = _environment(BUNDLE_HOME_ENV, LEGACY_BUNDLE_HOME_ENV).strip()
    return Path(value).resolve() if value else None


def _module_file() -> Path | None:
    # A merged Cython bundle is registered as a built-in module. CPython gives
    # it the spec origin "built-in" as __file__, which is not a path and has no
    # parent directories to count.
    value = globals().get("__file__")
    if not value:
        return None
    try:
        path = Path(value).resolve()
    except (OSError, RuntimeError, ValueError):
        return None
    return path if path.is_file() else None


def _project_root() -> Path | None:
    module = _module_file()
    if module is None:
        return None
    try:
        return module.parents[2]
    except IndexError:
        return None


def resource_root() -> Path:
    # In development: app/src/utils -> app/resources.
    # In a package: site-packages/utils -> bundled-app/resources.
    home = bundle_home()
    if home is not None:
        return home / "resources"
    project = _project_root()
    if project is not None:
        return project / "resources"
    # A merged bundle has no source path. The executable still lives in the
    # bundle root, which is the best fallback when the launcher export is lost.
    return Path(sys.executable).resolve().parent / "resources"


ASSETS_ENV = "DEVA_ASSETS_DIR"
_ASSETS_MODULE_DIR = "assets"


def assets_root() -> Path:
    """Where the renderer bundle and seed personas live.

    Development keeps ``app/assets`` next to ``app/src``. A package has no
    source tree at all (the application code ships as one merged extension or
    inside the egg archive, so ``__file__`` is useless), therefore the packager
    copies the tree to ``<bundle>/assets`` — beside ``resources`` — and this
    function reads it from the launcher-exported home. ``DEVA_ASSETS_DIR`` is
    the explicit override used by the parity scripts to point at a different
    build.
    """
    override = os.environ.get(ASSETS_ENV)
    if override:
        return Path(override).resolve()
    # The launcher's export is authoritative, exactly as it is for
    # `resource_root()`: a bundle that is missing its assets must report the
    # packaged location, not silently load a development tree that happens to
    # sit next to the source checkout.
    home = bundle_home()
    if home is not None:
        return home / _ASSETS_MODULE_DIR
    project = _project_root()
    if project is not None:
        return project / _ASSETS_MODULE_DIR
    # A merged bundle has no source path; the executable's directory is the
    # best answer when the launcher export is lost.
    return Path(sys.executable).resolve().parent / _ASSETS_MODULE_DIR


def app_name() -> str:
    """The user-facing application name.

    The launcher exports it, so a renamed executable still reports the
    configured name. Running from a source tree (tests, `PYTHONPATH=src python
    src/main.py`) there is no launcher, so the name is read from the same
    `[tool.ai_upper.app].name` the packager uses instead of being written twice.
    """
    value = _environment(APP_NAME_ENV, LEGACY_APP_NAME_ENV).strip()
    if value:
        return value
    return _declared_app_name() or _DEFAULT_APP_NAME


def _declared_app_name() -> str | None:
    # app/src/utils -> app/pyproject.toml. Inside a package there is no source
    # path to count from; the launcher's export is the only source there. The
    # read stays hand-rolled because `tomllib` is Python 3.11+ and this
    # application supports 3.8.
    root = _project_root()
    if root is None:
        return None
    project = root / "pyproject.toml"
    if not project.is_file():
        return None
    sections = (_APP_NAME_SECTION, *_LEGACY_APP_NAME_SECTIONS)
    found: dict[str, str | None] = {}
    section = None
    for line in project.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if entry.startswith("[") and entry.endswith("]"):
            section = entry[1:-1].strip()
        elif section in sections and "=" in entry:
            key, _, value = entry.partition("=")
            if key.strip() == "name" and section not in found:
                found[section] = _toml_string(value.strip())
    for name in sections:
        if found.get(name):
            return found[name]
    return None


def _toml_string(value: str) -> str | None:
    quote = value[:1]
    if quote not in {'"', "'"}:
        return None
    end = value.find(quote, 1)
    if end <= 0:
        return None
    return value[1:end] or None
