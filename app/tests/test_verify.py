from __future__ import annotations

import json
import os

import pytest


def test_smoke_modules_include_entry_and_direct_dependencies(tmp_path, monkeypatch):
    import ai_upper.verify as smoke

    monkeypatch.setattr(smoke, "selected_sources", lambda: [])
    monkeypatch.setattr(smoke, "entry_module", lambda: "main")
    manifest_dir = tmp_path / "wheels" / "linux-x86_64"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "manifest.json").write_text(json.dumps({"imports": ["PySide6"]}), encoding="utf-8")
    monkeypatch.setattr(smoke, "wheel_dir", lambda target: manifest_dir)
    from ai_upper.config import TARGETS
    assert smoke.smoke_modules(TARGETS["linux-x86_64"]) == ["PySide6", "main"]


def test_windows_pbs_package_requires_embeddable_layout(tmp_path, monkeypatch):
    from ai_upper import verify
    from ai_upper.config import TARGETS, runtime_spec

    target = TARGETS["windows-x86_64"]
    # The version-dependent names follow the configured pin; the check reads its
    # digits from the same runtime spec, so the test must not hardcode one.
    digits = runtime_spec(target).major_minor.replace(".", "")
    versioned = (f"python{digits}.dll", f"python{digits}.zip", f"python{digits}._pth")
    monkeypatch.setattr(verify, "DIST", tmp_path)
    monkeypatch.setattr(verify, "app_name", lambda: "MyApp")
    monkeypatch.setattr(verify, "selected_sources", lambda: [])
    root = tmp_path / "MyApp" / "runtime"
    root.mkdir(parents=True)
    labels = {label: ok for ok, label in verify._checks_for_package(target)}
    assert labels["Windows embed runtime is flat"]
    assert labels[f"Windows embed runtime {versioned[1]}"] is False
    for name in ("python3.dll", *versioned):
        (root / name).write_bytes(b"runtime")
    labels = {label: ok for ok, label in verify._checks_for_package(target)}
    assert all(labels[f"Windows embed runtime {name}"] for name in ("python3.dll", *versioned))


def test_windows_pbs_stage_smoke_uses_sdk_interpreter(tmp_path, monkeypatch):
    from ai_upper import verify, runtime
    from ai_upper.config import TARGETS

    target = TARGETS["windows-x86_64"]
    sdk_python = tmp_path / "sdk" / "install" / "python.exe"
    calls = []
    monkeypatch.setattr(verify, "host_target", lambda: target)
    monkeypatch.setattr(verify, "BUILD", tmp_path)
    monkeypatch.setattr(verify, "write_smoke_script", lambda target, path: path)
    monkeypatch.setattr(runtime, "sdk_info", lambda target: {"python_executable": str(sdk_python)})
    monkeypatch.setattr(verify.subprocess, "run", lambda command, **kwargs: calls.append((command, kwargs)))

    verify.run_target_python_smoke(target)
    assert calls[0][0][0] == str(sdk_python)
    assert "PYTHONHOME" not in calls[0][1]["env"]
    assert calls[0][1]["env"]["PYTHONPATH"].endswith("site-packages")


@pytest.mark.parametrize("member", ["module.pyd", "ai_upper_bundles/ai_upper_demo.pyd"])
def test_egg_cannot_hide_custom_native_dependencies(tmp_path, monkeypatch, member):
    from ai_upper import verify
    from ai_upper.config import TARGETS
    from ai_upper.egg import EggConfig, pack_egg, remove_packed_files
    from ai_upper.native import deps
    from test_native_deployment import _pe

    monkeypatch.setattr(deps, "_dumpbin_dependencies", lambda path, env=None: [])
    site = tmp_path / "site-packages"
    _pe(site / member, ["vendor_driver.dll"])
    config = EggConfig()
    egg = pack_egg(site, tmp_path / "ai_upper.dat", [member], config)
    remove_packed_files(site, [member])

    checks = verify._verify_egg_native_dependencies(egg, config.key_hex, TARGETS["windows-x86_64"], tmp_path / "runtime")

    assert len(checks) == 1
    assert checks[0][0] is False
    assert "vendor_driver.dll" in checks[0][1]
    assert "--no-egg" in checks[0][1]


