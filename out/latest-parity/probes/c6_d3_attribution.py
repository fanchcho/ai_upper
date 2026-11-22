import sys
sys.path.insert(0,'/home/agent/shared_workspace/ai_upper/scripts/parity')
from pngread import read_png
W,H,d=read_png('out/latest-parity/deva/model-picker-deva.png')
_,_,dc=read_png('out/latest-parity/deva/chat-deva.png')
_,_,q=read_png('out/latest-parity/qml/model-picker.png')
_,_,qc=read_png('out/latest-parity/qml/chat.png')
box=(600,470,1119,799)
def count(px):
    per={}
    for lo,hi in ((470,619),(620,650),(651,687),(688,752),(753,799)):
        n=0
        for y in range(lo,hi+1):
            for x in range(box[0],box[2]+1):
                if px[y*W+x]==(255,255,255): n+=1
        per[(lo,hi)]=n
    return per
a,b,c,e=count(d),count(q),count(dc),count(qc)
print("band            deva_mp qml_mp  Δmp   deva_chat qml_chat Δchat  picker-specific")
for k in sorted(a):
    print("%-14s %7d %6d %6d %9d %8d %6d %8d"%(str(k),a[k],b[k],a[k]-b[k],c[k],e[k],c[k]-e[k],(a[k]-b[k])-(c[k]-e[k])))
print("total          %7d %6d %6d %9d %8d %6d %8d"%(sum(a.values()),sum(b.values()),sum(a.values())-sum(b.values()),sum(c.values()),sum(e.values()),sum(c.values())-sum(e.values()),(sum(a.values())-sum(b.values()))-(sum(c.values())-sum(e.values()))))
