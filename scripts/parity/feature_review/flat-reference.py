import subprocess,json
for theme in ['dark','light']:
 dark=theme=='dark';bg='#2a2a2e' if dark else '#ffffff';fg='124,124,240' if dark else '91,91,214';items=[]
 for i,(alpha,offset,size) in enumerate([(a,o,s) for a in ([.2,.16] if dark else [.12,.1]) for o in [0,.5] for s in [20,40]]):
  items.append(f'<div style="position:absolute;left:{20+i*65+offset}px;top:30px;width:{size}px;height:{size}px;background:rgba({fg},{alpha})"></div>')
 html=f'<div style="position:fixed;z-index:99999;left:0;top:0;width:600px;height:100px;background:{bg}">'+''.join(items)+'</div>'
 expr='document.getElementById("rounding-probe")?.remove();var p=document.createElement("div");p.id="rounding-probe";p.innerHTML='+json.dumps(html)+';document.body.appendChild(p)'
 subprocess.run(['node','scripts/parity/extensions_reference_cdp.mjs',expr,f'out/feature-review/rounding/deva-{theme}-flat.png'],check=True)
