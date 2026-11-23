from pathlib import Path
from PIL import Image,ImageChops
import json,hashlib,itertools,re
root=Path('out/final-parity')
old={}
for line in Path('out/latest-parity/REPORT.md').read_text().splitlines():
    m=re.match(r"\| ([\w-]+) \| `[^`]+` \| `[^`]+` \| (\d+) \| ([\d.]+) \|",line)
    if m and m[1] not in old:old[m[1]]=int(m[2])
rows=[];manifest=[]
for q in sorted((root/'qml').glob('*.png')):
    page=q.stem;d=root/'deva'/(page+'-deva.png');a=Image.open(q).convert('RGB');b=Image.open(d).convert('RGB');assert a.size==b.size
    diff=ImageChops.difference(a,b);n=sum(1 for c in diff.getdata() if max(c));previous=old.get(page)
    rows.append(f"| {page} | {previous} | {n} | {n*100/(a.width*a.height):.2f}% | {n-previous:+d} |")
    for side,p in [('qml',q),('deva',d)]:
        im=Image.open(p);err=root/side/(page+'.err');rc=root/side/(page+'.rc')
        manifest.append({'side':side,'page':page,'width':im.width,'height':im.height,'bytes':p.stat().st_size,'md5':hashlib.md5(p.read_bytes()).hexdigest(),'stderr_bytes':err.stat().st_size,'rc':int(rc.read_text())})
(root/'page-table.md').write_text('| 页 | 上一完整表px | 本轮px | 本轮比例 | 增减px |\n|---|---:|---:|---:|---:|\n'+'\n'.join(rows)+'\n')
(root/'png-manifest.json').write_text(json.dumps(manifest,indent=2));print('\n'.join(rows))
for a,b in itertools.combinations(['chat','long-mid','long-bottom'],2):
    pa=root/'qml'/(a+'.png');pb=root/'qml'/(b+'.png');im=ImageChops.difference(Image.open(pa).convert('RGB'),Image.open(pb).convert('RGB'));ae=sum(1 for c in im.getdata() if max(c));different=pa.read_bytes()!=pb.read_bytes();assert ae>0 and different
    print('HARD_DIFFERENT',a,b,'AE',ae,'md5',hashlib.md5(pa.read_bytes()).hexdigest(),hashlib.md5(pb.read_bytes()).hexdigest())
print('MANIFEST')
for r in manifest:print(r['side'],r['page'],str(r['width'])+'x'+str(r['height']),'bytes='+str(r['bytes']),'stderr='+str(r['stderr_bytes']),'rc='+str(r['rc']))
