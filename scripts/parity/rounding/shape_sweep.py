"""C10 续做：同一 rgba token 在不同图元尺寸/相位下的中心像素矩阵。"""
import os, sys, json
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtCore import QUrl
from PySide6.QtTest import QTest

app = QGuiApplication([])
out = Path('out/extensions-rounding'); out.mkdir(parents=True, exist_ok=True)
result = {}
for theme in ('dark', 'light'):
    dark = theme == 'dark'
    bg = '#2a2a2e' if dark else '#ffffff'
    fg = '124/255,124/255,240/255' if dark else '91/255,91/255,214/255'
    alphas = (.2, .16) if dark else (.12, .1)
    items = []
    cells = []
    idx = 0
    for alpha in alphas:
      for shape in ('rect', 'circle'):
        for size in (18, 20, 22, 40):
            for offset in (0, .25, .5):
                x = 20 + idx * 60
                if shape == 'rect':
                    items.append(f'Rectangle {{ x: {x}+{offset}; y: 20; width: {size}; height: {size}; color: Qt.rgba({fg},{alpha}) }}')
                else:
                    items.append(f'Rectangle {{ x: {x}+{offset}; y: 20; width: {size}; height: {size}; radius: {size/2}; color: Qt.rgba({fg},{alpha}) }}')
                cells.append({'alpha': alpha, 'shape': shape, 'size': size, 'offset': offset, 'sample_x': x + size // 2, 'sample_y': 20 + size // 2})
                idx += 1
    qml = Path('.tmp/extensions-rounding/shape-sweep.qml')
    qml.parent.mkdir(parents=True, exist_ok=True)
    qml.write_text('import QtQuick\nRectangle { width: %d; height: 100; color: "%s"; %s }' % (20 + idx * 60 + 40, bg, '\n'.join(items)))
    view = QQuickView(); view.setSource(QUrl.fromLocalFile(str(qml.resolve()))); view.show(); QTest.qWait(300)
    img = view.grabWindow()
    rows = []
    for c in cells:
        col = img.pixelColor(c['sample_x'], c['sample_y'])
        rows.append({**{k: c[k] for k in ('alpha', 'shape', 'size', 'offset')}, 'rgb': [col.red(), col.green(), col.blue()]})
    view.close()
    result[theme] = rows
(out / 'shape-sweep.json').write_text(json.dumps(result, indent=1))
print(json.dumps(result, indent=1))
