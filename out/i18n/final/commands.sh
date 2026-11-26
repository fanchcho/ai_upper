#!/bin/bash
# Run from repository root; verification data stays isolated from ~/.ai_upper.
export AI_UPPER_HOME=/tmp/ai-upper-final
export TMPDIR="$PWD/.tmp"
export QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software
export LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu"
.venv/bin/python out/i18n/final/audit.py
.venv/bin/python out/i18n/final/cli-evidence.py
.venv/bin/python out/i18n/final/live-settings.py
.venv/bin/python out/i18n/final/render.py
for lang in en zh-CN; do
  AI_UPPER_LANG="$lang" .venv/bin/python out/i18n/close/render-widgets.py "out/i18n/final/$lang"
  AI_UPPER_LANG="$lang" .venv/bin/python out/i18n/close/render-widgets-dark.py "out/i18n/final/$lang-dark"
done
.venv/bin/python -m pytest app/tests -q
