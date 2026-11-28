"""Isolate QColor/CSS parsing and default/explicit source-over; no production edits."""
import os,json
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtCore import QUrl
from PySide6.QtTest import QTest
app=QGuiApplication([]);out=Path('docs/audit/deep-boundary/pixel');rows=[]
for theme,background,rgb,alpha in [('dark','#2a2a2e','124,124,240',.16),('light','#ffffff','91,91,214',.1)]:
 r,g,b=map(int,rgb.split(','));items=[];cells=[]
 for i,(kind,mode) in enumerate((k,m) for k in ['qcolor','css'] for m in ['default','source-over']):
  style='root.tint' if kind=='qcolor' else f'"rgba({rgb},{alpha})"'
  operation='' if mode=='default' else 'ctx.globalCompositeOperation="source-over";'
  items.append(f'''Canvas {{ x:{20+i*90};y:20;width:70;height:70;onPaint: {{ var ctx=getContext("2d"); console.log("MODE", "{kind}-{mode}",ctx.globalCompositeOperation); {operation} ctx.fillStyle={style};ctx.fillRect(0,0,70,70); }} }}''')
  cells.append((kind,mode,50+i*90,50))
 qml=Path('.tmp/deep-boundary/composite.qml');qml.write_text(f'import QtQuick\nRectangle {{ id:root; width:380;height:110;color:"{background}";property color tint:Qt.rgba({r}/255,{g}/255,{b}/255,{alpha});'+''.join(items)+'}')
 view=QQuickView();view.setSource(QUrl.fromLocalFile(str(qml.resolve())));view.show();QTest.qWait(500);im=view.grabWindow();im.save(str(out/f'{theme}-composition.png'))
 for kind,mode,x,y in cells:
  c=im.pixelColor(x,y);rows.append({'theme':theme,'style':kind,'mode':mode,'rgb':[c.red(),c.green(),c.blue()]})
 view.close()
(out/'composition.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
