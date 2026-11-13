"""上下文窗口 / 输出上限的纯函数测试（对齐 Deva shared/context.ts）。"""
from __future__ import annotations

from mvvm.services import context_window as cw


def test_builtin_table_hits_known_families():
    assert cw.builtin_context_window("claude-sonnet-5-5") == 1_000_000
    assert cw.builtin_context_window("claude-3-5-sonnet-20241022") == 200_000
    # 正则要求两位以上版本号；gpt-5.2 走通用 gpt-5 档
    assert cw.builtin_context_window("gpt-5.2") == 272_000
    assert cw.builtin_context_window("gpt-5.10") == 922_000
    assert cw.builtin_context_window("gpt-4.1") == 1_047_576
    assert cw.builtin_context_window("gpt-4o") == 128_000
    assert cw.builtin_context_window("gemini-2.5-pro") == 1_048_576
    assert cw.builtin_context_window("deepseek-chat") == 128_000
    # 4.6 起才进 200K 档；4.5 仍是 128K
    assert cw.builtin_context_window("glm-4.5") == 128_000
    assert cw.builtin_context_window("glm-4.6") == 200_000
    assert cw.builtin_context_window("kimi-k2-0711") == 131_072
    assert cw.builtin_context_window("qwen3:8b") == 40_960
    assert cw.builtin_context_window("llama-3.3-70b") == 32_000
    assert cw.builtin_context_window("totally-unknown") is None


def test_table_order_first_match_wins():
    """`claude` 的宽条目排在具体条目之后：不能被宽规则提前截走。"""
    assert cw.builtin_context_window("claude-fable-5") == 1_000_000
    assert cw.builtin_context_window("gpt-5-mini") == 272_000


def test_auto_window_prefers_id_suffix():
    assert cw.auto_context_window("some-model-128k") == 128_000
    # 非 Claude 模型封顶 AUTO_WINDOW_CAP：ID 里的 1m 也被压到 256K
    assert cw.auto_context_window("some-model-1m") == cw.AUTO_WINDOW_CAP
    assert cw.auto_context_window("big-model-2000k") == cw.AUTO_WINDOW_CAP
    assert cw.auto_context_window("claude-x-2000k") == 2_000_000


def test_auto_window_falls_back_to_table_then_default():
    assert cw.auto_context_window("claude-3-5-sonnet") == 200_000
    assert cw.auto_context_window("never-heard-of-it", fallback=64_000) == 64_000
    assert cw.auto_context_window("never-heard-of-it") == cw.DEFAULT_CONTEXT_WINDOW


def test_auto_window_ignores_out_of_range_suffix():
    # 3k 低于下限、5000k 高于上限：都不采信，退回表 / 默认值
    assert cw.auto_context_window("odd-model-3k") == cw.DEFAULT_CONTEXT_WINDOW
    assert cw.auto_context_window("odd-model-5000k") == cw.DEFAULT_CONTEXT_WINDOW


def test_auto_output_budget_per_adapter():
    assert cw.auto_output_budget("anthropic", "claude-opus-5-5") == 32_000
    assert cw.auto_output_budget("anthropic", "deepseek-chat") == 8_192
    assert cw.auto_output_budget("responses", "gpt-5") == 8_192
    # OpenAI Chat 协议不传 max_tokens，交给服务商
    assert cw.auto_output_budget("openai", "gpt-5") is None


def test_estimate_text_tokens_counts_cjk_separately():
    assert cw.estimate_text_tokens("") == 0
    assert cw.estimate_text_tokens("我们") == 2
    assert cw.estimate_text_tokens("abcd") == 4 / 3.5
    assert cw.estimate_text_tokens("我们abcd") == 2 + 4 / 3.5


def test_format_tokens():
    assert cw.format_tokens(1_000_000) == "1M"
    assert cw.format_tokens(200_000) == "200K"
    assert cw.format_tokens(131_072) == "128K"
    assert cw.format_tokens(8_192) == "8K"
    assert cw.format_tokens(999) == "999"
    assert cw.format_tokens(1_048_576) == "1M"


def test_parse_tokens_accepts_units_and_separators():
    assert cw.parse_tokens("200000") == 200_000
    assert cw.parse_tokens("200,000") == 200_000
    assert cw.parse_tokens("200k") == 200_000
    assert cw.parse_tokens("1m") == 1_000_000
    assert cw.parse_tokens("1.5M") == 1_500_000
    assert cw.parse_tokens("abc") is None
    assert cw.parse_tokens(200_000) is None  # 只解析字符串输入


def test_valid_limit_rejects_bool_and_float():
    assert cw.valid_limit(200_000) is True
    assert cw.valid_limit(True) is False
    assert cw.valid_limit(999) is False
    assert cw.valid_limit(20_000_001) is False


def test_keep_tokens_clamped():
    assert cw.keep_tokens_for(1_000) == cw.KEEP_TOKENS_MIN
    assert cw.keep_tokens_for(128_000) == 38_400
    assert cw.keep_tokens_for(1_000_000) == cw.KEEP_TOKENS_MAX


def test_trigger_tokens_reserves_output_and_buffer():
    # 128K 窗口、输出未知：128000 - 20000 - 12800 = 95200
    assert cw.trigger_tokens(128_000, None) == 95_200
    # 输出上限封顶半个窗口（防填错值导致每轮都压）
    assert cw.trigger_tokens(128_000, 500_000) == 128_000 - 64_000 - 12_800
    # triggerRatio 只能比默认更早
    assert cw.trigger_tokens(128_000, None, 0.5) == 64_000
    assert cw.trigger_tokens(128_000, None, 0.95) == 95_200
