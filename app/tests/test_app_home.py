"""数据根目录与旧名兼容：改名不能丢用户配置，也不能让旧配置静默失效。

覆盖两件事：
- `utils.app_home.app_home()` 的判定顺序（新变量 > 旧变量 > 新目录 > 旧目录）；
- 打包工具与 `utils.paths` 对旧 `[tool.py_upper]` 段 / 旧环境变量的兼容读取。
"""
from __future__ import annotations

import json
from pathlib import Path

# 宿主固定的工作区根：工程目录已改名为 ai_upper，但宿主的 workspaceRoot 仍写死这条
# 旧路径，磁盘上以软链 `py_upper -> ai_upper` 兼容；历史报告里也留着这条前缀。
# 常量保持旧值，下面按它把历史文本规范化掉。
# 文档里写死它是「记录真实路径」，不是残留旧名——CI 的检出根在别处，
# 所以这里必须是常量，不能靠 `str(root)` 推导。
HOST_FIXED_WORKSPACE = "/home/agent/shared_workspace/py_upper"


def _isolate_home(monkeypatch, tmp_path):
    """把 `Path.home()` 指到临时目录，避免读到真机上的 `~/.ai_upper` / `~/.deva`。"""
    home = tmp_path / "user"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.delenv("AI_UPPER_HOME", raising=False)
    monkeypatch.delenv("DEVA_HOME", raising=False)
    return home


def test_app_home_prefers_the_new_directory(tmp_path, monkeypatch):
    home = _isolate_home(monkeypatch, tmp_path)
    (home / ".deva").mkdir()
    (home / ".ai_upper").mkdir()

    from utils.app_home import app_home

    assert app_home() == home / ".ai_upper"


def test_app_home_keeps_using_the_legacy_directory(tmp_path, monkeypatch):
    home = _isolate_home(monkeypatch, tmp_path)
    (home / ".deva").mkdir()

    from utils.app_home import app_home

    assert app_home() == home / ".deva"


def test_app_home_defaults_to_the_new_name_on_a_fresh_machine(tmp_path, monkeypatch):
    home = _isolate_home(monkeypatch, tmp_path)

    from utils.app_home import app_home

    assert app_home() == home / ".ai_upper"


def test_app_home_prefers_the_new_variable_over_the_legacy_one(tmp_path, monkeypatch):
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.setenv("DEVA_HOME", str(tmp_path / "legacy"))
    monkeypatch.setenv("AI_UPPER_HOME", str(tmp_path / "current"))

    from utils.app_home import app_home

    assert app_home() == tmp_path / "current"


def test_app_home_still_honours_deva_home(tmp_path, monkeypatch):
    _isolate_home(monkeypatch, tmp_path)
    monkeypatch.setenv("DEVA_HOME", str(tmp_path / "legacy"))

    from utils.app_home import app_home

    assert app_home() == tmp_path / "legacy"


def test_services_and_entries_share_one_data_home(tmp_path, monkeypatch):
    """五个服务原先各读一遍 `DEVA_HOME`；目录判定现在只有一份实现。"""
    _isolate_home(monkeypatch, tmp_path)
    (tmp_path / "user" / ".deva").mkdir()

    from mvvm.services.chat_session_store import ChatSessionStore
    from mvvm.services.persona_store import PersonaStore
    from mvvm.services.secrets_vault import SecretsVault
    from mvvm.services.settings_service import default_home

    expected = tmp_path / "user" / ".deva"
    assert default_home() == expected
    assert ChatSessionStore().home == expected
    assert PersonaStore().home == expected
    assert SecretsVault()._home == expected  # 密钥库不对外暴露 home，直接看落点


def test_packager_reads_a_legacy_configuration_section(monkeypatch):
    """改名前的 `[tool.py_upper]` 工作副本还能直接构建。"""
    import ai_upper.config as config

    monkeypatch.setattr(config, "load_app_config", lambda: {
        "project": {"version": "0.17.33"},
        "tool": {"py_upper": {"app": {"name": "Legacy App", "identifier": "com.example.legacy"}}},
    })
    assert config.app_name() == "Legacy App"
    assert config.app_identifier() == "com.example.legacy"


def test_the_current_section_wins_over_the_legacy_one(monkeypatch):
    import ai_upper.config as config

    monkeypatch.setattr(config, "load_app_config", lambda: {
        "project": {"version": "0.17.33"},
        "tool": {
            "py_upper": {"app": {"name": "Legacy App"}},
            "ai_upper": {"app": {"name": "Current App"}},
        },
    })
    assert config.app_name() == "Current App"


def test_packager_falls_back_to_the_new_name(tmp_path, monkeypatch):
    import ai_upper.config as config

    monkeypatch.setattr(config, "load_app_config", lambda: {"project": {"version": "0.17.33"}, "tool": {}})
    assert config.app_name() == "ai_upper"


def test_paths_reads_the_legacy_name_variable(monkeypatch):
    from utils import paths

    monkeypatch.delenv(paths.APP_NAME_ENV, raising=False)
    monkeypatch.setenv("PY_UPPER_APP_NAME", "Legacy Name")
    assert paths.app_name() == "Legacy Name"


def test_paths_reads_the_legacy_bundle_home(monkeypatch, tmp_path):
    from utils import paths

    monkeypatch.delenv(paths.BUNDLE_HOME_ENV, raising=False)
    monkeypatch.setenv("PY_UPPER_HOME", str(tmp_path))
    assert paths.bundle_home() == tmp_path.resolve()


