import sys,os
from pathlib import Path
sys.path.insert(0,str(Path('app/src').resolve()))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
import qml_shell
app=QApplication([]);orig=qml_shell._start_ticker
def ticker(b):
 t=orig(b);b.setTheme(os.environ['PROBE_THEME'])
 def shot():
  im=b._window.grabWindow();print('WAYLAND_CAPTURE',im.size(),im.save('docs/audit/remaining-boundaries/wayland-'+os.environ['PROBE_THEME']+'.png'),flush=True);app.quit()
 QTimer.singleShot(3000,shot);return t
qml_shell._start_ticker=ticker
qml_shell.run(False)
