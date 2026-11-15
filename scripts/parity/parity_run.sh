#!/usr/bin/env bash
# 逐页像素比对的收口脚本：QML 实拍 → 归位到 parity/<page>/qml.png → 全量比对。
#
# 用法: scripts/parity/parity_run.sh [--shots]
#   --shots  重新实拍 QML 19 页（约 3 分钟）；不带则只复用上一批 /tmp/qml-pages-out。
# 原版图来自 out/qml-shell/pages/deva/<page>-deva.png（由 deva_pages_all.sh 产），
# 本脚本只读它，不重跑 Electron。
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 1

OUT=out/qml-shell/parity
SHOTS=/tmp/qml-pages-out
DEVA=out/qml-shell/pages/deva

if [ "${1:-}" = "--shots" ]; then
  bash scripts/parity/qml_pages_all.sh "$SHOTS" || exit 2
fi

# numbers.tsv 的 original 列按 <dir>/original.png 记录，所以先把原版图铺好。
for src in "$DEVA"/*-deva.png; do
  page="$(basename "$src" -deva.png)"
  mkdir -p "$OUT/$page"
  cp -f "$src" "$OUT/$page/original.png"
  if [ -f "$SHOTS/$page.png" ]; then
    cp -f "$SHOTS/$page.png" "$OUT/$page/qml.png"
  else
    echo "缺 QML 图: $page" >&2
  fi
done

bash scripts/parity/parity_all.sh "$OUT"
