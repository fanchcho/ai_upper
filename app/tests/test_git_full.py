"""F85：Git 面板完整常用操作的真实临时仓库验证。"""
from __future__ import annotations
import subprocess
from pathlib import Path


def _git(repo, *args):
    return subprocess.run(["git", "-C", str(repo)] + list(args), check=True, capture_output=True, text=True).stdout


def test_full_git_operations(tmp_path):
    from mvvm.services import git_service as g

    repo = tmp_path / "repo"; repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    _git(repo, "config", "user.email", "t@example.com"); _git(repo, "config", "user.name", "T")
    (repo / "a.txt").write_text("one\n")
    assert g.stage(str(repo), ["a.txt"])["ok"]
    assert g.commit(str(repo), "initial")["ok"]

    (repo / "a.txt").write_text("two\n")
    st = g.status(str(repo))
    assert st["dirty"] and st["branch"] == "main"
    assert "two" in g.diff(str(repo), "a.txt")["text"]
    assert g.stage(str(repo), ["a.txt"])["ok"]
    assert "two" in g.diff(str(repo), "a.txt", staged=True)["text"]
    assert g.unstage(str(repo), ["a.txt"])["ok"]
    assert g.discard(str(repo), ["a.txt"], [])["ok"] and (repo / "a.txt").read_text() == "one\n"

    (repo / "new.txt").write_text("new\n")
    assert g.discard(str(repo), [], ["new.txt"])["ok"] and not (repo / "new.txt").exists()

    assert g.create_branch(str(repo), "feature", True)["ok"]
    _git(repo, "checkout", "main")
    assert g.rename_branch(str(repo), "feature", "feature2")["ok"]
    _git(repo, "checkout", "feature2")
    (repo / "b.txt").write_text("b\n"); _git(repo, "add", "b.txt"); _git(repo, "commit", "-m", "b")
    _git(repo, "checkout", "main")
    assert g.merge(str(repo), "feature2")["ok"]
    assert (repo / "b.txt").exists()
    assert g.delete_branch(str(repo), "feature2", True)["ok"]

    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    assert g.add_remote(str(repo), "origin", str(bare))["ok"]
    assert g.push(str(repo), "main")["ok"]
    assert "origin" in g.remotes(str(repo))["remotes"]
    assert g.fetch(str(repo))["ok"]
    assert g.set_remote(str(repo), "origin", str(bare))["ok"]
    assert g.delete_remote_branch(str(repo), "origin", "main")["ok"]
    assert g.remove_remote(str(repo), "origin")["ok"]
    assert "origin" not in g.remotes(str(repo))["remotes"]

    log = g.log(str(repo), 1, 0)
    assert log["ok"] and len(log["commits"]) == 1
    assert g.log(str(repo), 2, 1)["commits"] == []


def test_git_identity_and_unverified_commit_message(tmp_path):
    from mvvm.services import git_service as g

    repo = tmp_path / "repo"; repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    (repo / "a.txt").write_text("one\n")
    result = g.set_config(str(repo), "Real Name", "real@example.com", False)
    assert result["ok"] is True, result
    assert _git(repo, "config", "--local", "--get", "user.name").strip() == "Real Name"
    assert _git(repo, "config", "--local", "--get", "user.email").strip() == "real@example.com"
    assert g.set_config(str(repo), "", "x@y", False)["reason"] == "identity-needed"
    result = g.generate_commit_message(None, None, str(repo))
    assert result["ok"] is False and result["reason"] == "unverified"
