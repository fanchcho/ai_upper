#!/bin/bash
# 原版逐页实拍：一套 120 条会话的固定数据 + 固定 config，按页逐个起窗口截 1280x820。
#
# 用法: scripts/parity/deva_pages_all.sh [输出目录]
# 每页一张 <page>-deva.png；页面清单与 QML 侧 scripts/parity/qml_pages_all.sh 相同。
#
# deva 工程只读：只启动它、不写它。
set -u
OUT="${1:-out/qml-shell/pages/deva}"
FIXTURE=/tmp/fx-pages/data/chats
CONFIG=/tmp/fx-page-home/config.json
DARK_CONFIG=/tmp/fx-page-home/config-dark.json

mkdir -p "$OUT"
if [ ! -d "$FIXTURE" ]; then
  echo "缺少固定数据 $FIXTURE，先跑 make_pages_fixture.py" >&2
  exit 2
fi

# 深色主题那份只改 theme 字段。
python3 - "$CONFIG" "$DARK_CONFIG" <<'PY'
import json, sys
cfg = json.load(open(sys.argv[1]))
cfg['theme'] = 'dark'
json.dump(cfg, open(sys.argv[2], 'w'), ensure_ascii=False, indent=2)
PY

run() {  # run <page> [config] [seed-chats]
  # 第三个参数允许显式传空串 = 不预置会话；用 ${3-...} 而不是 ${3:-...}，否则空串会被替换成默认值。
  local page="$1" cfg="${2:-$CONFIG}" seed="${3-$FIXTURE}"
  bash scripts/parity/deva_page_shot.sh "$page" "$OUT/$page-deva.png" "/tmp/pg-home-$page" "$seed" "$cfg" >/dev/null 2>&1
  if [ -f "$OUT/$page-deva.png" ]; then
    echo "ok   $page $(identify -format '%wx%h %b' "$OUT/$page-deva.png")"
  else
    echo "FAIL $page"
  fi
}

# 空态：没有任何会话、但有可用模型的正常启动 → 中列 QuickStart。
run empty "$CONFIG" ""
# 首启：全新 DEVA_HOME，连 config.json 都没有 → 原版的首次启动引导。
run first-run "$CONFIG" ""
run chat
run search-open
run search-results
run search-none
run ctx-menu
run delete-confirm
run model-picker
run hover-thread
run focus-composer
run long-mid
run long-bottom
run settings-general
run settings-models
run settings-extensions
run settings-about
run dark-chat "$DARK_CONFIG"
