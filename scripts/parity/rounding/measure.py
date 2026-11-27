from PIL import Image
from pathlib import Path
import json
out=Path('out/extensions-rounding');result={}
for t in ['dark','light']:
 rows=[]
 for renderer in ['deva','qt']:
  im=Image.open(out/f'{renderer}-{t}-flat.png').convert('RGB');rows.append({'renderer':renderer,'centers':[im.getpixel((25+i*65,35)) for i in range(8)]})
 result[t]={'flat':rows,'shifts':[]}
 for delta in ['0','0.5','1']:
  row={'delta':delta}
  for renderer,prefix in [('original','deva-'),('qt','')]:
   im=Image.open(out/f'{prefix}{t}-skill-shift-{delta}.png').convert('RGB');runs=[]
   for y in range(411,600):
    bg=im.getpixel((800,y))
    if any(sum(abs(a-b) for a,b in zip(im.getpixel((x,y)),bg))>180 for x in range(486,636)):
     if not runs or y>runs[-1][-1]+1:runs.append([y,y])
     else:runs[-1][-1]=y
   menu=Image.open(out/f'{prefix}{t}-menu-shift-{delta}.png').convert('RGB')
   pts=[(x,y) for y in range(388,406) for x in range(948,965) if (lambda c:c[2]-c[1]>30)(menu.getpixel((x,y)))]
   row[renderer]={'ink':runs,'shadow':[menu.getpixel((700,y)) for y in [646,650,660]],'check':[min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)]}
  result[t]['shifts'].append(row)
 for kind in ['skill','menu']:
  a=Image.open(out/f'deva-{t}-{kind}-shift-0.png');b=Image.open(out/f'{t}-{kind}-shift-0.png');im=Image.new('RGB',(2560,820));im.paste(a,(0,0));im.paste(b,(1280,0));im.save(out/f'compare-{t}-{kind}.png')
(out/'measurements.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
