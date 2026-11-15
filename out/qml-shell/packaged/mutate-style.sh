#!/usr/bin/env bash
# 变异检验 2：把「引擎自选的默认样式」这条保留逻辑退回旧版（只跟 .qml 的 import），
# 在真实 wheel 上重跑裁剪并真加载 Main.qml，证明产物会缺哪个模块、启动如何失败。
# 用法（仓库根）：bash out/qml-shell/packaged/mutate-style.sh 2>&1 | tee out/qml-shell/packaged/mutate-style.log
set -x
cd "$(dirname "$0")/../../.." || exit 1

QT=tools/ai_upper/qt_prune.py
cp "$QT" /tmp/qt_prune.style.keep || exit 1
trap 'cp /tmp/qt_prune.style.keep "$QT"' EXIT

.venv/bin/python - "$QT" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
needle = "        qml_imported |= qml_implicit_modules(qml_imported, target)\n"
assert needle in text
path.write_text(text.replace(needle, "        pass  # MUTATION: 旧判定，不补默认样式\n", 1), encoding="utf-8")
print("MUTATION applied")
PY

echo "=== 真实 wheel 裁剪 + 真引擎加载（旧判定）==="
.venv/bin/python out/qml-shell/packaged/probe_qml_prune.py 2>&1 | grep -E "PRUNE|PROBE|ROOTS|not installed|Fusion"
echo "PROBE_EXIT ${PIPESTATUS[0]}"

echo "=== 用例必须变红 ==="
.venv/bin/python -m pytest app/tests/test_qt_prune.py app/tests/test_qml_packaging.py -q 2>&1 | tail -8
echo "PYTEST_EXIT ${PIPESTATUS[0]}"

cp /tmp/qt_prune.style.keep "$QT"
echo "=== 恢复后 ==="
.venv/bin/python -m pytest app/tests/test_qt_prune.py app/tests/test_qml_packaging.py -q 2>&1 | tail -3
echo "RESTORED_EXIT ${PIPESTATUS[0]}"
