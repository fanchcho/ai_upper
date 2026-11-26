import os,subprocess,uuid
from pathlib import Path
run_id=uuid.uuid4().hex[:10]
p=Path('app/src/qml_shell.py');after=p.read_bytes()
body=Path('app/src/markdown/body.py');body_after=body.read_bytes()
try:
 for i in range(1,4):
  for mode in ['accepted-before','accepted-after']:
   p.write_bytes(Path('.tmp/hot-cache/bridge-before.py').read_bytes() if mode=='accepted-before' else after)
   body.write_bytes(Path('.tmp/hot-cache/body-before.py').read_bytes() if mode=='accepted-before' else body_after)
   env=dict(os.environ,AI_UPPER_HOME=f'/tmp/ai-upper-finaldisplay-{run_id}-{mode}-{i}',LD_LIBRARY_PATH=str(Path.cwd()/'.tmp/wm/usr/lib/aarch64-linux-gnu'),PYTHONDONTWRITEBYTECODE='1')
   out=f'.tmp/hot-cache/{mode}-{i}'
   with open(out+'.log','w') as f:subprocess.run(['.venv/bin/python','.tmp/hot-cache/measure.py',out],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
   print(mode,i,Path(out+'.log').read_text(),flush=True)
finally:
 p.write_bytes(after)
 body.write_bytes(body_after)
