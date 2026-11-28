#!/usr/bin/env bash
set -euo pipefail
# Existing isolated X11/D-Bus utilities are reused; no Qt 6.8 library path here.
export FCITX_PLUGIN_ROOT="${FCITX_PLUGIN_ROOT:-/tmp/ai-upper-qt611-sdk/plugins}"
export PARITY_OUTPUT_DIR="${PARITY_OUTPUT_DIR:-$PWD/docs/audit/qt611}"
export PATH="$PWD/.tmp/icon-dpi/runtime/usr/bin:$PWD/.tmp/wm/usr/bin:$PWD/.tmp/secret-service/root/usr/bin:$PATH"
export LD_LIBRARY_PATH="$PWD/.venv/lib/python3.13/site-packages/PySide6/Qt/lib:$PWD/.tmp/secret-service/root/usr/lib/aarch64-linux-gnu:$PWD/.tmp/extensions-complete/runtime/usr/lib/aarch64-linux-gnu:$PWD/.tmp/icon-dpi/runtime/usr/lib/aarch64-linux-gnu:$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu"
export QT_QPA_PLATFORM=xcb QT_QUICK_BACKEND=software
mkdir -p "$PARITY_OUTPUT_DIR" .tmp/qt611-input
export TMPDIR="$PWD/.tmp/qt611-input"
for theme in ${PROBE_THEMES:-dark light}; do
    export AI_UPPER_HOME
    AI_UPPER_HOME=$(mktemp -d "/tmp/ai-upper-qt611-$theme-XXXXXX")
    export PROBE_THEME="$theme"
    set +e
    .tmp/wm/usr/bin/xvfb-run -a .tmp/secret-service/root/usr/bin/dbus-run-session \
        --config-file="$PWD/.tmp/secret-service/bus.conf" -- \
        bash scripts/parity/qt611_input_session.sh > "$PARITY_OUTPUT_DIR/qml-$theme.log" 2>&1
    code=$?
    set -e
    printf '%s\n' "$code" > "$PARITY_OUTPUT_DIR/qml-$theme.exit"
done
