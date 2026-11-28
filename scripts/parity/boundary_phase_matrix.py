"""Probe-only phase/shape/size/blur matrix; no production token changes."""
from pathlib import Path
import json
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtQuick import QQuickView
from PySide6.QtCore import QUrl
from PySide6.QtTest import QTest
from PySide6.QtGui import QImage
def measure(a,b,roi):
 vals=[[abs(a.pixelColor(x,y).getRgb()[c]-b.pixelColor(x,y).getRgb()[c]) for c in range(3)] for y in range(roi[1],roi[3]) for x in range(roi[0],roi[2])]
 return {"changedPixels":sum(any(v) for v in vals),"meanAbsRGB":[sum(v[c] for v in vals)/len(vals) for c in range(3)],"maxRGB":[max(v[c] for v in vals) for c in range(3)]}
app=QGuiApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf');out=Path('docs/audit/remaining-boundaries');tmp=Path('.tmp/remaining-boundaries');rows=[]
for theme in ['dark','light']:
 dark=theme=='dark';bg='#2a2a2e' if dark else '#ffffff';fg='#eeeeee' if dark else '#222222'
 for phase in [0,.5]:
  items=[];cells=[]
  for i,(shape,size,blur) in enumerate((s,z,b) for s in ['rect','circle'] for z in [20,40] for b in [20,40]):
   x=60+(i%4)*190;y=150+(i//4)*230
   items.append(f'Prod.SoftShadow {{ target:c{i};blur:{blur};offsetY:6 }} Rectangle {{id:c{i};x:{x+phase};y:{y+phase};width:{size};height:{size};radius:{size/2 if shape=="circle" else 0};color:"{fg}"}}')
   cells.append({'shape':shape,'size':size,'blur':blur,'x':x,'y':y})
  qml=tmp/'matrix.qml';qml.write_text('import QtQuick\nimport "../../app/src/qml" as Prod\nRectangle {width:800;height:600;color:"'+bg+'";Component.onCompleted:Prod.Theme.dark='+str(dark).lower()+f'; TextEdit {{x:40;y:{20+phase};width:700;height:80;readOnly:true;text:"Detailed instructions.\\n正文相位实验";font.pixelSize:14;color:"{fg}"}}'+''.join(items)+'}')
  v=QQuickView();v.setSource(QUrl.fromLocalFile(str(qml.resolve())));v.show();QTest.qWait(400);v.grabWindow().save(str(out/f'{theme}-matrix-{phase}.png'));v.close()
 a=QImage(str(out/f'{theme}-matrix-0.png'));b=QImage(str(out/f'{theme}-matrix-0.5.png'))
 for c in cells:
  x,y=c['x'],c['y'];roi=(x-45,y-45,x+85,y+100);rows.append({'theme':theme,**c,**measure(a,b,roi),'tail0':a.pixelColor(x+c['size']//2,y+c['size']+8).getRgb()[:3],'tailHalf':b.pixelColor(x+c['size']//2,y+c['size']+8).getRgb()[:3]})
 rows.append({'theme':theme,'shape':'bodyText',**measure(a,b,(20,10,740,100))})
(out/'phase-matrix.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2))
