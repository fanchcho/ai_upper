"""Separate modal interior high deltas from flat fills and nearby edge matches.

A nearby match is evidence of an edge/position difference, not proof of harmless
rounding. All original differences remain counted.
"""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/parity'))
from pngread import read_png
from measure_page import measure
PAGES=tuple(sys.argv[1:]) or ('settings-general','settings-models','settings-extensions','settings-about','delete-confirm')
def delta(a,b):return max(abs(x-y) for x,y in zip(a,b))
def neighbors(p,w,x,y,r):return [p[yy*w+xx] for yy in range(y-r,y+r+1) for xx in range(x-r,x+r+1)]
results={}
for page in PAGES:
 path=ROOT/'out/residual-20261123/modal'/f'{page}.png'; w,h,q=read_png(str(path));_,_,d=read_png(str(ROOT/'out/latest-parity/deva'/f'{page}-deva.png'))
 box=(430,317,850,503) if page=='delete-confirm' else (280,130,1000,690)
 x0,y0,x1,y1=box; summary=measure(path,page);stats={'symmetric_neighbor1':0,'symmetric_neighbor2':0,'flat_both':0}; tiles={}; pixels=[]
 for y in range(y0,y1):
  for x in range(x0,x1):
   a,b=q[y*w+x],d[y*w+x]
   if delta(a,b)<=8:continue
   pixels.append((x,y));key=f'{x//40*40},{y//40*40}';tiles[key]=tiles.get(key,0)+1
   for r in (1,2):
    if any(delta(a,v)<=8 for v in neighbors(d,w,x,y,r)) and any(delta(b,v)<=8 for v in neighbors(q,w,x,y,r)): stats[f'symmetric_neighbor{r}']+=1
   if all(delta(a,v)<=2 for v in neighbors(q,w,x,y,1)) and all(delta(b,v)<=2 for v in neighbors(d,w,x,y,1)):stats['flat_both']+=1
 summary['interior_analysis']=stats;summary['top_40px_tiles']=sorted(tiles.items(),key=lambda x:-x[1])[:12]
 summary['high_delta_bbox']=[min(x for x,y in pixels),min(y for x,y in pixels),max(x for x,y in pixels),max(y for x,y in pixels)]
 results[page]=summary
print(json.dumps(results,indent=2))
