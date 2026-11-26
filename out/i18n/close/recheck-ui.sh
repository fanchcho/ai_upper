export AI_UPPER_HOME=/tmp/ai-upper-i18n-close
export LD_LIBRARY_PATH="$PWD/.tmp/wm/usr/lib/aarch64-linux-gnu"
export QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software TMPDIR="$PWD/.tmp"
for lang in en zh-CN; do
  AI_UPPER_LANG="$lang" .venv/bin/python out/i18n/close/render-widgets.py "out/i18n/close/$lang" > "out/i18n/close/$lang-shots-final.txt" 2>&1
  AI_UPPER_LANG="$lang" .venv/bin/python out/i18n/close/render-widgets-dark.py "out/i18n/close/$lang-dark" > "out/i18n/close/$lang-dark-shots-final.txt" 2>&1
done
