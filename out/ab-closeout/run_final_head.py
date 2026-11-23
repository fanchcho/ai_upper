"""Export the current HEAD under .tmp, verify sources, run the whole suite.

The original workspace's unchanged branding test scans historical .tmp trees.
This leaves those files and the test intact; only committed source is tested.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

root = Path(__file__).resolve().parents[2]
evidence = root / "out/ab-closeout"
work = root / ".tmp/ab-closeout"
source = work / "final-head-source"
source.mkdir(exist_ok=True)
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
names = subprocess.check_output(["git", "ls-tree", "--name-only", head], cwd=root, text=True).splitlines()
names = [name for name in names if name not in {"out", ".tmp"}]
archive = work / "final-head-source.tar"
subprocess.run(["git", "archive", "--format=tar", "--output", str(archive), head, "--", *names], cwd=root, check=True)
with tarfile.open(archive) as handle:
    handle.extractall(source, filter="data")
# This existing local packaging configuration is gitignored; do not manufacture one.
shutil.copy2(root / "app/pyproject.toml", source / "app/pyproject.toml")
files = subprocess.check_output(["git", "ls-files", "app", "tools", "launcher"], cwd=root, text=True).splitlines()
manifest = {}
for name in files:
    if (root/name).is_file() and (source/name).is_file():
        original = (root/name).read_bytes()
        assert original == (source/name).read_bytes(), name
        manifest[name] = hashlib.sha256(original).hexdigest()
command = [str(root/".venv/bin/python"), "-m", "pytest", "app/tests", "-q", "-ra"]
record = {"head": head, "cwd": str(source), "command": command,
          "AI_UPPER_HOME": os.environ["AI_UPPER_HOME"], "matching_files": len(manifest),
          "config_sha256": hashlib.sha256((source/"app/pyproject.toml").read_bytes()).hexdigest(),
          "manifest": manifest}
(evidence/"final-head-verification.json").write_text(json.dumps(record, indent=2))
with (evidence/"final-head.log").open("w") as log:
    result = subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT)
(evidence/"final-head.rc").write_text(str(result.returncode)+"\n")
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip() == head
print("tested_head", head, "matching_files", len(manifest), "pytest_rc", result.returncode)
for line in (evidence/"final-head.log").read_text().splitlines():
    if " passed" in line or line.startswith(("FAILED ", "SKIPPED ")):
        print(line)
raise SystemExit(result.returncode)
