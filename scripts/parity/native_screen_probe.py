import sys
from PySide6.QtGui import QGuiApplication
a=QGuiApplication([]);assert a.primaryScreen().grabWindow(0).save(sys.argv[1])
