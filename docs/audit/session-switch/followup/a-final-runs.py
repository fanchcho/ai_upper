import os,subprocess
from pathlib import Path
p=Path('app/src/qml/Main.qml'); final=p.read_bytes()
try:
 for mode in ['before','after']:
  p.write_bytes(Path('.tmp/selection-thread/Main-before.qml').read_bytes() if mode=='before' else final)
  env=dict(os.environ,AI_UPPER_HOME=f'/tmp/ai-upper-selection-final-{mode}',PYTHONDONTWRITEBYTECODE='1',LD_LIBRARY_PATH=str(Path.cwd()/'.tmp/wm/usr/lib/aarch64-linux-gnu'))
  output=f'.tmp/selection-thread/a-final-{mode}'
  with open(output+'.log','w') as f: subprocess.run(['.venv/bin/python','.tmp/selection-thread/selection.py',output],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
  print(Path(output+'.log').read_text(),flush=True)
finally:p.write_bytes(final)
