#!/bin/bash
# py_upper 端口逐页截图：与原版脚本走同一套 Xvfb 尺寸、窗口几何、点击坐标、取图方式。
#
# 用法: scripts/parity/port_shots.sh <输出目录> [DEVA_HOME]
# 前置: xvfb / xdotool / imagemagick；端口依赖装在 .venv。
# 对照: scripts/parity/deva_original_shots.sh 用同一组坐标点原版，两边截图才可逐像素比。
set -u
OUT="${1:?用法: port_shots.sh <输出目录> [DEVA_HOME]}"
HOME_DIR="${2:-/tmp/deva-home-port}"
ROOT=/home/agent/shared_workspace/py_upper
DISPLAY_NUM=:96

mkdir -p "$OUT"
rm -rf "$HOME_DIR" && mkdir -p "$HOME_DIR"
# 可选：预置对话数据（脚本参数 3），用于对话页截图；只写 DEVA_HOME。
if [ -n "${3:-}" ] && [ -d "$3" ]; then
  mkdir -p "$HOME_DIR/data/chats"
  cp -a "$3"/. "$HOME_DIR/data/chats/"
fi

DISPLAY=$DISPLAY_NUM Xvfb :96 -screen 0 1400x900x24 >/tmp/xvfb-port.log 2>&1 &
XPID=$!
sleep 2
export DISPLAY=$DISPLAY_NUM
export QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu"
export DEVA_HOME="$HOME_DIR"

"$ROOT/.venv/bin/python" "$ROOT/scripts/parity/port_run.py" >/tmp/port-run.log 2>&1 &
PPID_=$!
sleep 12

WID=$(xdotool search --name '^Deva$' 2>/dev/null | head -1)
[ -z "${WID:-}" ] && WID=$(xdotool search --class 'python3' 2>/dev/null | head -1)
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

# 设置页：图标栏底部齿轮（与原版坐标一致：x=27 y=787）
click 27 787 2.0
shot 02-settings-general

# 设置 › 模型（左侧导航第二项）
click 340 246 1.5
shot 03-settings-models

# 设置 › 扩展（第三项）
click 340 275 1.5
shot 04-settings-extensions

# 设置 › 关于（第四项）
click 340 305 1.5
shot 05-settings-about

# 关闭设置弹框（右上角 ✕），回主界面；若有预置对话则点列表首行进入对话页。
click 965 152 1.5
shot 06-after-settings
if [ -n "${3:-}" ]; then
  click 160 90 2.5
  shot 07-chat
fi

kill $PPID_ 2>/dev/null; sleep 1; kill $XPID 2>/dev/null; wait 2>/dev/null
