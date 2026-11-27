from PIL import Image
from pathlib import Path
import json
p=Path('out/parity-close/phase');rows=[]
for theme in ['dark','light']:
 for delta in ['0','0.5','1']:
  row={'theme':theme,'phase':float(delta)}
  for label,prefix in [('original','deva-'),('qt','')]:
   im=Image.open(p/f'{prefix}{theme}-skill-shift-{delta}.png').convert('RGB');runs=[]
   for y in range(411,600):
    bg=im.getpixel((800,y))
    if any(sum(abs(a-b) for a,b in zip(im.getpixel((x,y)),bg))>180 for x in range(486,636)):
     if not runs or y>runs[-1][-1]+1:runs.append([y,y])
     else:runs[-1][-1]=y
   shadow=Image.open(p/f'{prefix}{theme}-menu-shift-{delta}.png').convert('RGB')
   row[label]={'ink':runs,'shadow_at_700_700':shadow.getpixel((700,700)),'shadow_scan':[(y,shadow.getpixel((700,y))) for y in range(686,716)]}
  rows.append(row)
(p/'phase-measurements.json').write_text(json.dumps(rows,indent=2))
for r in rows:print(r['theme'],r['phase'],[x[0] for x in r['original']['ink']],[x[0] for x in r['qt']['ink']],r['original']['shadow_at_700_700'],r['qt']['shadow_at_700_700'])
