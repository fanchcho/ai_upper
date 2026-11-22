import sys
sys.path.insert(0,'/home/agent/shared_workspace/ai_upper/scripts/parity')
from pngread import read_png
def bbox_white(path, box=(600,470,1119,799), thr=255):
    w,h,px=read_png(path); x0,y0,x1,y1=box; n=0; bands={}
    for y in range(y0,y1+1):
        c=0
        for x in range(x0,x1+1):
            r,g,b=px[y*w+x]
            if r>=thr and g>=thr and b>=thr: c+=1
        n+=c
        for lo,hi in ((470,619),(620,650),(651,687),(688,752),(753,799)):
            if lo<=y<=hi: bands[(lo,hi)]=bands.get((lo,hi),0)+c
    return n,bands
for tag,p in (("deva","out/latest-parity/deva/model-picker-deva.png"),
              ("qml-after","out/latest-parity/qml/model-picker.png")):
    n,b=bbox_white(p); print(tag,"bbox255",n); 
    for k in sorted(b): print("   band",k,b[k])
# composer edges
def edge(path, pts):
    w,h,px=read_png(path); return {k:px[y*w+x] for k,(x,y) in pts.items()}
pts={"top":(700,658),"bottom":(700,803),"left":(428,720),"right":(1207,720)}
print("edges deva", edge("out/latest-parity/deva/model-picker-deva.png",pts))
print("edges qml ", edge("out/latest-parity/qml/model-picker.png",pts))
