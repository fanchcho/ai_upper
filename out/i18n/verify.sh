#!/bin/bash
set -u
cd /home/agent/shared_workspace/ai_upper
export LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu"
export AI_UPPER_HOME=/tmp/ai-upper-i18n-test
export QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software
export TMPDIR="$PWD/.tmp"
mkdir -p "$AI_UPPER_HOME"
env -u PYTHONPATH .venv/bin/python -m pytest app/tests -q --basetemp=/tmp/ai-upper-i18n-test/all > out/i18n/pytest.txt 2>&1
rc=$?
echo "$rc" > out/i18n/pytest.exit
tail -35 out/i18n/pytest.txt
exit "$rc"
