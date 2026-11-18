"""同口径的「改动前」：把旧版表格实现从 git 取出，在进程内换回 ``_Renderer``。

用法：设置 ``AI_UPPER_PROBE_OLD_TABLE=<git rev>``，探针在 import 之后调用
``apply(mdoc)``。换成旧实现只发生在当前进程，不改源码、不影响其它测量。

旧实现 = ``insertTable(1, n)`` + 逐行 ``appendRows(1)``，再整表
``_apply_cell_borders`` 补一遍边框。新版行数/列数一致、单元格属性逐项相同
（见 ``out/render-opt2/REPORT.md`` 的保真矩阵），所以两者可以互相替换做 A/B。
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(rev: str):
    src = subprocess.run(
        ["git", "-C", str(ROOT), "show", "%s:app/src/markdown/document.py" % rev],
        capture_output=True, text=True, check=True,
    ).stdout
    path = Path(tempfile.mkdtemp(prefix="old-doc-")) / "document_old.py"
    path.write_text(src)
    spec = importlib.util.spec_from_file_location("document_old", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["document_old"] = module
    spec.loader.exec_module(module)
    return module


def apply(mdoc, rev: str) -> None:
    old = _load(rev)
    mdoc._Renderer._table = old._Renderer._table
    mdoc._Renderer._table_row = old._Renderer._table_row
    mdoc._Renderer._apply_cell_borders = old._Renderer._apply_cell_borders