def test_egg_windows_runtime_dependency_must_be_bundled(tmp_path, monkeypatch):
    from ai_upper import verify
    from ai_upper.config import TARGETS
    from ai_upper.egg import EggConfig, pack_egg
    from ai_upper.native import deps
    from test_native_deployment import _pe

    monkeypatch.setattr(deps, "_dumpbin_dependencies", lambda path, env=None: [])
    site = tmp_path / "site-packages"
    _pe(site / "module.pyd", ["vcruntime140.dll", "kernel32.dll"])
    config = EggConfig()
    egg = pack_egg(site, tmp_path / "ai_upper.dat", ["module.pyd"], config)
    runtime = tmp_path / "runtime"
    target = TARGETS["windows-x86_64"]

    assert not all(ok for ok, _ in verify._verify_egg_native_dependencies(egg, config.key_hex, target, runtime))
    _pe(runtime / "vcruntime140.dll")
    assert not all(ok for ok, _ in verify._verify_egg_native_dependencies(egg, config.key_hex, target, runtime))
    _pe(runtime / "python313.dll", ["vcruntime140.dll"])
    assert all(ok for ok, _ in verify._verify_egg_native_dependencies(egg, config.key_hex, target, runtime))


def test_build_output_stays_in_print_order_under_redirection(tmp_path):
    """A child writes into our fd at once; our buffered prints catch up at exit.

    Run 44033731069's two macOS jobs failed `Full integration run` with an
    annotation holding only build.py's own ``[6/6]``, ``+ <launcher>
    [launcher smoke]`` and ``Application exit code: 1`` -- not one line from
    either child, neither the smoke program's ``SMOKE PASS`` nor the
    application's ``QML FAILED reason=...``. Both children had printed them.
    ``build.py --run > run.log 2>&1`` leaves stdout block-buffered, so the
    stage output still in memory reached the file only at exit, *after* what
    the children wrote. The annotation keeps the last 3000 characters of the
    log, and that window held none of the child's words.

    The probe is a fresh interpreter whose stdout is the file, so the buffering
    under test is Python's default rather than pytest's capture, and
    ``PYTHONUNBUFFERED`` is removed because CI does not set it.
    """
    import subprocess
    import sys
    from pathlib import Path

    child = tmp_path / "child"
    child.write_text("#!/bin/sh\necho 'SMOKE PASS launcher'\n", encoding="utf-8")
    child.chmod(0o755)

    probe = tmp_path / "probe.py"
    # The real entry point, so this fails if build.main stops installing the
    # buffering: --help exits immediately and its output does not matter, but
    # the stream settings main applied to this process do.
    probe.write_text(
        "import subprocess, sys\n"
        "sys.path.insert(0, {tools!r})\n"
        "import build\n"
        "try:\n"
        "    build.main(['--help'])\n"
        "except SystemExit:\n"
        "    pass\n"
        "for i in range(60):\n"
        "    print('PASS packaged check %d' % i)\n"
        "subprocess.run([{child!r}], check=True)\n"
        "print('[6/6] Target runtime smoke')\n".format(
            tools=str(Path(__file__).parents[2] / "tools"),
            child=str(child),
        ),
        encoding="utf-8",
    )

    log = tmp_path / "run.log"
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
    with log.open("w", encoding="utf-8") as handle:
        subprocess.run([sys.executable, str(probe)], stdout=handle, stderr=subprocess.STDOUT, check=True, env=env)

    content = log.read_text(encoding="utf-8")
    lines = content.splitlines()
    # --help printed its usage first, so compare positions rather than indices.
    last_parent = lines.index("PASS packaged check 59")
    assert lines.index("SMOKE PASS launcher") == last_parent + 1, lines[last_parent - 2 : last_parent + 4]
    assert lines[-1] == "[6/6] Target runtime smoke", lines[-4:]
    # The window the CI annotation keeps.
    assert "SMOKE PASS launcher" in content[-3000:]
