"""Build commands consume the same catalogue as the desktop application."""
import sys
from pathlib import Path

_source = str(Path(__file__).resolve().parents[2] / 'app' / 'src')
if _source not in sys.path:
    sys.path.insert(0, _source)
from locale_runtime import tr, selected_locale, configure_cli
