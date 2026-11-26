import subprocess,os,json
from pathlib import Path
base=dict(os.environ,LD_LIBRARY_PATH=str(Path.cwd()/'.tmp/wm/usr/lib/aarch64-linux-gnu'),PYTHONDONTWRITEBYTECODE='1',QT_QPA_PLATFORM='offscreen')
statuses=[]
for name,cmd,env in [('cancel',['.venv/bin/python','.tmp/idle-prefetch/cancel-probe.py','.tmp/idle-prefetch/cancel','prefetch'],dict(base,AI_UPPER_HOME='/tmp/ai-upper-idle-cancel',PROBE_INPUT='1')),('pytest',['.venv/bin/python','-m','pytest','--basetemp=/tmp/ai-upper-idle-full-base','-q'],dict(base,AI_UPPER_HOME='/tmp/ai-upper-idle-full'))]:
 with open(f'.tmp/idle-prefetch/{name}.log','w') as f:p=subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT)
 statuses.append(dict(name=name,exit_code=p.returncode));print(statuses[-1],flush=True)
Path('.tmp/idle-prefetch/final-exits.json').write_text(json.dumps(statuses,indent=2))
