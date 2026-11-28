"""Instrument the production entry point; real fcitx keyboard, no fake host/model."""
import os,sys,json,subprocess
from pathlib import Path
sys.path.append(str(Path('.venv/lib/python3.13/site-packages').resolve()))
sys.path.insert(0,str(Path('app/src').resolve()))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from PySide6.QtCore import QTimer,qVersion
import qml_shell
from local_model_fixture import start
fixture=start()
app=QApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf')
out=Path(os.environ.get('PARITY_OUTPUT_DIR','docs/audit/next-boundary'));out.mkdir(parents=True,exist_ok=True)
theme=os.environ['PROBE_THEME'];events=[];captured=[];preedit_capture=[]
def find(o):
 if o.objectName()=='inputField':return o
 for c in o.childItems():
  r=find(c)
  if r:return r
original=qml_shell._start_ticker
result=1

def ticker(b):
 timer=original(b);w=b._window
 b._settings.set_config({'models':{'activeModelId':'local:fixture','providers':[{'id':'local','adapter':'openai','apiHost':f'http://127.0.0.1:{fixture.server_port}/v1','enabled':True,'models':[{'id':'fixture','enabled':True}]}]}})
 b._vault.set_secret('local','local-fixture-not-a-real-key')
 def start():
  b.setTheme(theme);b.newSession();w.setTitle('FULL_APP_IME')
  QTimer.singleShot(700,type_input)
 def type_input():
  field=find(w.contentItem())
  def snapshot():
   value=field.property('preeditText')
   if value and w.grabWindow().save(str(out/f'{theme}-preedit.png')):
    preedit_capture.append(value);print('REAL_PREEDIT_SCREENSHOT',repr(value),flush=True)
  def preedit_changed():
   value=field.property('preeditText');events.append(value)
   if value=='ni hao':QTimer.singleShot(150,snapshot)
  field.preeditTextChanged.connect(preedit_changed)
  subprocess.Popen(['bash','-c','sleep 1; xdotool search --name Weston windowfocus --sync; xdotool mousemove 700 705 click 1; sleep 1; fcitx5-remote -s pinyin; fcitx5-remote -o; sleep 1; xdotool type --delay 250 nihao; sleep 2; xdotool key space'])
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
  w.grabWindow().save(str(out/f'{theme}-roundtrip.png'))
  from mvvm.services.chat_session_store import ChatSessionStore
  store=ChatSessionStore(Path(os.environ['AI_UPPER_HOME']));session=store.load_session(b._active)
  messages=[{'role':m.role,'text':m.text()} for m in session.messages]
  row={'committedText':captured[0],'qt':qVersion(),'python':sys.executable,'preedit':events,'preeditScreenshot':preedit_capture,'storedTitle':session.title,'messages':messages,'sessionId':b._active,'path':str(store.session_path(b._active))}
  (out/f'{theme}-session.json').write_bytes(store.session_path(b._active).read_bytes())
  (out/f'{theme}-maps.log').write_text(Path('/proc/self/maps').read_text())
  (out/f'{theme}-readback.json').write_text(json.dumps(row,ensure_ascii=False,indent=2))
  ok=bool(preedit_capture) and any(m['role']=='user' and '你好' in m['text'] for m in messages) and any(m['role']=='assistant' and '本地 fixture' in m['text'] for m in messages);print('REAL_HTTP_MESSAGE_READBACK',ok,json.dumps(row,ensure_ascii=False),flush=True)
  result=0 if ok else 1;app.exit(result)
 QTimer.singleShot(700,start);return timer
qml_shell._start_ticker=ticker
QTimer.singleShot(25000,lambda:app.exit(2))
code=qml_shell.run(False);sys.exit(code or result)
