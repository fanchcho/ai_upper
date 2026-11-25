# 从仓库根运行；测试夹具和运行数据均隔离。
export AI_UPPER_HOME=/tmp/ai-upper-plugin-port
export LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu"
export QT_QUICK_BACKEND=software
export QT_QPA_PLATFORM=offscreen
export TMPDIR="$PWD/.tmp"
# conftest 已设置导入路径；不要覆盖 PYTHONPATH，避免与打包环境继承用例冲突。
env -u PYTHONPATH .venv/bin/python -m pytest app/tests -q --basetemp=/tmp/ai-upper-plugin-port/reproduce-all > out/chrome-upgrade/port/reproduce-all.log 2>&1; echo rc=$?
env -u PYTHONPATH .venv/bin/python -m pytest app/tests/test_qml_*.py -q --basetemp=/tmp/ai-upper-plugin-port/reproduce-qml > out/chrome-upgrade/port/reproduce-qml.log 2>&1; echo rc=$?

# 最终运行链路针对性测试（24项）
env -u PYTHONPATH .venv/bin/python -m pytest app/tests/test_plugin_runtime.py app/tests/test_plugin_port.py app/tests/test_plugin_recovery.py app/tests/test_qml_plugin_settings.py -q --basetemp=/tmp/ai-upper-plugin-port/reproduce-runtime > out/chrome-upgrade/port/reproduce-runtime.log 2>&1; echo rc=$?
# 最终完整代码的全量与QML日志分别为 final-all.log / final-qml.log。
# 字体和显示后端来自当前环境；截图是offscreen，不是macOS或WM证据。
