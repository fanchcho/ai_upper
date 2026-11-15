#!/usr/bin/env bash
# 变异检验：把「按 .qml 保留 QML」这条判定退回旧版（只看 Python import），
# 证明 1) 真实 wheel 上裁完的产物缺 QML 模块树、2) 真产物启动失败、
# 3) 新用例变红。最后恢复源码并确认重新变绿。
#
# 用法（仓库根）：bash out/qml-shell/packaged/mutate.sh 2>&1 | tee out/qml-shell/packaged/mutate.log
set -x
cd "$(dirname "$0")/../../.." || exit 1

QT=tools/ai_upper/qt_prune.py
cp "$QT" /tmp/qt_prune.py.keep || exit 1
trap 'cp /tmp/qt_prune.py.keep "$QT"' EXIT

# 旧判定：QML 源码扫描永远返回空，于是 prune() 认为应用没有 QML，
# 走 `if not any(name.startswith(QML_MODULE_PREFIXES) ...): drop(layout.qml)`。
.venv/bin/python - "$QT" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
needle = "def qml_sources(source_root: Path | None = None) -> list[Path]:"
assert needle in text
old = (
    "def qml_sources(source_root: Path | None = None) -> list[Path]:\n"
    "    return []  # MUTATION: 旧判定，只看 Python import\n\n\n"
    "def _qml_sources_disabled(source_root: Path | None = None) -> list[Path]:"
)
path.write_text(text.replace(needle, old, 1), encoding="utf-8")
print("MUTATION applied")
PY

echo "=== (1) 用例：新用例必须变红 ==="
.venv/bin/python -m pytest app/tests/test_qml_packaging.py app/tests/test_qt_prune.py -q 2>&1 | tail -20
echo "PYTEST_EXIT ${PIPESTATUS[0]}"

echo "=== (2) 真实 wheel 上按旧判定裁剪：QML 模块树应当整棵消失 ==="
.venv/bin/python out/qml-shell/packaged/probe_qml_prune.py 2>&1 | tail -25
echo "PROBE_EXIT ${PIPESTATUS[0]}"

cp /tmp/qt_prune.py.keep "$QT"
echo "=== (3) 恢复后必须重新变绿 ==="
.venv/bin/python -m pytest app/tests/test_qml_packaging.py app/tests/test_qt_prune.py -q 2>&1 | tail -5
echo "RESTORED_EXIT ${PIPESTATUS[0]}"
