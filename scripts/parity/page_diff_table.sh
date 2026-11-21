#!/usr/bin/env bash
# 逐页对照：QML 壳实拍 vs 原版 Deva 实拍。
#
# 用法: scripts/parity/page_diff_table.sh [qml-dir] [deva-dir] [输出文件]
#   默认 /tmp/qml-pages-out 与 out/final-close/deva-rerun，输出到 stdout。
#
# 每页输出：页名 / 原版 md5 / QML md5 / 差异像素数 / 差异像素%。
# 差异用 ImageMagick `compare -metric AE`：逐通道任一不同即计为该像素不同，
# 分母恒为 1280*820=1049600（两图尺寸不同会先判 FAIL，不会算出假比例）。
set -u
QML_DIR="${1:-/tmp/qml-pages-out}"
DEVA_DIR="${2:-out/final-close/deva-rerun}"
OUT_FILE="${3:-}"
W=1280
H=820
TOTAL=$((W * H))

PAGES=(chat ctx-menu dark-chat delete-confirm empty first-run focus-composer hover-thread
       long-bottom long-mid model-picker search-none search-open search-results
       settings-about settings-extensions settings-general settings-models)

emit() { if [ -n "$OUT_FILE" ]; then tee -a "$OUT_FILE"; else cat; fi; }
[ -n "$OUT_FILE" ] && : >"$OUT_FILE"

printf '%-20s %-34s %-34s %10s %9s\n' page deva_md5 qml_md5 diff_px diff_pct | emit
for p in "${PAGES[@]}"; do
  a="$DEVA_DIR/$p-deva.png"
  b="$QML_DIR/$p.png"
  if [ ! -f "$a" ] || [ ! -f "$b" ]; then
    printf '%-20s %-34s %-34s %10s %9s\n' "$p" "MISSING" "MISSING" - - | emit
    continue
  fi
  sa=$(identify -format '%wx%h' "$a")
  sb=$(identify -format '%wx%h' "$b")
  if [ "$sa" != "${W}x${H}" ] || [ "$sb" != "${W}x${H}" ]; then
    printf '%-20s %-34s %-34s %10s %9s\n' "$p" "$sa" "$sb" "SIZE-MISMATCH" - | emit
    continue
  fi
  ma=$(md5sum "$a" | cut -d' ' -f1)
  mb=$(md5sum "$b" | cut -d' ' -f1)
  ae=$(compare -metric AE "$a" "$b" null: 2>&1 | tr -d ' ')
  pct=$(awk -v ae="$ae" -v t="$TOTAL" 'BEGIN{printf "%.2f", ae / t * 100}')
  printf '%-20s %-34s %-34s %10s %9s\n' "$p" "$ma" "$mb" "$ae" "$pct" | emit
done
