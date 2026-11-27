"""C10 续做：同一生产 TextEdit 在更细亚像素相位下的墨迹起点。

只移动探针里的真实 TextEdit.y；不改生产 token、不加坐标补偿。
输出 out/extensions-rounding/phase-sweep.json。
"""
import os, sys, json
from pathlib import Path
sys.path[:0] = ['app/src', 'app/tests']
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QPointF
from pytest import MonkeyPatch
from test_qml_settings_provider import _build_window, _pump

app = QGuiApplication([])
home = Path('/tmp/ai-upper-phase-sweep'); home.mkdir(parents=True, exist_ok=True)
os.environ['AI_UPPER_HOME'] = str(home)
os.environ['DEVA_ASSETS_DIR'] = str(Path('app/assets').resolve())
w, b, s, v, t, e = _build_window(home, MonkeyPatch(), 'chat')
fixture = s.home
p = fixture / 'skills' / 'alpha'; p.mkdir(parents=True)
(p / 'SKILL.md').write_text('---\nname: alpha\n---\n# alpha\n\n' + ('Detailed instructions.\n\n' * 70))
from mvvm.services.plugin_identity import shared_store
shared_store().ensure_seeded()
s.set_config({'theme': 'light', 'locale': 'en', 'skills': {'enabled': {}, 'roles': {}}})
b._apply_theme(); w.setProperty('page', 'settings-extensions'); _pump(app, 1.2)
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
QTest.mouseClick(w, Qt.LeftButton, Qt.NoModifier, QPoint(580, 397)); _pump(app, 0.4)

def visual(item):
    yield item
    for child in item.childItems():
        yield from visual(child)

textitem = next(o for o in visual(w.contentItem()) if 'Detailed instructions.' in str(o.property('text') or '') and o.property('readOnly'))
base = textitem.y()

def ink_runs(img):
    bg = img.pixelColor(800, 500)
    runs = []
    for y in range(380, 640):
        hit = False
        for x in range(486, 636):
            c = img.pixelColor(x, y)
            if abs(c.red() - bg.red()) + abs(c.green() - bg.green()) + abs(c.blue() - bg.blue()) > 180:
                hit = True; break
        if hit:
            if not runs or y > runs[-1][1] + 1: runs.append([y, y])
            else: runs[-1][1] = y
    return runs

rows = []
for delta in [0, 0.25, 0.33, 0.5, 0.66, 0.75, 1.0]:
    textitem.setY(base + delta); _pump(app, 0.25)
    scene = textitem.mapToScene(QPointF(0, 0))
    runs = ink_runs(w.grabWindow())
    rows.append({'delta': delta, 'scene_y': round(scene.y(), 3), 'ink_starts': [r[0] for r in runs[:6]]})
textitem.setY(base)
(result := {'theme': 'light', 'base_y': base, 'rows': rows}).__class__
out = Path('out/extensions-rounding'); out.mkdir(parents=True, exist_ok=True)
(out / 'phase-sweep.json').write_text(json.dumps(result, indent=1))
print(json.dumps(result, indent=1))
b._ext_runtime.close() if hasattr(b, '_ext_runtime') else None
t.stop(); w.close(); e.deleteLater(); _pump(app, .1)
