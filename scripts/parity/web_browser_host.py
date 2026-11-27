import sys,uuid,json
from pathlib import Path
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build
from test_qml_shell import text_stream
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QTimer
app=QGuiApplication([]);w,b,s,t,e,h=build(Path('/tmp/ai-upper-web-browser-'+uuid.uuid4().hex),'dark',text_stream('unused'))
api=b.botsService();url=api.webPairTicket();Path('.tmp/remaining-three/browser-url.json').write_text(json.dumps({'url':url,'home':str(h)}))
timer=QTimer();timer.setInterval(200);timer.timeout.connect(lambda:app.quit() if Path('.tmp/remaining-three/browser-done').exists() else None);timer.start();app.exec();api.close()
