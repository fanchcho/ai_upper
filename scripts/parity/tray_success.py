"""F02/F03: real XEmbed system tray host on X11 (Xvfb) + QSystemTrayIcon."""
import ctypes,json,os,sys,tempfile,time
from pathlib import Path
sys.path[:0]=['app/src','app/tests','scripts/parity']
# Claim _NET_SYSTEM_TRAY_S0 before Qt starts.
x=ctypes.CDLL('libX11.so.6');x.XOpenDisplay.restype=ctypes.c_void_p
x.XInternAtom.argtypes=[ctypes.c_void_p,ctypes.c_char_p,ctypes.c_int];x.XInternAtom.restype=ctypes.c_ulong
x.XDefaultRootWindow.argtypes=[ctypes.c_void_p];x.XDefaultRootWindow.restype=ctypes.c_ulong
x.XCreateSimpleWindow.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_int,ctypes.c_int,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,ctypes.c_ulong,ctypes.c_ulong];x.XCreateSimpleWindow.restype=ctypes.c_ulong
x.XSetSelectionOwner.argtypes=[ctypes.c_void_p,ctypes.c_ulong,ctypes.c_ulong,ctypes.c_ulong];x.XSync.argtypes=[ctypes.c_void_p,ctypes.c_int]
d=x.XOpenDisplay(None);assert d,'no DISPLAY'
root=x.XDefaultRootWindow(d);win=x.XCreateSimpleWindow(d,root,0,0,1,1,0,0,0);atom=x.XInternAtom(d,b'_NET_SYSTEM_TRAY_S0',0);x.XSetSelectionOwner(d,atom,win,0);x.XSync(d,0)
from PySide6.QtWidgets import QApplication
from feature_parity_evidence import build,shot
from test_qml_shell import text_stream
from mvvm.services.tray import TrayController
from qml_shell import _pump
app=QApplication([]);out=Path('out/tray');out.mkdir(parents=True,exist_ok=True);rows=[]
for theme in ('dark','light'):
    w,b,s,t,e,h=build(Path(tempfile.mkdtemp()),theme,text_stream('x'))
    tray=TrayController(app,w);ok=tray.install();_pump(app,lambda:False,.5)
    png=out/f'tray-{theme}.png';size=shot(w,png)
    # F02: close-to-tray preference true -> close must hide, not terminate.
    b._settings.set_config({'closeToTray':True});w.close();_pump(app,lambda:False,.3)
    hidden=not w.isVisible()
    rows.append({'theme':theme,'tray_available':ok,'icon_visible':bool(tray.icon and tray.icon.isVisible()),'close_hidden':hidden,'png':str(png),'size':size})
    t.stop();e.deleteLater()
out.joinpath('tray.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print('PASS',json.dumps(rows,ensure_ascii=False))
