"""Bundled emoji fallback must provide glyphs, not the font's .notdef box."""
from pathlib import Path
import sys
import pytest


def test_bundled_emoji_glyphs(qapp, monkeypatch):
    from utils import emoji_font
    from utils.qt_compat import QtGui
    monkeypatch.setenv('DEVA_ASSETS_DIR', str(Path(__file__).parents[1] / 'assets'))
    emoji_font.ensure_emoji_font()
    expected_family = 'Apple Color Emoji' if sys.platform == 'darwin' else 'Noto Color Emoji'
    for char in ('🚀', '✅'):
        layout = QtGui.QTextLayout(char, QtGui.QFont('Noto Sans CJK SC', 14))
        layout.beginLayout()
        line = layout.createLine()
        line.setLineWidth(100)
        layout.endLayout()
        runs = layout.glyphRuns()
        assert runs
        assert all(0 not in run.glyphIndexes() for run in runs)
        assert any(run.rawFont().familyName() == expected_family for run in runs)


@pytest.fixture(scope='module')
def qapp():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])
