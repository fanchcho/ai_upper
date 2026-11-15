# qt_prune QML 保留：修复与变异检验

日期：2026-11-15　分支：`develop`

## 缺陷

`prune()` 判断「要不要保留 QML 运行时」只看一件事件：`modules` 里有没有
`QtQml*`/`QtQuick*`。而 `modules` 来自 `app/src` 的 **Python import 扫描**。
一个只把 `.qml` 当资源加载的应用，Python 侧一行 QML import 都没有，于是：

1. 整棵 `Qt/qml`（36 MB）被 `drop(layout.qml)` 删掉；
2. shiboken 的 `libpyside6qml*` 一起被删；
3. 即使保住树，QML 插件 `libqtquickcontrols2plugin.so` 等也不在任何 Python
   包装模块的原生闭包里，可达性扫描会把 `libQt6Quick*` 删掉。

产物启动后 QML 引擎报 `module "QtQuick" is not installed`，窗口空白。

## 修复

`tools/ai_upper/qt_prune.py`：

- `qml_source_roots()/qml_sources()/qml_imports()`：扫 `app/src`、`app/assets/qml`、
  `app/resources` 下的 `.qml` import，得到 QML 模块名；
- `qml_required_modules()`：QML 模块名 → Qt 库模块名（`QML_MODULE_LIBRARIES`），
  折进 `modules`，让包装模块与插件分类按它保留；
- `qml_module_directories()`/`qml_shipped_modules()`：读 `qmldir` 的
  `module`/`import`/`depends` 与模块内 `.qml` 的 import 求闭包；`optional import`
  （Controls 的 Fusion/Material/…）不跟，`designer`/`tooling` 子树不算模块；
- `prune_qml_tree()`：逐模块删除，未被 import 的 QML 模块目录整个删掉；
- `qml_plugin_binaries()`：保留下来的模块目录里的原生插件库，作为可达性扫描的
  **根**（`reachable = wrapper ∪ plugins ∪ qml_libraries`）；
- `prune()` 新增 `source_root` 参数（缺省 `app/src` + 资源树），测试可注入。

## 变异检验

每一条都是「把修复的一处退回原样，观察用例是否变红」，跑完立即恢复。

命令（两次之间只有被测代码不同）：

```
cd app && ../.venv/bin/python -m pytest tests/test_qt_prune.py -q
```

| # | 变异 | 结果 |
| --- | --- | --- |
| A | 不把 `qml_required_modules()` 折进 `modules` | **红**：`test_prune_keeps_the_qml_runtime_for_a_resource_only_qml_app`（`QtQuick` 目录没了） |
| B | 可达性集合不带 `qml_libraries` | **红**：同上（`libQt6Quick.so.6` 被删） |
| C | `qml_modules = set()`（不裁 QML 树） | **红**：同上 + `test_qml_optional_imports_are_only_kept_when_used` |
| D | 跟 `optional import` 求闭包（不排除 optional） | **红**：同上 + `test_qml_optional_imports_are_only_kept_when_used` |
| E | 无条件 `drop(layout.qml)` | **红**：同上两条 |
| F | `_qml_imports_in()` 不跳过 `designer`/`tooling` | **红**：`test_prune_keeps_the_qml_runtime_for_a_resource_only_qml_app`（tooling 里的 Shapes 把 Shapes 拖了进来） |

恢复后：`50 passed in 0.99s`（原有 45 条 + 新增 5 条）。

## 新增用例

`app/tests/test_qt_prune.py`：

- `test_qml_sources_are_scanned_from_the_application_tree`
- `test_prune_keeps_the_qml_runtime_for_a_resource_only_qml_app`（正）
- `test_prune_still_drops_the_qml_tree_without_qml_sources`（反）
- `test_prune_drops_the_qml_tree_when_the_python_import_is_absent_too`（反）
- `test_qml_optional_imports_are_only_kept_when_used`（optional 语义）

同时给 autouse fixture 加了隔离：默认的 `qml_source_roots()` 在工作副本里会查到
本应用自己的 `.qml`，不隔离的话每条 prune 用例都会跟着工作区的 QML 状态漂移。
