"""Launch isolated real D-Bus + GNOME Secret Service; no mocked credential API."""
import os,sys,subprocess,time,json,uuid
from pathlib import Path
root=Path('.tmp/secret-service').resolve();runtime=root/'runtime';runtime.mkdir(exist_ok=True)
env=os.environ.copy();env.update(LD_LIBRARY_PATH=str(root/'root/usr/lib/aarch64-linux-gnu')+':'+str(Path('.tmp/wm/usr/lib/aarch64-linux-gnu').resolve()),XDG_DATA_HOME=str(runtime/'data'),XDG_RUNTIME_DIR=str(runtime),XDG_CONFIG_HOME=str(runtime/'config'))
config=root/'bus.conf';config.write_text('<busconfig><type>session</type><listen>unix:tmpdir='+str(runtime)+'</listen><auth>EXTERNAL</auth><policy context="default"><allow send_destination="*" eavesdrop="true"/><allow eavesdrop="true"/><allow own="*"/></policy></busconfig>')
bus=subprocess.Popen([str(root/'root/usr/bin/dbus-daemon'),'--nofork','--print-address=1','--config-file='+str(config)],stdout=subprocess.PIPE,text=True,env=env)
try:
 address=bus.stdout.readline().strip();assert address,address;env['DBUS_SESSION_BUS_ADDRESS']=address;print('BUS',address,flush=True)
 daemon=subprocess.run([str(root/'root/usr/bin/gnome-keyring-daemon'),'--unlock','--components=secrets','--control-directory='+str(runtime/'keyring')],input='fixture-only-password\n',text=True,env=env,capture_output=True,timeout=20);print('KEYRING',daemon.returncode,daemon.stdout,daemon.stderr,flush=True)
 for line in daemon.stdout.splitlines():
  if '=' in line:
   k,v=line.split('=',1);env[k]=v
 time.sleep(1)
 env['PYTHON_KEYRING_BACKEND']='keyring.backends.SecretService.Keyring'
 code="import keyring; print('BACKEND',keyring.get_keyring());keyring.set_password('ai-upper-isolated','probe','fixture'); assert keyring.get_password('ai-upper-isolated','probe')=='fixture';print('REAL_OS_ROUNDTRIP_OK');keyring.delete_password('ai-upper-isolated','probe')"
 subprocess.run([sys.executable,'-c',code],env=env,check=True,timeout=30)
 env.update(AI_UPPER_HOME='/tmp/ai-upper-reference-os-review',DEVA_HOME='/tmp/ai-upper-reference-os-review',TMPDIR=str(Path('.tmp/feature-review').resolve()))
 env['LD_LIBRARY_PATH']=':'.join(str(Path(p).resolve()) for p in ['.tmp/extensions-complete/runtime/usr/lib/aarch64-linux-gnu','.tmp/icon-dpi/runtime/usr/lib/aarch64-linux-gnu','.tmp/secret-service/root/usr/lib/aarch64-linux-gnu','.tmp/wm/usr/lib/aarch64-linux-gnu'])
 env['PATH']=str(Path('.tmp/icon-dpi/runtime/usr/bin').resolve())+':'+str(Path('.tmp/wm/usr/bin').resolve())+':'+env['PATH']
 env['XDG_CURRENT_DESKTOP']='GNOME'
 home=Path(env['DEVA_HOME']);home.mkdir(parents=True,exist_ok=True)
 (home/'config.json').write_text(json.dumps({'theme':'dark','locale':'en'}))
 (home/'mcp.json').write_text(json.dumps({'mcpServers':{'echo':{'name':'Echo','transport':'stdio','command':'/missing-disabled-fixture','env':{'TOKEN':{'secretRef':'mcp:echo:TOKEN'}}}}}))
 cmd=['.tmp/wm/usr/bin/xvfb-run','-a','.tmp/extensions-complete/browser/node_modules/electron/dist/electron','--no-sandbox','--disable-gpu','--password-store=gnome-libsecret','--remote-debugging-port=9344','--user-data-dir='+str(Path('.tmp/feature-review/electron-profile').resolve()),'/home/agent/shared_workspace/deva/apps/desktop/out/main/index.js']
 print('ELECTRON_COMMAND',cmd,flush=True)
 log=open('out/feature-review/electron.log','w')
 electron=subprocess.Popen(cmd,env=env,stdout=log,stderr=log,start_new_session=True)
 try:
  time.sleep(7)
  result=subprocess.run(['node','scripts/parity/extensions_reference_cdp.mjs',"window.deva.secrets.available().then(async available => ({available, saved: available ? await window.deva.secrets.set('audit-real-os','fixture') : false, has: await window.deva.secrets.has('audit-real-os')}))",'out/feature-review/deva-os.png'],env=env,capture_output=True,text=True,timeout=30)
  print('REAL_ELECTRON_SAFE_STORAGE',result.returncode,result.stdout,result.stderr,flush=True)
  Path('out/feature-review/electron-safe-storage.json').write_text(result.stdout)
  subprocess.run(['node','scripts/parity/feature_review/saved_ui.mjs'],env=env,check=True,timeout=40)
  for theme in ['dark','light']:
   env.update(AI_UPPER_HOME='/tmp/ai-upper-os-review-'+theme+'-'+uuid.uuid4().hex[:8],QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
   subprocess.run([sys.executable,'scripts/parity/feature_review/qt_os.py',theme],env=env,check=True,timeout=90)
 finally:
  import signal
  os.killpg(electron.pid,signal.SIGTERM);electron.wait(timeout=10)
finally:bus.terminate();bus.wait(timeout=5)
