import json,math,statistics,sys
from pathlib import Path
from PIL import Image,ImageChops
mode=sys.argv[1];root=Path('.tmp/architecture');groups=[];all=[]
for i in range(1,4):
 d=json.loads((root/f'{mode}-{i}.json').read_text());all+=d['samples']
 g=dict(group=i,rss_peak_kib=d['rss_peak_kib'],cache=d['cache'])
 for path in ['cold','hot']:
  r=[r for r in d['samples'] if r['path']==path];v=sorted(r['frame_ms'] for r in r)
  g[path]=dict(n=len(v),median_ms=statistics.median(v),p95_ms=v[math.ceil(.95*len(v))-1],max_gui_ms=max(x['max_gui_ms'] for x in r))
 if mode!='baseline':
  b=json.loads((root/f'baseline-{i}.json').read_text());g['text_equal']=[x['text_sha256'] for x in d['samples']]==[x['text_sha256'] for x in b['samples']]
  g['rgb']=[ImageChops.difference(Image.open(root/f'{mode}-{i}{s}.png').convert('RGB'),Image.open(root/f'baseline-{i}{s}.png').convert('RGB')).getbbox() for s in ['','-cold']]
 groups.append(g)
result=dict(groups=groups)
for path in ['cold','hot']:
 r=[r for r in all if r['path']==path];v=sorted(r['frame_ms'] for r in r)
 result[path]=dict(n=len(v),median_ms=statistics.median(v),p95_ms=v[math.ceil(.95*len(v))-1],max_gui_ms=max(x['max_gui_ms'] for x in r))
(root/f'{mode}-summary.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
