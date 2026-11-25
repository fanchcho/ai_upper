import os,subprocess,json,statistics,math
from pathlib import Path
from PIL import Image,ImageChops
root=Path.cwd(); out=root/'.tmp/push-closeout'; samples=[]; entries=[]
for i in range(1,4):
 env=dict(os.environ,AI_UPPER_HOME=f'/tmp/ai-upper-push-final-{i}',LD_LIBRARY_PATH=str(root/'.tmp/wm/usr/lib/aarch64-linux-gnu'),PYTHONDONTWRITEBYTECODE='1')
 command=['.venv/bin/python','docs/audit/session-switch/costs/switch.py',str(out/f'final-{i}')]
 with (out/f'final-{i}.log').open('w') as log:
  log.write('$ AI_UPPER_HOME='+env['AI_UPPER_HOME']+' '+' '.join(command)+'\n');log.flush()
  result=subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT)
  log.write(f'\nexit={result.returncode}\n')
 assert result.returncode==0
 data=json.loads((out/f'final-{i}.json').read_text());samples+=data['samples']
 expected=Image.open(root/f'docs/audit/session-switch/costs/sync-{i}.png').convert('RGB')
 actual=Image.open(out/f'final-{i}.png').convert('RGB')
 assert expected.size==actual.size
 bbox=ImageChops.difference(expected,actual).getbbox();assert bbox is None,bbox
 entry=dict(run=i,n=data['n'],median_ms=data['median_ms'],p95_ms=data['p95_ms'],max_gui_ms=max(x['max_gui_ms'] for x in data['samples']),rgb_bbox=bbox)
 entries.append(entry);print(json.dumps(entry),flush=True)
values=sorted(x['frame_ms'] for x in samples)
summary=dict(runs=entries,n=len(samples),median_ms=statistics.median(values),p95_ms=values[math.ceil(.95*len(values))-1],max_gui_ms=max(x['max_gui_ms'] for x in samples),dispatch_median_ms=statistics.median(x['dispatch_ms'] for x in samples))
(out/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
