"""单实例锁：第二个进程只唤起既有窗口后退出（deva main/index.ts:276-286）。

用两个真实进程跑，不用 mock：第一个保持运行，第二个必须 rc=0 且在数秒内退出，
第一个进程打印出激活日志。
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _env(home: Path) -> dict:
    env = os.environ.copy()
    env.update(
        AI_UPPER_HOME=str(home),
        DEVA_ASSETS_DIR=str(ROOT / "app" / "assets"),
        QT_QPA_PLATFORM="offscreen",
        QT_QUICK_BACKEND="software",
        PYTHONUNBUFFERED="1",
    )
    return env


def test_second_process_activates_first_and_exits(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    cmd = [sys.executable, str(ROOT / "app" / "src" / "main.py")]
    first = subprocess.Popen(cmd, env=_env(home), cwd=str(ROOT), stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True)
    try:
        deadline = time.time() + 25
        while time.time() < deadline and not (home / "instance.lock").exists():
            if first.poll() is not None:
                raise AssertionError("first instance exited early: " + first.stdout.read())
            time.sleep(0.1)
        assert (home / "instance.lock").exists(), "first instance did not take the lock"
        # 等 QLocalServer 真正 listen 后再起第二个，避免启动窗口期误报。
        time.sleep(0.8)
        second = subprocess.run(cmd, env=_env(home), cwd=str(ROOT), capture_output=True,
                                text=True, timeout=15)
        assert second.returncode == 0, (second.returncode, second.stdout, second.stderr)
        assert "Traceback" not in (second.stdout + second.stderr)
        # first 仍活着，并在收到激活后打印日志。
        deadline = time.time() + 8
        seen = False
        while time.time() < deadline and not seen:
            line = first.stdout.readline()
            if not line:
                time.sleep(0.05)
                continue
            if "SINGLE INSTANCE ACTIVATE" in line:
                seen = True
        assert seen, "first instance never reported activation"
    finally:
        first.terminate()
        try:
            first.wait(timeout=10)
        except subprocess.TimeoutExpired:
            first.kill()
