"""设置页 ViewModel：服务商 / 模型 / 密钥 / 默认模型的读写语义。

对齐 Deva 渲染层 `store/models.tsx`：
- `models` 段整块写回（`config:set` 只做顶层浅合并，漏写兄弟字段即被清掉）；
- 删除服务商 → 连带删密钥、清空悬空默认模型；禁用服务商 / 删除模型同理清理默认；
- 新增模型顺带启用服务商；批量添加去重；
- 密钥明文只进密钥库，ViewModel 的属性里只有布尔状态。
"""
from __future__ import annotations

import json

import pytest

from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.settings_service import SettingsService
from mvvm.view_models.settings_vm import SettingsViewModel, split_ref

MODELS = {
    "activeModelId": "p1:claude-sonnet-5-5",
    "activeEffort": "high",
    "providers": [
        {
            "id": "p1",
            "name": "Anthropic",
            "adapter": "anthropic",
            "apiHost": "https://api.anthropic.com",
            "enabled": True,
            "models": [
                {"id": "claude-sonnet-5-5", "enabled": True, "contextWindow": 200_000},
                {"id": "claude-haiku-5-5", "enabled": False},
            ],
        },
        {
            "id": "p2",
            "name": "DeepSeek",
            "adapter": "openai",
            "apiHost": "https://api.deepseek.com",
            "enabled": False,
            "models": [{"id": "deepseek-chat", "enabled": True}],
        },
    ],
    "somethingElse": {"keep": True},
}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    settings = SettingsService(tmp_path)
    settings.set_config({"models": MODELS, "theme": "dark"})
    vault = SecretsVault(tmp_path)
    return settings, vault, SettingsViewModel(settings, vault)


def config(tmp_path) -> dict:
    return json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))


# ── 投影 ────────────────────────────────────────────────────────────────
def test_projection_lists_providers_models_and_selection(tmp_path, env):
    settings, vault, vm = env
    assert [p["id"] for p in vm.providers] == ["p1", "p2"]
    assert vm.providers[0]["adapter_label"] == "Anthropic 协议"
    assert [m["id"] for m in vm.models_of("p1")] == [
        "claude-sonnet-5-5",
        "claude-haiku-5-5",
    ]
    assert vm.models_of("p1")[0]["context_window"] == 200_000
    assert vm.active_model == "p1:claude-sonnet-5-5"
    assert vm.active_effort == "high"


def test_has_key_never_exposes_the_secret(env):
    settings, vault, vm = env
    assert vm.has_key("p1") is False
    vault.set_secret("p1", "sk-very-secret")
    assert vm.has_key("p1") is True
    # 属性里不能出现明文：只有服务商投影与选择项
    dumped = json.dumps(vm.providers, ensure_ascii=False)
    assert "sk-very-secret" not in dumped


def test_set_api_key_writes_vault_and_empty_removes(tmp_path, env):
    settings, vault, vm = env
    assert vm.set_api_key("p1", "  sk-abc  ") is True
    assert vault.get_secret("p1") == "sk-abc"
    assert "sk-abc" not in (tmp_path / "config.json").read_text(encoding="utf-8")
    assert vm.set_api_key("p1", "") is True
    assert vault.has_secret("p1") is False


# ── 服务商 ──────────────────────────────────────────────────────────────
def test_add_provider_matches_deva_defaults(tmp_path, env):
    """与 Deva `addCustomProvider` 同口径：未启用、无模型、默认 OpenAI 兼容协议。"""
    settings, vault, vm = env
    identifier = vm.add_provider("本地 Ollama", "http://127.0.0.1:11434")
    # id 形如 custom-<毫秒时间戳>，不复用旧 id
    assert identifier.startswith("custom-")
    entry = next(p for p in vm.providers if p["id"] == identifier)
    assert entry["enabled"] is False
    assert entry["models"] == []
    assert entry["adapter"] == "openai"
    assert entry["base_url"] == "http://127.0.0.1:11434"


def test_new_provider_has_placeholder_url(tmp_path, env):
    settings, vault, vm = env
    identifier = vm.add_provider("草稿")
    entry = next(p for p in vm.providers if p["id"] == identifier)
    assert entry["base_url"] == "https://"


def test_update_provider_keeps_sibling_fields(tmp_path, env):
    """改名字不能把 models / apiHost 抹掉：models 段是整块写回的。"""
    settings, vault, vm = env
    assert vm.update_provider("p1", name="Anthropic 官方") is True
    saved = config(tmp_path)["models"]
    p1 = next(p for p in saved["providers"] if p["id"] == "p1")
    assert p1["name"] == "Anthropic 官方"
    assert p1["apiHost"] == "https://api.anthropic.com"
    assert len(p1["models"]) == 2
    assert saved["activeModelId"] == "p1:claude-sonnet-5-5"
    # models 段里用户自己加的其它键也要活下来
    assert saved["somethingElse"] == {"keep": True}
    # 顶层其它段不受影响
    assert config(tmp_path)["theme"] == "dark"


def test_disable_provider_clears_its_active_model(tmp_path, env):
    settings, vault, vm = env
    assert vm.update_provider("p1", enabled=False) is True
    assert vm.active_model == ""
    assert "activeModelId" not in config(tmp_path)["models"]
    # 别的服务商的默认模型不受波及
    vm.set_active_model("p2", "deepseek-chat")
    vm.update_provider("p1", enabled=True)
    assert vm.active_model == "p2:deepseek-chat"


