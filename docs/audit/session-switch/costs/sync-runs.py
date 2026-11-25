import subprocess,os
from pathlib import Path
p=Path('app/src/qml_shell.py'); before=p.read_bytes()
final=before.decode().replace('            steps = self._body.attach_steps(self._document)\n            self._advance_attach(epoch, steps)','            self._body.attach(self._document)\n            self.rendered += 1\n            self._scroll_to_bottom()').encode()
try:
 for i in range(1,4):
  for mode in ['before','sync']:
   p.write_bytes(before if mode=='before' else final)
   env=dict(os.environ,AI_UPPER_HOME=f'/tmp/ai-upper-cost-{mode}-{i}',LD_LIBRARY_PATH=str(Path.cwd()/'.tmp/wm/usr/lib/aarch64-linux-gnu'),PYTHONDONTWRITEBYTECODE='1')
   out=f'.tmp/frame-cost/{mode}-{i}'
   with open(out+'.log','w') as f:subprocess.run(['.venv/bin/python','.tmp/frame-cost/switch.py',out],env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
   print(mode,i,Path(out+'.log').read_text(),flush=True)
finally:p.write_bytes(before)
