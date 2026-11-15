#!/usr/bin/env bash
# 证据脚本（里程碑 3）：在**真实打包产物**上跑 QML 壳。
# 用法（仓库根）：bash out/qml-shell/packaged/run-packaged.sh 2>&1 | tee out/qml-shell/packaged/run.log
set -x
cd "$(dirname "$0")/../../.." || exit 1

BUNDLE=dist/ai_upper
EXE=$BUNDLE/ai_upper
SHOT=out/qml-shell/packaged/shot.png

ls -l "$EXE" || exit 1
# 产物里到底有没有 QML：模块树、插件原生库、assets/qml 入口。
ls -l "$BUNDLE/assets/qml" || exit 1
ls -d "$BUNDLE"/site-packages/PySide6/Qt/qml/QtQuick/Controls/Fusion || exit 1
ls -l "$BUNDLE"/site-packages/PySide6/Qt/qml/QtQuick/Controls/libqtquickcontrols2plugin.so || exit 1
ls -l "$BUNDLE"/site-packages/PySide6/Qt/qml/QtQuick/Controls/Fusion/libqtquickcontrols2fusionstyleplugin.so || exit 1
du -sb "$BUNDLE"/site-packages/PySide6/Qt/qml || exit 1

rm -f "$SHOT"

# 不传 AI_UPPER_HOME：launcher 用 SetEnvironmentVariable/setenv 覆盖它，
# 值就是产物根（AiUpper.cpp:881）。所以数据目录 = dist/ai_upper，全新产物即空状态。
AI_UPPER_UI=qml AI_UPPER_HEADLESS=1 AI_UPPER_QML_SHOT=$SHOT "$EXE"
echo "EXIT $?"

ls -l "$SHOT" || exit 1
.venv/bin/python - "$SHOT" <<'PY'
import struct, sys
with open(sys.argv[1], "rb") as fh:
    head = fh.read(33)
assert head[:8] == b"\x89PNG\r\n\x1a\n", sys.argv[1]
w, h = struct.unpack(">II", head[16:24])
print("PNG", sys.argv[1], "%dx%d" % (w, h))
PY
