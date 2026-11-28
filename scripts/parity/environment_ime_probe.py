import json,subprocess
from PySide6.QtWidgets import QApplication,QLineEdit
from PySide6.QtCore import QTimer,qVersion
class Edit(QLineEdit):
 def inputMethodEvent(self,e):
  print('REAL_INPUT_METHOD',repr(e.preeditString()),repr(e.commitString()),flush=True);super().inputMethodEvent(e)
a=QApplication([]);w=Edit();w.setWindowTitle('IME_ISOLATED');w.show();w.activateWindow();w.setFocus()
def run():
 subprocess.run(['.tmp/wm/usr/bin/xdotool','search','--name','IME_ISOLATED','windowfocus','--sync','key','ctrl+space'])
 subprocess.run(['.tmp/wm/usr/bin/xdotool','type','nihao'])
 QTimer.singleShot(1200,finish)
def finish():
 print('QT',qVersion(),'FINAL',repr(w.text()),flush=True);a.quit()
QTimer.singleShot(1500,run);a.exec()
