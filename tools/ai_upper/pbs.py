"""PBS (python-build-standalone) resolution: release metadata, assets, runtime and SDK."""
from __future__ import annotations
from ai_upper.localization import tr

import json
import os
import re
import shutil
import subprocess
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, unquote

from .config import CACHE, LEGACY_SDK_MARKER, Target, pbs_release, pbs_sdk_dir, python_version
from .fs import copy_tree_contents, marker_file, sha256
from .net import download, http_json, http_text


PBS_RELEASE_URL = "https://github.com/astral-sh/python-build-standalone/releases/download/{tag}"
# uv maintains the exact build index for every python-build-standalone release.
# Upstream reorganises its source tree without notice: the file moved from
# crates/uv-python to crates/uv-python-managed in uv commit 00e49e7e, which
# turned the old path into a hard 404 for every build that had a cold cache.
# Known locations are therefore tried in order instead of pinning one path on a
# branch that moves.
PBS_RUNTIME_METADATA_URLS = (
    "https://raw.githubusercontent.com/astral-sh/uv/main/crates/uv-python-managed/download-metadata.json",
    "https://raw.githubusercontent.com/astral-sh/uv/main/crates/uv-python/download-metadata.json",
)
_METADATA_CACHE = CACHE / "pbs" / "uv-download-metadata.json"


@dataclass(frozen=True)
class PBSAsset:
    name: str
    url: str
    sha256: str | None = None


@dataclass(frozen=True)
class PBSInputs:
    tag: str
    runtime: PBSAsset
    sdk: PBSAsset
    source: str


def metadata_key(target: Target, pyver: str) -> str:
    platform = {
        ("macos", "arm64"): "darwin-aarch64-none",
        ("macos", "x86_64"): "darwin-x86_64-none",
        ("windows", "x86"): "windows-i686-none",
        ("windows", "x86_64"): "windows-x86_64-none",
        ("windows", "arm64"): "windows-aarch64-none",
        ("linux", "x86_64"): "linux-x86_64-gnu",
        ("linux", "arm64"): "linux-aarch64-gnu",
    }[(target.os, target.arch)]
    return f"cpython-{pyver.strip()}-{platform}"


def windows_embed_asset(target: Target, pyver: str) -> PBSAsset:
    """Official CPython embeddable runtime; PBS remains the build-only SDK."""
    if target.os != "windows":
        raise ValueError(tr('legacy.439dcd8da297' ,p1=target.key))
    architecture = {"x86": "win32", "x86_64": "amd64", "arm64": "arm64"}[target.arch]
    name = f"python-{pyver}-embed-{architecture}.zip"
    return PBSAsset(name, f"https://www.python.org/ftp/python/{pyver}/{name}")


def asset_python_version(name: str) -> str | None:
    match = re.match(r"^cpython-(\d+\.\d+\.\d+)(?:\+|-)", str(name).strip())
    return match.group(1) if match else None


def release_assets(checksums: str, tag: str) -> list[PBSAsset]:
    """Read the public release inventory and hashes without the GitHub API."""
    base_url = PBS_RELEASE_URL.format(tag=quote(tag, safe=""))
    assets: dict[str, PBSAsset] = {}
    for number, line in enumerate(checksums.splitlines(), 1):
        if not line.strip():
            continue
        match = re.fullmatch(r"([a-fA-F0-9]{64}) [ *]([A-Za-z0-9_][A-Za-z0-9_+.-]*)", line)
        if not match:
            raise RuntimeError(tr('legacy.f46539ab8683' ,p1=tag, p3=number))
        digest, name = match.groups()
        if name in assets:
            raise RuntimeError(tr('legacy.77e3f31bd766' ,p1=tag, p3=name))
        assets[name] = PBSAsset(name, f"{base_url}/{quote(name, safe='')}", digest.lower())
    if not assets:
        raise RuntimeError(tr('legacy.90ccff1e8e67' ,p1=tag))
    return list(assets.values())


def _release_assets(fetch_text: Callable[[str], str], tag: str) -> list[PBSAsset]:
    url = PBS_RELEASE_URL.format(tag=quote(tag, safe="")) + "/SHA256SUMS"
    return release_assets(fetch_text(url), tag)


