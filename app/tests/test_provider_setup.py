"""真实 provider 装配的离线测试：配置 → 解析 → 密钥 → 适配器，全程不发网络。

这里测的是 `ModelGateway` 的接线与失败路径（未配置 / 密钥缺失 / 模型悬空），
真实网络的正确性由适配器自己的离线测试（test_anthropic_provider 等）覆盖。
"""
from __future__ import annotations

import pytest

from mvvm.services.provider_gateway import ProviderError
from mvvm.services.provider_setup import ModelGateway
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.settings_service import SettingsService

MODELS = {
    "activeModelId": "p1:claude-sonnet-5-5",
    "providers": [
        {
            "id": "p1",
            "adapter": "anthropic",
            "apiHost": "https://api.anthropic.com",
            "enabled": True,
            "models": [{"id": "claude-sonnet-5-5", "enabled": True, "contextWindow": 200_000}],
        },
        {
            "id": "p2",
            "adapter": "openai",
            "apiHost": "https://api.deepseek.com",
            "enabled": True,
            "models": [{"id": "deepseek-chat", "enabled": True}],
        },
    ],
}


@pytest.fixture()
def gateway(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    settings = SettingsService(tmp_path)
    settings.set_config({"models": MODELS})
    vault = SecretsVault(tmp_path)
    # 没有真实网络：显式给一个「一调用就失败」的传输，测试只验证装配，不发请求。
    from tests.scripted_transport import ScriptedTransport

    return ModelGateway(settings, vault, ScriptedTransport())


def test_default_model_resolves_and_provider_is_built(tmp_path, monkeypatch):
    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    settings = SettingsService(tmp_path)
    settings.set_config({"models": MODELS})
    vault = SecretsVault(tmp_path)
    vault.set_secret("p1", "sk-test-123")

    from tests.scripted_transport import ScriptedTransport

    gw = ModelGateway(settings, vault, ScriptedTransport())
    provider, model = gw.turn_provider(None, None)
    assert model == "claude-sonnet-5-5"
    assert provider.name == "anthropic"
    assert gw.api_key("p1") == "sk-test-123"
    # 密钥只进适配器，不再是网关上的可读属性
    assert not hasattr(gw, "secrets" )


def test_session_model_ref_wins_over_default(gateway):
    provider, model = gateway.turn_provider(None, "p2:deepseek-chat")
    assert model == "deepseek-chat"
    assert provider.name == "openai"


def test_dangling_session_ref_falls_back_to_default(gateway):
    """会话里定格的模型被删掉后回落全局默认，而不是带着不存在的模型发请求。"""
    provider, model = gateway.turn_provider(None, "p9:gone")
    assert model == "claude-sonnet-5-5"
    assert provider.name == "anthropic"


def test_no_usable_model_raises_not_configured(tmp_path):
    settings = SettingsService(tmp_path)
    settings.set_config({"models": {"providers": []}})
    gw = ModelGateway(settings, SecretsVault(tmp_path), None)
    with pytest.raises(ProviderError) as info:
        gw.turn_provider(None, None)
    assert "尚未配置" in info.value.error.message
    # 压缩模型在同样情况下返回 None：不压缩，而不是报错阻断回合
    assert gw.compact_model() is None


def test_compact_model_carries_provider_and_window(gateway):
    compact = gateway.compact_model()
    assert compact is not None
    assert (compact.adapter, compact.provider_id, compact.model) == (
        "anthropic",
        "p1",
        "claude-sonnet-5-5",
    )


def test_missing_secret_continues_with_empty_key(tmp_path, monkeypatch):
    """没配密钥时继续（本地 Ollama 之类可无钥），由目标服务决定是否放行。"""
    settings = SettingsService(tmp_path)
    settings.set_config({"models": MODELS})
    gw = ModelGateway(settings, SecretsVault(tmp_path), None)
    assert gw.api_key("p1") == ""
    provider, _ = gw.turn_provider(None, None)
    assert provider.api_key == ""


def test_effort_level_prefers_session_then_global(gateway):
    assert gateway.effort_level("high") == "high"
    assert gateway.effort_level(None) == "default"
    gateway.settings.set_config({"models": {**MODELS, "activeEffort": "medium"}})
    assert gateway.effort_level(None) == "medium"


def test_effort_request_is_ready_for_adapters(gateway):
    """会话档位 → 适配器参数；默认档不发任何思考参数。"""
    assert gateway.effort_for("anthropic", "claude-sonnet-5-5", "https://api.anthropic.com", "default") is None
    effort = gateway.effort_for("anthropic", "claude-sonnet-5-5", "https://api.anthropic.com", "high")
    assert effort is not None and effort.effort == "high"


def test_effort_parameter_uses_the_turn_model(gateway):
    """`effort_parameter` 是 ViewModel 唯一需要的能力：会话档位 → 本轮模型的思考参数。"""
    assert gateway.model_key() == ("anthropic", "claude-sonnet-5-5", "https://api.anthropic.com")
    assert gateway.effort_parameter("default") is None
    effort = gateway.effort_parameter("high")
    assert effort is not None and effort.effort == "high"
    # 会话定格的模型优先：换成 deepseek 时走它的表达方式（开关字段，不带 effort 值）
    other = gateway.effort_parameter("high", "p2:deepseek-chat")
    assert other is not None and other.format == "deepseek"


def test_effort_parameter_without_model_is_none(tmp_path):
    """没有可用模型时思考参数给 None：由回合边界报「未配置」，而不是在这里炸掉。"""
    settings = SettingsService(tmp_path)
    settings.set_config({"models": {"providers": []}})
    gw = ModelGateway(settings, SecretsVault(tmp_path), None)
    assert gw.model_key() == ("", "", "")
    assert gw.effort_parameter("high") is None


def test_config_changes_take_effect_on_the_next_turn(gateway):
    """设置页改了默认模型，下一轮现查即生效（ViewModel 每轮都走同一个网关）。"""
    _, model = gateway.turn_provider(None, None)
    assert model == "claude-sonnet-5-5"
    gateway.settings.set_config(
        {"models": {**MODELS, "activeModelId": "p2:deepseek-chat"}}
    )
    provider, model = gateway.turn_provider(None, None)
    assert model == "deepseek-chat"
    assert provider.name == "openai"


def test_list_models_probes_the_configured_provider(tmp_path, monkeypatch):
    """设置页的「拉取模型」：地址/适配器/密钥都从配置与密钥库现取，结果与 Deva 同形。"""
    import asyncio
    import json as jsonlib

    from tests.scripted_transport import ScriptedTransport

    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    settings = SettingsService(tmp_path)
    settings.set_config({"models": MODELS})
    vault = SecretsVault(tmp_path)
    vault.set_secret("p1", "sk-test-123")
    transport = ScriptedTransport(
        chunks=[
            jsonlib.dumps(
                {"data": [{"id": "claude-sonnet-5-5"}, {"id": "claude-haiku-5-5"}]}
            ).encode()
        ]
    )
    gw = ModelGateway(settings, vault, transport)

    result = asyncio.run(gw.list_models("p1"))

    assert result.ok is True
    # 与 Deva 一致：去重后按名称排序
    assert result.models == ("claude-haiku-5-5", "claude-sonnet-5-5")
    call = transport.calls[-1]
    assert call["url"] == "https://api.anthropic.com/v1/models"
    assert call["headers"]["x-api-key"] == "sk-test-123"


def test_list_models_failure_is_reported_not_raised(tmp_path, monkeypatch):
    """探针失败只回 ok=False，界面据此退回手动输入（不是崩溃，也不是假成功）。"""
    import asyncio

    from tests.scripted_transport import ScriptedTransport

    monkeypatch.setenv("DEVA_SECRETS_BACKEND", "file")
    settings = SettingsService(tmp_path)
    settings.set_config({"models": MODELS})
    gw = ModelGateway(
        settings, SecretsVault(tmp_path), ScriptedTransport(connect_error="连接被拒绝")
    )
    result = asyncio.run(gw.list_models("p2"))
    assert result.ok is False
    assert result.kind == "network"
    assert "连接被拒绝" in (result.message or "")


def test_compaction_section_is_read_from_config(tmp_path):
    settings = SettingsService(tmp_path)
    settings.set_config({"compaction": {"enabled": False, "triggerRatio": 0.5}})
    gw = ModelGateway(settings, SecretsVault(tmp_path), None)
    cfg = gw.compaction_settings()
    assert cfg.enabled is False
    assert cfg.trigger_ratio == 0.5
