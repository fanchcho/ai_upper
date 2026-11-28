import json,subprocess,os
from pathlib import Path
from PySide6.QtGui import QPalette,QColor,QFontDatabase,QFont
events=[]
theme=os.environ.get("PROBE_THEME","light")
out=Path("docs/audit/deep-boundary")
from PySide6.QtWidgets import QApplication,QLineEdit
from PySide6.QtCore import QTimer,qVersion
class Edit(QLineEdit):
 def inputMethodEvent(self,e):
  events.append({'preedit':e.preeditString(),'commit':e.commitString()});print('REAL_INPUT_METHOD',repr(e.preeditString()),repr(e.commitString()),flush=True);super().inputMethodEvent(e)
a=QApplication([])
font_id=QFontDatabase.addApplicationFont(".tmp/theme-settings/NotoSansCJKsc-Regular.otf")
assert font_id >= 0
a.setFont(QFont(QFontDatabase.applicationFontFamilies(font_id)[0],18))
palette=a.palette();palette.setColor(QPalette.Base,QColor('#242424' if theme=='dark' else '#ffffff'));palette.setColor(QPalette.Text,QColor('#ffffff' if theme=='dark' else '#000000'));a.setPalette(palette)
w=Edit();w.resize(460,80);w.setWindowTitle('IME_ISOLATED');w.show();w.activateWindow();w.setFocus()
def run():
 subprocess.Popen(['bash','-c',"sleep 1; .tmp/wm/usr/bin/xdotool search --name IME_ISOLATED windowfocus --sync; sleep 1; .tmp/wm/usr/bin/xdotool getwindowfocus getwindowname; fcitx5-remote -s pinyin; fcitx5-remote -o; fcitx5-remote; sleep 1; .tmp/wm/usr/bin/xdotool type --delay 250 nihao; sleep 2; .tmp/wm/usr/bin/xdotool key space"])
 QTimer.singleShot(5500,lambda:w.grab().save(str(out/f'ime-{theme}-preedit.png')))
 QTimer.singleShot(8500,finish)
def finish():
 w.grab().save(str(out/f'ime-{theme}-commit.png'));print('QT',qVersion(),'FINAL',repr(w.text()),flush=True)
 (out/f'ime-{theme}-readback.json').write_text(json.dumps({'qt':qVersion(),'text':w.text(),'events':events},ensure_ascii=False,indent=2))
 result=json.loads((out/f'ime-{theme}-readback.json').read_text());assert result['text']=='你好' and any(e['preedit'] for e in result['events'])
 print('CHINESE_DISK_READBACK_OK',flush=True);a.quit()
QTimer.singleShot(1500,run);a.exec()
