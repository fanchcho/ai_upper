import os,subprocess,json
from pathlib import Path
results=[]
for i in range(1,4):
 env=dict(os.environ,AI_UPPER_HOME=f'/tmp/ai-upper-cold-retained-{i}',LD_LIBRARY_PATH=str(Path.cwd()/'.tmp/wm/usr/lib/aarch64-linux-gnu'),PYTHONDONTWRITEBYTECODE='1')
 with open(f'.tmp/cold-path/retained-{i}.log','w') as f:p=subprocess.run(['.venv/bin/python','.tmp/cold-path/measure.py',f'.tmp/cold-path/retained-{i}'],env=env,stdout=f,stderr=subprocess.STDOUT)
 results.append(dict(name=f'retained-{i}',exit_code=p.returncode));print(results[-1],flush=True)
 if p.returncode:break
else:
 env=dict(os.environ,AI_UPPER_HOME='/tmp/ai-upper-cold-full',QT_QPA_PLATFORM='offscreen',LD_LIBRARY_PATH=str(Path.cwd()/'.tmp/wm/usr/lib/aarch64-linux-gnu'),PYTHONDONTWRITEBYTECODE='1')
 with open('.tmp/cold-path/pytest.log','w') as f:p=subprocess.run(['.venv/bin/python','-m','pytest','--basetemp=/tmp/ai-upper-cold-full-base','-q'],env=env,stdout=f,stderr=subprocess.STDOUT)
 results.append(dict(name='pytest',exit_code=p.returncode));print(results[-1],flush=True)
Path('.tmp/cold-path/verify-exits.json').write_text(json.dumps(results,indent=2))
