import sys,json,uuid
from pathlib import Path
sys.path[:0]=['app/src','app/tests','scripts/parity']
from feature_parity_evidence import build,shot
from test_qml_shell import text_stream
from qml_shell import _pump
from PySide6.QtGui import QGuiApplication,QFontDatabase
from PySide6.QtCore import Qt
app=QGuiApplication([]);QFontDatabase.addApplicationFont('.tmp/theme-settings/NotoSansCJKsc-Regular.otf');rows=[]
for theme in ['dark','light']:
 w,b,s,t,e,h=build(Path('/tmp/ai-upper-nonmac-'+uuid.uuid4().hex),theme,text_stream('unused'))
 assert sys.platform!='darwin' and w.property('macChrome') is False
 assert w.flags() & Qt.FramelessWindowHint
 assert not w.flags() & Qt.ExpandedClientAreaHint
 assert not w.flags() & Qt.NoTitleBarBackgroundHint
 rows.append({'theme':theme,'platform':sys.platform,'macChrome':w.property('macChrome'),'flags':int(w.flags()),'home':str(h)})
 shot(w,Path('docs/audit/parity-close')/f'nonmac-{theme}.png');t.stop();w.close();e.deleteLater();_pump(app,lambda:False,.1)
Path('docs/audit/parity-close/nonmac.json').write_text(json.dumps(rows,indent=2));print('PASS Linux real QML flags; macOS success remains unverified')
