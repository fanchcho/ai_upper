import os,subprocess,json
from pathlib import Path
statuses=[]
for i in range(1,4):
 name=f'release-after-{i}'
 env=dict(os.environ,AI_UPPER_HOME=f'/tmp/ai-upper-cache-{name}',LD_LIBRARY_PATH=str(Path.cwd()/'.tmp/wm/usr/lib/aarch64-linux-gnu'),PYTHONDONTWRITEBYTECODE='1')
 with open(f'.tmp/hot-cache/{name}.log','w') as f:
  p=subprocess.run(['.venv/bin/python','.tmp/hot-cache/measure.py',f'.tmp/hot-cache/{name}'],env=env,stdout=f,stderr=subprocess.STDOUT)
 statuses.append(dict(name=name,exit_code=p.returncode));print(statuses[-1],flush=True)
 if p.returncode:break
else:
 env=dict(os.environ,AI_UPPER_HOME='/tmp/ai-upper-cache-release-full',QT_QPA_PLATFORM='offscreen',LD_LIBRARY_PATH=str(Path.cwd()/'.tmp/wm/usr/lib/aarch64-linux-gnu'),PYTHONDONTWRITEBYTECODE='1')
 with open('.tmp/hot-cache/pytest-release-full.log','w') as f:
  p=subprocess.run(['.venv/bin/python','-m','pytest','--basetemp=/tmp/ai-upper-cache-release-full-base','-q'],env=env,stdout=f,stderr=subprocess.STDOUT)
 statuses.append(dict(name='pytest-release-full',exit_code=p.returncode));print(statuses[-1],flush=True)
Path('.tmp/hot-cache/final-release-exits.json').write_text(json.dumps(statuses,indent=2))
