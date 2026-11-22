import sys
sys.path.insert(0,'/home/agent/shared_workspace/ai_upper/scripts/parity')
from pngread import read_png
W,H,d=read_png('out/latest-parity/deva/model-picker-deva.png')
_,_,b=read_png('out/latest-parity/qml/model-picker-before-d1.png')
_,_,a=read_png('out/latest-parity/qml/model-picker.png')
def cnt(img,x0,y0,x1,y1):
    return sum(1 for y in range(y0,y1+1) for x in range(x0,x1+1) if d[y*W+x]!=img[y*W+x])
regions=[("旧面板位置(HEAD 700,540-1130,760)",700,540,1130,760),
         ("新面板位置(776,688-1023,752)",776,688,1023,752),
         ("面板上方投影 y651-687",700,651,1130,687),
         ("输入区贴片行 y753-799",400,753,1250,799)]
print("| 区域 | before | after | Δ |")
print("|---|---:|---:|---:|")
for name,x0,y0,x1,y1 in regions:
    vb=cnt(b,x0,y0,x1,y1); va=cnt(a,x0,y0,x1,y1)
    print("| %s | %d | %d | %+d |"%(name,vb,va,va-vb))
tb=sum(1 for i in range(W*H) if d[i]!=b[i]); ta=sum(1 for i in range(W*H) if d[i]!=a[i])
print("| **全图 1280×820** | **%d** | **%d** | **%+d** |"%(tb,ta,ta-tb))
