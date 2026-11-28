"""Instrument the production entry point; real fcitx keyboard, no fake host/model."""
import os,sys,json,subprocess
from pathlib import Path
sys.path.append(str(Path('.venv/lib/python3.13/site-packages').resolve()))
sys.path.insert(0,str(Path('app/src').resolve()))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import QTimer,qVersion
import qml_shell
app=QApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf')
out=Path('docs/audit/full-ime');theme=os.environ['PROBE_THEME'];events=[];captured=[]
def find(o):
 if o.objectName()=='inputField':return o
 for c in o.childItems():
  r=find(c)
  if r:return r
original=qml_shell._start_ticker
result=1

def ticker(b):
 timer=original(b);w=b._window
 def start():
  b.setTheme(theme);b.newSession();w.setTitle('FULL_APP_IME')
  QTimer.singleShot(700,type_input)
 def type_input():
  field=find(w.contentItem());field.preeditTextChanged.connect(lambda:events.append(field.property('preeditText')))
  subprocess.Popen(['bash','-c','sleep 1; xdotool search --name FULL_APP_IME windowfocus --sync; xdotool mousemove 700 705 click 1; sleep 1; fcitx5-remote -s pinyin; fcitx5-remote -o; sleep 1; xdotool type --delay 250 nihao; sleep 2; xdotool key space'])
  QTimer.singleShot(5500,lambda:w.grabWindow().save(str(out/f'{theme}-preedit.png')))
  QTimer.singleShot(8000,commit)
 def commit():
  field=find(w.contentItem());text=field.property('text');print('REAL_APP_COMMIT',repr(text),events,flush=True)
  w.grabWindow().save(str(out/f'{theme}-commit.png'))
  if text!='你好' or not any(events):app.exit(1);return
  captured.append(text)
  assert b.renameSession(b._active,text)
  subprocess.Popen(['xdotool','key','Return'])
  QTimer.singleShot(1800,readback)
 def readback():
  global result
  from mvvm.services.chat_session_store import ChatSessionStore
  store=ChatSessionStore(Path(os.environ['AI_UPPER_HOME']));session=store.load_session(b._active)
  messages=[{'role':m.role,'text':m.text()} for m in session.messages]
  row={'committedText':captured[0],'qt':qVersion(),'preedit':events,'storedTitle':session.title,'messages':messages,'sessionId':b._active,'path':str(store.session_path(b._active))}
  (out/f'{theme}-readback.json').write_text(json.dumps(row,ensure_ascii=False,indent=2))
  ok=session.title==captured[0]=='你好';print('REAL_APP_TITLE_READBACK',ok,json.dumps(row,ensure_ascii=False),flush=True)
  result=0 if ok else 1;app.exit(result)
 QTimer.singleShot(700,start);return timer
qml_shell._start_ticker=ticker
QTimer.singleShot(25000,lambda:app.exit(2))
code=qml_shell.run(False);sys.exit(code or result)
