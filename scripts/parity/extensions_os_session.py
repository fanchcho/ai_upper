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
 for theme in ['dark','light']:
  env['AI_UPPER_HOME']='/tmp/ai-upper-real-os-'+theme+'-'+uuid.uuid4().hex[:8];env['QT_QPA_PLATFORM']='offscreen';env['QT_QUICK_BACKEND']='software'
  subprocess.run([sys.executable,'scripts/parity/extensions_os_evidence.py',theme],env=env,check=True,timeout=90)
finally:bus.terminate();bus.wait(timeout=5)
