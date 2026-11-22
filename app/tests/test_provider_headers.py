"""自定义请求头（Deva `shared/provider-headers.ts`）与 403 文案的离线测试。

对齐上游 `b0f0d82` 的新行为：
- `sanitizeHeaders` / `headerIssue`：名字与值校验、保留名剔除、32 条上限；
- 请求头最后并入、同名覆盖默认的 `user-agent`；
- 403 不再报「请检查 API 密钥」，而是把服务商给的原因带出来。
"""
from __future__ import annotations

from mvvm.services.provider_gateway import http_error
from mvvm.services.provider_headers import (
    MAX_CUSTOM_HEADERS,
    header_issue,
    sanitize_headers,
)
from mvvm.services.provider_registry import provider_custom_headers, provider_headers

MODELS = {
    "providers": [
        {
            "id": "relay",
            "headers": {"originator": "codex_cli", "User-Agent": " my-ua/1.0 ", "authorization": "x"},
        },
        {"id": "plain"},
    ]
}


# ── 校验 ────────────────────────────────────────────────────────────────────
def test_header_issue_rejects_invalid_name_reserved_and_bad_value():
    assert header_issue("originator", "codex") is None
    assert header_issue("bad header", "v") == "name"
    assert header_issue("Authorization", "Bearer x") == "reserved"
    assert header_issue("x-note", "中文") == "value"
    # 空名 / 空值不是「错误」，整理时直接略过（与上游同口径）
    assert header_issue("", "v") is None
    assert header_issue("x-a", "") is None


def test_sanitize_headers_lowercases_trims_and_drops_reserved():
    cleaned = sanitize_headers(
        {
            " Originator ": " codex ",
            "User-Agent": "ua/1",
            "authorization": "Bearer leak",
            "x-bad name": "v",
            "x-cjk": "中文",
            "x-empty": "   ",
            7: "not-a-string-name-is-fine but value is str",
            "x-num": 3,
        }
    )
    assert cleaned == {
        "originator": "codex",
        "user-agent": "ua/1",
        "7": "not-a-string-name-is-fine but value is str",
    }


def test_sanitize_headers_caps_at_max_and_accepts_garbage():
    raw = {f"x-{i}": "v" for i in range(MAX_CUSTOM_HEADERS + 5)}
    assert len(sanitize_headers(raw)) == MAX_CUSTOM_HEADERS
    for garbage in (None, [], "x", 3, {"a": None}):
        assert sanitize_headers(garbage) == {}


# ── 并入请求头 ─────────────────────────────────────────────────────────────
def test_provider_headers_merge_custom_last_and_override_ua():
    custom = provider_custom_headers("relay", MODELS)
    assert custom == {"originator": "codex_cli", "user-agent": "my-ua/1.0"}

    headers = provider_headers("https://relay.test/v1", "sess", "", "relay", MODELS)
    assert headers["originator"] == "codex_cli"
    # 自定义头在最后并入：同名覆盖默认 UA，而不是并排发两条
    assert headers["user-agent"] == "my-ua/1.0"
    # 保留名即使写进配置也不会被发出
    assert "authorization" not in headers


def test_provider_headers_without_custom_headers_unchanged():
    baseline = provider_headers("https://api.deepseek.com", "sess-1", "", "plain", MODELS)
    assert baseline == {"user-agent": baseline["user-agent"]}
    assert baseline["user-agent"].startswith("deva/")

    # opencode 的 session 头仍在，且 providerId 缺省时行为与旧签名一致
    opencode = provider_headers("https://opencode.ai/inference", None, run_id="run-1")
    assert opencode["x-opencode-session"] == "run-1"
    assert "originator" not in opencode


def test_provider_custom_headers_tolerates_missing_provider():
    assert provider_custom_headers("nope", MODELS) == {}
    assert provider_custom_headers("relay", None) == {}
    assert provider_custom_headers("relay", {"providers": "bad"}) == {}


# ── 403 文案 ───────────────────────────────────────────────────────────────
def test_403_carries_provider_reason_instead_of_key_advice():
    body = '{"error":{"message":"model not allowed for this account"}}'
    err = http_error(403, body)
    assert err.kind == "auth"
    assert err.retryable is False
    assert err.status == 403
    assert "403" in err.message
    assert "model not allowed for this account" in err.message
    # 解析出 message 后只显示原因，不把整段 JSON 原样塞给用户
    assert '{"error"' not in err.message
    # 有正文原因时只显示原因（上游 `hint || advice` 同一取舍），不再给通用建议
    assert "请检查 API 密钥、账号对该模型的权限" not in err.message


def test_403_json_message_and_error_fields():
    message = http_error(403, '{"message":"quota exhausted, contact admin"}')
    assert "quota exhausted, contact admin" in message.message
    assert '{"message"' not in message.message

    error = http_error(403, '{"error":"region not supported"}')
    assert "region not supported" in error.message
    assert '{"error"' not in error.message


def test_403_plain_text_and_truncation():
    plain = http_error(403, "Forbidden: model not enabled")
    assert "Forbidden: model not enabled" in plain.message

    long_body = "x" * 300
    truncated = http_error(403, long_body)
    assert truncated.message.endswith("：" + "x" * 200)
    assert len(truncated.message) < len(long_body)


def test_403_html_body_falls_back_to_advice():
    err = http_error(403, "<html><body>Blocked by WAF</body></html>")
    assert "Blocked by WAF" not in err.message
    assert "请检查 API 密钥、账号对该模型的权限" in err.message

    empty = http_error(403, "")
    assert "请检查 API 密钥、账号对该模型的权限" in empty.message


def test_401_still_says_check_api_key():
    err = http_error(401, "bad key")
    assert err.kind == "auth"
    assert "请检查 API 密钥" in err.message
