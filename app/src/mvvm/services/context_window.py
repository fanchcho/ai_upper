"""上下文窗口与输出上限（纯函数，主进程压缩触发与界面展示共用）。

逐条对齐 Deva `apps/desktop/src/shared/context.ts`：

- 窗口取值优先级：用户为单个模型填的覆盖值 > 模型 ID 自带（`-128k` / `-1m`）> 内置表 > 全局默认；
- 非 Claude 模型的「自动」窗口封顶 `AUTO_WINDOW_CAP`（标称窗口 ≠ 好用的长度）；
- 输出上限：「自动」值按协议与模型族决定，OpenAI Chat 协议返回 None（不传，交给服务商）；
- token 估算：中日韩字符按一字一 token，其余按 3.5 字符一 token；
- 压缩线与保留量：窗口 − 输出上限 − 余量；保留尾部 ≈ 30% 窗口，夹在 [2000, 40000]。

这个模块不读磁盘、不认识 Qt：配置由调用方传进来，便于离线测试。
"""
from __future__ import annotations

import re
from typing import Any, Optional

# 表里查不到、ID 也不带窗口的模型所用的默认窗口（config.json 的 compaction.defaultWindow 可改）。
DEFAULT_CONTEXT_WINDOW = 128_000

# 用户在模型详情页可填的范围（token）：超出即视为无效输入。
CONTEXT_WINDOW_RANGE = (1_000, 20_000_000)
MAX_OUTPUT_RANGE = (256, 2_000_000)

# 非 Claude 模型「自动」窗口的上限（见模块注释）。
AUTO_WINDOW_CAP = 256_000

# Claude 系的每步输出预算；保守预算（Anthropic / Responses 适配器默认值）。
OUTPUT_BUDGET_WIDE = 32_000
OUTPUT_BUDGET_SAFE = 8_192
# 输出上限未知时为回复预留的量（同 CC 的 20K）。
OUTPUT_RESERVE_UNKNOWN = 20_000
# 压缩线与窗口之间留给估算误差的余量（同 CC 的 13K）；小窗口按窗口的一成封顶。
COMPACT_BUFFER = 13_000
# 压缩后保留尾部的目标比例与上下限。
KEEP_RATIO = 0.3
KEEP_TOKENS_MIN = 2_000
KEEP_TOKENS_MAX = 40_000

# 拉丁文字等按约 3.5 字符 ≈ 1 token 估算。
CHARS_PER_TOKEN = 3.5
IMAGE_TOKENS = 1_600
DOC_TOKENS = 3_000

