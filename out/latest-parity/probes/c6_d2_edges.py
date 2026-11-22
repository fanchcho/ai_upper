import sys
sys.path.insert(0,'/home/agent/shared_workspace/ai_upper/scripts/parity')
from pngread import read_png
pts={"top":(700,658),"bottom":(700,803),"left":(428,720),"right":(1207,720)}
imgs=[("deva model-picker","out/latest-parity/deva/model-picker-deva.png"),
      ("before: HEAD same-code reshoot","out/latest-parity/qml/model-picker-before-d1.png"),
      ("after: current","out/latest-parity/qml/model-picker.png"),
      ("deva chat (menu closed)","out/latest-parity/deva/chat-deva.png"),
      ("qml  chat (menu closed)","out/latest-parity/qml/chat.png")]
for tag,p in imgs:
    w,h,px=read_png(p)
    print("%-30s"%tag, {k:px[y*w+x] for k,(x,y) in pts.items()})
print()
print("row y=658 scan (x450..1150 step100):")
for tag,p in imgs[2:4]:
    w,h,px=read_png(p)
    print("%-30s"%tag,[(x,px[658*w+x]) for x in range(450,1151,100)])
