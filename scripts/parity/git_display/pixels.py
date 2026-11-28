import json
from pathlib import Path
from collections import Counter
from PySide6.QtGui import QImage
root=Path.cwd();out=root/'docs/audit/git-display'
def hexat(im,x,y):return im.pixelColor(x,y).name()
def find_pixel(im,rect,color):
 x,y,w,h=map(round,rect)
 for yy in range(y,y+h):
  for xx in range(x,x+w):
   if hexat(im,xx,yy)==color:return [xx,yy]
 return None
def contrast(a,b):
 def l(s):
  v=[int(s[i:i+2],16)/255 for i in [1,3,5]];v=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in v]
  return .2126*v[0]+.7152*v[1]+.0722*v[2]
 v=sorted([l(a),l(b)]);return round((v[1]+.05)/(v[0]+.05),3)
results={}
for theme in ['dark','light']:
 result={}
 for phase in ['before','after']:
  data=json.loads((out/f'{phase}-{theme}.json').read_text());im=QImage(str(out/f'{phase}-{theme}-git-full.png'));warn=QImage(str(out/f'{phase}-{theme}-warning-full.png'))
  warn.copy(936,200,1025,1746).save(str(out/f'{phase}-{theme}-warning.png'))
  points={'panel':(870,600),'status_panel':(900,460),'status_border':(880,500),'separator':(1200,806),'input_background':(1100,910),'input_left_border':(880,900),'secondary_border':(1200,830),'primary_fill':(1680,890),'danger_fill':(1060,814),'warning_fill':(1100,844),'warning_border':(1100,832)}
  # Freeze explicit positions for both phases; edges that move have a separate geometry-derived sample too.
  samples={}
  for name,(x,y) in points.items():
   image=warn if name.startswith('warning') or name=='separator' else im
   samples[name]={'xy':[x,y],'hex':hexat(image,x,y)}
  x,y,w,h=data['items']['gitIdentityName']['rect'];r=[2*x,2*y,2*w,2*h]
  fg='#a1a1aa' if theme=='dark' else '#5c5c66'
  p=find_pixel(im,r,fg)
  if not p and phase=='before':
   # The native style's actual placeholder colour, not the desired theme colour.
   fg='#808080';p=find_pixel(im,r,fg)
  samples['placeholder']={'xy':p,'hex':fg if p else None}
  p=[round(2*x),round(2*(y+h/2))];samples['input_actual_border']={'xy':p,'hex':hexat(im,*p)}
  p=[round(2*(x+w-5)),round(2*(y+h/2))];samples['input_actual_background']={'xy':p,'hex':hexat(im,*p)}
  wfg=('#a1a1aa' if theme=='dark' else '#5c5c66') if phase=='before' else ('#fcc419' if theme=='dark' else '#1f1f24')
  p=find_pixel(warn,[990,840,700,45],wfg);samples['warning_text']={'xy':p,'hex':wfg if p else None}
  result[phase]={'samples':samples,'input_rect':data['items']['gitIdentityName']['rect']}
  if samples['warning_text']['hex']:result[phase]['warning_contrast']=contrast(wfg,samples['warning_fill']['hex'])
  if samples['placeholder']['hex']:result[phase]['placeholder_contrast']=contrast(fg,samples['input_actual_background']['hex'])
 result['original_light_warning_contrast']=contrast('#d9860b','#f5efe6') if theme=='light' else None
 results[theme]=result
(out/'pixels.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results,indent=2))
