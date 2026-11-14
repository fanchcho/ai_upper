"""Audit helper: build the real MVVM window graph, screenshot main + about.

Not part of the application. Run from the repository's app/ directory:

    ../.venv/bin/python ../audit-tools/screenshot_app.py /abs/out/dir

Uses the repo's own assembly (application.PyUpperApplication), so the widgets
grabbed are the ones the shipped app builds.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    # Running this file puts audit-tools/ on sys.path[0], not app/src/. Add the
    # source root explicitly so the import works from any cwd.
    src = Path(__file__).resolve().parents[1] / "app" / "src"
    sys.path.insert(0, str(src))

    from application import PyUpperApplication  # noqa: E402

    app = PyUpperApplication()
    app.prepare()
    qt_app = app.qt_app
    qt_app.processEvents()

    from utils.qt_compat import QtWidgets

    tops = [w for w in qt_app.topLevelWidgets() if w.isWindow()]
    print("platform:", qt_app.platformName())
    print("top-level windows:", [(type(w).__name__, w.windowTitle()) for w in tops])

    main_window = app.mvvm_app.get_view("main")._window  # audit-only private access
    main_path = out_dir / "main-window.png"
    ok_main = main_window.grab().save(str(main_path))
    print("saved main window:", main_path, ok_main, main_window.size().toTuple())

    # Drive the same path a user takes: the command the button is bound to.
    viewmodel = app.mvvm_app.get_viewmodel("main")
    viewmodel.show_about_command.execute()
    qt_app.processEvents()
    about = app.mvvm_app.get_view("about")._dialog
    print("about visible:", about.isVisible())
    about_path = out_dir / "about-window.png"
    ok_about = about.grab().save(str(about_path))
    print("saved about window:", about_path, ok_about, about.size().toTuple())

    app.mvvm_app.stop()
    qt_app.processEvents()
    return 0 if (ok_main and ok_about) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
