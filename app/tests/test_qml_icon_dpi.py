"""Exercise offscreen rasterization in a fresh Qt process at each screen DPR."""
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize('scale', ['1', '1.5', '2'])
@pytest.mark.parametrize('highdpi', ['0', '1'])
def test_icon_visible_at_screen_dpr(tmp_path, scale, highdpi):
    qml = Path(__file__).resolve().parents[1] / 'src' / 'qml'
    script = '''
import sys
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow
from PySide6.QtTest import QTest
app = QGuiApplication([])
engine = QQmlApplicationEngine()
engine.loadData(('import QtQuick\\nimport QtQuick.Window\\nimport "' + sys.argv[1] + '"\\n'
 'Window { visible: true; width: 60; height: 100; color: "#191919";'
 'Icon { x:18; y:60; size:20; name:IconData.users; color:"#71717a" } }').encode(), QUrl.fromLocalFile(sys.argv[2] + '.qml'))
assert engine.rootObjects()
w = engine.rootObjects()[0]
QTest.qWait(300)
im = w.grabWindow(); d = w.devicePixelRatio()
points = [(x,y) for x in range(round(18*d),round(38*d))
          for y in range(round(60*d),round(80*d)) if im.pixelColor(x,y).red()>70]
assert points, 'Icon disappeared at DPR=' + str(d)
assert max(y for x,y in points)-min(y for x,y in points)>14*d, 'Icon was clipped'
assert im.save(sys.argv[2])
'''
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software',
               QT_SCALE_FACTOR=scale, QT_ENABLE_HIGHDPI_SCALING=highdpi,
               AI_UPPER_HOME=str(tmp_path / 'home'))
    result = subprocess.run([sys.executable, '-c', script, qml.as_uri(), str(tmp_path/'icon.png')],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
