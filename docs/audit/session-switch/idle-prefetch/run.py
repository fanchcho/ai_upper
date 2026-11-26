import os,subprocess,json
from pathlib import Path
out=[]
for i in range(1,4):
 for mode in ['baseline','prefetch']:
  env=dict(os.environ,AI_UPPER_HOME=f'/tmp/ai-upper-idle-{mode}-{i}',LD_LIBRARY_PATH=str(Path.cwd()/'.tmp/wm/usr/lib/aarch64-linux-gnu'),PYTHONDONTWRITEBYTECODE='1')
  name=f'.tmp/idle-prefetch/{mode}-{i}'
  with open(name+'.log','w') as f:p=subprocess.run(['.venv/bin/python','.tmp/idle-prefetch/probe.py',name,mode],env=env,stdout=f,stderr=subprocess.STDOUT)
  out.append(dict(mode=mode,group=i,exit_code=p.returncode));print(out[-1],flush=True)
Path('.tmp/idle-prefetch/exits.json').write_text(json.dumps(out,indent=2))
