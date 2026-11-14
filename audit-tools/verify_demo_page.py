"""Verify the demo page end to end against real PySide6.

Run (needs a Qt platform; offscreen is enough):
    QT_QPA_PLATFORM=offscreen ../.venv/bin/python ../audit-tools/verify_demo_page.py out/

Checks:
  1. user typing (real Qt signal) updates the ViewModel;
  2. ViewModel change updates the widget (ViewModel -> UI);
  3. command (RelayCommand) resets the field through the binding;
  4. the offscreen env var path still builds the whole graph.
Screenshots: demo-page.png after typing, demo-page-reset.png after reset.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    src = Path(__file__).resolve().parents[1] / "app" / "src"
    sys.path.insert(0, str(src))

    from demo_application import DemoApplication
    from utils.qt_compat import QtCore, QtTest

    app = DemoApplication()
    app.prepare()
    qt_app = app.qt_app
    qt_app.processEvents()

    view = app.mvvm_app.get_view("demo")
    vm = app.mvvm_app.get_viewmodel("demo")
    window = view._window
    window.resize(420, 160)
    qt_app.processEvents()

    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        print(f"[{'PASS' if condition else 'FAIL'}] {label}{(' :: ' + detail) if detail else ''}")
        if not condition:
            failures.append(label)

    print("platform:", qt_app.platformName())
    print("initial vm.name =", repr(vm.name), "widget =", repr(view._line_edit.text()))
    check("initial UI == VM", view._line_edit.text() == vm.name == "ai_upper")

    # 1. Real user typing: QtTest.keyClicks delivers genuine QKeyEvents, so the
    #    textEdited signal fires exactly as it would for a human.
    view._line_edit.clear()
    QtTest.QTest.keyClicks(view._line_edit, "Alice_2024")
    qt_app.processEvents()
    print("after typing vm.name =", repr(vm.name), "widget =", repr(view._line_edit.text()))
    check("UI -> VM propagates", vm.name == "Alice_2024")
    check("derived greeting follows", vm.greeting == "你好，Alice_2024！", vm.greeting)
    check("derived greeting reached the label", view._greeting_label.text() == vm.greeting)
    shot = out_dir / "demo-page.png"
    check("screenshot saved", window.grab().save(str(shot)), str(shot))

    # 2. ViewModel -> UI directly.
    vm.name_property.set_value("Bob")
    qt_app.processEvents()
    print("after vm.set('Bob') widget =", repr(view._line_edit.text()), "label =", repr(view._greeting_label.text()))
    check("VM -> UI propagates", view._line_edit.text() == "Bob")
    check("label updated from VM", view._greeting_label.text() == "你好，Bob！")

    # 3. Command through CommandBinding (the button's clicked signal).
    QtTest.QTest.mouseClick(view._reset_button, QtCore.Qt.MouseButton.LeftButton)
    qt_app.processEvents()
    print("after reset click vm.name =", repr(vm.name), "widget =", repr(view._line_edit.text()))
    check("command reset VM", vm.name == "ai_upper")
    check("command reset widget via binding", view._line_edit.text() == "ai_upper")
    shot_reset = out_dir / "demo-page-reset.png"
    check("reset screenshot saved", window.grab().save(str(shot_reset)), str(shot_reset))

    # 4. Empty input path (derived property + placeholder text).
    QtTest.QTest.keyClicks(view._line_edit, "")
    view._line_edit.clear()
    vm.name_property.set_value("")
    qt_app.processEvents()
    check("empty name yields hint", vm.greeting == "（请输入名字）", vm.greeting)

    app.mvvm_app.stop()
    print("RESULT:", "PASS" if not failures else f"FAIL {failures}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
