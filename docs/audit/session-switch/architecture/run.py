import os,sys,subprocess,json
from pathlib import Path
mode=sys.argv[1];results=[]
for i in range(1,4):
 env=dict(os.environ,AI_UPPER_HOME=f'/tmp/ai-upper-architecture-{mode}-{i}',LD_LIBRARY_PATH=str(Path.cwd()/'.tmp/wm/usr/lib/aarch64-linux-gnu'),PYTHONDONTWRITEBYTECODE='1')
 out=f'.tmp/architecture/{mode}-{i}'
 with open(out+'.log','w') as f:p=subprocess.run(['.venv/bin/python','.tmp/architecture/measure.py',out],env=env,stdout=f,stderr=subprocess.STDOUT)
 results.append(dict(mode=mode,group=i,exit_code=p.returncode));print(results[-1],flush=True)
Path(f'.tmp/architecture/{mode}-exits.json').write_text(json.dumps(results,indent=2))
