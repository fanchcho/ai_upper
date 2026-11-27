import os,sys,json
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtCore import QUrl
from PySide6.QtTest import QTest
app=QGuiApplication([]);theme=sys.argv[1];dark=theme=='dark'
bg='#2a2a2e' if dark else '#ffffff';fg='124/255,124/255,240/255' if dark else '91/255,91/255,214/255'
items=[]
for i,(alpha,offset,size) in enumerate([(a,o,s) for a in ([.2,.16] if dark else [.12,.1]) for o in [0,.5] for s in [20,40]]):
 items.append(f'Rectangle {{ x: {20+i*65+offset}; y: 30; width: {size}; height: {size}; color: Qt.rgba({fg},{alpha}) }}')
p=Path('.tmp/extensions-rounding/flat.qml');p.write_text('import QtQuick\nRectangle { width: 600; height: 100; color: "'+bg+'"; '+ '\n'.join(items)+'}')
w=QQuickView();w.setSource(QUrl.fromLocalFile(str(p.resolve())));w.show();QTest.qWait(300);w.grabWindow().save('out/extensions-rounding/qt-'+theme+'-flat.png');w.close()
