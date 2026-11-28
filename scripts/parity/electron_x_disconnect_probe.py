"""Minimal real Electron/Xvfb shutdown callback reproduction. No deva startup."""
import os,subprocess,time,json,resource,sys
from pathlib import Path
mode=sys.argv[1] if len(sys.argv)>1 else 'disconnect'
prefix='minimal' if mode=='disconnect' else 'graceful'
root=Path.cwd();out=root/'docs/audit/deep-boundary';temp=root/'.tmp/deep-boundary'
# This is a deliberate abort reproduction; retain the existing large core, avoid another 0.5GB duplicate.
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
env=os.environ.copy();env['DISPLAY']=':187';env['TMPDIR']=str(temp);env['PROBE_PROFILE']=str(temp/'min-profile');env['PROBE_GRACEFUL']='1' if mode=='graceful' else '0'
env['LD_LIBRARY_PATH']=':'.join(str(root/p) for p in ['.tmp/extensions-complete/runtime/usr/lib/aarch64-linux-gnu','.tmp/icon-dpi/runtime/usr/lib/aarch64-linux-gnu','.tmp/wm/usr/lib/aarch64-linux-gnu'])
xlog=open(out/f'{prefix}-xvfb.log','w');elog=open(out/f'{prefix}-electron.log','w')
x=subprocess.Popen([str(root/'.tmp/wm/usr/bin/Xvfb'),':187','-screen','0','800x600x24','-nolisten','tcp'],env=env,stdout=xlog,stderr=xlog)
try:
 time.sleep(1)
 e=subprocess.Popen([str(root/'.tmp/extensions-complete/browser/node_modules/electron/dist/electron'),'--no-sandbox','--disable-gpu',str(root/'scripts/parity/electron_x_disconnect_probe.cjs')],env=env,stdout=elog,stderr=elog)
 try:
  for _ in range(50):
   if 'MINIMAL_WINDOW_READY' in (out/f'{prefix}-electron.log').read_text():break
   time.sleep(.1)
  assert 'MINIMAL_WINDOW_READY' in (out/f'{prefix}-electron.log').read_text()
  if mode=='disconnect':x.terminate();x.wait(timeout=5)
  code=e.wait(timeout=15)
  result={'action':'SIGTERM Xvfb only after real window ready' if mode=='disconnect' else 'app.quit before Xvfb termination','electron_exit':code,'fatal_shutdown':'Failed to shutdown.' in (out/f'{prefix}-electron.log').read_text()}
  (out/f'{prefix}-shutdown.json').write_text(json.dumps(result,indent=2));print(result)
 finally:
  if e.poll() is None:e.terminate();e.wait(timeout=5)
finally:
 if x.poll() is None:x.terminate();x.wait(timeout=5)
