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

FAILED=()
PRODUCED=0

run() {  # run <page> [config] [seed-chats]
  # 第三个参数允许显式传空串 = 不预置会话；用 ${3-...} 而不是 ${3:-...}，否则空串会被替换成默认值。
  local page="$1" cfg="${2:-$CONFIG}" seed="${3-$FIXTURE}"
  # 空图重试一次：Xvfb/Electron 偶尔没画出首帧就截到全黑或全白（<5KB），
  # 这种图若留在证据里会让「像素差异」变成假数据。
  local attempt bytes
  for attempt in 1 2; do
    rm -f "$OUT/$page-deva.png"
    bash scripts/parity/deva_page_shot.sh "$page" "$OUT/$page-deva.png" "/tmp/pg-home-$page" "$seed" "$cfg" >/dev/null 2>&1
    if [ -f "$OUT/$page-deva.png" ]; then
      bytes=$(stat -c %s "$OUT/$page-deva.png")
      if [ "$bytes" -ge 5000 ]; then
        echo "ok   $page $(identify -format '%wx%h %b' "$OUT/$page-deva.png")"
        PRODUCED=$((PRODUCED + 1))
        return 0
      fi
    fi
    echo "retry $page (attempt $attempt)"
  done
  echo "FAIL $page"
  FAILED+=("$page")
  return 1
}

# 只跑指定页：`deva_pages_all.sh out/... chat empty`（不给页名 = 全跑）。
# 分块跑是因为 18 页一次性跑约 7 分钟，跑挂了要整批重来；分块能把失败限制在一小段里。
# 注意 $1 是输出目录，页名从 $2 开始；早先写成 "$*" 会把输出目录也算进页名，
# 于是所有 want 判定都不命中、静默产出 0 张图还返回 0。
ONLY="${*:2}"
want() {
  [ -z "$ONLY" ] && return 0
  case " $ONLY " in
    *" $1 "*) return 0 ;;
    *) return 1 ;;
  esac
}

run_if() {
  local page="$1"
  shift
  if want "$page"; then
    run "$page" "$@"
  fi
}

# 空态：没有任何会话、但有可用模型的正常启动 → 中列 QuickStart。
run_if empty "$CONFIG" ""
run_if first-run "$CONFIG" ""
run_if chat
run_if search-open
run_if search-results
run_if search-none
run_if ctx-menu
run_if delete-confirm
run_if model-picker
run_if hover-thread
run_if focus-composer
run_if long-mid
run_if long-bottom
run_if settings-general
run_if settings-models
run_if settings-extensions
run_if settings-about
run_if dark-chat "$DARK_CONFIG"

# 静默成功是这次踩到的坑：筛选条件与实跑页名对不上时，跑 0 页也返回 0。收尾把
# 「一张都没产出」和「有页失败」都变成非零退出码，调用方（CI / 分块脚本）才看得见。
if [ "$PRODUCED" -eq 0 ]; then
  echo "FAIL: 0 页产出（输出目录 $OUT，筛选条件 ONLY='${ONLY}'）" >&2
  exit 1
fi
if [ "${#FAILED[@]}" -gt 0 ]; then
  echo "FAIL: ${#FAILED[@]} 页失败: ${FAILED[*]}" >&2
  exit 1
fi
echo "done: $PRODUCED 页 -> $OUT"
