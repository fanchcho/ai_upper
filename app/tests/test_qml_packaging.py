"""QML 必须跟着打包产物走，且不能只留在源码树里。

QML 引擎从**磁盘**读 ``.qml``/``qmldir``：加密 egg 是它读不了的归档，所以这两类
文件既不能进 egg，也不能只存在于开发树的 ``app/src/qml``。本文件锁住打包链的两端：

- ``package.py::_copy_supporting_trees`` 把 ``app/src/qml`` 放到
  ``<bundle>/assets/qml``（``utils.paths.assets_root()`` 读的位置）；
- ``python_build.py::copy_python_tree`` 把它们从 site 阶段删掉，于是
  ``egg.application_files()`` 收不到它们；
- 裁剪留下的 QML 插件原生库确实在磁盘上，且被当作可达性根。

真实产物上的验证不在这里（需要整条 build），用例只锁判定，不替代实跑。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ai_upper import qt_prune
from ai_upper.config import TARGETS

MAIN_QML = "import QtQuick\nimport QtQuick.Controls\nApplicationWindow { }\n"


def _write(path: Path, text: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _qml_source(app: Path) -> Path:
    _write(app / "src" / "qml" / "Main.qml", MAIN_QML)
    _write(app / "src" / "qml" / "Theme.qml", "pragma Singleton\nimport QtQuick\nQtObject { }\n")
    _write(app / "src" / "qml" / "qmldir", "singleton Theme 1.0 Theme.qml\n")
    _write(app / "src" / "main.py", "print('entry')\n")
    return app


def test_the_qml_entry_point_ships_beside_the_payload_root(tmp_path, monkeypatch):
    """``assets/qml`` 是 ``qml_shell.qml_main()`` 在产物里读的那个位置。"""
    from ai_upper import package as pkg

    app = _qml_source(tmp_path / "app")
    monkeypatch.setattr(pkg, "APP", app)

    out = tmp_path / "bundle"
    pkg._copy_supporting_trees(out)

    assert (out / "assets" / "qml" / "Main.qml").read_text(encoding="utf-8") == MAIN_QML
    assert (out / "assets" / "qml" / "qmldir").read_text(encoding="utf-8") == (
        "singleton Theme 1.0 Theme.qml\n"
    )
    assert (out / "assets" / "qml" / "Theme.qml").is_file()
    # ``src/ui`` 里的 .qml 不是入口树，只有 ``src/qml`` 会落位。
    assert not (out / "assets" / "qml" / "ui").exists()


def test_the_stage_keeps_qml_out_of_the_encrypted_egg(tmp_path, monkeypatch):
    """site 里没有 ``.qml``/``qmldir``，egg 也就收不到它们。

    QML 引擎读不了加密包；把它们留在 site 的结果是产物里有一份「看起来存在、
    实际加载不了」的 QML，启动后只剩空窗口。
    """
    from ai_upper import egg as egg_module
    from ai_upper import python_build

    app = _qml_source(tmp_path / "app")
    monkeypatch.setattr(python_build, "APP", app)
    monkeypatch.setattr(egg_module, "APP", app)

    site = tmp_path / "site"
    python_build.copy_python_tree(site)

    assert (site / "main.py").is_file()
    assert not (site / "qml").exists()
    assert not list(site.rglob("*.qml"))
    assert not list(site.rglob("qmldir"))
    assert egg_module.application_files(site, set()) == ["main.py"]


def test_staging_never_touches_the_qt_qml_runtime(tmp_path, monkeypatch):
    """Qt 的 ``Qt/qml/**`` 也叫 ``qml``，但它不是应用源码，一个文件都不能删。

    按目录名在整棵 site 里匹配 ``qml`` 曾经把 Qt 的 ``qmldir`` 与样式 ``.qml``
    一起删掉：模块目录还在、插件库也在，引擎却报 "module is not installed"。
    """
    from ai_upper import python_build

    app = _qml_source(tmp_path / "app")
    monkeypatch.setattr(python_build, "APP", app)

    site = tmp_path / "site"
    runtime = site / "PySide6" / "Qt" / "qml" / "QtQuick" / "Controls"
    _write(runtime / "qmldir", "module QtQuick.Controls\nplugin qtquickcontrols2plugin\n")
    _write(runtime / "ApplicationWindow.qml", "import QtQuick\n")
    _write(site / "PySide6" / "Qt" / "qml" / "QtQuick" / "qmldir", "module QtQuick\n")

    python_build.copy_python_tree(site)

    assert (runtime / "qmldir").is_file()
    assert (runtime / "ApplicationWindow.qml").is_file()
    assert (site / "PySide6" / "Qt" / "qml" / "QtQuick" / "qmldir").is_file()
    # 应用自己的 QML 照旧清掉。
    assert not (site / "qml").exists()


# ── 裁剪：树与插件库 ──────────────────────────────────────────────────────
def _module(root: Path, name: str, plugin: str, extra: str = "") -> Path:
    directory = root.joinpath(*name.split("."))
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "qmldir").write_text(
        "module %s\nplugin %s\n%s" % (name, plugin, extra), encoding="utf-8"
    )
    (directory / ("lib%s.so" % plugin)).write_bytes(b"\x7fELF")
    return directory


def _site(tmp_path: Path) -> tuple[Path, Path]:
    site = tmp_path / "site-packages"
    pyside = site / "PySide6"
    (pyside / "Qt" / "lib").mkdir(parents=True)
    (pyside / "Qt" / "plugins" / "platforms").mkdir(parents=True)
    (pyside / "QtCore.abi3.so").write_bytes(b"\x7fELF")
    (pyside / "QtQml.abi3.so").write_bytes(b"\x7fELF")
    (pyside / "Qt" / "lib" / "libQt6Quick.so.6").write_bytes(b"\x7fELF")
    (pyside / "Qt" / "plugins" / "platforms" / "libqoffscreen.so").write_bytes(b"\x7fELF")
    tree = pyside / "Qt" / "qml"
    _module(tree, "QtQuick", "qtquick2plugin")
    _module(tree, "QtQuick.Templates", "qtquicktemplates2plugin")
    _module(
        tree,
        "QtQuick.Controls",
        "qtquickcontrols2plugin",
        "default import QtQuick.Controls.Basic auto\ndepends QtQuick\n",
    )
    _module(tree, "QtQuick.Controls.Basic", "qtquickcontrols2basicstyleplugin", "import QtQuick.Templates auto\n")
    _module(tree, "QtQuick.Controls.Fusion", "qtquickcontrols2fusionstyleplugin")
    return site, pyside


@pytest.fixture
def isolated_prune(monkeypatch):
    """按默认选项跑裁剪：本仓库的 ``[tool.ai_upper.optimize]`` 不能影响判定。"""
    monkeypatch.setattr(qt_prune, "optimize_config", lambda: {})
    monkeypatch.setattr(qt_prune, "dependency_names", lambda path: [])
    real_roots = qt_prune.qml_source_roots
    monkeypatch.setattr(
        qt_prune, "qml_source_roots", lambda root=None: () if root is None else real_roots(root)
    )


def test_prune_leaves_the_qml_tree_and_its_plugin_libraries(tmp_path, isolated_prune):
    site, pyside = _site(tmp_path)
    source = tmp_path / "src"
    _write(source / "Main.qml", MAIN_QML)

    qt_prune.prune(site, TARGETS["linux-arm64"], {"QtCore"}, source_root=source)

    tree = pyside / "Qt" / "qml"
    for module in ("QtQuick", "QtQuick.Templates", "QtQuick.Controls", "QtQuick.Controls.Basic"):
        assert tree.joinpath(*module.split(".")).is_dir(), module
    # 插件原生库：QML 运行时只 dlopen 这些，不保留就是「模块未安装」。
    for module, plugin in (
        ("QtQuick", "qtquick2plugin"),
        ("QtQuick.Templates", "qtquicktemplates2plugin"),
        ("QtQuick.Controls", "qtquickcontrols2plugin"),
        ("QtQuick.Controls.Basic", "qtquickcontrols2basicstyleplugin"),
        ("QtQuick.Controls.Fusion", "qtquickcontrols2fusionstyleplugin"),
    ):
        library = tree.joinpath(*module.split(".")) / ("lib%s.so" % plugin)
        assert library.stat().st_size > 0, library
    # 未被导入的样式照旧删掉（Basic 由 ``default import`` 拉进来）。
    assert not (tree / "QtQuick" / "Controls" / "Material").exists()


def test_qml_plugin_binaries_are_the_kept_module_libraries(tmp_path, isolated_prune):
    """"保留的模块目录 → 其原生库" 是一个纯函数，可直接断言，不依赖裁剪顺序。"""
    site, pyside = _site(tmp_path)
    tree = pyside / "Qt" / "qml"

    found = qt_prune.qml_plugin_binaries(
        [tree / "QtQuick", tree / "QtQuick" / "Controls" / "Basic"]
    )

    names = sorted(path.name for path in found)
    # ``QtQuick`` 目录包含 Controls 与其样式，所以插件会被多个根重复列出——
    # 结果必须去重，否则同一个库会被当成多个可达性根。
    assert names == [
        "libqtquick2plugin.so",
        "libqtquickcontrols2basicstyleplugin.so",
        "libqtquickcontrols2fusionstyleplugin.so",
        "libqtquickcontrols2plugin.so",
        "libqtquicktemplates2plugin.so",
    ]
    assert len(found) == len(set(found))


def test_a_style_the_app_imports_survives_pruning(tmp_path, isolated_prune):
    """显式 ``import QtQuick.Controls.Material`` 时那个样式必须留下。"""
    site, pyside = _site(tmp_path)
    tree = pyside / "Qt" / "qml"
    _module(tree, "QtQuick.Controls.Material", "qtquickcontrols2materialstyleplugin")
    source = tmp_path / "src"
    _write(source / "Main.qml", MAIN_QML + "import QtQuick.Controls.Material\n")

    qt_prune.prune(site, TARGETS["linux-arm64"], {"QtCore"}, source_root=source)

    assert (tree / "QtQuick" / "Controls" / "Material").is_dir()
    assert (tree / "QtQuick" / "Controls" / "Material" / "libqtquickcontrols2materialstyleplugin.so").is_file()