def is_matching_asset(name: str, target: Target, pyver: str, *, kind: str) -> bool:
    name = str(name).strip()
    if asset_python_version(name) != pyver.strip() or target.triple not in name:
        return False
    if "freethreaded" in name or "debug" in name:
        return False
    if kind == "runtime":
        return name.endswith("-install_only_stripped.tar.gz")
    if kind == "sdk":
        return name.endswith(("-pgo+lto-full.tar.zst", "-pgo-full.tar.zst", "-full.tar.zst"))
    raise ValueError(tr('legacy.e58f13a64356' ,p1=kind))


def matching_assets(assets: list[PBSAsset], target: Target, pyver: str, *, kind: str) -> list[PBSAsset]:
    return [
        asset for asset in assets
        if is_matching_asset(asset.name, target, pyver, kind=kind)
    ]


def available_python_versions(assets: list[PBSAsset], target: Target, *, kind: str) -> list[str]:
    values = {
        version
        for asset in assets
        for version in [asset_python_version(asset.name)]
        if version and is_matching_asset(asset.name, target, version, kind=kind)
    }
    return sorted(values, key=lambda x: tuple(int(part) for part in x.split(".")))


def available_metadata_python_versions(data: dict[str, Any], target: Target) -> list[str]:
    suffix = metadata_key(target, "0.0.0").split("0.0.0-", 1)[1]
    prefix = "cpython-"
    values: set[str] = set()
    for key, value in data.items():
        if not isinstance(key, str) or not key.startswith(prefix) or not key.endswith("-" + suffix):
            continue
        version = key[len(prefix): -len(suffix) - 1]
        if re.fullmatch(r"\d+\.\d+\.\d+", version) and isinstance(value, dict) and value.get("url"):
            values.add(version)
    return sorted(values, key=lambda x: tuple(int(part) for part in x.split(".")))


def _fetch_metadata_index(fetch_json: Callable[[str], Any]) -> dict[str, Any]:
    failures: list[str] = []
    for url in PBS_RUNTIME_METADATA_URLS:
        try:
            value = fetch_json(url)
        except (OSError, ValueError) as exc:
            failures.append(f"{url}: {exc}")
            continue
        if isinstance(value, dict):
            return value
        failures.append(f"{url}: expected a JSON object, got {type(value).__name__}")
    raise RuntimeError(
        tr('legacy.c6e636ea6cdc')
        + "\n".join(failures)
        + tr('legacy.6569969659e6')
    )


