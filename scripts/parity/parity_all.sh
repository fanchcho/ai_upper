#!/usr/bin/env bash
# 逐页像素比对批处理：out/qml-shell/parity/<page>/{original,qml}.png → diff.png + numbers。
# 输出为 TSV（写进 REPORT.md 的表格就是它），另存 parity/numbers.tsv 供复现。
set -u
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 1
OUT="${1:-out/qml-shell/parity}"
TSV="$OUT/numbers.tsv"
: > "$TSV"
printf 'page\toriginal\tsize\tdiff_px\tratio_pct\tbbox\tmax_delta\tlevels\n' >> "$TSV"
for dir in "$OUT"/*/; do
  page="$(basename "$dir")"
  a="$dir/original.png"
  b="$dir/qml.png"
  [ -f "$a" ] && [ -f "$b" ] || { echo "skip $page (缺图)" >&2; continue; }
  line="$(.venv/bin/python scripts/parity/page_diff.py "$a" "$b" "$dir/diff.png" --json)"
  .venv/bin/python - "$page" "$line" "$TSV" <<'PY'
import json, sys
page, line, tsv = sys.argv[1], sys.argv[2], sys.argv[3]
d = json.loads(line)
with open(tsv, "a", encoding="utf-8") as f:
    f.write("%s\t%s\t%s\t%d\t%.4f\t%s\t%d\t%s\n" % (
        page, d["original"], d["size"], d["diff_px"], d["diff_ratio_pct"],
        d["bbox"], d["max_channel_delta"], json.dumps(d["levels"], separators=(",", ":"))))
print("%-20s %s diff=%d (%.4f%%) bbox=%s maxD=%d" % (
    page, d["size"], d["diff_px"], d["diff_ratio_pct"], d["bbox"], d["max_channel_delta"]))
PY
done
