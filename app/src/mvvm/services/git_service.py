"""Git 面板：deva `git:*` 25 个通道的 Python 对位（常用操作完整，远程写操作同 git 语义）。"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _run(root: str, args: list[str], timeout: int = 60) -> tuple[int, str, str]:
    try:
        p = subprocess.run(["git", "-C", str(root)] + args, capture_output=True, text=True,
                           timeout=timeout, env={**__import__("os").environ, "GIT_TERMINAL_PROMPT": "0"})
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)


def _remotes(root: str) -> list[str]:
    code, out, _ = _run(root, ["remote"])
    return out.splitlines() if code == 0 else []


def available() -> dict[str, Any]:
    code, out, err = _run(".", ["--version"])
    if code != 0:
        return {"available": False, "error": err.strip()}
    return {"available": True, "version": out.strip().replace("git version ", ""), "path": "git"}


def status(root: str) -> dict[str, Any]:
    root = str(Path(root).resolve())
    code, out, err = _run(root, ["status", "--porcelain=v1", "-z", "--branch", "--untracked-files=all"])
    if code != 0:
        return {"ok": False, "error": err.strip() or "git status failed", "isRepo": False}
    branch = ""; upstream = ""; ahead = behind = 0; entries = []
    for field in out.split("\x00"):
        if not field:
            continue
        if field.startswith("## "):
            head = field[3:]
            branch = head.split("...")[0].strip()
            if "..." in head:
                rest = head.split("...", 1)[1]
                upstream = rest.split(" ")[0]
                import re
                m = re.search(r"\[ahead (\d+)(?:, behind (\d+))?\]|\[behind (\d+)\]", rest)
                if m:
                    ahead = int(m.group(1) or 0); behind = int(m.group(2) or m.group(3) or 0)
            continue
        if len(field) < 3:
            continue
        code_txt, path = field[:2], field[3:]
        entries.append({"path": path, "index": code_txt[0], "worktree": code_txt[1],
                        "staged": code_txt[0] not in (" ", "?"), "untracked": code_txt == "??"})
    return {"ok": True, "root": root, "isRepo": True, "branch": branch, "upstream": upstream,
            "ahead": ahead, "behind": behind, "remotes": _remotes(root), "entries": entries,
            "dirty": len(entries) > 0}


def diff(root: str, path: str = "", staged: bool = False, untracked: bool = False) -> dict[str, Any]:
    if untracked:
        target = Path(root) / path
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return {"ok": False, "text": str(exc)}
        return {"ok": True, "text": text, "untracked": True}
    args = ["diff", "--no-color", "--no-ext-diff"]
    if staged:
        args.append("--cached")
    args += ["--", path] if path else []
    code, out, err = _run(root, args)
    return {"ok": code == 0, "text": out if code == 0 else (err.strip() or "git diff failed")}


def stage(root: str, paths: Any) -> dict[str, Any]:
    code, _, err = _run(root, ["add", "--"] + [str(p) for p in (paths or [])])
    return {"ok": code == 0, "error": err.strip()}


def unstage(root: str, paths: Any) -> dict[str, Any]:
    head = _run(root, ["rev-parse", "--verify", "HEAD"])
    args = ["reset", "-q", "HEAD", "--"] if head[0] == 0 else ["rm", "--cached", "-q", "--"]
    code, _, err = _run(root, args + [str(p) for p in (paths or [])])
    return {"ok": code == 0, "error": err.strip()}


def discard(root: str, tracked: Any, untracked: Any) -> dict[str, Any]:
    tracked = [str(p) for p in (tracked or [])]
    if tracked:
        code, _, err = _run(root, ["checkout", "HEAD", "--"] + tracked)
        if code != 0:
            return {"ok": False, "error": err.strip()}
    for path in untracked or []:
        try:
            target = (Path(root) / str(path)).resolve()
            if str(target).startswith(str(Path(root).resolve())) and target.is_file():
                target.unlink()
        except OSError:
            pass
    return {"ok": True}


def commit(root: str, message: str) -> dict[str, Any]:
    if not str(message or "").strip():
        return {"ok": False, "error": "commit message is empty", "reason": "empty"}
    code, _, err = _run(root, ["commit", "-m", str(message)], timeout=120)
    return {"ok": code == 0, "error": err.strip()}


def branches(root: str) -> dict[str, Any]:
    code, out, err = _run(root, ["for-each-ref", "--format=%(refname)%00%(HEAD)%00%(upstream:short)%00%(symref)",
                                 "refs/heads", "refs/remotes"])
    if code != 0:
        return {"ok": False, "branches": [], "error": err.strip()}
    remotes = sorted(_remotes(root), key=len, reverse=True)
    rows = []
    for line in out.splitlines():
        if not line.strip():
            continue
        ref, head, upstream, symref = (line.split("\x00") + ["", "", "", ""])[:4]
        if ref.startswith("refs/heads/"):
            rows.append({"name": ref[11:], "current": head == "*", "remote": None, "upstream": upstream or None})
        elif ref.startswith("refs/remotes/") and not symref:
            name = ref[13:]
            remote = next((r for r in remotes if name.startswith(r + "/")), name.split("/")[0])
            rows.append({"name": name, "current": False, "remote": remote, "upstream": None})
    return {"ok": True, "branches": rows}


def checkout(root: str, ref: str) -> dict[str, Any]:
    code, _, err = _run(root, ["checkout", str(ref)], timeout=120)
    return {"ok": code == 0, "error": err.strip(), "reason": "dirty" if "would be overwritten" in err else "error"}


def checkout_remote(root: str, ref: str) -> dict[str, Any]:
    code, _, err = _run(root, ["checkout", "--track", str(ref)], timeout=120)
    return {"ok": code == 0, "error": err.strip()}


def create_branch(root: str, name: str, checkout_it: bool = True) -> dict[str, Any]:
    if not str(name or "").strip():
        return {"ok": False, "error": "empty name"}
    code, _, err = _run(root, (["checkout", "-b", str(name)] if checkout_it else ["branch", str(name)]))
    return {"ok": code == 0, "error": err.strip()}


def delete_branch(root: str, name: str, force: bool = False) -> dict[str, Any]:
    code, _, err = _run(root, ["branch", "-D" if force else "-d", str(name)])
    return {"ok": code == 0, "error": err.strip(), "reason": "unmerged" if "not fully merged" in err else "error"}


def rename_branch(root: str, old: str, new: str) -> dict[str, Any]:
    code, _, err = _run(root, ["branch", "-m", str(old), str(new)])
    return {"ok": code == 0, "error": err.strip()}


def delete_remote_branch(root: str, remote: str, branch: str) -> dict[str, Any]:
    if remote not in _remotes(root):
        return {"ok": False, "error": "unknown remote"}
    code, _, err = _run(root, ["push", remote, "--delete", branch], timeout=120)
    return {"ok": code == 0, "error": err.strip()}


def merge(root: str, ref: str) -> dict[str, Any]:
    code, out, err = _run(root, ["merge", "--no-edit", str(ref)], timeout=120)
    return {"ok": code == 0, "error": (out + "\n" + err).strip(), "reason": "conflict" if code else ""}


def merge_abort(root: str) -> dict[str, Any]:
    code, _, err = _run(root, ["merge", "--abort"])
    return {"ok": code == 0, "error": err.strip()}


def log(root: str, depth: int = 30, page: int = 0) -> dict[str, Any]:
    count = max(1, min(500, int(depth)))
    skip = max(0, int(page)) * count
    fmt = "%H%x00%h%x00%an%x00%ae%x00%at%x00%s"
    code, out, err = _run(root, ["log", f"--format={fmt}", "-n", str(count), "--skip", str(skip)])
    rows = []
    if code == 0:
        for line in out.splitlines():
            bits = line.split("\x00")
            if len(bits) >= 6:
                rows.append({"oid": bits[0], "short": bits[1], "author": bits[2], "email": bits[3],
                             "timestamp": int(bits[4]) * 1000 if bits[4].isdigit() else 0, "subject": bits[5]})
    return {"ok": code == 0, "commits": rows, "page": int(page), "depth": count, "error": err.strip()}


def init(root: str) -> dict[str, Any]:
    code, _, err = _run(root, ["init"])
    return {"ok": code == 0, "error": err.strip()}


def fetch(root: str) -> dict[str, Any]:
    code, _, err = _run(root, ["fetch", "--prune"], timeout=180)
    return {"ok": code == 0, "error": err.strip()}


def pull(root: str) -> dict[str, Any]:
    code, _, err = _run(root, ["pull"], timeout=180)
    return {"ok": code == 0, "error": err.strip()}


def push(root: str, set_upstream: str | None = None) -> dict[str, Any]:
    args = ["push", "-u", "origin", str(set_upstream)] if set_upstream else ["push"]
    code, _, err = _run(root, args, timeout=180)
    return {"ok": code == 0, "error": err.strip()}


def remotes(root: str) -> dict[str, Any]:
    return {"ok": True, "remotes": _remotes(root)}


def add_remote(root: str, name: str, url: str) -> dict[str, Any]:
    code, _, err = _run(root, ["remote", "add", str(name), str(url)])
    return {"ok": code == 0, "error": err.strip()}


def remove_remote(root: str, name: str) -> dict[str, Any]:
    code, _, err = _run(root, ["remote", "remove", str(name)])
    return {"ok": code == 0, "error": err.strip()}


def set_remote(root: str, name: str, url: str) -> dict[str, Any]:
    code, _, err = _run(root, ["remote", "set-url", str(name), str(url)])
    return {"ok": code == 0, "error": err.strip()}


__all__ = ["add_remote", "available", "branches", "checkout", "checkout_remote", "commit", "create_branch",
           "delete_branch", "delete_remote_branch", "diff", "discard", "fetch", "init", "log", "merge",
           "merge_abort", "pull", "push", "remotes", "remove_remote", "rename_branch", "set_remote", "stage",
           "status", "unstage"]
