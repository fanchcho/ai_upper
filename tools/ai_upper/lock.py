from __future__ import annotations
from ai_upper.localization import tr

import hashlib
import json
from pathlib import Path

from .config import (
    LEGACY_LOCK, LEGACY_RUNTIME_MARKER, LEGACY_SDK_MARKER, LOCK, Target, load_app_config,
    python_version, runtime_provider, runtime_spec, wheel_dir,
)
from .fs import marker_file
from .manifest import manifest_hash, read_manifest
from .pbs import SDK_MARKER
from .runtime import RUNTIME_MARKER
from .third_party import dependency_specs

FORMAT = 5


def lock_path() -> Path:
    """The lock file to read: the current name, else the pre-rename one."""
    return LOCK if LOCK.exists() or not LEGACY_LOCK.exists() else LEGACY_LOCK


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _wheel_records(target: Target) -> list[dict]:
    return [
        {"file": path.name, "sha256": _sha256(path), "size": path.stat().st_size}
        for path in sorted(wheel_dir(target).glob("*.whl"))
    ]


def _marker(root: Path, name: str, legacy: str) -> dict:
    path = marker_file(root, name, legacy)
    if path is None:
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_lock(target: Target) -> Path:
    spec = runtime_spec(target)
    manifest = read_manifest(spec.root)
    project = str(load_app_config().get("project", {}).get("name") or "ai_upper")
    data = {
        "format": FORMAT,
        "project": project,
        "python": python_version(),
        "runtime_provider": runtime_provider(),
        "targets": {},
    }
    existing_path = lock_path()
    if existing_path.exists():
        try:
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            existing = {}
        if (
            isinstance(existing, dict)
            and existing.get("format") == FORMAT
            and existing.get("python") == python_version()
            and existing.get("runtime_provider") == runtime_provider()
        ):
            existing_targets = existing.get("targets", {})
            if isinstance(existing_targets, dict):
                data["targets"].update(existing_targets)
    target_data: dict = {
        "runtime_manifest_sha256": manifest_hash(manifest),
        "requirements": dependency_specs(),
        "wheels": _wheel_records(target),
    }
    if runtime_provider() == "pbs":
        runtime = _marker(spec.root, RUNTIME_MARKER, LEGACY_RUNTIME_MARKER)
        sdk = _marker(spec.sdk_root, SDK_MARKER, LEGACY_SDK_MARKER)
        target_data["runtime"] = {key: runtime.get(key) for key in ("source", "tag", "asset", "url", "sha256", "python", "target") if runtime.get(key) is not None}
        target_data["sdk"] = {key: sdk.get(key) for key in ("tag", "asset", "url", "sha256", "python", "target") if sdk.get(key) is not None}
    data["targets"][target.key] = target_data
    LOCK.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    return LOCK


def verify_lock(target: Target) -> None:
    path = lock_path()
    if not path.exists():
        raise RuntimeError(tr('legacy.7fa7f36a712d' ,p1=path))
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != FORMAT:
        raise RuntimeError(tr('legacy.73915115af15' ,p1=repr(data.get('format'))))
    if data.get("python") != python_version() or data.get("runtime_provider") != runtime_provider():
        raise RuntimeError(tr('legacy.b505dee94c09'))
    target_data = data.get("targets", {}).get(target.key)
    if not isinstance(target_data, dict):
        raise RuntimeError(tr('legacy.2adbbe8ac2c6' ,p1=target.key, p3=path))
    if target_data.get("requirements", []) != dependency_specs():
        raise RuntimeError(tr('legacy.15f4dcb61026'))

    spec = runtime_spec(target)
    manifest = read_manifest(spec.root)
    expected_manifest = target_data.get("runtime_manifest_sha256")
    if expected_manifest and manifest_hash(manifest) != expected_manifest:
        raise RuntimeError(tr('legacy.8d965fcc31e7' ,p1=target.key))

    if runtime_provider() == "pbs":
        recorded_runtime = target_data.get("runtime", {})
        if target.os == "windows" and (not isinstance(recorded_runtime, dict)
                                       or recorded_runtime.get("source") != "python.org"):
            raise RuntimeError(tr('legacy.06c62855273f'))
        for label, root, marker_name, legacy_marker in (
            ("runtime", spec.root, RUNTIME_MARKER, LEGACY_RUNTIME_MARKER),
            ("sdk", spec.sdk_root, SDK_MARKER, LEGACY_SDK_MARKER),
        ):
            current = _marker(root, marker_name, legacy_marker)
            if not current:
                raise RuntimeError(tr('legacy.b31d726c4c2d' ,p1=label, p3=root))
            for key, expected in target_data.get(label, {}).items():
                if expected and current.get(key) != expected:
                    raise RuntimeError(tr('legacy.af704404e11e' ,p1=label, p3=target.key, p5=key))

    actual = {path.name: path for path in wheel_dir(target).glob("*.whl")}
    expected_wheels = {str(record["file"]): record for record in target_data.get("wheels", []) if isinstance(record, dict) and record.get("file")}
    if set(actual) != set(expected_wheels):
        raise RuntimeError(tr('legacy.1a73f42b3189' ,p1=sorted(expected_wheels), p3=sorted(actual)))
    for name, record in expected_wheels.items():
        if _sha256(actual[name]).lower() != str(record["sha256"]).lower():
            raise RuntimeError(tr('legacy.685561550505' ,p1=name))
