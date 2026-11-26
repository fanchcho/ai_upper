import sys,os,runpy
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'app/src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
app=QApplication([])
QFontDatabase.addApplicationFont(str(Path.cwd()/'.tmp/theme-settings/NotoSansCJKsc-Regular.otf'))
runpy.run_path('scripts/deva_ui_shots.py',run_name='__main__')
