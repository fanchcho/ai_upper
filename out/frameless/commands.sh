# 从仓库根执行；工具通过 apt-get download + dpkg-deb -x 解压在 .tmp/wm。
# 不安装到系统；Xvfb 的 /usr/bin 字符串改为 .tmp，使用 .tmp/xkbcomp 链接。
export LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu"
export PATH="$PWD/.tmp/wm/usr/bin:$PATH"
export AI_UPPER_HOME=/tmp/ai-upper-frameless-20261125
export QT_QUICK_BACKEND=software
export TMPDIR="$PWD/.tmp"
export PYTHONPATH="$PWD/app/src"
# 改前会话 :100，最终独立会话 :101（:99 留有早期启动失败的锁）。
# 在持久终端中启动：
# Xvfb :101 -screen 0 1600x1100x24 -ac -xkbdir "$PWD/.tmp/wm/usr/share/X11/xkb" > out/frameless/final-xvfb.log 2>&1
# DISPLAY=:101 XDG_DATA_DIRS="$PWD/.tmp/wm/usr/share" openbox --config-file "$PWD/.tmp/wm/etc/xdg/openbox/rc.xml" > out/frameless/final-openbox.log 2>&1
# DISPLAY=:101 QT_QPA_PLATFORM=xcb .venv/bin/python app/src/main.py > out/frameless/accepted-app.log 2>&1
# xprop/xwininfo、鼠标操作、截图命令及 rc 见 accepted-wm-actions.log。
# DISPLAY=:101 QT_QPA_PLATFORM=xcb .venv/bin/python scripts/parity/verify_frameless_wm.py <wid> out/frameless > out/frameless/accepted-wm-actions.log 2>&1; echo rc=$?
.venv/bin/python -m pytest app/tests/test_qml_*.py -q --basetemp=/tmp/ai-upper-frameless-20261125/reproduce-tests > out/frameless/reproduce-tests.log 2>&1; echo rc=$?
.venv/bin/python scripts/parity/compare_frameless_shots.py out/frameless > out/frameless/reproduce-pixels.log 2>&1; echo rc=$?
