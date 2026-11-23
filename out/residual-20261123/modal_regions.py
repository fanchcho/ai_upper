from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts/parity'))
from pngread import read_png
regions={
 'settings-models':{'provider_name':(500,248,670,275),'provider_count':(500,274,620,293),'title':(465,195,580,225)},
 'settings-extensions':{'title':(465,195,600,225),'row1':(480,247,690,278),'row2':(480,291,690,322),'row3':(480,337,690,367),'switches':(920,243,970,367)},
 'delete-confirm':{'title':(445,330,835,384),'description':(445,393,835,440),'cancel':(690,457,747,479),'delete':(760,452,830,483)}
}
result={}
for page,boxes in regions.items():
 images={s:read_png(str(ROOT/folder/(page+suffix+'.png'))) for s,folder,suffix in [('qml','out/residual-20261123/modal',''),('deva','out/latest-parity/deva','-deva')]}
 result[page]={}
 for name,(x0,y0,x1,y1) in boxes.items():
  result[page][name]={}
  for side,(w,h,p) in images.items():
   pts=[(x,y) for y in range(y0,y1) for x in range(x0,x1) if max(p[y*w+x])<200]
   result[page][name][side]={'dark_pixels':len(pts),'bbox': [min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)] if pts else None}
print(json.dumps(result,indent=2))