def test_paths_reads_a_legacy_app_name_section(tmp_path, monkeypatch):
    from utils import paths

    project = tmp_path / "app" / "pyproject.toml"
    project.parent.mkdir(parents=True)
    project.write_text('[tool.py_upper.app]\nname = "Legacy Name"\n', encoding="utf-8")
    module = project.parent / "src" / "utils" / "paths.py"
    module.parent.mkdir(parents=True)
    module.write_text("", encoding="utf-8")
    monkeypatch.setattr(paths, "__file__", str(module))

    assert paths._declared_app_name() == "Legacy Name"


def test_lock_reads_the_legacy_file_but_writes_the_new_one(tmp_path, monkeypatch):
    from ai_upper import lock as lock_module

    legacy = tmp_path / "py_upper.lock.json"
    legacy.write_text('{"format": 5}', encoding="utf-8")
    monkeypatch.setattr(lock_module, "LOCK", tmp_path / "ai_upper.lock.json")
    monkeypatch.setattr(lock_module, "LEGACY_LOCK", legacy)

    assert lock_module.lock_path() == legacy


def test_egg_loader_reads_the_legacy_cache_variable(monkeypatch, tmp_path):
    from ai_upper import egg_loader

    monkeypatch.delenv("AI_UPPER_EGG_CACHE", raising=False)
    monkeypatch.setenv("PY_UPPER_EGG_CACHE", str(tmp_path / "cache"))
    assert egg_loader._cache_root() == str(tmp_path / "cache")


def test_cached_runtime_still_counts_after_the_rename(tmp_path, monkeypatch):
    """旧名标记的运行时缓存要照旧命中：否则每次构建重下几百 MB 并解压 zstd。"""
    from ai_upper import runtime

    out = tmp_path / "runtimes" / "linux-arm64" / "3.13.5"
    out.mkdir(parents=True)
    (out / ".py_upper-runtime.json").write_text(
        json.dumps({
            "format": 1, "provider": "pbs", "tag": "20250723",
            "target": "linux-arm64", "python": runtime.python_version(),
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime, "target_runtime_dir", lambda target: out)
    monkeypatch.setattr(runtime, "pbs_release", lambda: "")

    target = type("Target", (), {"key": "linux-arm64"})()
    assert runtime.ensure_pbs_runtime(target) == out


def test_cached_sdk_still_counts_after_the_rename(tmp_path, monkeypatch):
    from ai_upper import pbs

    out = tmp_path / "sdk"
    out.mkdir()
    (out / ".py_upper-sdk.json").write_text(
        json.dumps({
            "format": 2, "provider": "pbs", "tag": "20250723",
            "target": "linux-arm64", "python": pbs.python_version(),
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(pbs, "pbs_sdk_dir", lambda target: out)

    target = type("Target", (), {"key": "linux-arm64"})()
    assert pbs.ensure_pbs_sdk(target) == out


def test_marker_reads_the_new_name_first(tmp_path):
    from ai_upper.fs import marker_file

    (tmp_path / ".py_upper-runtime.json").write_text("{}", encoding="utf-8")
    assert marker_file(tmp_path, ".ai_upper-runtime.json", ".py_upper-runtime.json").name == ".py_upper-runtime.json"
    (tmp_path / ".ai_upper-runtime.json").write_text("{}", encoding="utf-8")
    assert marker_file(tmp_path, ".ai_upper-runtime.json", ".py_upper-runtime.json").name == ".ai_upper-runtime.json"
    assert marker_file(tmp_path / "empty", ".ai_upper-runtime.json", ".py_upper-runtime.json") is None


def test_repository_keeps_no_stale_old_name(tmp_path):
    """改名的验收线：仓库里只允许「显式兼容旧名」这几处提到旧拼写。"""
    root = Path(__file__).parents[2]
    allowed = {
        "README.md",
        "tools/ai_upper/config.py",
        "tools/ai_upper/egg_loader.py",
        "tools/ai_upper/lock.py",
        "tools/ai_upper/third_party.py",
        "app/src/utils/app_home.py",
        "app/src/utils/paths.py",
        "launcher/src/AiUpper.cpp",
        "app/tests/test_app_home.py",
    }
    offenders: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".cpp", ".h", ".md", ".toml", ".yml", ".json", ".js", ".sh"}:
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith(("out/", ".git/", ".cache/", "build/", "dist/", "runtimes/")):
            continue
        if relative in allowed:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # 工作区根目录由宿主固定，不随改名移动；它的绝对路径出现在历史证据里
        # 是记录而不是命名，替换掉再查。
        #
        # 这个路径是**常量**：CI 的检出根是另一条路径（`/home/agent/work/...`），
        # 只剔除 `str(root)` 时，文档里写死的宿主路径会留下来，被当成残留旧名——
        # 本机跑绿、CI 十二条 job 全红正是这么来的。
        for host_fixed in (str(root), HOST_FIXED_WORKSPACE):
            text = text.replace(host_fixed, "<repo>")
        for old in ("py_upper", "PY_UPPER", "PyUpper", "pyupper"):
            if old in text:
                offenders.append(f"{relative}: {old}")
                break
    assert not offenders, offenders

