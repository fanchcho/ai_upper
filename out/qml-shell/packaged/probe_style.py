"""问真实 Qt：不设 QT_QUICK_CONTROLS_STYLE 时，它到底挑哪个样式模块。"""
import sys
from PySide6 import QtGui
from PySide6.QtQuickControls2 import QQuickStyle

app = QtGui.QGuiApplication([])
print("QQuickStyle.name() =", QQuickStyle.name())
print("platform =", app.platformName())
