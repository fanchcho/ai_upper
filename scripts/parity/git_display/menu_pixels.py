from pathlib import Path
from PySide6.QtGui import QImage
import json
p=Path('docs/audit/git-version');result={}
def lum(c):
 v=[int(c[i:i+2],16)/255 for i in (1,3,5)];v=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in v];return sum(a*b for a,b in zip(v,[.2126,.7152,.0722]))
def contrast(a,b):
 x,y=sorted([lum(a),lum(b)]);return round((y+.05)/(x+.05),3)
for t in ['dark','light']:
 d=json.loads((p/f'{t}-interaction.json').read_text());im=QImage(str(p/f'{t}-menu.png'));x,y,w,h=d['menu_rect'];x,y,w,h=map(round,[x,y,w,h]);bg=im.pixelColor(x+3,y+30).name();border=im.pixelColor(x,y+30).name();fg='#e4e4e7' if t=='dark' else '#1f1f24'
 pts=[]
 for yy in range(y+8,y+36):
  for xx in range(x+35,x+100):
   if im.pixelColor(xx,yy).name()==fg:pts.append([xx,yy]);break
  if pts:break
 warning=QImage(str(p/f'{t}-warning.png'));wb=warning.pixelColor(550,422).name();wt='#fcc419' if t=='dark' else '#d9860b'
 result[t]={'size':[im.width(),im.height()],'menu_rect':[x,y,w,h],'bg':{'xy':[x+3,y+30],'hex':bg},'border':{'xy':[x,y+30],'hex':border},'text':{'xy':pts[0] if pts else None,'hex':fg},'menu_contrast':contrast(bg,fg),'warning_bg':{'xy':[550,422],'hex':wb},'warning_text':wt,'warning_contrast':contrast(wb,wt)}
(p/'samples.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
