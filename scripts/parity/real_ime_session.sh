# Run inside the private D-Bus + Xvfb session documented in ime.md.
set -eu
export XDG_CONFIG_HOME=$PWD/.tmp/environment-closeout/ime-config XDG_DATA_HOME=$PWD/.tmp/environment-closeout/ime-data XDG_RUNTIME_DIR=$PWD/.tmp/environment-closeout/ime-runtime
mkdir -p "$XDG_CONFIG_HOME" "$XDG_DATA_HOME" "$XDG_RUNTIME_DIR"
dbus-monitor --session "interface=org.fcitx.Fcitx.InputContext1" "interface=org.fcitx.Fcitx.InputMethod1" > "docs/audit/deep-boundary/ime-${PROBE_THEME}-dbus.log" 2>&1 &
mkdir -p "$XDG_CONFIG_HOME/fcitx5"
cat > "$XDG_CONFIG_HOME/fcitx5/profile" <<'PROFILE'
[Groups/0]
Name=Default
Default Layout=us
DefaultIM=pinyin
[Groups/0/Items/0]
Name=keyboard-us
Layout=
[Groups/0/Items/1]
Name=pinyin
Layout=
[GroupOrder]
0=Default
PROFILE
fcitx5 -d > "docs/audit/deep-boundary/fcitx-${PROBE_THEME}.log" 2>&1
QT_IM_MODULE=fcitx QT_DEBUG_PLUGINS=1 QT_PLUGIN_PATH=/usr/lib/aarch64-linux-gnu/qt6/plugins /usr/bin/python3 scripts/parity/environment_ime_probe.py
