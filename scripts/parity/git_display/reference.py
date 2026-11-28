import os,subprocess,time
from pathlib import Path
r=Path.cwd(); env=os.environ.copy();env.update(DISPLAY=':193',AI_UPPER_HOME='/tmp/ai-upper-git-css-reference',LD_LIBRARY_PATH=':'.join(str(r/p) for p in ['.tmp/extensions-complete/runtime/usr/lib/aarch64-linux-gnu','.tmp/icon-dpi/runtime/usr/lib/aarch64-linux-gnu','.tmp/wm/usr/lib/aarch64-linux-gnu']),TMPDIR=str(r/'.tmp/git-display'))
with open(r/'docs/audit/git-display/original-css-render.log','w') as log:
 x=subprocess.Popen([str(r/'.tmp/wm/usr/bin/Xvfb'),':193','-screen','0','1280x960x24','-nolisten','tcp'],env=env,stdout=log,stderr=log)
 try:
  time.sleep(1)
  p=subprocess.run([str(r/'.tmp/extensions-complete/browser/node_modules/electron/dist/electron'),'--no-sandbox',str(r/'scripts/parity/git_display/reference.cjs')],env=env,stdout=log,stderr=log,timeout=45)
  print('Electron CSS specimen exit:',p.returncode)
 finally:x.terminate();x.wait(timeout=5)
