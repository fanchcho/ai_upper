"""F85 Git 面板最小子集：真实 git 状态的 stage/commit/branch/log。"""
from __future__ import annotations

import os
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_git_service_real_repo(tmp_path):
    from mvvm.services import git_service as bridge

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "a.txt").write_text("one\n")
    out = bridge.stage(str(repo), ["a.txt"])
    assert out["ok"] is True, out
    assert bridge.commit(str(repo), "initial")["ok"] is True
    (repo / "a.txt").write_text("two\n")
    status = bridge.status(str(repo))
    assert status["ok"] and status["dirty"] and status["branch"] == "main"
    assert any(e["path"] == "a.txt" for e in status["entries"])
    assert bridge.stage(str(repo), ["a.txt"])["ok"] is True
    assert bridge.commit(str(repo), "update")["ok"] is True
    log = bridge.log(str(repo), 5)
    assert log["ok"] and len(log["commits"]) >= 2
    assert bridge.branches(str(repo))["ok"] is True
    assert bridge.create_branch(str(repo), "feature")["ok"] is True
    assert "feature" in bridge.branches(str(repo))["branches"]
