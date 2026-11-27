import json,os,sys,uuid
from pathlib import Path
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot,find_item
from test_qml_shell import text_stream
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QUrl,QObject,QPointF,Qt
from PySide6.QtQml import QQmlComponent
from PySide6.QtTest import QTest
app=QGuiApplication([]);result=[]
for theme in ['dark','light']:
 w,b,s,t,e,h=build(Path('/tmp/ai-upper-edge-'+uuid.uuid4().hex),theme,text_stream('ok'))
 c=QQmlComponent(e,QUrl.fromLocalFile(str(Path('app/src/qml/ExtensionDetail.qml').resolve())))
 detail=c.create();assert detail,c.errors();detail.setParentItem(w.contentItem());detail.setWidth(550);detail.setHeight(620)
 detail.setX(650);detail.setZ(999)
 detail.setProperty('item',{'kind':'skill','id':'edge-fixture','name':'Edge','personas':[{'id':str(i),'name':'Role '+str(i)} for i in range(30)],'roles':[]})
 for y in [20,490]:
  detail.setY(y);_pump(app,lambda:False,.2)
  trigger=find_item(detail,'extensionRolesTrigger');pt=trigger.mapToScene(QPointF(trigger.width()/2,trigger.height()/2))
  QTest.mouseClick(w,Qt.LeftButton,Qt.NoModifier,pt.toPoint());_pump(app,lambda:False,.2)
  popup=detail.findChild(QObject,'extensionRolesPopup');assert popup.property('opened')
  down=popup.property('opensDown');assert down==(y==20)
  point=trigger.mapToScene(QPointF(0,0));top=point.y()+popup.property('y')
  assert top>=12 and top+popup.property('height')<=w.height()-12
  shot(w,Path('out/final-port')/f'menu-{theme}-'+Path('x')) if False else None
  shot(w,Path('out/final-port')/f'menu-{theme}-{"down" if down else "up"}.png')
  result.append({'theme':theme,'direction':'down' if down else 'up','top':top,'height':popup.property('height'),'window':w.height()})
  QTest.keyClick(w,Qt.Key_Escape);_pump(app,lambda:False,.2)
 detail.deleteLater();t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.1)
Path('out/final-port/menu-edges.json').write_text(json.dumps(result,indent=2));print(result)
