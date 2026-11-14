"""Audit helper: real X11 window under Xvfb, grab both windows, quit the loop.

Run with xvfb-run:
    xvfb-run -a -s "-screen 0 1280x800x24" ../.venv/bin/python ../audit-tools/xvfb_run.py out/
"""
from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    src = Path(__file__).resolve().parents[1] / "app" / "src"
    sys.path.insert(0, str(src))

    from application import AiUpperApplication

    app = AiUpperApplication()
    app.prepare()
    qt_app = app.qt_app
    qt_app.processEvents()

    print("platform:", qt_app.platformName())
    main_window = app.mvvm_app.get_view("main")._window
    print("main visible:", main_window.isVisible(), "size:", main_window.size().toTuple())
    print("window title:", main_window.windowTitle())
    print("screen geometry:", qt_app.primaryScreen().geometry().getRect())
    ok_main = main_window.grab().save(str(out_dir / "main-window-xvfb.png"))
    print("saved:", out_dir / "main-window-xvfb.png", ok_main)

    viewmodel = app.mvvm_app.get_viewmodel("main")
    viewmodel.show_about_command.execute()
    qt_app.processEvents()
    about = app.mvvm_app.get_view("about")._dialog
    ok_about = about.grab().save(str(out_dir / "about-window-xvfb.png"))
    print("saved:", out_dir / "about-window-xvfb.png", ok_about, "visible:", about.isVisible())

    app.mvvm_app.stop()
    return 0 if (ok_main and ok_about) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
