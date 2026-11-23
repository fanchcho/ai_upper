from PIL import Image,ImageChops
from pathlib import Path
import hashlib
r=Path('out/final-parity')
for scale in (1,2):
 for page in ('chat','empty'):
  q=r/'qml'/(page+'.png') if scale==1 else r/'scale'/f'qml-{page}-2.png';d=r/'scale'/f'deva-{page}-{scale}.png'
  a=Image.open(q).convert('RGB');b=Image.open(d).convert('RGB');assert a.size==b.size
  diff=ImageChops.difference(a,b);n=sum(1 for c in diff.getdata() if max(c));print(page,scale,'size',a.size,'AE',n,'pct',round(n*100/(a.width*a.height),5),'qml_md5',hashlib.md5(q.read_bytes()).hexdigest(),'deva_md5',hashlib.md5(d.read_bytes()).hexdigest())
