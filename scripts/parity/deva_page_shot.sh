#!/bin/bash
# 原版 Deva 单页截图（固定 1280x820 客户端区，Xvfb 1400x900）。
#
# 用法: scripts/parity/deva_page_shot.sh <页面名> <输出 png> <DEVA_HOME> [<预置 chats 目录>] [<config.json 模板>]
#
# 页面名（与 QML 侧 scripts/parity/qml_page_shot.sh 同名，两边凑齐同一组才可比）：
#   chat            有消息的对话页（含代码块 + 表格）
#   empty           无会话（首启页 = 空状态，原版两者是同一屏）
#   first-run       会话 + 空列表两种起始状态（与 empty 同屏，保留别名便于对照）
#   search-open     搜索浮层已打开、未输入
#   search-results  搜索浮层：输入「会话」有结果
#   search-none     搜索浮层：输入 zzz 无结果
#   ctx-menu        会话行右键菜单
#   delete-confirm  右键 → Delete 后的确认框
#   model-picker    输入区模型下拉
#   hover-thread    鼠标悬停在会话行上（交互态）
#   focus-composer  输入框获得焦点（Send 禁用态）
#   long-mid        120 条会话滚到中途
#   long-bottom     120 条会话滚到底
#   dark-chat       深色主题下的对话页
#
# 隔离：每页起一份全新的 electron。起之前、截之后都强制清掉上一次的 electron / Xvfb，
# 否则没被回收的旧窗口会留在 root 上，导致后面每页截到的都是同一张旧图（踩过）。
#
# deva 工程只读：本脚本只启动它、不写它；数据全部落在 DEVA_HOME。
set -u
PAGE="${1:?用法: deva_page_shot.sh <页面名> <输出 png> <DEVA_HOME> [预置 chats]}"
OUT="${2:?缺少输出路径}"
HOME_DIR="${3:?缺少 DEVA_HOME}"
SEED_DIR="${4:-}"
CONFIG_FILE="${5:-}"
DEVA_ROOT=/home/agent/shared_workspace/deva
DISPLAY_NUM=:97

cleanup() {
  pkill -f "apps/desktop/out/main/index.js" >/dev/null 2>&1
  pkill -f "Xvfb ${DISPLAY_NUM}" >/dev/null 2>&1
  for _ in $(seq 1 40); do
    if ! pgrep -f "apps/desktop/out/main/index.js" >/dev/null 2>&1; then break; fi
    sleep 0.2
  done
  wait 2>/dev/null
  rm -f "/tmp/.X${DISPLAY_NUM#:}-lock" "/tmp/.X11-unix/X${DISPLAY_NUM#:}"
}
trap cleanup EXIT

mkdir -p "$(dirname "$OUT")"
rm -rf "$HOME_DIR" && mkdir -p "$HOME_DIR"
if [ -n "$SEED_DIR" ] && [ -d "$SEED_DIR" ]; then
  mkdir -p "$HOME_DIR/data/chats"
  cp -a "$SEED_DIR"/. "$HOME_DIR/data/chats/"
fi
# 语言 / 主题 / 可用模型由调用方先写进 config.json（见 make_pages_config.py）：
# 参数 5 给出模板时复制过来，否则补一份默认（英文 + 浅色），保证两端文案一致。
if [ -n "$CONFIG_FILE" ] && [ -f "$CONFIG_FILE" ]; then
  cp "$CONFIG_FILE" "$HOME_DIR/config.json"
elif [ ! -f "$HOME_DIR/config.json" ]; then
  printf '{"locale":"en","theme":"light"}\n' >"$HOME_DIR/config.json"
fi

cleanup
export DISPLAY=$DISPLAY_NUM
Xvfb "$DISPLAY_NUM" -screen 0 1400x900x24 >/tmp/xvfb-page.log 2>&1 &
XPID=$!
sleep 2

# 独立 user-data-dir：electron 默认共享 ~/.config/Electron，第二份进程会被单实例锁拦下、
# 直接把新 url 转给旧进程然后自己退出——那正是之前「每页截到同一张旧图」的根因。
PROFILE_DIR="/tmp/electron-profile-$(basename "$HOME_DIR")"
rm -rf "$PROFILE_DIR" && mkdir -p "$PROFILE_DIR"
DEVA_HOME="$HOME_DIR" "$DEVA_ROOT/node_modules/electron/dist/electron" \
  --no-sandbox --disable-gpu --user-data-dir="$PROFILE_DIR" \
  "$DEVA_ROOT/apps/desktop/out/main/index.js" >/tmp/deva-page.log 2>&1 &
EPID=$!
sleep 10

