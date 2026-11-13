"""SSE 分帧、思考等级映射、模型引用解析、服务商注册表的离线测试。"""
from __future__ import annotations

import asyncio
import json

import pytest

from mvvm.services.effort import (
    clamp_effort,
    effort_request,
    is_toggle_effort,
    supported_effort_levels,
)
from mvvm.services.model_resolve import (
    ModelOverrides,
    has_usable_model,
    model_overrides,
    resolve_default_model,
    resolve_model_ref,
    resolve_ref,
    split_ref,
    usable_models,
    valid_limit,
)
from mvvm.services.provider_registry import (
    app_version,
    auth_headers,
    build_provider,
    extract_model_ids,
    models_url,
    opencode_models_url,
    provider_headers,
)
from mvvm.services.sse import StreamIdleError, iterate_sse
from mvvm.services.provider_gateway import GenerateRequest
from mvvm.services.anthropic_provider import AnthropicProvider
from mvvm.services.openai_provider import OpenAIProvider
from mvvm.services.responses_provider import ResponsesProvider

from scripted_transport import ScriptedTransport


# ── SSE ─────────────────────────────────────────────────────────────────────
async def _chunks(*items):
    for item in items:
        yield item


async def _collect_sse(*items, idle_ms=0):
    return [event async for event in iterate_sse(_chunks(*items), idle_ms)]


def test_sse_parses_events_and_ignores_comments():
    events = asyncio.run(
        _collect_sse(b": keep-alive\n\n", b"event: ping\ndata: {\"a\":1}\n\n", b"data: line1\ndata: line2\n\n")
    )
    # 心跳注释块不产出事件；带 event 名的照常带出
    assert [(e.event, e.data) for e in events] == [("ping", '{"a":1}'), (None, "line1\nline2")]


def test_sse_crlf_and_split_across_reads():
    events = asyncio.run(_collect_sse(b"data: hel", b"lo\r\n\r\n"))
    assert [e.data for e in events] == ["hello"]


def test_sse_block_without_data_is_skipped():
    events = asyncio.run(_collect_sse(b"event: ping\n\n", b"data: ok\n\n"))
    assert [e.data for e in events] == ["ok"]


def test_sse_idle_timeout_raises():
    async def slow():
        yield b"data: a\n\n"
        await asyncio.sleep(5)
        yield b"data: b\n\n"

    async def scenario():
        seen = []
        with pytest.raises(StreamIdleError):
            async for event in iterate_sse(slow(), idle_ms=10):
                seen.append(event)
        return seen

    assert [e.data for e in asyncio.run(scenario())] == ["a"]


# ── effort ──────────────────────────────────────────────────────────────────
def test_effort_levels_per_model():
    assert supported_effort_levels("anthropic", "claude-opus-5-5") == ["low", "medium", "high", "xhigh", "max"]
    assert supported_effort_levels("anthropic", "claude-3-5-sonnet") == []
    assert supported_effort_levels("openai", "gpt-5-pro") == ["high"]
    assert supported_effort_levels("openai", "gpt-4o") == []


def test_effort_toggle_models():
    assert is_toggle_effort("openai", "deepseek-chat") is True
    assert is_toggle_effort("openai", "claude-opus-5-5") is False


def test_clamp_effort_prefers_lower():
    assert clamp_effort("openai", "gpt-5-pro", "max") == "high"
    assert clamp_effort("openai", "gpt-5-pro", "low") == "high"  # 低处没有就往高找
    assert clamp_effort("openai", "gpt-4o", "high") == "default"
    assert clamp_effort("anthropic", "claude-opus-5-5", "default") == "default"


def test_effort_request_shapes():
    standard = effort_request("anthropic", "claude-opus-5-5", "https://api.anthropic.com", "high")
    assert standard is not None
    assert (standard.format, standard.effort) == ("standard", "high")

    toggle = effort_request("openai", "deepseek-chat", "https://api.deepseek.com", "high")
    assert toggle is not None
    assert toggle.effort is None
    assert toggle.format == "deepseek"

    assert effort_request("openai", "gpt-4o", None, "high") is None
    assert effort_request("anthropic", "claude-opus-5-5", None, "default") is None


