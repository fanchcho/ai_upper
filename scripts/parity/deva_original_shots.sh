#!/bin/bash
# 原版 Deva 逐页截图（固定 1280x820 窗口，Xvfb 1400x900）。
#
# 用法: scripts/parity/deva_original_shots.sh <输出目录> [DEVA_HOME]
# 前置: xvfb / xdotool / imagemagick，以及 Deva 的 Electron 运行依赖
#       （libgtk-3-0 libnss3 libasound2 libatk-bridge2.0-0 libcups2 libdrm2
#         libxkbcommon-x11-0 libxcomposite1 libxdamage1 libxrandr2 libpango-1.0-0
#         libcairo2 libxshmfence1 fonts-noto-cjk）。
# 说明: deva 工程只读——本脚本只启动它、不写它；数据全部落在 DEVA_HOME。
#
# 坐标约定：窗口固定在 (0,0) 的 1280x820；点击坐标即客户端坐标。
# 这些坐标同时被 scripts/parity/port_shots.sh 使用，两边取同一组页面才可逐像素对比。
set -u
OUT="${1:?用法: deva_original_shots.sh <输出目录> [DEVA_HOME]}"
HOME_DIR="${2:-/tmp/deva-home-parity}"
DEVA_ROOT=/home/agent/shared_workspace/deva
DISPLAY_NUM=:95

mkdir -p "$OUT"
rm -rf "$HOME_DIR" && mkdir -p "$HOME_DIR"
# 可选：预置对话数据（脚本参数 3），用于对话页截图；只写 DEVA_HOME，不碰工程目录。
if [ -n "${3:-}" ] && [ -d "$3" ]; then
  mkdir -p "$HOME_DIR/data/chats"
  cp -a "$3"/. "$HOME_DIR/data/chats/"
fi

DISPLAY=$DISPLAY_NUM Xvfb :95 -screen 0 1400x900x24 >/tmp/xvfb-parity.log 2>&1 &
XPID=$!
sleep 2
export DISPLAY=$DISPLAY_NUM

DEVA_HOME="$HOME_DIR" "$DEVA_ROOT/node_modules/electron/dist/electron" \
  --no-sandbox --disable-gpu "$DEVA_ROOT/apps/desktop/out/main/index.js" >/tmp/deva-parity.log 2>&1 &
EPID=$!
sleep 10

WID=$(xdotool search --name '^Deva$' 2>/dev/null | head -1)
[ -z "${WID:-}" ] && WID=$(xdotool search --class electron 2>/dev/null | head -1)
if [ -n "${WID:-}" ]; then
  xdotool windowmove "$WID" 0 0 windowsize "$WID" 1280 820
  sleep 2
fi

# 指针先移到中立位置（空白区）：Xvfb 的指针默认停在屏幕中心，正好落在首启页的提供方卡片上，
# 原版会因 :hover 画出强调色边框，鼠标位置不一致时首启页无法逐像素比较。
xdotool mousemove 200 700
sleep 0.6

shot() { import -window root "$OUT/$1.png" && echo "shot $1"; }
click() { xdotool mousemove "$1" "$2" click 1; sleep "${3:-1.2}"; }

shot 01-first-run

# 设置页：图标栏底部齿轮（图标中心 27,787）
click 27 787 2.0
shot 02-settings-general

# 设置 › 模型 / 扩展 / 关于：左侧导航第二、三、四项（导航项中心 y = 246 / 275 / 305）
click 340 246 1.5
shot 03-settings-models
click 340 275 1.5
shot 04-settings-extensions
click 340 305 1.5
shot 05-settings-about

# 关闭设置弹框（右上角 ✕），回主界面；若有预置对话则点列表首行进入对话页。
click 965 152 1.5
shot 06-after-settings
if [ -n "${3:-}" ]; then
  click 160 90 2.5
  shot 07-chat
fi

kill $EPID 2>/dev/null; sleep 1; kill $XPID 2>/dev/null; wait 2>/dev/null
