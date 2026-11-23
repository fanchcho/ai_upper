"""D3: inclusive historical white bbox; same <=2/>8 buckets as modal attribution."""
from pathlib import Path
import hashlib, json, sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/parity'))
from pngread import read_png
OUT=Path(__file__).resolve().parent
W,H=1280,820
paths={
 'deva_picker':ROOT/'out/latest-parity/deva/model-picker-deva.png',
 'deva_chat':ROOT/'out/latest-parity/deva/chat-deva.png',
 'qml_picker':OUT/'qml/model-picker.png',
 'qml_chat':OUT/'qml/chat.png',
}
images={};meta={}
for key,path in paths.items():
 w,h,p=read_png(str(path));assert (w,h)==(W,H);images[key]=p
 meta[key]={'path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'md5':hashlib.md5(path.read_bytes()).hexdigest()}
d,q,dc,qc=(images[k] for k in ('deva_picker','qml_picker','deva_chat','qml_chat'))
box=(600,470,1120,800);panel=(847,688,1095,753)
def indices(bounds):
 x0,y0,x1,y1=bounds
 return (y*W+x for y in range(y0,y1) for x in range(x0,x1))
def delta(a,b):return max(abs(x-y) for x,y in zip(a,b))
def metrics(bounds):
 result={'pixels':(bounds[2]-bounds[0])*(bounds[3]-bounds[1]),'diff':0,'d1_2':0,'d3_8':0,'gt8':0,'gt8_flat_both':0}
 for i in indices(bounds):
  md=delta(q[i],d[i])
  if not md:continue
  result['diff']+=1;result['d1_2' if md<=2 else 'd3_8' if md<=8 else 'gt8']+=1
  if md>8 and 0<i%W<W-1 and W<i<(H-1)*W:
   near=(i-W,i-1,i+1,i+W)
   if all(q[j]==q[i] and d[j]==d[i] for j in near): result['gt8_flat_both']+=1
 return result
bands=[]
for lo,hi in ((470,620),(620,651),(651,688),(688,753),(753,800)):
 area=(600,lo,1120,hi);counts={k:sum(p[i]==(255,255,255) for i in indices(area)) for k,p in images.items()}
 mp=counts['deva_picker']-counts['qml_picker'];chat=counts['deva_chat']-counts['qml_chat']
 bands.append({'y_inclusive':[lo,hi-1],**counts,'deva_minus_qml':mp,'chat_deva_minus_qml':chat,'picker_specific':mp-chat,**metrics(area)})
regions={'full':metrics((0,0,W,H)),'historical_box':metrics(box),'panel':metrics(panel),'panel_core':metrics((848,689,1094,752))}
regions['outside_panel']={k:regions['full'][k]-regions['panel'][k] for k in regions['full']}
thresholds={str(t):{k:sum(min(p[i])>=t for i in indices(box)) for k,p in images.items()} for t in (240,250,254,255)}
samples={f'{x},{y}':{k:list(p[y*W+x]) for k,p in images.items()} for x,y in ((60,120),(300,700),(1100,100),(1200,100),(900,700),(850,720),(700,680),(520,812))}
result={'meta':meta,'historical_box_half_open':box,'panel_half_open':panel,'bands':bands,'regions':regions,'white_threshold_diagnostic':thresholds,'samples':samples}
(OUT/'d3-attribution.json').write_text(json.dumps(result,indent=2)+'\n')
print('white bbox x600..1119 y470..799; sign=deva-qml')
for b in bands:print('band',b['y_inclusive'],'deva',b['deva_picker'],'qml',b['qml_picker'],'gap',b['deva_minus_qml'],'chat_gap',b['chat_deva_minus_qml'],'picker_specific',b['picker_specific'])
print('TOTAL', {k:sum(b[k] for b in bands) for k in ('deva_picker','qml_picker','deva_minus_qml','chat_deva_minus_qml','picker_specific')})
for k in ('full','panel','outside_panel'):print(k,regions[k])
