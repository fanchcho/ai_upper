from __future__ import annotations

from pathlib import Path

import pytest

from application import run_application


def test_application(capsys):
    run_application()
    assert "ai_upper" in capsys.readouterr().out


def test_resource_root_prefers_the_launcher_exported_home(monkeypatch, tmp_path):
    """The launcher knows the bundle root; counting parent directories guesses."""
    from utils import paths

    monkeypatch.delenv(paths.BUNDLE_HOME_ENV, raising=False)
    assert paths.bundle_home() is None
    assert paths.resource_root() == Path(paths.__file__).resolve().parents[2] / "resources"

    monkeypatch.setenv(paths.BUNDLE_HOME_ENV, str(tmp_path))
    assert paths.bundle_home() == tmp_path.resolve()
    assert paths.resource_root() == tmp_path.resolve() / "resources"


def test_assets_root_follows_the_launcher_exported_home(monkeypatch, tmp_path):
    """A bundle has no source tree, so the assets path cannot be counted out.

    The packager copies `app/assets` to `<bundle>/assets`; that is the only
    location that exists after the egg is unpacked, and the launcher exports
    its root as AI_UPPER_HOME.
    """
    from utils import paths

    monkeypatch.delenv(paths.ASSETS_ENV, raising=False)
    monkeypatch.delenv(paths.BUNDLE_HOME_ENV, raising=False)
    assert paths.assets_root() == Path(paths.__file__).resolve().parents[2] / "assets"

    monkeypatch.setenv(paths.BUNDLE_HOME_ENV, str(tmp_path))
    assert paths.assets_root() == tmp_path.resolve() / "assets"

    # The explicit override is what the parity scripts point at another build.
    other = tmp_path / "other-assets"
    other.mkdir()
    monkeypatch.setenv(paths.ASSETS_ENV, str(other))
    assert paths.assets_root() == other.resolve()


def test_assets_root_names_the_packaged_location_when_nothing_exists(monkeypatch, tmp_path):
    """A missing payload must report where it was expected, not a dev path."""
    from utils import paths

    monkeypatch.delenv(paths.ASSETS_ENV, raising=False)
    monkeypatch.setattr(paths, "_module_file", lambda: None)
    monkeypatch.setenv(paths.BUNDLE_HOME_ENV, str(tmp_path))

    assert paths.assets_root() == tmp_path.resolve() / "assets"

    # Without either export (a merged bundle whose env was lost) the executable
    # directory is the only place left to name.
    monkeypatch.delenv(paths.BUNDLE_HOME_ENV, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(tmp_path / "Upper"))
    assert paths.assets_root() == tmp_path.resolve() / "assets"


def test_app_name_agrees_with_the_packaging_configuration(monkeypatch):
    """The name is written once, in app/pyproject.toml, and read from there."""
    from ai_upper.config import app_name as packaged_app_name
    from utils import paths

    monkeypatch.delenv(paths.APP_NAME_ENV, raising=False)
    assert paths.app_name() == packaged_app_name()

    # The launcher wins: a renamed executable still reports the configured name.
    monkeypatch.setenv(paths.APP_NAME_ENV, "Renamed Tool")
    assert paths.app_name() == "Renamed Tool"


def test_paths_survive_the_builtin_file_a_merged_bundle_reports(monkeypatch, tmp_path):
    """A merged bundle is a built-in module: __file__ is "built-in", not a path."""
    from utils import paths

    monkeypatch.delenv(paths.BUNDLE_HOME_ENV, raising=False)
    monkeypatch.delenv(paths.APP_NAME_ENV, raising=False)
    monkeypatch.setattr(paths, "__file__", "built-in")
    monkeypatch.setattr(paths.sys, "executable", str(tmp_path / "Upper.exe"))

    assert paths._module_file() is None
    assert paths._project_root() is None
    assert paths._declared_app_name() is None
    assert paths.app_name() == paths._DEFAULT_APP_NAME
    assert paths.resource_root() == tmp_path.resolve() / "resources"


def test_declared_app_name_ignores_the_project_section(tmp_path, monkeypatch):
    from utils import paths

    project = tmp_path / "app" / "pyproject.toml"
    project.parent.mkdir(parents=True)
    project.write_text(
        '[project]\nname = "not-the-app-name"\n\n[tool.ai_upper.app]\nname = "Real App"  # inline comment\n',
        encoding="utf-8",
    )
    module = project.parent / "src" / "utils" / "paths.py"
    module.parent.mkdir(parents=True)
    module.write_text("", encoding="utf-8")
    monkeypatch.setattr(paths, "__file__", str(module))

    assert paths._declared_app_name() == "Real App"


def test_gui_opens_a_window_headlessly(monkeypatch, capsys):
    """The Qt window is the real check that a bundled PySide6 payload works.

    The development interpreter may not have PySide6 installed, so this is
    skipped there; the packaged application exercises the same code path in the
    build's launcher smoke and in the CI integration run.
    """
    pytest.importorskip("PySide6.QtWidgets", reason="PySide6 is only required for the packaged application")

    from application import run_gui

    monkeypatch.setenv("AI_UPPER_HEADLESS", "1")
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)

    assert run_gui() == 0
    assert "GUI OK offscreen" in capsys.readouterr().out


def test_every_third_party_import_is_a_declared_runtime_dependency():
    """A dependency imported but not declared ships outside the bundle.

    Cython compiles the application's own sources and the bundler installs
    exactly ``[project].dependencies``; nothing else lands in site-packages.
    ``httpx`` was imported by ``http_client.py`` and missing from both lists,
    so every source-mode test passed while the packaged application died on the
    first window with ``ModuleNotFoundError: No module named 'httpx'``. Only a
    real build starting a real bundle found it.

    The comparison is import-name based, and distribution and import names can
    differ: ``PySide6-Essentials`` is the distribution that installs the
    ``PySide6`` package, ``cryptography`` installs ``cryptography``. The map
    below spells out the pairs this project uses; anything not in it has to
    match its import name.
    """
    import ast
    import sys

    # distribution name (lowercase, as written in requirements.txt) -> import name
    distribution_import_names = {"pyside6-essentials": "pyside6"}

    project = Path(__file__).resolve().parents[1]
    source_root = project / "src"
    local = {path.stem for path in source_root.rglob("*.py")}
    local |= {path.name for path in source_root.iterdir() if path.is_dir()}

    imported: set[str] = set()
    for path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])

    third_party = {
        name for name in imported
        if name not in sys.stdlib_module_names and name not in local
    }
    declared = {
        line.strip().split("==")[0].split(">=")[0].split("[")[0].lower()
        for line in (project / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#") and not line.lstrip().startswith("-")
    }
    provided = declared | {distribution_import_names[name] for name in declared if name in distribution_import_names}
    missing = {name for name in third_party if name.lower() not in provided}
    assert not missing, (
        f"imported but not in app/requirements.txt (so not in the bundle): {sorted(missing)}"
    )
