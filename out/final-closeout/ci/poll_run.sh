#!/bin/bash
# Poll the CI run for HEAD a09b52d until it reaches a terminal state (max ~15 min).
set -u
cd /home/agent/shared_workspace/ai_upper || exit 1
OUT=out/final-closeout/ci/turn2
mkdir -p "$OUT"
RUN=45519144976
START=$(date +%s)
: > "$OUT/poll.log"
while :; do
  NOW=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
  curl -sS -fL --max-time 30 -H 'Accept: application/vnd.github+json' \
    "https://api.github.com/repos/fanchcho/ai_upper/actions/runs/$RUN" \
    -o "$OUT/run.json" 2>>"$OUT/poll.err"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "$NOW curl_rc=$rc" >> "$OUT/poll.log"
  else
    read -r STATUS CONCLUSION <<<"$(python3 - "$OUT/run.json" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
print(d.get('status'), d.get('conclusion'))
PY
)"
    echo "$NOW status=$STATUS conclusion=$CONCLUSION" >> "$OUT/poll.log"
    if [ "$STATUS" = "completed" ]; then
      echo "TERMINAL $NOW $STATUS $CONCLUSION" >> "$OUT/poll.log"
      break
    fi
  fi
  ELAPSED=$(( $(date +%s) - START ))
  if [ "$ELAPSED" -ge 900 ]; then
    echo "TIMEOUT $NOW elapsed=${ELAPSED}s" >> "$OUT/poll.log"
    break
  fi
  sleep 30
done
cat "$OUT/poll.log"
