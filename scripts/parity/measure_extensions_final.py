"""Compare opened menus against saved original-renderer evidence."""
from pathlib import Path
from PIL import Image
import json
out=Path('out/extensions-final');data=[]
for t in ['dark','light']:
 for stage,p in [('original',f'out/extensions-finish/deva-{t}-all-roles-popup.png'),('before',f'out/extensions-finish/{t}-all-roles-popup.png'),('after',f'out/extensions-final/{t}-all-roles-popup.png')]:
  im=Image.open(p).convert('RGB')
  pts=[(x,y) for y in range(388,405) for x in range(948,965) if (lambda c:c[2]-c[1]>30)(im.getpixel((x,y)))]
  data.append(dict(theme=t,stage=stage,check_bbox=[min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)] if pts else None,pixels={str(xy):im.getpixel(xy) for xy in [(700,325),(700,328),(700,380),(480,343),(700,660)]}))
 for stage,root in [('before',Path('out/extensions-finish')),('after',out)]:
  a=Image.open(f'out/extensions-finish/deva-{t}-all-roles-popup.png');b=Image.open(root/f'{t}-all-roles-popup.png');im=Image.new('RGB',(2560,820));im.paste(a,(0,0));im.paste(b,(1280,0));im.save(out/f'compare-{t}-menu-{stage}.png')
(out/'pixels.json').write_text(json.dumps(data,indent=2));print(json.dumps(data,indent=2))
