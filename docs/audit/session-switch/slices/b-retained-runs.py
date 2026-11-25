import os,subprocess
from pathlib import Path
paths={'app/src/qml_shell.py':'bridge-before.py','app/src/markdown/body.py':'body-before.py'}
final={p:Path(p).read_bytes() for p in paths}
try:
 for i in range(1,4):
  for mode in ['before','after']:
   for p,b in paths.items():Path(p).write_bytes((Path('.tmp/selection-slices')/b).read_bytes() if mode=='before' else final[p])
   env=dict(os.environ,AI_UPPER_HOME=f'/tmp/ai-upper-slices-retained-b-{mode}-{i}',PYTHONDONTWRITEBYTECODE='1',LD_LIBRARY_PATH=str(Path.cwd()/'.tmp/wm/usr/lib/aarch64-linux-gnu'))
   out=f'.tmp/selection-slices/b-retained-{mode}-{i}'
   with open(out+'.log','w') as f:subprocess.run(['.venv/bin/python','.tmp/selection-slices/switch.py',out],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
   print(mode,i,Path(out+'.log').read_text(),flush=True)
finally:
 for p,v in final.items():Path(p).write_bytes(v)
