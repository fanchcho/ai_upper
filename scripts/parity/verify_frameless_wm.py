"""Exercise an already running QML window through X11 input; requires xdotool/xprop."""
import json
import subprocess
import sys
import time
from pathlib import Path

from PySide6.QtGui import QGuiApplication

wid, output = sys.argv[1], Path(sys.argv[2])
app = QGuiApplication([])


def run(*args):
    result = subprocess.run(args, text=True, capture_output=True)
    print('$', *args, '\n', result.stdout, result.stderr, 'rc=', result.returncode, flush=True)
    result.check_returncode()
    return result.stdout


def geometry():
    values = run('xdotool', 'getwindowgeometry', '--shell', wid)
    return {k: int(v) for k, v in (line.split('=') for line in values.splitlines())}


def click(x, y):
    run('xdotool', 'mousemove', '--window', wid, str(x), str(y))
    time.sleep(0.2)
    run('xdotool', 'getmouselocation', '--shell')
    run('xdotool', 'click', '1')
    time.sleep(0.5)


def drag(x, y, dx, dy):
    run('xdotool', 'mousemove', '--window', wid, str(x), str(y), 'mousedown', '1')
    time.sleep(0.2)
    run('xdotool', 'mousemove_relative', '--', str(dx), str(dy))
    time.sleep(0.3)
    run('xdotool', 'mouseup', '1')
    time.sleep(0.5)


run('xdotool', 'windowactivate', '--sync', wid)
time.sleep(0.5)
assert '= 0, 0, 0, 0' in run('xprop', '-id', wid, '_NET_FRAME_EXTENTS')
run('xprop', '-id', wid, '_MOTIF_WM_HINTS')
run('xwininfo', '-id', wid, '-frame')
assert app.primaryScreen().grabWindow(0).save(str(output / 'after-desktop.png'))
initial = geometry()
click(1200, 20)
assert 'Iconic' in run('xprop', '-id', wid, 'WM_STATE')
run('xdotool', 'windowmap', wid, 'windowactivate', '--sync', wid)
time.sleep(0.5)
assert 'Normal' in run('xprop', '-id', wid, 'WM_STATE')
drag(700, 15, 70, 50)
moved = geometry()
assert (moved['X'] - initial['X'], moved['Y'] - initial['Y']) == (70, 50)
drag(1278, 818, 90, 60)
resized = geometry()
assert (resized['WIDTH'], resized['HEIGHT']) == (1370, 880)
click(resized['WIDTH'] - 48, 20)
assert '_NET_WM_STATE_MAXIMIZED_HORZ' in run('xprop', '-id', wid, '_NET_WM_STATE')
maximized = geometry()
click(maximized['WIDTH'] - 48, 20)
assert '_NET_WM_STATE_MAXIMIZED_HORZ' not in run('xprop', '-id', wid, '_NET_WM_STATE')
restored = geometry()
assert (restored['WIDTH'], restored['HEIGHT']) == (1370, 880)
click(restored['WIDTH'] - 16, 20)
# Closed clients disappear from the WM client list (no BadWindow command required).
clients = run('xprop', '-root', '_NET_CLIENT_LIST')
assert hex(int(wid)) not in clients
(output / 'wm-results.json').write_text(json.dumps(dict(initial=initial, moved=moved, resized=resized,
    restored=restored, minimize=True, maximize=True, close=True), indent=2))
print('PASS: minimize/restore, move, resize, maximize/restore, close')
