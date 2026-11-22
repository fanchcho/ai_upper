import sys
sys.path.insert(0, '/home/agent/shared_workspace/ai_upper/scripts/parity')
from pngread import read_png
ROOT='/home/agent/shared_workspace/ai_upper/out/latest-parity'
PAGES=["chat","empty","search-results","ctx-menu","delete-confirm","model-picker",
       "hover-thread","long-mid","settings-general","settings-models","settings-about","dark-chat"]
for p in PAGES:
    w,h,a=read_png(ROOT+'/deva/%s-deva.png'%p)
    w2,h2,b=read_png(ROOT+'/qml/%s.png'%p)
    tot=le2=le8=gt8=0
    for x,y in zip(a,b):
        d=max(abs(x[0]-y[0]),abs(x[1]-y[1]),abs(x[2]-y[2]))
        if d:
            tot+=1
            if d<=2: le2+=1
            elif d<=8: le8+=1
            else: gt8+=1
    print('%-20s %7d %7d %6d %7d %7d %6.2f%%' % (p, tot, le2, le8, gt8, tot, le2*100.0/tot if tot else 0))
