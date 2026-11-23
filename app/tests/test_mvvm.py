"""MVVM framework port: core, views, container, binding-neutral imports."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from conftest import install_fake_binding

SRC = Path(__file__).resolve().parents[1] / "src"


def test_mvvm_core_imports_without_qt():
    import mvvm.core
    import mvvm.models

    for name in ("BaseViewModel", "ObservableProperty", "PropertyChangedEvent",
                 "RelayCommand", "AsyncRelayCommand", "PropertyFactory", "ViewModelFactory"):
        assert hasattr(mvvm.core, name), f"mvvm.core lost {name}"
    for name in ("BaseModel", "ApplicationModel"):
        assert hasattr(mvvm.models, name), f"mvvm.models lost {name}"

    class Demo(mvvm.core.BaseViewModel):
        pass

    vm = Demo()
    prop = mvvm.core.ObservableProperty(42)
    vm._register_property("value", prop)
    assert vm.get_property_value("value") == 42
    vm.set_property_value("value", 7)
    assert vm.get_property_value("value") == 7
    events = []
    vm.subscribe_property_changed(lambda e: events.append(e.property_name))
    vm.set_property_value("value", 8)
    assert "value" in events


def test_mvvm_application_container():
    from mvvm.core import BaseViewModel
    from mvvm.mvvm_application import MVVMApplication
    from mvvm.models import ApplicationModel
    from mvvm.views import ViewBase

    model = ApplicationModel()
    app = MVVMApplication(model)
    assert app.model is model
    assert app.is_running is False

    service = object()
    app.register_service("demo", service)
    assert app.get_service("demo") is service
    assert app.resolve_service(object) is service
    assert app.resolve_service(str) is None

    viewmodel = BaseViewModel()
    view = ViewBase(viewmodel)
    app.register_viewmodel("main", viewmodel)
    app.register_view("main", view)
    assert app.get_viewmodel("main") is viewmodel
    assert app.get_view("main") is view

    app.start()
    assert app.is_running and model.is_running
    assert repr(app) == "MVVMApplication(viewmodels=1, views=1)"

    app.stop()
    assert not app.is_running and not model.is_running
    assert app.get_viewmodel("main") is None
    assert app.get_view("main") is None


def test_services_belong_to_the_application_that_registered_them():
    """A class-level registry hands one application another application's services.

    The container exists to keep dependencies explicit; a process-global
    locator defeats that the moment two MVVMApplication objects exist (tests,
    an embedder, a second window set).
    """
    from mvvm.mvvm_application import MVVMApplication
    from mvvm.models import ApplicationModel

    first = MVVMApplication(ApplicationModel())
    second = MVVMApplication(ApplicationModel())
    first.register_service("demo", object())

    assert first.get_service("demo") is not None
    assert second.get_service("demo") is None


def test_a_binding_can_target_a_setter_method():
    """``bind_property(..., 'setText')`` has to call setText.

    setattr(label, 'setText', value) only shadows the method with an attribute:
    the widget never updates and nothing reports a problem.
    """
    from mvvm.core import BaseViewModel, ObservableProperty
    from mvvm.views import ViewBase

    class Label:
        def __init__(self):
            self.text = ""

        def setText(self, value):  # noqa: N802 - Qt spelling
            self.text = value

    viewmodel = BaseViewModel()
    viewmodel._register_property("message", ObservableProperty("a"))
    label = Label()
    ViewBase(viewmodel).bind_property("message", label, "setText")

    viewmodel.set_property_value("message", "b")
    assert label.text == "b"


def test_a_binding_can_target_a_plain_attribute():
    from mvvm.core import BaseViewModel, ObservableProperty
    from mvvm.views import ViewBase

    class Element:
        value = ""

    viewmodel = BaseViewModel()
    viewmodel._register_property("message", ObservableProperty("a"))
    element = Element()
    ViewBase(viewmodel).bind_property("message", element, "value")

    viewmodel.set_property_value("message", "b")
    assert element.value == "b"


def test_two_way_binding_needs_an_explicit_getter():
    """Guessing the getter from the setter name reads the wrong value in Qt."""
    from mvvm.core import BaseViewModel, ObservableProperty
    from mvvm.views import ViewBase

    class Field:
        text = "from the widget"

    viewmodel = BaseViewModel()
    viewmodel._register_property("message", ObservableProperty("a"))
    view = ViewBase(viewmodel)

    one_way = view.bind_property("message", Field(), "text")
    with pytest.raises(ValueError, match="getter_name"):
        one_way.update_viewmodel_from_ui()

    two_way = view.bind_property("message", Field(), "text", getter_name="text")
    two_way.update_viewmodel_from_ui()
    assert viewmodel.get_property_value("message") == "from the widget"


def test_mvvm_import_does_not_require_qt():
    """The framework must not pull a Qt binding at import time.

    This has to run in a fresh interpreter. Deleting ``PySide6`` entries from
    this process's ``sys.modules`` does not unload the C++ modules: the shim
    and ``ShellBridge`` keep the original module generation, while the next
    QML test imports a second generation. Mixing both in one QApplication
    segfaults in ``QQuickWindow.contentItem`` (the full-suite crash).
    """
    script = (
        "import sys\n"
        "sys.path.insert(0, '.')\n"
        "import mvvm\n"
        "import mvvm.mvvm_application\n"
        "bad = [name for name in sys.modules "
        "if name.startswith(('PySide6', 'PySide2', 'PyQt6', 'PyQt5'))]\n"
        "assert not bad, bad\n"
    )
    result = subprocess.run(
        [str(Path(sys.executable).resolve()), "-I", "-c", script],
        cwd=SRC,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_factories_have_a_single_home():
    """mvvm.core.factory defines the factories; mvvm.core only re-exports them.

    A second definition under the same name made ``from mvvm.core import
    PropertyFactory`` resolve to whichever module the package imported last,
    which is not a decision anything should be making by accident.
    """
    import mvvm.core
    import mvvm.core.base_view_model as base_view_model
    import mvvm.core.factory as factory
    import mvvm.core.observable as observable

    assert mvvm.core.PropertyFactory is factory.PropertyFactory
    assert mvvm.core.ViewModelFactory is factory.ViewModelFactory
    assert not hasattr(observable, "PropertyFactory")
    assert not hasattr(base_view_model, "ViewModelFactory")
    assert mvvm.core.__all__.count("PropertyFactory") == 1
    assert mvvm.core.__all__.count("ViewModelFactory") == 1
    assert set(mvvm.core.__all__) <= set(dir(mvvm.core))


def test_every_mvvm_module_imports(monkeypatch):
    """Every module in the tree must be importable.

    The port arrived with a models/app_model.py that imported four model modules
    that do not exist in this repository and redefined ApplicationModel. Nothing
    referenced it, so the only symptom was Cython compiling dead source into the
    bundle. mvvm_bootstrap is the one module that needs Qt, hence the fake.

    No module is exempt any more. The three that needed Qt **while the class body
    was evaluated** are gone with the web entry: ``title_bar_overlay`` (the
    frameless WebEngine window's own title bar), ``web_shell_window`` (the
    QWebEngineView host) and the ``DevaBridge`` QObject inside
    ``mvvm.webui.bridge``. What remains there is a pure function, so the fake
    binding below is enough for every module in the tree.
    """
    import importlib

    install_fake_binding(monkeypatch, {"PySide6": {"QtCore": {}, "QtGui": {}, "QtWidgets": {}}})

    imported = []
    for path in sorted((SRC / "mvvm").rglob("*.py")):
        parts = list(path.relative_to(SRC).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        imported.append(importlib.import_module(".".join(parts)))
    assert len(imported) >= 8
    # WebEngine 承载层不许悄悄回来：这两个模块随「唯一界面 = QML 壳」删除，
    # 谁把同功能文件加回来，这条会立刻失败，而不是多出一条没人测的界面路线。
    for gone in ("views.web_shell_window", "views.title_bar_overlay"):
        module_path = SRC.joinpath("mvvm", *gone.split(".")).with_suffix(".py")
        assert not module_path.exists(), f"WebEngine 承载层又出现了：{module_path}"