# 模型 → 上下文窗口规则表（按顺序匹配小写模型 ID，不锚定首尾；首条命中即用）。
# 拿不准的宁可报小：报小只是压缩来得早，报大则请求会被拒。
WINDOW_RULES: tuple[tuple[re.Pattern[str], int], ...] = tuple(
    (re.compile(pattern, re.I), window)
    for pattern, window in (
        (r"claude-(fable|mythos)", 1_000_000),
        (r"claude-(opus|sonnet)-4[-.][6-9](?!\d)|claude-(opus|sonnet|haiku)-[5-9]", 1_000_000),
        (r"claude", 200_000),
        (r"codex-spark", 100_000),
        (r"gpt-5(\.\d+)?-(chat|instant)", 128_000),
        (r"gpt-5([.-]?[4-9](?!\d)|\.\d{2,})-(mini|nano)", 272_000),
        (r"gpt-(5([.-]?[4-9](?!\d)|\.\d{2,})|[6-9])", 922_000),
        (r"gpt-5", 272_000),
        (r"gpt-4\.1", 1_047_576),
        (r"gpt-oss", 131_072),
        (r"(^|[^a-z0-9])o[134](-|$)", 200_000),
        (r"gpt|chatgpt", 128_000),
        (r"grok-4(\.1-fast|-1-fast|-fast)", 2_000_000),
        (r"grok-4\.(20|3)(?!\d)", 1_000_000),
        (r"grok-4\.([4-9]|\d{2,})", 500_000),
        (r"grok-4|grok-code|grok-build", 256_000),
        (r"grok", 131_072),
        (r"gemini", 1_048_576),
        (r"gemma-?2", 8_192),
        (r"gemma-4", 262_144),
        (r"gemma", 131_072),
        (r"deepseek-(v4|flash|pro)", 1_000_000),
        (r"deepseek", 128_000),
        (r"glm-4\.5v", 64_000),
        (r"glm-4\.\d+v", 128_000),
        (r"glm-5[.-][2-9](?!\d)|glm-[6-9]", 1_000_000),
        (r"glm-(4\.([6-9]|\d{2,})|5)", 200_000),
        (r"glm", 128_000),
        (r"qwen-plus-character", 32_768),
        (r"qwen3(\.\d+)?-coder-(plus|flash)", 1_000_000),
        (r"qwen3\.\d+-(\w+-)?(plus|flash)|qwen-(plus|flash|turbo)", 1_000_000),
        (r"qwen3\.([7-9]|\d{2,})-max", 1_000_000),
        (r"qwen3(\.\d+)?-max", 262_144),
        (r"qwen-?max", 131_072),
        (r"qwen3\.\d+", 262_144),
        (r"qwen3-(coder|next|vl-plus)|qwen3-.*2507", 262_144),
        (r"qwen3[-:]\d+b", 40_960),  # 含 Ollama 的 qwen3:8b 写法
        (r"qwen2", 32_000),
        (r"qwq", 131_072),
        (r"qwen", 128_000),
        (r"kimi-k2(-0711|-instruct$|$)", 131_072),
        (r"moonshot-v1", 128_000),
        (r"kimi-k([3-9]|\d{2,})|kimi-for-coding(?!-highspeed)|(^|/)k[3-9](\.\d+)?(-|$)", 1_000_000),
        (r"kimi|moonshot", 262_144),
        (r"minimax-m(1|[3-9])", 1_000_000),
        (r"minimax", 196_608),
        (r"doubao-seed|(^|[^a-z])seed-[12]", 256_000),
        (r"mimo-v2(\.\d+)?-pro|mimo-v2\.([5-9]|\d{2,})", 1_000_000),
        (r"mimo", 262_144),
        (r"(^|[^a-z0-9])hy[4-9](?!\d)", 1_000_000),
        (r"(^|[^a-z0-9])hy3(?!\d)", 256_000),
        (r"longcat-[2-9]", 1_000_000),
        (r"(^|[^a-z])step-[5-9]", 1_000_000),
        (r"(^|[^a-z])step-3\.[5-9]", 256_000),
        (r"mistral-large-4", 1_000_000),
        (r"ministral-3b", 128_000),
        (r"(mistral|devstral|codestral|magistral|ministral)[\w.-]*-(latest|2512|26\d\d)", 256_000),
        (r"mistral|codestral|devstral|magistral", 128_000),
        (r"llama", 32_000),
    )
)

_ID_K = re.compile(r"(\d+)k\b", re.I)
_ID_M = re.compile(r"(\d+)m\b", re.I)


def builtin_context_window(model_id: str) -> Optional[int]:
    """内置表里的窗口；查不到返回 None。"""
    lowered = (model_id or "").lower()
    for pattern, window in WINDOW_RULES:
        if pattern.search(lowered):
            return window
    return None


def _cap_auto_window(model_id: str, window: int) -> int:
    return window if "claude" in model_id.lower() else min(window, AUTO_WINDOW_CAP)


def auto_context_window(
    model_id: str, fallback: int = DEFAULT_CONTEXT_WINDOW
) -> int:
    """「自动」窗口：ID 自带（如 -128k / -1m）> 内置表 > fallback；前两者对非 Claude 封顶。"""
    km = _ID_K.search(model_id or "")
    if km:
        n = int(km.group(1))
        if 4 <= n <= 4000:
            return _cap_auto_window(model_id, n * 1000)
    mm = _ID_M.search(model_id or "")
    if mm:
        n = int(mm.group(1))
        if 1 <= n <= 10:
            return _cap_auto_window(model_id, n * 1_000_000)
    builtin = builtin_context_window(model_id)
    return _cap_auto_window(model_id, builtin) if builtin is not None else fallback


def auto_output_budget(adapter: str, model_id: str) -> Optional[int]:
    """「自动」输出上限：Claude 32K；其余 Anthropic / Responses 8K；OpenAI Chat 不传（None）。"""
    if re.search(r"claude", model_id or "", re.I):
        return OUTPUT_BUDGET_WIDE
    return None if adapter == "openai" else OUTPUT_BUDGET_SAFE


