"""Measure actual screenshot ink and saved DOM/QML geometry; Pillow only in this audit."""
import json
from pathlib import Path
from PIL import Image
out=Path('out/extensions-calibration')
results=[]
for theme in ['dark','light']:
    ink={}
    for renderer,name in [('original',f'deva-{theme}-skill'),('qt',f'{theme}-skill-detail')]:
        im=Image.open(out/(name+'.png')).convert('RGB'); runs=[]
        for y in range(411,600):
            bg=im.getpixel((800,y))
            if any(sum(abs(a-b) for a,b in zip(im.getpixel((x,y)),bg))>180 for x in range(486,636)):
                if not runs or y>runs[-1][-1]+1:runs.append([y,y])
                else:runs[-1][-1]=y
        ink[renderer]=runs
    fields=[]
    original=json.loads(json.loads((out/f'deva-{theme}-mcp.json').read_text())['result']['result']['value'])
    qt=json.loads((out/f'{theme}-mcp-detail-geometry.json').read_text())
    for name in ['Transport','Command','Arguments','Environment variables']:
        a=next(r['rect']['y'] for r in original if r['text'].lower()==name.lower())
        b=next(r['y'] for r in qt if r['text']==name)
        fields.append(dict(name=name,original=a,qt=b,delta=b-a))
    lock={}
    for renderer,name in [('original',f'deva-{theme}-lock'),('qt',f'{theme}-lock')]:
        im=Image.open(out/(name+'.png')).convert('RGB')
        pts=[(x,y) for y in range(490,530) for x in range(915,940) if (lambda p:p[2]-p[1]>20 and p[2]-p[0]>10)(im.getpixel((x,y)))]
        lock[renderer]=[min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)]
    results.append(dict(theme=theme,ink=ink,fields=fields,lock_ink=lock))
    for kind,a,b in [('skill',f'deva-{theme}-skill',f'{theme}-skill-detail'),('mcp',f'deva-{theme}-mcp',f'{theme}-mcp-detail'),('tools',f'deva-{theme}-bottom',f'{theme}-mcp-bottom'),('lock',f'deva-{theme}-lock',f'{theme}-lock')]:
        im=Image.new('RGB',(2560,820));im.paste(Image.open(out/(a+'.png')),(0,0));im.paste(Image.open(out/(b+'.png')),(1280,0));im.save(out/f'compare-{theme}-{kind}.png')
(out/'measurements.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
