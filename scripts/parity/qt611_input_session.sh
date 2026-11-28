#!/usr/bin/env bash
set -euo pipefail
# Run inside a private D-Bus session and Xvfb; the application keeps its venv Qt.
: "${AI_UPPER_HOME:?}" "${FCITX_PLUGIN_ROOT:?}" "${PARITY_OUTPUT_DIR:?}" "${PROBE_THEME:?}"
export XDG_CONFIG_HOME="$AI_UPPER_HOME/xdg-config"
export XDG_DATA_HOME="$AI_UPPER_HOME/xdg-data"
export XDG_RUNTIME_DIR="$AI_UPPER_HOME/xdg-runtime"
mkdir -p "$XDG_CONFIG_HOME/fcitx5" "$XDG_DATA_HOME" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
cat > "$XDG_CONFIG_HOME/fcitx5/profile" <<'EOF'
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
EOF
dbus-monitor --session 'interface=org.fcitx.Fcitx.InputContext1' 'interface=org.fcitx.Fcitx.InputMethod1' > "$PARITY_OUTPUT_DIR/ime-$PROBE_THEME-dbus.log" 2>&1 &
monitor_pid=$!
fcitx5 --replace --disable=wayland -d > "$PARITY_OUTPUT_DIR/fcitx-$PROBE_THEME.log" 2>&1
trap 'fcitx5-remote -e || true; kill "$monitor_pid" 2>/dev/null || true' EXIT
QT_IM_MODULE=fcitx QT_DEBUG_PLUGINS=1 QT_PLUGIN_PATH="$FCITX_PLUGIN_ROOT" \
    .venv/bin/python scripts/parity/full_app_local_turn.py