def _load_metadata(fetch_json: Callable[[str], Any], *, force: bool = False) -> dict[str, Any]:
    if not force and _METADATA_CACHE.exists():
        try:
            value = json.loads(_METADATA_CACHE.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                return value
        except (OSError, ValueError):
            pass
    value = _fetch_metadata_index(fetch_json)
    _METADATA_CACHE.parent.mkdir(parents=True, exist_ok=True)
    _METADATA_CACHE.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return value


def metadata_asset(data: dict[str, Any], target: Target, pyver: str) -> PBSAsset | None:
    entry = data.get(metadata_key(target, pyver))
    if not isinstance(entry, dict):
        return None
    url = str(entry.get("url") or "").strip()
    if not url:
        return None
    return PBSAsset(
        name=unquote(url.rsplit("/", 1)[-1]),
        url=url,
        sha256=str(entry.get("sha256") or "").strip() or None,
    )


def asset_flavor(name: str) -> str:
    """The build flavour a PBS asset name records, or "" when it records none.

    Windows releases used to ship a shared and a static flavour of every
    artifact, and the two are not interchangeable: extension modules link the
    versioned import library (python3XX.lib), which only the shared flavour
    carries. Newer releases dropped the flavour from the name altogether.
    """
    for flavor in ("shared", "static"):
        if f"-{flavor}-" in name:
            return flavor
    return ""


def is_full_build_asset(name: str) -> bool:
    """Whether a PBS asset is a full build rather than an install-only runtime.

    A full build carries the build tree, the SDK (headers and import
    libraries) and an ``install/`` runtime; an install-only archive carries
    the runtime alone. PBS releases before 20210724 publish full builds only,
    which is why uv's metadata entry for them points at a full build.
    """
    name = str(name).strip()
    return (
        name.endswith(".tar.zst")
        and "install_only" not in name
        and "debug" not in name
        and "freethreaded" not in name
    )


def _best_sdk(assets: list[PBSAsset], runtime_name: str) -> PBSAsset:
    """The SDK matching the runtime's build flavour, best optimisation first."""
    flavor = asset_flavor(runtime_name)
    candidates = assets
    if flavor:
        candidates = [asset for asset in assets if asset_flavor(asset.name) == flavor]
        if not candidates:
            raise RuntimeError(
                tr('legacy.42da2e780bcb' ,p1=flavor, p3=runtime_name, p5=', '.join((asset.name for asset in assets)))
            )
    return max(candidates, key=lambda asset: ("pgo+lto-full" in asset.name, asset.name))


def no_asset_error(release_tag: str, target: Target, pyver: str, assets: list[PBSAsset], *, missing_runtime: bool, missing_sdk: bool) -> RuntimeError:
    missing = []
    if missing_runtime:
        missing.append("install_only_stripped runtime")
    if missing_sdk:
        missing.append("full SDK")
    return RuntimeError(
        tr('legacy.b56d9089d8c7' ,p1=' / '.join(missing), p3=pyver, p5=target.triple, p7=release_tag, p9=pyver, p11=release_tag, p13=target.triple, p15=', '.join(available_python_versions(assets, target, kind='runtime')) or 'none', p17=', '.join(available_python_versions(assets, target, kind='sdk')) or 'none')
    )


def resolve_pbs_inputs(
    fetch_json: Callable[[str], Any], configured_tag: str, target: Target, pyver: str,
    *, fetch_text: Callable[[str], str],
) -> PBSInputs:
    """Resolve one exact PBS runtime + SDK pair.

    Automatic mode uses the uv-generated exact runtime metadata to determine the
    build tag. Both modes select the SDK from that release's public SHA256SUMS,
    avoiding the authenticated/rate-limited GitHub API entirely.
    """
    if configured_tag:
        try:
            assets = _release_assets(fetch_text, configured_tag)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            raise RuntimeError(
                tr('legacy.0acc26c43917' ,p1=configured_tag)
            ) from exc
        runtime_assets = matching_assets(assets, target, pyver, kind="runtime")
        sdk_assets = matching_assets(assets, target, pyver, kind="sdk")
        if not runtime_assets or not sdk_assets:
            raise no_asset_error(configured_tag, target, pyver, assets, missing_runtime=not runtime_assets, missing_sdk=not sdk_assets)
        runtime = runtime_assets[0]
        sdk = _best_sdk(sdk_assets, runtime.name)
        return PBSInputs(configured_tag, runtime, sdk, "release")

    data = _load_metadata(fetch_json)
    runtime = metadata_asset(data, target, pyver)
    if runtime is None:
        available = available_metadata_python_versions(data, target)
        if available and pyver not in available:
            raise RuntimeError(
                tr('legacy.8486ae0f78fe' ,p1=pyver, p3=target.triple, p5=pyver, p7=target.triple, p9=', '.join(available))
            )
        data = _load_metadata(fetch_json, force=True)
        runtime = metadata_asset(data, target, pyver)
    if runtime is None:
        raise RuntimeError(tr('legacy.4930db3b40d6' ,p1=pyver, p3=target.triple))

    match = re.search(r"/releases/download/([^/]+)/", runtime.url)
    tag = unquote(match.group(1)) if match else ""
    if not tag:
        raise RuntimeError(tr('legacy.dc7832017530' ,p1=runtime.url))

    try:
        assets = _release_assets(fetch_text, tag)
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
        # Old releases predate SHA256SUMS and publish full builds only, so the
        # metadata entry already points at the only asset carrying the SDK.
        # It is a runtime too: ensure_pbs_runtime copies its install/ tree.
        if not is_full_build_asset(runtime.name):
            raise RuntimeError(
                tr('legacy.51226f70634a' ,p1=tag, p3=runtime.name)
            ) from exc
        return PBSInputs(tag, runtime, runtime, "metadata-full")

    sdk_assets = matching_assets(assets, target, pyver, kind="sdk")
    if not sdk_assets:
        raise no_asset_error(tag, target, pyver, assets, missing_runtime=False, missing_sdk=True)
    sdk = _best_sdk(sdk_assets, runtime.name)
    return PBSInputs(tag, runtime, sdk, "metadata")


SDK_MARKER = ".ai_upper-sdk.json"


def _run_tar(tar: str, flags: str, archive: Path, destination: Path, **kwargs: Any) -> subprocess.CompletedProcess:
    """Run tar on `archive` without handing it any Windows path at all.

    Git for Windows ships GNU tar built with MSYS2. Two rounds of Windows
    failures came out of passing it a path:

    * ``tar: Cannot connect to D: resolve failed`` (exit 128) -- an absolute
      ``D:\\\\a\\\\...`` archive argument has no leading slash, so GNU tar reads
      it as an rsh ``host:path``;
    * ``tar: D:\\\\a\\\\...: Cannot open: No such file or directory`` (exit 2) --
      with the archive argument fixed, the absolute ``-C`` destination was
      still unusable, because the MSYS2 build reinterprets arguments its own
      way instead of taking a Windows path verbatim.

    So both paths leave the command line. tar runs *inside* the destination
    directory (``cwd``) with an archive name relative to it; the only thing it
    parses is a name that cannot contain a drive letter. This needs no
    GNU-only flag (``--force-local`` does not exist in macOS's bsdtar) and no
    assumption about how a particular tar build translates arguments.
    """
    archive_arg = os.path.relpath(archive, destination).replace(os.sep, "/")
    return subprocess.run([tar, flags, archive_arg], cwd=str(destination), **kwargs)


def _safe_extract_zst(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    tar = shutil.which("tar")
    if not tar:
        raise RuntimeError(tr('legacy.2b8d631eafff'))
    result = _run_tar(tar, "-axf", archive, destination, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        return
    zstd = shutil.which("zstd")
    if not zstd:
        raise RuntimeError(tr('legacy.d722543719b0' ,p1=archive.name))
    raw = archive.with_suffix("")
    subprocess.run([zstd, "-d", "-f", archive.name, "-o", raw.name], cwd=str(archive.parent), check=True)
    try:
        _run_tar(tar, "-xf", raw, destination, check=True)
    finally:
        raw.unlink(missing_ok=True)


def _sdk_metadata(root: Path) -> dict:
    """The SDK's own PYTHON.json, which is the authoritative layout record."""
    path = root / "PYTHON.json"
    if not path.is_file():
        raise RuntimeError(tr('legacy.aa9ec5e138ef' ,p1=path))
    return json.loads(path.read_text(encoding="utf-8"))


def _recorded_path(root: Path, value: Any) -> Path | None:
    """Resolve one path recorded in PYTHON.json, refusing to escape the SDK."""
    if not isinstance(value, str) or not value:
        return None
    candidate = (root / value).resolve()
    if root.resolve() not in candidate.parents:
        return None
    return candidate if candidate.is_file() else None


def _sdk_include(root: Path, metadata: dict) -> Path:
    """The include directory holding Python.h.

    PYTHON.json records it, and the value differs per platform:
    install/include/python3.10 on POSIX, install/include on Windows. Searching
    the tree is only a fallback for metadata without the field, and an ambiguous
    tree is an error rather than a silent pick between candidates.
    """
    recorded = _recorded_path(root, (metadata.get("python_paths") or {}).get("include"))
    if recorded is not None and (recorded / "Python.h").is_file():
        return recorded
    matches = sorted(path.parent for path in root.rglob("Python.h"))
    if not matches:
        raise RuntimeError(tr('legacy.3e237050c5ea' ,p1=root))
    if len(matches) > 1:
        raise RuntimeError(
            tr('legacy.53c6f4889476')
            + ", ".join(str(path) for path in matches)
        )
    return matches[0]


def _sdk_interpreter(root: Path, target: Target, metadata: dict) -> Path:
    """The target interpreter, at the path PYTHON.json records.

    PBS does not use one layout everywhere: POSIX builds put the interpreter in
    install/bin, Windows builds put python.exe next to python3XX.dll with no bin
    directory at all. Reading the recorded path is what makes one implementation
    cover both; the name guesses below only serve metadata without the field.
    """
    recorded = _recorded_path(root, metadata.get("python_exe"))
    if recorded is not None:
        return recorded
    if target.os == "windows":
        names, directories = ("python.exe", "python3.exe"), (root / "install", root)
    else:
        version = python_version()
        names = (f"python{version}", f"python{'.'.join(version.split('.')[:2])}", "python3", "python")
        directories = (root / "install" / "bin", root / "bin")
    for directory in directories:
        for name in names:
            if (directory / name).is_file():
                return directory / name
    raise RuntimeError(
        tr('legacy.a35163b0cc16' ,p1=root, p3=repr(metadata.get('python_exe'))) + ", ".join(names) + tr('legacy.64d2f058b2c6') + ", ".join(str(directory) for directory in directories)
    )


def _validate_layout(root: Path, target: Target) -> tuple[Path, dict]:
    python_root = root / "python"
    metadata = _sdk_metadata(python_root)
    install_root = python_root / "install"
    if not install_root.is_dir():
        raise RuntimeError(tr('legacy.20e7e19f4bbe' ,p1=install_root))
    # Resolve both now: a truncated or renamed archive has to fail here, not
    # after the tree has been copied into the cache.
    _sdk_interpreter(python_root, target, metadata)
    _sdk_include(python_root, metadata)
    return python_root, metadata


def resolve_inputs(target: Target) -> PBSInputs:
    return resolve_pbs_inputs(http_json, pbs_release(), target, python_version(), fetch_text=http_text)


def ensure_pbs_sdk(target: Target) -> Path:
    out = pbs_sdk_dir(target)
    existing = marker_file(out, SDK_MARKER, LEGACY_SDK_MARKER)
    if existing is not None:
        try:
            marker = json.loads(existing.read_text(encoding="utf-8"))
            if (
                marker.get("format") == 2
                and marker.get("target") == target.key
                and marker.get("python") == python_version()
                and out.exists()
            ):
                return out
        except (OSError, ValueError):
            pass

    inputs = resolve_inputs(target)
    archive = CACHE / "pbs" / inputs.tag / target.key / inputs.sdk.name
    download(inputs.sdk.url, archive)
    actual = sha256(archive)
    if inputs.sdk.sha256 and actual.lower() != inputs.sdk.sha256.lower():
        raise RuntimeError(tr('legacy.8cfb269f86ec' ,p1=inputs.sdk.sha256, p3=actual))

    extract = CACHE / "pbs" / inputs.tag / target.key / "sdk-extract"
    if extract.exists():
        shutil.rmtree(extract)
    _safe_extract_zst(archive, extract)
    python_root, metadata = _validate_layout(extract, target)
    if out.exists():
        shutil.rmtree(out)
    copy_tree_contents(python_root, out)
    marker = {
        "format": 2,
        "provider": "pbs",
        "tag": inputs.tag,
        "asset": inputs.sdk.name,
        "url": inputs.sdk.url,
        "sha256": actual,
        "target": target.key,
        "python": str(metadata.get("python_version") or python_version()),
    }
    (out / SDK_MARKER).write_text(json.dumps(marker, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def sdk_info(target: Target) -> dict:
    root = ensure_pbs_sdk(target)
    marker_path = marker_file(root, SDK_MARKER, LEGACY_SDK_MARKER)
    if marker_path is None:
        raise RuntimeError(tr('legacy.129e557d8985' ,p1=root))
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    metadata = _sdk_metadata(root)
    include = _sdk_include(root, metadata)
    executable = _sdk_interpreter(root, target, metadata)

    actual_python = str(marker.get("python") or python_version())
    return {
        "provider": "pbs",
        "sdk_root": str(root),
        "tag": marker.get("tag"),
        "asset": marker.get("asset"),
        "url": marker.get("url"),
        "sha256": marker.get("sha256"),
        "python": actual_python,
        "python_executable": str(executable),
        "include_dir": str(include),
        "python_major_minor": ".".join(actual_python.split(".")[:2]),
        "python_tag": "cp" + "".join(actual_python.split(".")[:2]),
        "python_platform_tag": target.primary_wheel_platform,
        "python_implementation_name": "cpython",
    }
