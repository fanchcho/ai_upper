"""Register the bundled emoji fallback without changing the UI text font."""
from utils.qt_compat import QtGui
from utils.paths import assets_root

_font_id = None


def ensure_emoji_font():
    global _font_id
    if _font_id is not None or QtGui.QGuiApplication.instance() is None:
        return
    _font_id = QtGui.QFontDatabase.addApplicationFont(str(assets_root() / "fonts/NotoColorEmoji.ttf"))
    if _font_id >= 0:
        for family in QtGui.QFontDatabase.applicationFontFamilies(_font_id):
            QtGui.QFontDatabase.addApplicationEmojiFontFamily(family)
    else:
        _font_id = None
