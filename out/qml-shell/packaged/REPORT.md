# 里程碑 3 · 打包链带 QML（产物实跑）

1. 落位：`tools/ai_upper/package.py:309` 把 `app/src/qml` 拷到 `<bundle>/assets/qml`（含 `qmldir`）。
2. 不入 egg：`tools/ai_upper/python_build.py:961-998` 只清 `site/qml`，不再误删 `PySide6/Qt/qml/**` 运行时。
3. 裁剪：`tools/ai_upper/qt_prune.py:260-276` 推出平台默认 Controls 样式，`1078` 折进依赖起点，`1080` 把 qml 插件库当可达性根；产品保留 QtQml/QtQuick/Controls/Basic/Fusion/impl/Layouts/Shapes/Templates/Window。
4. 产物实跑：`AI_UPPER_UI=qml AI_UPPER_HEADLESS=1 dist/ai_upper/ai_upper` → `QML OK ... size=1280x820`、`EXIT 0`（run.log:633/635）。
5. PNG：`/home/agent/shared_workspace/py_upper/out/qml-shell/packaged/shot.png`（34212 B，1280×820）。
6. pytest：`1159 passed, 5 skipped`（基线 1150/5，+9；新增 `app/tests/test_qml_packaging.py` 6 例 + `test_qt_prune.py` 3 例）。
7. 变异 1（`qml_sources` 退回空）：`7 failed, 52 passed`，真实 wheel `PROBE rc=1 / ROOTS 0`，缺 `libQt6QuickControls2Fusion.so.6`。
8. 变异 2（去掉默认样式推导）：保留文件 191→112，`PROBE rc=1`，报 `module "QtQuick.Controls.Fusion" is not installed`，`3 failed, 56 passed`。
9. 两次变异均已恢复源码并复跑 `59 passed`；原始输出见 `mutate.log` / `mutate-style.log`。
