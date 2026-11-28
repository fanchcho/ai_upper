export XDG_CONFIG_HOME=$PWD/.tmp/environment-closeout/ime-config XDG_DATA_HOME=$PWD/.tmp/environment-closeout/ime-data XDG_RUNTIME_DIR=$PWD/.tmp/environment-closeout/ime-runtime
mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_RUNTIME_DIR"
dbus-monitor --session "interface=org.fcitx.Fcitx.InputContext1" "interface=org.fcitx.Fcitx.InputMethod1" > "docs/audit/full-ime/ime-${PROBE_THEME}-dbus.log" 2>&1 &
fcitx5 -d > "docs/audit/full-ime/fcitx-${PROBE_THEME}.log" 2>&1
QT_IM_MODULE=fcitx QT_DEBUG_PLUGINS=1 QT_PLUGIN_PATH=$PWD/.tmp/deep-boundary/qt-runtime/usr/lib/aarch64-linux-gnu/qt6/plugins:/usr/lib/aarch64-linux-gnu/qt6/plugins /usr/bin/python3 scripts/parity/full_app_ime.py
