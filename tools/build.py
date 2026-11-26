from __future__ import annotations
from ai_upper.localization import tr

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from ai_upper.config import (
    BUILD, DIST, TARGETS, app_name, host_description, host_target, pbs_release,
    pbs_sdk_dir, python_version, runtime_provider, target_runtime_dir,
    trim_policy, validate_build_python_version, validate_target, require_local_python,
)
from ai_upper.egg import COMPRESSIONS, egg_config
from ai_upper.lock import verify_lock, write_lock
from ai_upper.package import build_launcher, package, write_release_manifest
from ai_upper.python_build import build_python_package
from ai_upper.runtime import ensure_runtime, ensure_sdk
from ai_upper.fs import retire_tree
from ai_upper.verify import run_launcher_smoke, run_packaged_launcher, run_target_python_smoke
from ai_upper.toolchain import describe_toolchain
from ai_upper.third_party import resolve_wheels
from ai_upper.trim import PRESETS
from ai_upper.egg_loader import BACKENDS
from ai_upper.verify import verify


def _run_app(out: Path, target) -> int:
    name = app_name()
    executable = out / (f"{name}.exe" if target.os == "windows" else name)
    if target.os == "macos":
        executable = out / "Contents" / "MacOS" / name
    if not executable.exists():
        raise RuntimeError(tr('legacy.7d146fdd72cc' ,p1=executable))
    result = run_packaged_launcher(executable, cwd=out)
    print(tr('legacy.bfec4ce35310'), result.returncode)
    return result.returncode


def _clean() -> int:
    # dist/ carries a working interpreter that environment discovery tools
    # execute, so deleting it in place races with the bytecode they write.
    retire_tree(DIST, trash=BUILD / "retired")
    if BUILD.exists():
        shutil.rmtree(BUILD)
    print(tr('legacy.ab0d461476e3'))
    return 0


def _doctor(target) -> int:
    print(tr('legacy.b5b379cb878c'), host_description())
    print(tr('legacy.83e75b7fd519'), target.key, target.triple)
    print(tr('legacy.bca299ecf9c5'), python_version())
    print(tr('legacy.35d5d317b79a'), runtime_provider())
    print(tr('legacy.36ef05bdfea0'), pbs_release() or "auto")
    try:
        print(tr('legacy.ea97c9af6812'), require_local_python())
    except Exception as exc:
        print(tr('legacy.90d30a83f58c'), exc)
    print(tr('legacy.b206933d1c87'), pbs_sdk_dir(target))
    print(tr('legacy.8529e3e5bcef'), target_runtime_dir(target))
    missing = []
    for tool in ("cmake", "ninja"):
        path = shutil.which(tool)
        print(f"{tool}:", path or "MISSING")
        if not path:
            missing.append(tool)
    try:
        print(tr('legacy.635ce45cfa9c'), describe_toolchain(target))
    except Exception as exc:
        print(tr('legacy.7ba3bdcb4c48'), exc)
        missing.append("toolchain")
    # A build cannot start without these, so the diagnostic exits non-zero and
    # doubles as the toolchain gate in CI instead of a second, hand-rolled probe.
    if missing:
        print(tr('legacy.fd0c36279915'), ", ".join(missing))
        return 1
    return 0


