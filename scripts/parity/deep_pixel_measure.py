"""Compare isolated renderer perturbations; reference is the preserved prior run."""
from pathlib import Path
from PIL import Image,ImageChops
import json
p=Path('docs/audit/deep-boundary/pixel')
reference=Path('docs/audit/environment-closeout/phase')
rows=[];shadow=[]
for theme in ['dark','light']:
 base=Image.open(p/f'{theme}-hint-0-phase-0.png').convert('RGB')
 for hint in range(4):
  for phase in [0,.5]:
   im=Image.open(p/f'{theme}-hint-{hint}-phase-{phase}.png').convert('RGB')
   crop=(486,411,900,600)
   diff=ImageChops.difference(im.crop(crop),base.crop(crop));runs=[]
   for y in range(411,600):
    bg=im.getpixel((800,y))
    if any(sum(abs(a-b) for a,b in zip(im.getpixel((x,y)),bg))>180 for x in range(486,636)):
     if not runs or y>runs[-1][-1]+1:runs.append([y,y])
     else:runs[-1][-1]=y
   ref=Image.open(reference/f'deva-{theme}-skill-shift-{phase}.png').convert('RGB')
   refdiff=ImageChops.difference(im.crop(crop),ref.crop(crop))
   rows.append({'theme':theme,'hint':hint,'phase':phase,'changedVsDefault':sum(any(px) for px in diff.get_flattened_data()),'changedVsPreservedReference':sum(any(px) for px in refdiff.get_flattened_data()),'ink':runs})
 for f in sorted(p.glob(f'{theme}-shadow-*.png')):
  im=Image.open(f).convert('RGB')
  shadow.append({'file':f.name,'sample_700_700':im.getpixel((700,700)),'scan_700':[(y,im.getpixel((700,y))) for y in range(686,716)]})
 for category,qtname,refname,crop in [('text',f'{theme}-hint-0-phase-0.png',f'deva-{theme}-skill-shift-0.png',(470,405,930,610)),('shadow',f'{theme}-shadow-baseline.png',f'deva-{theme}-menu-shift-0.png',(460,665,960,735))]:
  a=Image.open(reference/refname).convert('RGB').crop(crop);b=Image.open(p/qtname).convert('RGB').crop(crop)
  joined=Image.new('RGB',(a.width*2,a.height));joined.paste(a,(0,0));joined.paste(b,(a.width,0));joined.save(p/f'{theme}-{category}-reference-left.png')
result={'reference':'preserved previous run, not a fresh Electron run','hinting':rows,'shadow':shadow}
(p/'measurements.json').write_text(json.dumps(result,indent=2))
for r in rows:print(r)
for r in shadow:print(r['file'],r['sample_700_700'])
