#!/bin/bash
set -u
cd /home/agent/shared_workspace/ai_upper
export LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu"
export AI_UPPER_HOME=/tmp/ai-upper-i18n-test
export QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software
export TMPDIR="$PWD/.tmp"
export I18N_TEST_FONT="$PWD/.tmp/theme-settings/NotoSansCJKsc-Regular.otf"
export I18N_EVIDENCE="$PWD/out/i18n"
mkdir -p "$AI_UPPER_HOME"
env -u PYTHONPATH .venv/bin/python -m pytest app/tests/test_native_i18n.py app/tests/test_qml_settings_theme.py app/tests/test_qml_chat_files.py -q --basetemp=/tmp/ai-upper-i18n-test/focused
