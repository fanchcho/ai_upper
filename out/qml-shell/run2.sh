#!/usr/bin/env bash
# 证据脚本（里程碑 2）：真实数据截图、空状态截图、真实模型往返。
# 用法（仓库根目录）：bash out/qml-shell/run2.sh 2>&1 | tee out/qml-shell/run2.log
#
# 三跑：
#   1) 真实会话（含代码块与表格）→ shot-real.png
#   2) 空 home（无会话）→ shot-empty.png
#   3) 空 home 里真发一条消息 → shot-turn.png（原始 SEND/STREAM/DONE 日志）
set -x
cd "$(dirname "$0")/../.." || exit 1

.venv/bin/python -c 'import PySide6, sys; print("python", sys.version.split()[0], "PySide6", PySide6.__version__)'

# 每次都从零灌数据，避免上一跑的残留会话混进截图。
rm -rf out/qml-shell/home-real out/qml-shell/home-empty
.venv/bin/python out/qml-shell/seed_home.py out/qml-shell/home-real
.venv/bin/python out/qml-shell/seed_home.py out/qml-shell/home-empty --empty

AI_UPPER_UI=qml AI_UPPER_HEADLESS=1 AI_UPPER_HOME=out/qml-shell/home-real \
  AI_UPPER_QML_SHOT=out/qml-shell/shot-real.png .venv/bin/python app/src/main.py
echo "EXIT(real) $?"

AI_UPPER_UI=qml AI_UPPER_HEADLESS=1 AI_UPPER_HOME=out/qml-shell/home-empty \
  AI_UPPER_QML_SHOT=out/qml-shell/shot-empty.png .venv/bin/python app/src/main.py
echo "EXIT(empty) $?"

AI_UPPER_UI=qml AI_UPPER_HEADLESS=1 AI_UPPER_HOME=out/qml-shell/home-empty \
  AI_UPPER_QML_SHOT=out/qml-shell/shot-turn.png \
  AI_UPPER_QML_SEND='只说三个字：收到。' .venv/bin/python app/src/main.py
echo "EXIT(turn) $?"

ls -l out/qml-shell/shot-real.png out/qml-shell/shot-empty.png out/qml-shell/shot-turn.png
# 本机没有 `file` 命令；直接读 PNG 头确认真的是 PNG 且尺寸非零。
.venv/bin/python - <<'PY'
import struct
for name in ("out/qml-shell/shot-real.png", "out/qml-shell/shot-empty.png", "out/qml-shell/shot-turn.png"):
    with open(name, "rb") as fh:
        head = fh.read(33)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", name
    width, height = struct.unpack(">II", head[16:24])
    print(name, "PNG", width, "x", height)
PY
echo "EXIT(check) $?"

# 落盘证据：发完之后会话文件里到底有什么（用户消息 + 助手回复）。
.venv/bin/python - <<'PY'
import json, glob
for path in sorted(glob.glob("out/qml-shell/home-empty/data/chats/*.json")):
    if path.endswith("_index.json"):
        continue
    data = json.load(open(path, encoding="utf-8"))
    print("CHAT", path, "title=", data.get("title"), "messages=", len(data.get("messages", [])))
    for message in data.get("messages", []):
        print("  ", message.get("role"), ":", json.dumps(message.get("content"), ensure_ascii=False))
PY
echo "EXIT(disk) $?"
