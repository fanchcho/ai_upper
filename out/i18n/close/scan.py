"""Compatibility entry for the reviewed, fail-closed Python/QML audit."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parents[1]/'final/audit.py'),run_name='__main__')