# 窗口出现要等（Electron 首帧 5–15s 波动很大）。轮询到 30s，别在窗口还没 map 时
# 就断言「找不到窗口」——那会把整个页面判成失败。
WID=""
for _ in $(seq 1 60); do
  WID=$(xdotool search --name '^Deva$' 2>/dev/null | head -1)
  [ -z "${WID:-}" ] && WID=$(xdotool search --class electron 2>/dev/null | head -1)
  [ -n "${WID:-}" ] && break
  sleep 0.5
done
if [ -n "${WID:-}" ]; then
  xdotool windowmove "$WID" 0 0 windowsize "$WID" 1280 820
  xdotool windowactivate "$WID" 2>/dev/null
  # 内容（会话列表 / 正文）比窗口晚到，多给 3s 让首屏数据落定。
  sleep 3
else
  echo "未找到 Deva 窗口，见 /tmp/deva-page.log" >&2
  exit 3
fi

xdotool mousemove 200 700
sleep 0.6

shot() { import -window root /tmp/page-raw.png && convert /tmp/page-raw.png -crop 1280x820+0+0 +repage "$OUT"; }
click() { xdotool mousemove "$1" "$2" click 1; sleep "${3:-1.0}"; }
rclick() { xdotool mousemove "$1" "$2" click 3; sleep 1.0; }
type_text() { xdotool type --delay 40 "$1"; sleep 1.2; }

case "$PAGE" in
  chat)
    click 160 90 2.5
    xdotool mousemove 200 700; sleep 0.4
    shot
    ;;
  empty)
    # 首启 = 空状态：原版没有会话时右侧就是「Start a conversation」，两者是同一屏。
    shot
    ;;
  first-run)
    shot
    ;;
  search-open)
    click 180 27 1.2
    xdotool mousemove 200 700; sleep 0.4
    shot
    ;;
  search-results)
    # xdotool 打不出中文（没有对应键位映射），用能命中中文标题的 ASCII 片段。
    click 180 27 1.2
    type_text '00'
    xdotool mousemove 200 700; sleep 0.4
    shot
    ;;
  search-none)
    click 180 27 1.2
    type_text 'zzz'
    xdotool mousemove 200 700; sleep 0.4
    shot
    ;;
  ctx-menu)
    rclick 160 90
    shot
    ;;
  delete-confirm)
    rclick 160 90
    # 菜单项数与几何由 CDP 在渲染进程里实测（scripts/parity/verify_menu_geometry.mjs，
    # 输出 out/final-close/logs/22-menu-geometry.json）：
    #   role=menu 面板 rect=(160,90,148,157)；5 个 role=menuitem，高 29px、从 y=96 起，
    #   New chat 96 / Rename 125 / Select 154 / Archive 183 / Delete 212，
    #   Delete 中心 = (234, 227)。
    # 旧坐标 (225, 205) 落在 Archive 项（183..212）上，截到的是「Archived … Undo」toast
    # 而不是删除确认框——这就是旧基线错的地方。
    click 234 227 1.4
    shot
    ;;
  model-picker)
    click 160 90 2.5
    click 1067 775 1.2
    shot
    ;;
  hover-thread)
    xdotool mousemove 160 90; sleep 1.2
    shot
    ;;
  focus-composer)
    click 160 90 2.5
    click 700 700 1.0
    xdotool mousemove 200 700; sleep 0.4
    shot
    ;;
  long-mid)
    click 180 400 0.2
    xdotool click --repeat 12 --delay 60 5; sleep 1.0
    xdotool mousemove 200 700; sleep 0.4
    shot
    ;;
  long-bottom)
    xdotool mousemove 200 400
    xdotool click --repeat 60 --delay 40 5; sleep 1.2
    xdotool mousemove 200 700; sleep 0.4
    shot
    ;;
  settings-general)
    click 28 787 1.6
    xdotool mousemove 200 700; sleep 0.4
    shot
    ;;
  settings-models)
    click 28 787 1.6
    click 360 244 1.2
    xdotool mousemove 200 700; sleep 0.4
    shot
    ;;
  settings-extensions)
    click 28 787 1.6
    click 360 277 1.2
    xdotool mousemove 200 700; sleep 0.4
    shot
    ;;
  settings-about)
    click 28 787 1.6
    click 360 310 1.2
    xdotool mousemove 200 700; sleep 0.4
    shot
    ;;
  dark-chat)
    click 160 90 2.5
    xdotool mousemove 200 700; sleep 0.4
    shot
    ;;
  *)
    echo "unknown page: $PAGE" >&2
    exit 2
    ;;
esac

echo "shot $PAGE -> $OUT"
