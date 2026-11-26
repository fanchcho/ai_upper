export LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu"
export AI_UPPER_HOME=/tmp/ai-upper-i18n-close
export QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software TMPDIR="$PWD/.tmp"
.venv/bin/python -m pytest app/tests -q --basetemp=/tmp/ai-upper-i18n-close/final3 > out/i18n/close/pytest-final.txt 2>&1
echo $? > out/i18n/close/pytest-final.exit
