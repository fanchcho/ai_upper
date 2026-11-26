import json,statistics,math
from pathlib import Path
from PIL import Image,ImageChops
root=Path('.tmp/cold-path');out={}
for mode in ['baseline','deferred','batch','retained']:
 samples=[];groups=[]
 for i in range(1,4):
  p=root/f'{mode}-{i}.json'
  if not p.exists():continue
  d=json.loads(p.read_text());samples+=d['samples']
  rgb={suffix:ImageChops.difference(Image.open(root/(f'{mode}-{i}'+suffix)).convert('RGB'),Image.open('docs/audit/session-switch/cache/release-after-1.png').convert('RGB')).getbbox() for suffix in ['.png','-cold.png']}
  b=json.loads((root/f'baseline-{i}.json').read_text())
  same=[(x['id'],x['path'],x['text_sha256']) for x in b['samples']]==[(x['id'],x['path'],x['text_sha256']) for x in d['samples']]
  group=dict(group=i,cache=d['cache'],rss_peak_kib=d['rss_peak_kib'],rgb_bbox=rgb,text_equal=same)
  for path in ['cold','hot']:
   r=[x for x in d['samples'] if x['path']==path];v=sorted(x['frame_ms'] for x in r)
   group[path]=dict(n=len(r),median_ms=statistics.median(v),p95_ms=v[math.ceil(.95*len(v))-1],max_gui_ms=max(x['max_gui_ms'] for x in r))
  groups.append(group)
 if not samples:continue
 out[mode]={'groups':groups}
 for path in ['cold','hot']:
  r=[x for x in samples if x['path']==path];v=sorted(x['frame_ms'] for x in r)
  out[mode][path]=dict(n=len(r),median_ms=statistics.median(v),p95_ms=v[math.ceil(.95*len(v))-1],max_gui_ms=max(x['max_gui_ms'] for x in r))
(root/'summary.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
