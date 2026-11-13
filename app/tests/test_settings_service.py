"""应用配置 `config.json`：顶层浅合并、None 删除、坏文件回落空、写失败必须抛出。

对应 Deva `services/config.ts` 的 `config:get-sync` / `config:get` / `config:set`。
与 Deva 唯一的刻意差异是「落盘失败不再静默」，这里专门有一条用例守住它。
"""
from __future__ import annotations

import json
import os

import pytest

from mvvm.services.settings_service import CONFIG_FILE, SettingsService


@pytest.fixture()
def home(tmp_path):
    return tmp_path / "deva-home"


def write_config(home, data):
    home.mkdir(parents=True, exist_ok=True)
    (home / CONFIG_FILE).write_text(json.dumps(data), encoding="utf-8")


def read_config(home):
    return json.loads((home / CONFIG_FILE).read_text(encoding="utf-8"))


def test_missing_file_is_empty_config(home):
    service = SettingsService(home)
    assert service.get_config_sync() == {}
    assert service.get("theme") is None
    assert service.get("theme", "system") == "system"


def test_set_then_get_and_persist(home):
    service = SettingsService(home)
    assert service.set_config({"theme": "dark", "language": "en"}) == {"ok": True}
    assert service.get("theme") == "dark"
    assert read_config(home) == {"theme": "dark", "language": "en"}
    # 新实例 = 重启
    assert SettingsService(home).get_config_sync() == {"theme": "dark", "language": "en"}


def test_top_level_shallow_merge_replaces_nested_object(home):
    """整段替换，不是深合并：渲染层依赖这条语义整段写回模型配置。"""
    write_config(home, {"models": {"a": 1, "b": 2}, "theme": "light"})
    service = SettingsService(home)
    service.set_config({"models": {"c": 3}})
    assert read_config(home) == {"models": {"c": 3}, "theme": "light"}


def test_none_deletes_key(home):
    write_config(home, {"theme": "dark", "proxy": "http://127.0.0.1:7890"})
    service = SettingsService(home)
    service.set_config({"proxy": None})
    assert "proxy" not in read_config(home)
    assert service.get("proxy") is None
    # 删除不存在的键也不报错
    service.set_config({"nope": None})
    assert "nope" not in read_config(home)


def test_unknown_keys_are_preserved(home):
    """Deva 与本工程可能共用一个 DEVA_HOME：不认识的键原样留着，不丢数据。"""
    write_config(home, {"rendererOnlyKey": {"x": [1, 2]}})
    service = SettingsService(home)
    service.set_config({"theme": "dark"})
    assert read_config(home)["rendererOnlyKey"] == {"x": [1, 2]}


def test_snapshot_is_a_deep_copy(home):
    write_config(home, {"models": {"a": 1}})
    service = SettingsService(home)
    snapshot = service.get_config_sync()
    snapshot["models"]["a"] = 999
    snapshot["newKey"] = True
    assert service.get("models") == {"a": 1}
    assert service.get("newKey") is None


def test_corrupt_file_is_treated_as_empty(home):
    home.mkdir(parents=True, exist_ok=True)
    (home / CONFIG_FILE).write_text("{ not json", encoding="utf-8")
    service = SettingsService(home)
    assert service.get_config_sync() == {}
    # 写入时会覆盖掉坏文件
    service.set_config({"theme": "dark"})
    assert read_config(home) == {"theme": "dark"}


def test_non_object_json_is_treated_as_empty(home):
    home.mkdir(parents=True, exist_ok=True)
    (home / CONFIG_FILE).write_text("[1, 2, 3]", encoding="utf-8")
    assert SettingsService(home).get_config_sync() == {}


def test_write_failure_raises_instead_of_pretending(home):
    """Deva 的 persist() 吞异常；这里必须抛，否则界面会显示「已保存」但盘上没有。"""
    blocker = home.parent / "blocker"
    blocker.write_text("我是文件不是目录", encoding="utf-8")
    service = SettingsService(blocker / "nested")
    with pytest.raises(OSError):
        service.set_config({"theme": "dark"})
    # 内存态已改但确实没落盘，用户会看到错误提示而不是假成功
    assert not (blocker / "nested").exists()


def test_reload_rereads_disk(home):
    write_config(home, {"theme": "dark"})
    service = SettingsService(home)
    assert service.theme() == "dark"
    (home / CONFIG_FILE).write_text(json.dumps({"theme": "light"}), encoding="utf-8")
    assert service.theme() == "dark"  # 内存缓存
    service.reload()
    assert service.theme() == "light"


def test_typed_readers_clamp_invalid_values(home):
    write_config(home, {"theme": "neon", "language": "fr", "layout": "x", "dataDir": "  ", "proxy": 42})
    service = SettingsService(home)
    assert service.theme() == "system"
    assert service.language() == "zh"
    assert service.layout() == {}
    assert service.data_dir() is None
    assert service.proxy() is None


def test_typed_readers_valid_values(home):
    write_config(
        home,
        {
            "theme": "light",
            "language": "en",
            "layout": {"sidebar": 280},
            "dataDir": "/tmp/project",
            "proxy": "socks5://127.0.0.1:1080",
            "models": {"providers": {"anthropic": {"model": "claude-sonnet-5-5"}}},
        },
    )
    service = SettingsService(home)
    assert service.theme() == "light"
    assert service.language() == "en"
    assert service.layout() == {"sidebar": 280}
    assert service.data_dir() == "/tmp/project"
    assert service.proxy() == "socks5://127.0.0.1:1080"
    assert service.models_section()["providers"]["anthropic"]["model"] == "claude-sonnet-5-5"


def test_models_section_is_detached(home):
    write_config(home, {"models": {"a": 1}})
    service = SettingsService(home)
    service.models_section()["a"] = 2
    assert service.models_section() == {"a": 1}


def test_patch_must_be_object(home):
    with pytest.raises(TypeError):
        SettingsService(home).set_config(["not", "a", "dict"])  # type: ignore[arg-type]


def test_default_home_uses_deva_home_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DEVA_HOME", str(tmp_path / "custom"))
    service = SettingsService()
    service.set_config({"theme": "dark"})
    assert (tmp_path / "custom" / CONFIG_FILE).exists()


def test_written_file_is_utf8_not_escaped(home):
    service = SettingsService(home)
    service.set_config({"dataDir": "/项目/目录"})
    raw = (home / CONFIG_FILE).read_text(encoding="utf-8")
    assert "/项目/目录" in raw  # ensure_ascii=False：与 Deva 的写法一致，肉眼可核对
