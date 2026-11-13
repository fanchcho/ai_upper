#!/bin/bash
# 逐页对齐判定：对同一组页面，比较原版与端口在 1280x820 下的实拍。
#
# 用法: scripts/parity/compare.sh <原版截图目录> <端口截图目录>
# 输出: 每页一行，含
#   raw   = 完全相同的像素之外的像素数（AE 无容差，对 1 级抗锯齿差异也计数）
#   fz3   = 容差 3% 的 AE（≈ 允许 ±7 级灰度，肉眼不可见的抗锯齿差异不计）
#   maxd  = 全图最大单通道差值（0..255，RGB 三通道取最大）。≤10 视为不可见。
# 判定: fz3 ≤ 1 且 maxd ≤ 10 → 「已一致」。
#
# 依赖: imagemagick（compare / convert）。
set -u
A="${1:?用法: compare.sh <原名目录> <端口目录>}"
B="${2:?用法: compare.sh <原名目录> <端口目录>}"

PAGES="01-first-run 02-settings-general 03-settings-models 04-settings-extensions 05-settings-about 06-after-settings 07-chat"

printf '%-24s %8s %8s %6s  %s\n' PAGE raw fuzz3 maxd VERDICT
for page in $PAGES; do
  a="$A/$page.png"; b="$B/$page.png"
  if [ ! -f "$a" ] || [ ! -f "$b" ]; then
    printf '%-24s %8s %8s %6s  %s\n' "$page" - - - "缺图（$([ -f "$a" ] || echo 原名) $([ -f "$b" ] || echo 端口)）"
    continue
  fi
  raw=$(compare -metric AE "$a" "$b" null: 2>&1 || true)
  fz3=$(compare -metric AE -fuzz 3% "$a" "$b" null: 2>&1 || true)
  # 最大单通道差：差值图必须留在 RGB 里取 maxima。先转灰度会把三个通道的差平均掉
  # （实测灰度法得 7，真实单通道差是 9），判定口径就偏了。
  maxd=$(convert "$a" "$b" -compose difference -composite \
         -format "%[fx:round(maxima*255)]" info: 2>/dev/null || echo "?")
  if [ "$fz3" -le 1 ] 2>/dev/null && [ "$maxd" -le 10 ] 2>/dev/null; then
    verdict="已一致"
  else
    verdict="仍不一致"
  fi
  printf '%-24s %8s %8s %6s  %s\n' "$page" "$raw" "$fz3" "$maxd" "$verdict"
done