def _line_buffered() -> None:
    """Make this process's output reach the log in the order it was printed.

    Every tool this builds with is a child that inherits our ``stdout`` and
    ``stderr``, so it writes straight into whatever file the caller redirected
    us to (CI runs ``build.py --run > run.log 2>&1``). Our own prints do not:
    redirected to a file, Python buffers them by blocks. A child that writes
    while our last fifty lines are still in memory puts its output *before*
    them in the file, and the rest of our log is flushed on top at exit.

    That is what made run 44033731069's two macOS jobs unreadable: the
    annotation keeps the last 3000 characters of run.log, which showed
    ``[6/6]``, ``+ <launcher> [launcher smoke]`` and ``Application exit code:
    1`` but not one line from either child -- their ``SMOKE PASS`` and the
    application's own ``QML FAILED reason=...`` had been written earlier in the
    file, behind the buffered stage-5 output. Line buffering costs nothing
    measurable on a build log and keeps every child's words where they belong.

    ``PYTHONUNBUFFERED`` does this for the interpreter globally; this is for
    the case where it is unset, which is how CI runs.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(line_buffering=True)
        except (ValueError, OSError):
            # Detached or replaced stream: ordering is then decided elsewhere
            # and a build must not fail over it.
            pass


def main(argv=None) -> int:
    from ai_upper.localization import configure_cli
    configure_cli(argv)
    _line_buffered()
    validate_build_python_version()
    parser = argparse.ArgumentParser(description=tr('legacy.9e8a12d793eb'))
    parser.add_argument("command", nargs="?", choices=["doctor", "build", "run", "verify", "lock", "release", "clean"])
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--doctor", action="store_true")
    actions.add_argument("--run", dest="run_app", action="store_true")
    actions.add_argument("--verify", action="store_true")
    actions.add_argument("--lock", action="store_true")
    actions.add_argument("--release", action="store_true")
    actions.add_argument("--clean", action="store_true")
    parser.add_argument("--target", choices=list(TARGETS))
    parser.add_argument("--locked", action="store_true")
    parser.add_argument("--identity")
    parser.add_argument("--notary-profile")
    parser.add_argument("--trim-preset", choices=tuple(PRESETS), metavar="NAME",
                        help=tr('finish.756641af3a9d') + ", ".join(PRESETS))
    parser.add_argument("--trim-site", action="append", default=[], metavar="GLOB",
                        help=tr('legacy.99c42b87afe8'))
    parser.add_argument("--trim-site-keep", action="append", default=[], metavar="GLOB",
                        help=tr('legacy.821af90ca8fc'))
    parser.add_argument("--trim-runtime", action="append", default=[], metavar="GLOB",
                        help=tr('legacy.8be52bec09f6'))
    parser.add_argument("--trim-runtime-keep", action="append", default=[], metavar="GLOB",
                        help=tr('legacy.f29fab35580f'))
    egg_actions = parser.add_mutually_exclusive_group()
    egg_actions.add_argument("--egg", dest="egg", action="store_true", default=None,
                             help=tr('legacy.c6fd2cda2739'))
    egg_actions.add_argument("--no-egg", dest="egg", action="store_false", default=None,
                             help=tr('legacy.5490f2c8bbcd'))
    parser.add_argument("--egg-key", metavar="HEX",
                        help=tr('legacy.3b421fff22d3'))
    parser.add_argument("--egg-backend", choices=BACKENDS, metavar="NAME",
                        help=tr('legacy.57e54def59d6'))
    parser.add_argument("--egg-compression", choices=COMPRESSIONS, metavar="NAME",
                        help=tr('finish.bd68c71b08fa') + ", ".join(COMPRESSIONS))
    parser.add_argument("--lang", choices=("zh-CN", "en"), help=tr('cli.d7fa6622c296'))
    args = parser.parse_args(argv)

    action = args.command or "build"
    if args.doctor:
        action = "doctor"
    elif args.run_app:
        action = "run"
    elif args.verify:
        action = "verify"
    elif args.lock:
        action = "lock"
    elif args.release:
        action = "release"
    elif args.clean:
        action = "clean"

    target = validate_target(args.target)
    try:
        if action == "doctor":
            return _doctor(target)
        if action == "clean":
            return _clean()
        if action == "verify":
            return verify(target)
        if action == "lock":
            ensure_sdk(target)
            ensure_runtime(target)
            resolve_wheels(target)
            print(tr('legacy.e3ec3573f9b3'), write_lock(target))
            return 0
        if action not in {"build", "run", "release"}:
            return 1
        if action == "run" and target != host_target():
            raise RuntimeError(tr('legacy.8fc0da44b55c' ,p1=host_target().key, p3=target.key))
        if args.locked:
            verify_lock(target)
            os.environ["AI_UPPER_LOCKED"] = "1"
            os.environ["PYSTAND_LOCKED"] = "1"

        trim = trim_policy(args.trim_preset).merge(
            site_packages=args.trim_site,
            site_packages_keep=args.trim_site_keep,
            runtime=args.trim_runtime,
            runtime_keep=args.trim_runtime_keep,
        )

        egg = egg_config(args.egg, args.egg_key, args.egg_backend, args.egg_compression)

        print(tr('legacy.4213af8a9ae5'))
        ensure_sdk(target)
        ensure_runtime(target)
        print(tr('legacy.d297eedc8c9e'))
        build_python_package(target, trim, egg)
        print(tr('legacy.cdde33d8c30a'))
        launcher = build_launcher(target, egg)
        print(tr('legacy.8cf42e666d61'))
        out = package(target, launcher, trim)
        print(tr('legacy.b0a4b0aceabb'))
        if verify(target):
            return 1
        print(tr('legacy.821bd0b25b7e'))
        run_target_python_smoke(target)
        run_launcher_smoke(target, out / ("Contents/MacOS/" + app_name() if target.os == "macos" else (app_name() + ".exe" if target.os == "windows" else app_name())))

        if action == "run":
            return _run_app(out, target)
        if action == "release":
            release(target, args.identity, args.notary_profile)
            print(tr('legacy.7b9b2ee07a29'), write_release_manifest(target))
        else:
            print(tr('legacy.2db9a748ad8a'), out)
        return 0
    except subprocess.CalledProcessError as exc:
        print(tr('legacy.d59a5b3f12e7' ,p1=exc.returncode, p3=' '.join(map(str, exc.cmd)) if isinstance(exc.cmd, (list, tuple)) else exc.cmd))
        return exc.returncode or 1
    except Exception as exc:
        print(tr('legacy.82862f1bf8bc' ,p1=type(exc).__name__, p3=exc))
        if os.environ.get("AI_UPPER_TRACEBACK") == "1":
            raise
        return 1


def release(target, identity=None, notary_profile=None) -> int:
    if target.os == "linux":
        print(tr('legacy.56dad428204b'))
        return 0
    if target.os == "windows":
        tool = shutil.which("signtool")
        cert = os.environ.get("AI_UPPER_SIGN_CERT") or os.environ.get("PYSTAND_SIGN_CERT")
        if not tool or not cert:
            raise RuntimeError(tr('legacy.bc120a8a2434'))
        for path in (DIST / app_name()).rglob("*"):
            if path.is_file() and path.suffix.lower() in {".exe", ".dll", ".pyd"}:
                subprocess.run([tool, "sign", "/fd", "SHA256", "/a", "/f", cert, str(path)], check=True)
        return 0
    app = DIST / f"{app_name()}.app"
    codesign = shutil.which("codesign")
    xcrun = shutil.which("xcrun")
    ident = identity or os.environ.get("AI_UPPER_CODESIGN_IDENTITY") or os.environ.get("PYSTAND_CODESIGN_IDENTITY")
    if not codesign or not xcrun or not ident:
        raise RuntimeError(tr('legacy.68114bd60220'))
    nested = [p for p in app.rglob("*") if p.is_file() and p.suffix.lower() in {".dylib", ".so"}]
    nested.append(app / "Contents" / "MacOS" / app_name())
    for path in nested:
        subprocess.run([codesign, "--force", "--timestamp", "--options", "runtime", "--sign", ident, str(path)], check=True)
    subprocess.run([codesign, "--force", "--timestamp", "--options", "runtime", "--sign", ident, str(app)], check=True)
    subprocess.run([codesign, "--verify", "--deep", "--strict", "--verbose=2", str(app)], check=True)
    if notary_profile:
        subprocess.run([xcrun, "notarytool", "submit", str(app), "--keychain-profile", notary_profile, "--wait"], check=True)
        subprocess.run([xcrun, "stapler", "staple", str(app)], check=True)
        subprocess.run([xcrun, "stapler", "validate", str(app)], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
