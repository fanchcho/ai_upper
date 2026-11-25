import subprocess,os
from pathlib import Path
p=Path('app/src/qml_shell.py'); final=p.read_bytes()
try:
 for i in range(1,4):
  for mode in ['before','after']:
   p.write_bytes(Path('.tmp/selection-thread/bridge-before.py').read_bytes() if mode=='before' else final)
   env=dict(os.environ,AI_UPPER_HOME=f'/tmp/ai-upper-thread-{mode}-values-{i}',PYTHONDONTWRITEBYTECODE='1',LD_LIBRARY_PATH=str(Path.cwd()/'.tmp/wm/usr/lib/aarch64-linux-gnu'))
   output=f'.tmp/selection-thread/b-{mode}-values-{i}'
   with open(output+'.log','w') as f:
    subprocess.run(['.venv/bin/python','.tmp/selection-thread/switch.py',output],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
   print(mode,i,Path(output+'.log').read_text().strip(),flush=True)
finally: p.write_bytes(final)
