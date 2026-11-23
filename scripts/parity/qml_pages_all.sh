#!/usr/bin/env bash
# QML 壳逐页实拍：与 deva_pages_all.sh 同一份固定数据、同一 config、同一窗口尺寸。
#
# 用法: scripts/parity/qml_pages_all.sh [输出目录] [home]
#   输出目录默认 /tmp/qml-pages-out（<page>.png），home 默认 /tmp/fx-qml-home。
#   dark-chat 用 config-dark.json（theme=dark）；empty / first-run 用「无 chats」的临时 home，
#   否则 QML 侧会画 120 条会话，跟原版的空态不是同一屏。
#
# 真实渲染：offscreen + 软件光栅，QQuickWindow.grabWindow() 出图；stderr 原样保留。
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-/tmp/qml-pages-out}"
HOME_DIR="${2:-/tmp/fx-qml-home}"
mkdir -p "$OUT"
FAILED=0

shot() {  # shot <page> [config] [seed]
  local page="$1" cfg="${2:-config.json}" seed="${3:-1}"
  local home="$HOME_DIR" png="$OUT/$page.png"
  if [ "$seed" = "0" ]; then
    home="/tmp/qml-page-empty-$page"
    rm -rf "$home" && mkdir -p "$home"
    cp "$HOME_DIR/$cfg" "$home/config.json"
  fi
  rm -f "$png"
  bash "$ROOT/scripts/parity/qml_page_shot.sh" "$page" "$png" "$home" "$cfg" \
    >"$OUT/$page.out" 2>"$OUT/$page.err"
  local rc=$?
  printf '%s\n' "$rc" > "$OUT/$page.rc"
  if [ "$rc" -eq 0 ] && [ -f "$png" ]; then
    echo "ok   $page $(identify -format '%wx%h %b' "$png") rc=$rc"
  else
    echo "FAIL $page rc=$rc"
    FAILED=1
  fi
}

shot empty config.json 0
shot first-run config.json 0
shot chat
shot search-open
shot search-results
shot search-none
shot ctx-menu
shot delete-confirm
shot model-picker
shot hover-thread
shot focus-composer
shot long-mid
shot long-bottom
shot settings-general
shot settings-models
shot settings-extensions
shot settings-about
shot dark-chat config-dark.json

exit "$FAILED"