def test_effort_endpoint_decides_format():
    # 同一模型放在百炼上要用通义的开关（规则表里 kimi-k2 默认是 deepseek 格式）
    request = effort_request("openai", "kimi-k2", "https://dashscope.aliyuncs.com/compatible-mode/v1", "high")
    assert request is not None
    assert request.format == "qwen"

    # 换回 Moonshot 自家端点则按家族格式
    moonshot = effort_request("openai", "kimi-k2", "https://api.moonshot.cn/v1", "high")
    assert moonshot is not None
    assert moonshot.format == "deepseek"


def test_compat_format_for_non_claude_on_anthropic_endpoint():
    request = effort_request("anthropic", "deepseek-chat", "https://api.deepseek.com/anthropic", "high")
    assert request is not None
    assert request.format == "compat"
    assert request.thinking == "enabled"


# ── model_resolve ───────────────────────────────────────────────────────────
MODELS = {
    "activeModelId": "p1:claude-sonnet-5-5",
    "providers": [
        {
            "id": "p1",
            "adapter": "anthropic",
            "apiHost": "https://api.anthropic.com",
            "enabled": True,
            "models": [
                {"id": "claude-sonnet-5-5", "enabled": True, "contextWindow": 200000, "maxOutput": 64000},
                {"id": "claude-haiku-5-5", "enabled": False},
            ],
        },
        {
            "id": "p2",
            "adapter": "openai",
            "apiHost": "http://localhost:11434/v1",
            "enabled": True,
            "models": [{"id": "qwen3:8b", "enabled": True}],
        },
        {
            "id": "p3",
            "adapter": "responses",
            "enabled": False,
            "models": [{"id": "gpt-5", "enabled": True, "contextWindow": 5}],
        },
    ],
}


def test_split_ref_uses_first_colon():
    assert split_ref("p2:qwen3:8b") == ("p2", "qwen3:8b")
    assert split_ref(":x") is None
    assert split_ref("nocolon") is None
    assert split_ref(None) is None


def test_resolve_ref_keeps_colon_in_model_id():
    resolved = resolve_ref("p2:qwen3:8b", MODELS)
    assert resolved is not None
    assert resolved.model == "qwen3:8b"
    assert resolved.ref == "p2:qwen3:8b"


def test_resolve_ref_returns_none_on_misses():
    assert resolve_ref("p9:x", MODELS) is None
    assert resolve_ref("p1:nope", MODELS) is None
    assert resolve_ref(None, MODELS) is None
    assert resolve_ref("p1:x", "not a dict") is None


def test_resolve_model_ref_falls_back():
    fallback = resolve_ref("p1:claude-sonnet-5-5", MODELS)
    assert resolve_model_ref("bogus", MODELS, fallback) == fallback


def test_resolve_default_model():
    assert resolve_default_model(MODELS).model == "claude-sonnet-5-5"
    assert resolve_default_model({}) is None


def test_model_overrides_rejects_out_of_range():
    assert model_overrides("p1", "claude-sonnet-5-5", MODELS) == ModelOverrides(200000, 64000)
    assert model_overrides("p3", "gpt-5", MODELS) == ModelOverrides()  # 5 < 1000
    assert model_overrides("p1", "claude-haiku-5-5", MODELS) == ModelOverrides()


def test_valid_limit_rejects_bool_and_float():
    assert valid_limit(200000, (1000, 20_000_000)) is True
    assert valid_limit(True, (1000, 20_000_000)) is False
    assert valid_limit(2000.5, (1000, 20_000_000)) is False


def test_usable_models_only_enabled_llm():
    ids = [(pid, model["id"]) for pid, _provider, model in usable_models(MODELS)]
    assert ids == [("p1", "claude-sonnet-5-5"), ("p2", "qwen3:8b")]
    assert has_usable_model(MODELS) is True
    assert has_usable_model({"providers": []}) is False


