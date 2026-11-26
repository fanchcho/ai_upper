import sys,os,runpy
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'app/src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QPalette,QColor
app=QApplication([]);app.setStyle('Fusion')
QFontDatabase.addApplicationFont(str(Path.cwd()/'.tmp/theme-settings/NotoSansCJKsc-Regular.otf'))
p=QPalette()
for role,color in [('Window','#202022'),('WindowText','#e4e4e7'),('Base','#18181b'),('AlternateBase','#27272a'),('Text','#e4e4e7'),('PlaceholderText','#a1a1aa'),('Button','#27272a'),('ButtonText','#e4e4e7'),('Highlight','#5b5bd6'),('HighlightedText','#ffffff')]:p.setColor(getattr(QPalette.ColorRole,role),QColor(color))
app.setPalette(p)
runpy.run_path('scripts/deva_ui_shots.py',run_name='__main__')
