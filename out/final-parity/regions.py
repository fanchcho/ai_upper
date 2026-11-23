from pathlib import Path
from PIL import Image,ImageChops
from collections import Counter
import json
root=Path('out/final-parity');result={}
for page in ['settings-general','settings-models','settings-extensions','settings-about','long-mid']:
 dpath=root/'deva'/(page+'-deva.png')
 if not dpath.exists():dpath=Path('out/latest-parity/deva')/(page+'-deva.png')
 a=Image.open(root/'qml'/(page+'.png')).convert('RGB');b=Image.open(dpath).convert('RGB');pa=a.load();pb=b.load()
 box=(280,130,1000,690) if page.startswith('settings') else (64,56,339,810)
 inside=high=outside=0;samples=[];colors=Counter();tiles=Counter()
 for y in range(820):
  for x in range(1280):
   aa,bb=pa[x,y],pb[x,y];delta=max(abs(c-d) for c,d in zip(aa,bb))
   if not delta:continue
   if box[0]<=x<box[2] and box[1]<=y<box[3]:
    inside+=1;high+=delta>8
    if delta>8:
     tiles[(x//40*40,y//40*40)]+=1
     if len(samples)<8:samples.append([x,y,aa,bb,delta])
   else:outside+=1
   colors[(aa,bb)]+=1
 r={'reference':str(dpath),'inside_diff':inside,'inside_gt8':high,'outside_diff':outside,'samples':samples,'top_tiles':tiles.most_common(6),'common_color_pairs':[(str(k),v) for k,v in colors.most_common(4)]}
 if page=='long-mid':
  for side,p in [('qml',pa),('deva',pb)]:
   ys=[y for y in range(56,810) if sum(p[x,y]==(236,236,237) for x in range(64,339))>100]
   bands=[]
   for y in range(56,810):
    if sum(max(p[x,y])<170 for x in range(115,310))>6:
     if bands and bands[-1][1]==y-1:bands[-1][1]=y
     else:bands.append([y,y])
   r[side]={'hover_rows':len(ys),'hover_range':[min(ys),max(ys)] if ys else [],'text_bands':bands,'pixel_668_721':p[668,721]}
 result[page]=r
print(json.dumps(result,indent=2));(root/'region-results.json').write_text(json.dumps(result,indent=2))
for page,r in result.items(): print(page,'inside',r['inside_diff'],'gt8',r['inside_gt8'],'outside',r['outside_diff'])
