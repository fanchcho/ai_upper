"""Measure a fresh page against the tracked deva reference; no image mutation."""
from pathlib import Path
import json, sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/parity'))
from pngread import read_png

def bands(p,w,region):
 x0,y0,x1,y1=region; out=[]
 for y in range(y0,y1):
  if sum(max(p[y*w+x])<200 for x in range(x0,x1))<=3: continue
  if out and out[-1][1]==y-1: out[-1][1]=y
  else: out.append([y,y])
 return out

def measure(path,page):
 w,h,q=read_png(str(path)); dw,dh,d=read_png(str(ROOT/'out/latest-parity/deva'/f'{page}-deva.png')); assert (w,h)==(dw,dh)==(1280,820)
 box=(430,317,850,503) if page=='delete-confirm' else (280,130,1000,690) if page.startswith('settings-') else (0,0,w,h)
 counts=dict(total=0,inside=0,inside_gt8=0,outside=0,outside_le2=0)
 for i,(a,b) in enumerate(zip(q,d)):
  delta=max(abs(x-y) for x,y in zip(a,b))
  if not delta: continue
  x,y=i%w,i//w; inside=box[0]<=x<box[2] and box[1]<=y<box[3]
  counts['total']+=1; counts['inside' if inside else 'outside']+=1
  counts['inside_gt8']+=inside and delta>8; counts['outside_le2']+=not inside and delta<=2
 counts['percent']=counts['total']*100/(w*h)
 for side,p in [('qml',q),('deva',d)]:
  counts[side+'_bands']=bands(p,w,(430,40,1200,640)); counts[side+'_lower_bands']=bands(p,w,(430,200,1200,700))
  ys=[y for y in range(50,810) if sum(p[y*w+x]==(236,236,237) for x in range(64,339))>100]
  counts[side+'_hover']=[len(ys),[ys[0],ys[-1]] if ys else None]
 return counts
if __name__=='__main__': print(json.dumps(measure(Path(sys.argv[1]),sys.argv[2]),indent=2))
