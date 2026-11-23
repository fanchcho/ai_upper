import json, sys
from pathlib import Path
from PIL import Image
for path in sys.argv[1:]:
    if path.endswith('.json'):
        j=json.loads(Path(path).read_text());print(path)
        for b in j['blocks']:
            if b['text'] and len(b['text'])<50: print(repr(b['text']),round(b['y'],4),round(b['height'],4))
    else:
        im=Image.open(path).convert('RGB');p=im.load();bands=[]
        for y in range(40,640):
            n=sum(max(p[x,y])<200 for x in range(530,1184))
            if n>3:
                if bands and bands[-1][1]==y-1: bands[-1][1]=y
                else:bands.append([y,y])
        print(path,'bands',bands)
        # Horizontal table-border runs; exact palette and low-spread near-border pixels.
        rows=[]
        for y in range(60,245):
            n=sum(p[x,y]==(230,230,234) for x in range(484,795))
            if n>200:rows.append((y,n))
        print('border_rows',rows)
