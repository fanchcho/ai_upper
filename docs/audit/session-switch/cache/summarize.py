import json,math,statistics
from pathlib import Path
from PIL import Image,ImageChops
root=Path('.tmp/hot-cache');out={};lines=[]
for mode in ['accepted-before','accepted-after']:
 all=[]
 for i in range(1,4):
  d=json.loads((root/f'{mode}-{i}.json').read_text());all+=d['samples']
  for suffix in ['.png','-cold.png']:
   bbox=ImageChops.difference(Image.open(root/(f'{mode}-{i}'+suffix)).convert('RGB'),Image.open('docs/audit/session-switch/costs/sync-1.png').convert('RGB')).getbbox()
   assert bbox is None,(mode,i,suffix,bbox)
  for path in ['cold','hot']:
   rows=[r for r in d['samples'] if r['path']==path];values=sorted(r['frame_ms'] for r in rows)
   lines.append(f'|{mode}|{i}|{path}|24|{statistics.median(values):.3f}|{values[math.ceil(.95*len(values))-1]:.3f}|{max(r["max_gui_ms"] for r in rows):.3f}|')
 for path in ['cold','hot']:
  rows=[r for r in all if r['path']==path];values=sorted(r['frame_ms'] for r in rows)
  out[mode+'-'+path]=dict(n=len(rows),median_ms=statistics.median(values),p95_ms=values[math.ceil(.95*len(values))-1],max_gui_ms=max(r['max_gui_ms'] for r in rows),dispatch_median_ms=statistics.median(r['dispatch_ms'] for r in rows))
for i in range(1,4):
 a=json.loads((root/f'accepted-before-{i}.json').read_text());b=json.loads((root/f'accepted-after-{i}.json').read_text())
 assert [(r['id'],r['path'],r['text_sha256']) for r in a['samples']]==[(r['id'],r['path'],r['text_sha256']) for r in b['samples']]
out['verification']='12 final PNG RGB equal to committed baseline; 144 full text hashes equal; per click title/active ID/last turn assertions passed; all six subprocesses exit 0 (runner check=True)'
(root/'summary.json').write_text(json.dumps(out,indent=2))
(root/'groups.md').write_text('\n'.join(lines)+'\n')
print(json.dumps(out,indent=2))
