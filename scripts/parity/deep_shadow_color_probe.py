"""Compare production shadow with a CSS-style conversion only in a copied probe."""
from pathlib import Path
import json
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtCore import QUrl
from PySide6.QtTest import QTest
app=QGuiApplication([]);temp=Path('.tmp/deep-boundary');out=Path('docs/audit/deep-boundary/pixel')
source=Path('app/src/qml/SoftShadow.qml').read_text()
source=source.replace('import QtQuick','import QtQuick\nimport "../../app/src/qml"')
source=source.replace('ctx.shadowColor = root.color', '''ctx.shadowColor = "rgba(" + Math.round(root.color.r*255) + "," + Math.round(root.color.g*255) + "," + Math.round(root.color.b*255) + "," + root.color.a + ")"''')
(temp/'ShadowCss.qml').write_text(source)
results=[]
for theme in ['dark','light']:
 dark=theme=='dark';bg='#0e0e10' if dark else '#8f8f8f';card='#2a2a2e' if dark else '#ffffff'
 for kind in ['production','css']:
  typ='Prod.SoftShadow' if kind=='production' else 'ShadowCss'
  text=f'''import QtQuick
import "../../app/src/qml" as Prod
Rectangle {{ width:640;height:450;color:"{bg}"; Component.onCompleted:Prod.Theme.dark={str(dark).lower()}
{typ} {{ target:card }}
Rectangle {{ id:card;x:100;y:50;width:440;height:320;radius:12;color:"{card}";border.width:1;border.color:"#aaaaaa" }} }}'''
  qml=temp/'shadow-root.qml';qml.write_text(text);v=QQuickView();v.setSource(QUrl.fromLocalFile(str(qml.resolve())));v.show();QTest.qWait(500);im=v.grabWindow();im.save(str(out/f'{theme}-shadow-color-{kind}.png'))
  results.append({'theme':theme,'kind':kind,'scan':[(y,im.pixelColor(320,y).getRgb()[:3]) for y in range(370,411)]});v.close()
(out/'shadow-color.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))
