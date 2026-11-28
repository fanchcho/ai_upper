export XDG_RUNTIME_DIR=$PWD/.tmp/remaining-boundaries/xdg
export LD_LIBRARY_PATH=$PWD/.tmp/remaining-boundaries/weston/usr/lib/aarch64-linux-gnu:$PWD/.tmp/remaining-boundaries/weston/usr/lib/aarch64-linux-gnu/weston:$LD_LIBRARY_PATH
export WESTON_MODULE_MAP="x11-backend.so=$PWD/.tmp/remaining-boundaries/weston/usr/lib/aarch64-linux-gnu/libweston-14/x11-backend.so;kiosk-shell.so=$PWD/.tmp/remaining-boundaries/weston/usr/lib/aarch64-linux-gnu/weston/kiosk-shell.so"
.tmp/remaining-boundaries/weston/usr/bin/weston -B x11 --renderer=pixman --socket=ai-upper-nested --width=1280 --height=820 --idle-time=0 --no-config --shell=kiosk-shell.so > docs/audit/remaining-boundaries/weston-nested.log 2>&1 &
wpid=$!
sleep 2
export WAYLAND_DISPLAY=ai-upper-nested QT_QPA_PLATFORM=wayland QT_IM_MODULE=fcitx QT_QUICK_BACKEND=software
export XDG_CONFIG_HOME=$PWD/.tmp/remaining-boundaries/config XDG_DATA_HOME=$PWD/.tmp/remaining-boundaries/data
mkdir -p "$XDG_CONFIG_HOME/fcitx5"
cp .tmp/environment-closeout/ime-config/fcitx5/profile "$XDG_CONFIG_HOME/fcitx5/profile"
fcitx5 -d > docs/audit/remaining-boundaries/nested-fcitx.log 2>&1
dbus-monitor --session 'interface=org.fcitx.Fcitx.InputContext1' 'interface=org.fcitx.Fcitx.InputMethod1' > docs/audit/remaining-boundaries/nested-dbus.log 2>&1 &
export QT_PLUGIN_PATH=/tmp/ai-upper-qt611-sdk/plugins
export LD_LIBRARY_PATH=$PWD/.venv/lib/python3.13/site-packages/PySide6/Qt/lib:$LD_LIBRARY_PATH
export PARITY_OUTPUT_DIR=$PWD/docs/audit/remaining-boundaries/nested
mkdir -p "$PARITY_OUTPUT_DIR"
for theme in dark light; do
 AI_UPPER_HOME=/tmp/ai-upper-nested-$theme PROBE_THEME=$theme PYTHONPATH=$PWD/scripts/parity WAYLAND_DEBUG=1 .venv/bin/python scripts/parity/wayland_turn_probe.py > "$PARITY_OUTPUT_DIR/$theme.log" 2>&1
 printf '%s\n' "$?" > "$PARITY_OUTPUT_DIR/$theme.exit"
done
fcitx5-remote -e
kill "$wpid"