def test_remove_provider_deletes_secret_and_dangling_selection(tmp_path, env):
    settings, vault, vm = env
    vault.set_secret("p1", "sk-secret")
    assert vm.remove_provider("p1") is True
    assert [p["id"] for p in vm.providers] == ["p2"]
    assert vault.has_secret("p1") is False
    assert vm.active_model == ""
    assert "activeModelId" not in config(tmp_path)["models"]
    assert vm.remove_provider("p1") is False


# ── 模型 ────────────────────────────────────────────────────────────────
def test_add_model_enables_provider_and_dedupes(tmp_path, env):
    settings, vault, vm = env
    assert vm.add_model("p2", "deepseek-reasoner") is True
    entry = next(p for p in vm.providers if p["id"] == "p2")
    assert entry["enabled"] is True
    assert "deepseek-reasoner" in [m["id"] for m in entry["models"]]
    assert vm.add_model("p2", "deepseek-reasoner") is False
    assert vm.add_model("p2", "  ") is False


def test_add_models_dedupes_within_batch(tmp_path, env):
    settings, vault, vm = env
    added = vm.add_models("p2", ["a", "a", "", "b", "deepseek-chat"])
    assert added == 2
    ids = [m["id"] for m in vm.models_of("p2")]
    assert ids == ["deepseek-chat", "a", "b"]


def test_toggle_and_remove_model(tmp_path, env):
    settings, vault, vm = env
    assert vm.toggle_model("p1", "claude-haiku-5-5") is True
    assert vm.models_of("p1")[1]["enabled"] is True
    # 删掉正被选为默认的模型：默认清空，不留悬空引用
    assert vm.remove_model("p1", "claude-sonnet-5-5") is True
    assert vm.active_model == ""
    assert "activeModelId" not in config(tmp_path)["models"]
    assert vm.remove_model("p1", "claude-sonnet-5-5") is False


def test_update_model_edits_details_and_restores_auto(tmp_path, env):
    """模型详情的「恢复自动」是删键，不是写 null（落盘文件里不残留空字段）。"""
    settings, vault, vm = env
    assert vm.update_model("p1", "claude-sonnet-5-5", name="Sonnet", max_output=8192) is True
    model = vm.models_of("p1")[0]
    assert model["name"] == "Sonnet"
    assert model["context_window"] == 200_000  # 没传的字段保持不变
    assert model["max_output"] == 8192
    assert vm.update_model("p1", "claude-sonnet-5-5", clear=True) is True
    saved = vm.models_of("p1")[0]
    assert saved["context_window"] is None and saved["max_output"] is None
    raw = config(tmp_path)["models"]["providers"][0]["models"][0]
    assert "contextWindow" not in raw and "maxOutput" not in raw
    assert raw["name"] == "Sonnet"
    assert vm.update_model("p1", "ghost", name="x") is False


def test_set_active_model_rejects_unknown(tmp_path, env):
    settings, vault, vm = env
    assert vm.set_active_model("p1", "not-a-model") is False
    assert vm.active_model == "p1:claude-sonnet-5-5"
    assert vm.set_active_model("p2", "deepseek-chat") is True
    assert vm.active_model == "p2:deepseek-chat"


def test_set_active_effort_validates(tmp_path, env):
    settings, vault, vm = env
    assert vm.set_active_effort("max") is True
    assert vm.active_effort == "max"
    assert vm.set_active_effort("ultra") is False
    assert config(tmp_path)["models"]["activeEffort"] == "max"


# ── 引用与边界 ──────────────────────────────────────────────────────────
def test_split_ref_uses_first_colon_only():
    assert split_ref("p1:claude-sonnet-5-5") == ("p1", "claude-sonnet-5-5")
    assert split_ref("ollama:qwen3:8b") == ("ollama", "qwen3:8b")
    assert split_ref("nope") is None
    assert split_ref(":model") is None
    assert split_ref("p1:") is None
    assert split_ref(None) is None


def test_fresh_provider_id_is_unique_under_collision(tmp_path, env, monkeypatch):
    """同一毫秒内连建两个也必须是两个 id：撞了就顺延时间戳。"""
    settings, vault, vm = env
    monkeypatch.setattr("mvvm.view_models.settings_vm.time.time", lambda: 1_700_000_000.0)
    first = vm.add_provider("一", "http://x")
    second = vm.add_provider("二", "http://y")
    assert first == "custom-1700000000000"
    assert second == "custom-1700000000001"
    assert {first, second}.issubset({p["id"] for p in vm.providers})


def test_set_api_key_enables_provider(tmp_path, env):
    """填入密钥即自动启用服务商（Deva `setApiKey`）；清空密钥不动启用态。"""
    settings, vault, vm = env
    assert next(p for p in vm.providers if p["id"] == "p2")["enabled"] is False
    assert vm.set_api_key("p2", "sk-deepseek") is True
    assert next(p for p in vm.providers if p["id"] == "p2")["enabled"] is True
    assert vm.set_api_key("p2", "") is True
    assert next(p for p in vm.providers if p["id"] == "p2")["enabled"] is True


def test_message_property_reports_vault_failure(env, monkeypatch):
    settings, vault, vm = env

    def boom(*_args, **_kwargs):
        raise RuntimeError("钥匙串不可用")

    monkeypatch.setattr(vault, "set_secret", boom)
    assert vm.set_api_key("p1", "sk-x") is False
    assert "密钥保存失败" in vm.message
