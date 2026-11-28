"""Real fcitx input on production Main.qml using isolated system Qt 6.8.2.
The host assembly fixture stays idle; no model response is claimed.
"""
import os,sys,json,subprocess
from pathlib import Path
sys.path.append(str(Path('.venv/lib/python3.13/site-packages').resolve()))
sys.path[:0]=['app/src','app/tests']
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtCore import QTimer,QPointF,qVersion
from pytest import MonkeyPatch
from test_qml_settings_provider import _build_window,_find_item,_pump
app=QGuiApplication([])
QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf')
w,b,s,v,t,e=_build_window(Path(os.environ['AI_UPPER_HOME']),MonkeyPatch(),'chat')
theme=os.environ['PROBE_THEME'];out=Path('docs/audit/deep-boundary')
s.set_config({'theme':theme});b._apply_theme();w.setTitle('IME_QML_REAL');_pump(app,.6)
field=_find_item(w.contentItem(),'inputField');assert field
preedits=[]
def changed():
 value=field.property('preeditText');preedits.append(value);print('REAL_QML_PREEDIT',repr(value),flush=True)
field.preeditTextChanged.connect(changed)
p=field.mapToScene(QPointF(45,25));g=w.mapToGlobal(p.toPoint())
def start():
 subprocess.Popen(['bash','-c',f'sleep 1; xdotool search --name IME_QML_REAL windowfocus --sync; xdotool mousemove {g.x()} {g.y()} click 1; sleep 1; fcitx5-remote -s pinyin; fcitx5-remote -o; fcitx5-remote; sleep 1; xdotool type --delay 250 nihao; sleep 2; xdotool key space'])
 QTimer.singleShot(5500,lambda:w.grabWindow().save(str(out/f'qml-ime-{theme}-preedit.png')))
 QTimer.singleShot(8500,finish)
def finish():
 text=field.property('text');print('REAL_QML_COMMIT',repr(text),flush=True)
 w.grabWindow().save(str(out/f'qml-ime-{theme}-commit.png'))
 path=out/f'qml-ime-{theme}-readback.json';path.write_text(json.dumps({'qt':qVersion(),'theme':theme,'preedits':preedits,'text':text,'focus':field.property('activeFocus')},ensure_ascii=False,indent=2))
 result=json.loads(path.read_text());assert result['text']=='你好' and any(result['preedits'])
 print('REAL_QML_CHINESE_READBACK_OK',flush=True)
 t.stop();w.close();e.deleteLater();app.quit()
QTimer.singleShot(600,start);app.exec()
