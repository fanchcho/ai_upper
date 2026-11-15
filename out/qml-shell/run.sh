#!/usr/bin/env bash
# 证据脚本：真实执行 QML 壳的两条 offscreen 路径，原始输出由调用方 tee 进 run.log。
# 用法（仓库根目录）：bash out/qml-shell/run.sh 2>&1 | tee out/qml-shell/run.log
set -x
cd "$(dirname "$0")/../.." || exit 1

.venv/bin/python -c 'import PySide6, sys; print("python", sys.version.split()[0], "PySide6", PySide6.__version__)'

AI_UPPER_UI=qml AI_UPPER_HEADLESS=1 .venv/bin/python app/src/main.py
echo "EXIT(run) $?"

AI_UPPER_UI=qml AI_UPPER_HEADLESS=1 AI_UPPER_QML_PLAIN=1 \
  AI_UPPER_QML_SHOT=out/qml-shell/shot-plain.png .venv/bin/python app/src/main.py
echo "EXIT(plain) $?"

ls -l out/qml-shell/shot.png out/qml-shell/shot-plain.png
# 本机没有 `file` 命令；直接读 PNG 头确认真的是 PNG 且尺寸非零。
.venv/bin/python - <<'PY'
import struct
for name in ("out/qml-shell/shot.png", "out/qml-shell/shot-plain.png"):
    head = open(name, "rb").read(33)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", name
    width, height = struct.unpack(">II", head[16:24])
    print(name, "PNG", width, "x", height)
PY
echo "EXIT(check) $?"
