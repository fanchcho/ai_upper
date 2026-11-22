import sys
sys.path.insert(0,'/home/agent/shared_workspace/ai_upper/scripts/parity')
from pngread import read_png
def load(p):
    w,h,px=read_png(p); return w,h,px
W,H,dmp=load('out/latest-parity/deva/model-picker-deva.png')
_,_,qmp=load('out/latest-parity/qml/model-picker.png')
_,_,dch=load('out/latest-parity/deva/chat-deva.png')
_,_,qch=load('out/latest-parity/qml/chat.png')
bands=[(0,469),(470,619),(620,650),(651,687),(688,752),(753,799),(800,820)]
def cnt(a,b,lo,hi):
    n=0
    for y in range(lo,min(hi+1,H)):
        for x in range(W):
            p=a[y*W+x]; q=b[y*W+x]
            if p!=q: n+=1
    return n
print("band          mp_diff  chat_diff  picker-specific")
tm=tc=0
for lo,hi in bands:
    m=cnt(dmp,qmp,lo,hi); c=cnt(dch,qch,lo,hi); tm+=m; tc+=c
    print("y%-4d-%-4d %8d %9d %10d"%(lo,hi,m,c,m-c))
print("TOTAL        %8d %9d %10d"%(tm,tc,tm-tc))