# ── provider_registry ──────────────────────────────────────────────────────
def test_models_url_variants():
    assert models_url("anthropic", "https://api.anthropic.com") == "https://api.anthropic.com/v1/models"
    assert models_url("openai", "https://api.deepseek.com/") == "https://api.deepseek.com/models"
    assert models_url("responses", "https://api.openai.com/v1") == "https://api.openai.com/v1/models"


def test_opencode_models_url_uses_inference_root():
    assert (
        opencode_models_url("https://opencode.ai/inference/go/openai/v1")
        == "https://opencode.ai/inference/go/v1/models"
    )
    assert opencode_models_url("https://opencode.ai/inference/anthropic/v1") == "https://opencode.ai/inference/v1/models"
    assert opencode_models_url("https://api.deepseek.com") is None


def test_provider_headers_add_session_only_for_opencode():
    headers = provider_headers("https://api.deepseek.com", "sess-1")
    assert headers["user-agent"] == f"deva/{app_version()}"
    assert "x-opencode-session" not in headers

    opencode = provider_headers("https://opencode.ai/inference/go/openai/v1", "sess-1")
    assert opencode["x-opencode-session"] == "sess-1"

    fallback = provider_headers("https://opencode.ai/inference", None, run_id="run-abc")
    assert fallback["x-opencode-session"] == "run-abc"


def test_auth_headers_per_adapter():
    assert auth_headers("anthropic", "k")["x-api-key"] == "k"
    assert auth_headers("anthropic", "k")["anthropic-version"] == "2023-06-01"
    assert auth_headers("openai", "k") == {"authorization": "Bearer k"}


def test_extract_model_ids_sorted_and_deduped():
    payload = {"data": [{"id": "b"}, {"id": "a"}, {"id": "a"}, {"name": "c"}, {}]}
    assert extract_model_ids(payload) == ["a", "b", "c"]
    assert extract_model_ids({"models": [{"id": "z"}]}) == ["z"]
    assert extract_model_ids(None) == []


def test_build_provider_per_adapter():
    from mvvm.services.model_resolve import ResolvedModel

    for adapter, expected in (
        ("anthropic", AnthropicProvider),
        ("openai", OpenAIProvider),
        ("responses", ResponsesProvider),
    ):
        resolved = ResolvedModel(adapter=adapter, provider_id="p", base_url="https://x.test", model="m")
        provider = build_provider(resolved, "sk-1")
        assert isinstance(provider, expected)
        # 密钥不能出现在发出去的请求体里
        body = provider.build_body(GenerateRequest(model="m", messages=[]))
        assert "sk-1" not in json.dumps(body, ensure_ascii=False)

    with pytest.raises(ValueError):
        build_provider(ResolvedModel("nope", "p", "https://x.test", "m"), "k")


def test_list_models_success_and_failure():
    from mvvm.services.provider_registry import list_models

    transport = ScriptedTransport(
        chunks=[b'{"data":[{"id":"m2"},{"id":"m1"}]}'], headers={"content-type": "application/json"}
    )
    result = asyncio.run(list_models("openai", "https://x.test", "k", transport))
    assert result.ok is True
    assert result.models == ("m1", "m2")
    assert transport.calls[0]["url"] == "https://x.test/models"

    failing = ScriptedTransport(status=401, chunks=[b'{"error":"bad key"}'])
    failed = asyncio.run(list_models("anthropic", "https://x.test", "k", failing))
    assert failed.ok is False
    assert failed.kind == "auth"
    assert failing.calls[0]["url"] == "https://x.test/v1/models"


def test_list_models_network_failure():
    from mvvm.services.provider_registry import list_models

    transport = ScriptedTransport(connect_error="连接失败")
    result = asyncio.run(list_models("openai", "https://x.test", "k", transport))
    assert result.ok is False
    assert result.kind == "network"
