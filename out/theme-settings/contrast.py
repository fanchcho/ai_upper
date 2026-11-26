import json, collections
from pathlib import Path
from PySide6.QtGui import QImage,QColor
root=Path(__file__).resolve().parent

def lum(rgb):
 v=[x/255 for x in rgb];v=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in v]
 return sum(a*b for a,b in zip(v,[.2126,.7152,.0722]))
def ratio(a,b):
 l,h=sorted([lum(a),lum(b)]);return (h+.05)/(l+.05)
allrows=[]
for stage in ['before','after']:
 for row in json.loads((root/stage/'text-regions.json').read_text()):
  im=QImage(str(root/stage/(row['page']+'-'+row['theme']+'.png')))
  for t in row['texts']:
   if t['w']<=0 or t['h']<=0:continue
   pixels=collections.Counter(im.pixelColor(x,y).name() for x in range(max(0,int(t['x'])),min(im.width(),int(t['x']+t['w']))) for y in range(max(0,int(t['y'])),min(im.height(),int(t['y']+t['h']))))
   if not pixels:continue
   bg=pixels.most_common(1)[0][0];target=QColor(t['color']).getRgb()[:3]
   fg=min(pixels,key=lambda c:sum((a-b)**2 for a,b in zip(QColor(c).getRgb()[:3],target)))
   distance=sum((a-b)**2 for a,b in zip(QColor(fg).getRgb()[:3],target))**.5
   r=ratio(QColor(fg).getRgb()[:3],QColor(bg).getRgb()[:3])
   allrows.append(dict(stage=stage,page=row['page'],theme=row['theme'],text=t['text'],fg=fg,bg=bg,ratio=round(r,3),distance=round(distance,2)))
(root/'contrast.json').write_text(json.dumps(allrows,ensure_ascii=False,indent=2))
lines=['|阶段|页面|主题|文字|实际字像素|实际底像素|对比度|','|---|---|---|---|---|---|---|']
for r in allrows:lines.append('|'+ '|'.join(str(r[k]).replace('\n',' ') for k in ['stage','page','theme','text','fg','bg','ratio'])+'|')
(root/'CONTRAST.md').write_text('\n'.join(lines)+'\n')
print('after failures:',json.dumps([r for r in allrows if r['stage']=='after' and r['ratio']<4.5],ensure_ascii=False,indent=2))
assert all(r['ratio'] >= 4.5 for r in allrows if r['stage']=='after'), 'Rendered text contrast below 4.5:1'
