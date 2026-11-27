"""Git 面板的最小真实实现（deva GitWidget.tsx / git:* 通道子集）。"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _run(root: str, args: list[str], timeout: int = 20) -> tuple[int, str, str]:
    try:
        p = subprocess.run(["git", "-C", str(root)] + args, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)


def status(root: str) -> dict[str, Any]:
    root = str(Path(root).resolve())
    code, out, err = _run(root, ["status", "--porcelain=v1", "-z", "--branch"])
    if code != 0:
        return {"ok": False, "error": err.strip() or "git status failed"}
    branch = ""
    entries = []
    fields = out.split("\x00")
    skip = False
    for i, field in enumerate(fields):
        if not field:
            continue
        if field.startswith("## "):
            branch = field[3:].split("...")[0].strip()
            continue
        if len(field) < 3:
            continue
        code_txt, path = field[:2], field[3:]
        entries.append({"path": path, "index": code_txt[0], "worktree": code_txt[1]})
    return {"ok": True, "root": root, "branch": branch, "entries": entries,
            "dirty": len(entries) > 0}


def diff(root: str, path: str = "") -> dict[str, Any]:
    args = ["diff", "--"] + ([path] if path else [])
    code, out, err = _run(root, args)
    return {"ok": code == 0, "text": out if code == 0 else (err.strip() or "git diff failed")}


def stage(root: str, paths: Any) -> dict[str, Any]:
    code, _, err = _run(root, ["add", "--"] + [str(p) for p in (paths or [])])
    return {"ok": code == 0, "error": err.strip()}


def unstage(root: str, paths: Any) -> dict[str, Any]:
    code, _, err = _run(root, ["restore", "--staged", "--"] + [str(p) for p in (paths or [])])
    return {"ok": code == 0, "error": err.strip()}


def commit(root: str, message: str) -> dict[str, Any]:
    if not str(message or "").strip():
        return {"ok": False, "error": "commit message is empty"}
    code, _, err = _run(root, ["commit", "-m", str(message)], timeout=60)
    return {"ok": code == 0, "error": err.strip()}


def branches(root: str) -> dict[str, Any]:
    code, out, err = _run(root, ["branch", "--format=%(refname:short)"])
    return {"ok": code == 0, "branches": out.splitlines() if code == 0 else [], "error": err.strip()}


def checkout(root: str, ref: str) -> dict[str, Any]:
    code, _, err = _run(root, ["checkout", str(ref)], timeout=60)
    return {"ok": code == 0, "error": err.strip()}


def create_branch(root: str, name: str, checkout_it: bool = True) -> dict[str, Any]:
    args = ["checkout", "-b", str(name)] if checkout_it else ["branch", str(name)]
    code, _, err = _run(root, args)
    return {"ok": code == 0, "error": err.strip()}


def log(root: str, depth: int = 30) -> dict[str, Any]:
    code, out, err = _run(root, ["log", "--oneline", "-n", str(int(depth))])
    return {"ok": code == 0, "commits": out.splitlines() if code == 0 else [], "error": err.strip()}


__all__ = ["branches", "checkout", "commit", "create_branch", "diff", "log", "stage", "status", "unstage"]