def is_cjk(code: int) -> bool:
    """中日韩文字、全角符号：一字约 1 token（各家分词器在 0.6~1.5 之间，取 1 偏保守）。"""
    return (
        0x2E80 <= code <= 0x9FFF  # 部首、标点、假名、汉字
        or 0xAC00 <= code <= 0xD7AF  # 韩文
        or 0xF900 <= code <= 0xFAFF  # 兼容汉字
        or 0xFF00 <= code <= 0xFFEF  # 全角字符
    )


def estimate_text_tokens(text: str) -> float:
    """文本 token 估算（拿不到真实用量时用）。

    统一按 3.5 字符 ≈ 1 token 会把中文低估到三分之一左右，压缩线贴近窗口时容易估少撞上限，
    故中日韩字符单独按一字一 token 计。
    """
    cjk = sum(1 for ch in text if is_cjk(ord(ch)))
    return cjk + (len(text) - cjk) / CHARS_PER_TOKEN


def format_tokens(n: int) -> str:
    """token 数的紧凑写法：1M / 1.05M / 200K / 128K（131072）/ 8K（8192）。"""
    if n >= 1_000_000:
        if n % 1_000_000 == 0:
            return f"{n // 1_000_000}M"
        if n % 1_048_576 == 0:
            return f"{n // 1_048_576}M"
        return f"{round(n / 1_000_000, 2)}M"
    if n >= 1000:
        if n % 1000 == 0:
            return f"{n // 1000}K"
        if n % 1024 == 0:
            return f"{n // 1024}K"
        return f"{round(n / 1000, 1)}K"
    return str(n)


def parse_tokens(value: Any) -> Optional[int]:
    """解析用户输入的 token 数：支持 200000 / 200,000 / 200k / 1m / 1.5M；无法解析返回 None。"""
    if not isinstance(value, str):
        return None
    cleaned = re.sub(r"[\s,_，]", "", value)
    match = re.fullmatch(r"(\d+(?:\.\d+)?)([km])?", cleaned, re.I)
    if not match:
        return None
    unit = (match.group(2) or "").lower()
    n = float(match.group(1)) * (1000 if unit == "k" else 1_000_000 if unit == "m" else 1)
    return round(n)


def valid_limit(value: Any, bounds: tuple[int, int] = CONTEXT_WINDOW_RANGE) -> bool:
    """配置里存的覆盖值是否可用（整数、落在范围内）。布尔值不算数字。"""
    return isinstance(value, int) and not isinstance(value, bool) and bounds[0] <= value <= bounds[1]


def keep_tokens_for(window: int) -> int:
    """压缩后保留尾部的目标 token 数（窗口的 30%，夹在 [2000, 40000]）。"""
    return min(KEEP_TOKENS_MAX, max(KEEP_TOKENS_MIN, round(window * KEEP_RATIO)))


def trigger_tokens(window: int, output_budget: Optional[int], trigger_ratio: Optional[float] = None) -> int:
    """触发压缩的输入量：窗口 − 输出上限 − 余量；配了 triggerRatio 时取两者中更早的那个。"""
    output = output_budget if output_budget is not None else OUTPUT_RESERVE_UNKNOWN
    by_window = window - min(output, window // 2) - min(COMPACT_BUFFER, window * 0.1)
    if trigger_ratio is not None:
        return int(min(window * trigger_ratio, by_window))
    return int(by_window)


__all__ = [
    "AUTO_WINDOW_CAP",
    "CHARS_PER_TOKEN",
    "COMPACT_BUFFER",
    "CONTEXT_WINDOW_RANGE",
    "DEFAULT_CONTEXT_WINDOW",
    "DOC_TOKENS",
    "IMAGE_TOKENS",
    "KEEP_RATIO",
    "KEEP_TOKENS_MAX",
    "KEEP_TOKENS_MIN",
    "MAX_OUTPUT_RANGE",
    "OUTPUT_BUDGET_SAFE",
    "OUTPUT_BUDGET_WIDE",
    "OUTPUT_RESERVE_UNKNOWN",
    "WINDOW_RULES",
    "auto_context_window",
    "auto_output_budget",
    "builtin_context_window",
    "estimate_text_tokens",
    "format_tokens",
    "is_cjk",
    "keep_tokens_for",
    "parse_tokens",
    "trigger_tokens",
    "valid_limit",
]
