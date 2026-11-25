#!/bin/bash
# Single clean deva 18-page capture. Kept in one script so the process-matching
# patterns below can use bracket tricks (a bare `pkill -f "Xvfb :97"` in an
# inline bash -c matches its own command line and kills the caller).
set -u
cd /home/agent/shared_workspace/ai_upper || exit 1
pkill -f "[a]pps/desktop/out/main/index.js" >/dev/null 2>&1
pkill -f "[X]vfb :97" >/dev/null 2>&1
sleep 2
rm -f /tmp/.X97-lock /tmp/.X11-unix/X97
rm -rf out/final-closeout/deva
mkdir -p out/final-closeout/deva
bash scripts/parity/deva_pages_all.sh out/final-closeout/deva \
  >out/final-closeout/logs/deva-18pages.log 2>&1
rc=$?
printf '%s\n' "$rc" >out/final-closeout/logs/deva-18pages.rc
echo "deva_rc=$rc"
tail -25 out/final-closeout/logs/deva-18pages.log
exit 0
