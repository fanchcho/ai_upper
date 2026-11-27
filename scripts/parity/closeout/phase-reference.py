import subprocess,time,json
from pathlib import Path
out=Path('out/parity-close/phase')
def run(js,name=None):
 args=['node','scripts/parity/extensions_reference_cdp.mjs',js]
 if name:args.append(str(out/(name+'.png')))
 r=subprocess.run(args,capture_output=True,text=True);print(r.stdout,r.stderr)
 if name:(out/(name+'.json')).write_text(r.stdout)
measure='JSON.stringify([...document.querySelectorAll(".select,.select-icon,.select-menu,.select-menu__opt,.cf-avstack,.ext-detail__md,.md")].map(x=>({cls:x.className,rect:x.getBoundingClientRect().toJSON(),bg:getComputedStyle(x).backgroundColor,shadow:getComputedStyle(x).boxShadow,radius:getComputedStyle(x).borderRadius})))'
for theme in ['dark','light']:
 run(f'window.deva.config.set({{theme:"{theme}"}}).then(()=>location.reload())');time.sleep(1)
 run('document.querySelector("button[title=Settings]").click()')
 run('[...document.querySelectorAll("button")].find(x=>x.textContent.trim()==="Extensions").click()')
 run('[...document.querySelectorAll(".cf-setrow__open")].find(x=>x.textContent.includes("alpha")).click()')
 run(measure,f'deva-{theme}-skill')
 for delta in [0,.5,1]:
  run(f'document.querySelector(".md").style.transform="translateY({delta}px)"',f'deva-{theme}-skill-shift-{delta}')
 run('document.querySelector(".md").style.transform=""')
 run('document.querySelector(".select").click()')
 run(measure,f'deva-{theme}-roles-popup')
 run('document.querySelector(".select-menu__opt").click()')
 run(measure,f'deva-{theme}-all-roles')
 run('document.querySelector(".select").click()')
 run(measure,f'deva-{theme}-all-roles-popup')
 for delta in [0,.5,1]:
  run(f'document.querySelector(".select-menu").style.transform="translateY({delta}px)"',f'deva-{theme}-menu-shift-{delta}')
