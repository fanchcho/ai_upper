#!/usr/bin/env bash
# QML 逐页实拍：与 scripts/parity/deva_pages_all.sh 同一份固定数据、同一窗口尺寸。
#
# 用法: scripts/parity/qml_page_shot.sh <page> <输出png> [home] [config]
#   page   见 app/src/qml_shell.py::PAGE_NAMES
#   home   数据目录（默认 /tmp/fx-qml-home，由 make_qml_home.py 从同一夹具生成）
#   config home 下要使用的 config 文件名（默认 config.json）
#
# 真实渲染：offscreen + 软件光栅，QQuickWindow.grabWindow() 出图；stderr 原样保留，
# 有 QML 警告/报错时由调用方看到（不吞）。
set -u
PAGE="${1:?用法: qml_page_shot.sh <page> <png> [home] [config]}"
OUT="${2:?缺少输出路径}"
HOME_DIR="${3:-/tmp/fx-qml-home}"
CONFIG="${4:-config.json}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

mkdir -p "$(dirname "$OUT")"
if [ "$CONFIG" != "config.json" ]; then
  # 同一数据目录换配置：复制一份独立 home，避免两页互相覆盖。
  TMP="/tmp/qml-page-home-$PAGE"
  rm -rf "$TMP"
  mkdir -p "$TMP"
  cp -a "$HOME_DIR/data" "$TMP/data" 2>/dev/null || true
  cp "$HOME_DIR/$CONFIG" "$TMP/config.json"
  HOME_DIR="$TMP"
fi

cd "$ROOT" || exit 1
timeout 120 env \
  AI_UPPER_UI=qml \
  AI_UPPER_HEADLESS=1 \
  AI_UPPER_HOME="$HOME_DIR" \
  AI_UPPER_QML_PAGE="$PAGE" \
  AI_UPPER_QML_SHOT="$OUT" \
  "${PYTHON:-$ROOT/.venv/bin/python}" app/src/main.py
