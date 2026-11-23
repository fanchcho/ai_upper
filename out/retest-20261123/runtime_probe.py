"""Observe the real headless capture path without modifying application state."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app/src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
import qml_shell as shell

observed = {}
original_bind = shell.ShellBridge.bind_window
original_path = shell._shot_path


def bind(bridge, window):
    observed.update(bridge=bridge, window=window)
    return original_bind(bridge, window)


def shot_path():
    window = observed["window"]
    bridge = observed["bridge"]
    result = {"page": window.property("page"), "active": bridge._active,
              "forced_hover_index": window.property("forceHoverRow")}
    for name in ("sessionList", "bodyScroll", "bodyView"):
        item = window.findChild(shell.QtCore.QObject, name)
        result[name] = {key: item.property(key) for key in
                        ("x", "y", "width", "height", "contentY", "contentHeight")}
    doc = bridge._body.document
    result["plain_text"] = doc.toPlainText()
    result["blocks"] = []
    block = doc.begin()
    while block.isValid():
        rect = doc.documentLayout().blockBoundingRect(block)
        result["blocks"].append({"text": block.text(), "y": rect.y(), "height": rect.height()})
        block = block.next()
    print("RUNTIME " + json.dumps(result, ensure_ascii=False), flush=True)
    return original_path()


shell.ShellBridge.bind_window = bind
shell._shot_path = shot_path
raise SystemExit(shell.run(headless=True))
