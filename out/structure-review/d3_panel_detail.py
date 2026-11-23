from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts/parity'))
from pngread import read_png
OUT=Path(__file__).resolve().parent
_,_,q=read_png(str(OUT/'qml/model-picker.png'));_,_,d=read_png(str(ROOT/'out/latest-parity/deva/model-picker-deva.png'))
W=1280
parts={'top_edge':(847,688,1095,700),'group_text_band':(847,700,1095,714),'row_gap':(847,714,1095,727),'model_check_band':(847,727,1095,740),'bottom_edge':(847,740,1095,753)}
result={}
for name,(x0,y0,x1,y1) in parts.items():
 n=gt8=near2=0
 for y in range(y0,y1):
  for x in range(x0,x1):
   a,b=q[y*W+x],d[y*W+x];delta=max(abs(i-j) for i,j in zip(a,b));n+=delta>0;gt8+=delta>8
   if delta>8:
    near2+=any(max(abs(a[k]-d[yy*W+xx][k]) for k in range(3))<=8 for yy in range(max(y0,y-2),min(y1,y+3)) for xx in range(max(x0,x-2),min(x1,x+3)))
 result[name]={'diff':n,'gt8':gt8,'qml_has_deva_color_within2px':near2}
 print(name,result[name])
def bbox(p,region,predicate):
 pts=[(x,y) for y in range(region[1],region[3]) for x in range(region[0],region[2]) if predicate(p[y*W+x])]
 return {'count':len(pts),'bbox':[min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)] if pts else None}
ink={}
for name,region,pred in [('heading',(855,698,1050,715),lambda c:max(c)<200),('model',(855,720,1060,742),lambda c:c[2]>c[0]+40),('check',(1065,720,1086,742),lambda c:c[2]>c[0]+40)]:
 ink[name]={side:bbox(p,region,pred) for side,p in [('qml',q),('deva',d)]};print(name,ink[name])
(OUT/'d3-panel-detail.json').write_text(json.dumps({'parts':result,'ink':ink},indent=2)+'\n')
a=json.load(open(OUT/'d3-attribution.json'))
for key in ('60,120','300,700','1100,100','1200,100'):print('outside_sample',key,a['samples'][key])
