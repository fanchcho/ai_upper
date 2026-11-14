"""思考等级（effort）与模型能力表。

逐条移植 Deva `apps/desktop/src/shared/effort.ts` 的规则表与判定函数。这个模块是纯函数，
不依赖 Qt / 网络，主进程（决定发什么参数）与界面（决定显示哪几档）共用同一份数据——
两边各写一份必然漂移，Deva 的注释也正是这么说的。

参数格式（ThinkFormat）：

- `standard`：Anthropic adaptive thinking + `output_config.effort`（Claude 原生）/
  OpenAI `reasoning_effort` / Responses `reasoning.effort`；
- `deepseek` / `zai` / `qwen`：国产家族在 OpenAI Chat 协议上开思考要各自的私有开关
  （`thinking.type` / `enable_thinking`），能调档的再附 `reasoning_effort`。
  格式先按服务地址判定（同一模型放在百炼上就得用通义的开关），认不出再按模型家族；
- `compat`：国产模型走 Anthropic 兼容端点——各家都认 `output_config.effort`、大多默认开着思考，
  却未必认 Claude 专属的 `adaptive`，故只发 effort。

Responses 协议不分家族，一律按 standard 发 `reasoning.effort`。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, Optional
from urllib.parse import urlparse

EffortLevel = str  # 'default' | 'low' | 'medium' | 'high' | 'xhigh' | 'max'
THINK_LEVELS: tuple[str, ...] = ("low", "medium", "high", "xhigh", "max")
EFFORT_LEVELS: tuple[str, ...] = ("default",) + THINK_LEVELS

EffortAdapter = str  # 'anthropic' | 'openai' | 'responses'
ThinkFormat = str  # 'standard' | 'deepseek' | 'zai' | 'qwen' | 'compat'


def is_effort_level(value: object) -> bool:
    return isinstance(value, str) and value in EFFORT_LEVELS


@dataclass(frozen=True)
class EffortRequest:
    """一次请求要带的思考参数（适配器据 format 拼成各家字段）。"""

    format: ThinkFormat
    # 档位值（reasoning_effort / output_config.effort）；None = 只开思考、不调档。
    effort: Optional[str] = None
    # 回放的助手消息补 reasoning_content 字段。
    reasoning_field: bool = False
    # compat 格式另发的 thinking.type：只能开不能调的发 'enabled'，默认不思考的发 'adaptive'。
    thinking: Optional[str] = None


# 模块级赋值里的 `dict[str, str]` 是**运行期求值**：PEP 563 只字符串化注解，
# 不管赋值右侧。3.8 的内置 dict 不可下标，会抛
# `TypeError: 'type' object is not subscriptable`，所以这里用 typing.Dict。
LevelMap = Dict[str, str]

LMH: LevelMap = {"low": "low", "medium": "medium", "high": "high"}
LMHX: LevelMap = {**LMH, "xhigh": "xhigh"}
LMH_MAX: LevelMap = {**LMH, "max": "max"}
FULL: LevelMap = {**LMHX, "max": "max"}
H_MAX: LevelMap = {"high": "high", "max": "max"}
L_H_MAX: LevelMap = {"low": "low", "high": "high", "max": "max"}


@dataclass(frozen=True)
class Rule:
    match: re.Pattern[str]
    # 支持的档；None = 不支持思考等级（选择器整个隐藏、恒按「默认」发）。toggle 规则可省略。
    # 用 default_factory 而不是直接默认 dict：dataclass 禁止可变默认值（Python 3.11+ 直接报错）。
    levels: Optional[LevelMap] = field(default_factory=lambda: dict(LMH))
    # 该家族在 OpenAI Chat 协议上开思考的参数格式（缺省 standard）。
    format: ThinkFormat = "standard"
    # 只能开、不能调档：只发开思考的开关、不发档位值。
    toggle: bool = False
    # 开着思考时，回放的助手消息须带 reasoning_content 字段（DeepSeek 思考模式的硬要求）。
    reasoning_field: bool = False
    # 国产模型走 Anthropic 协议时按 compat 格式发：'effort' = 只发 output_config.effort；
    # 'adaptive' = 该模型默认不思考，另发 thinking.type=adaptive 打开。
    compat: Optional[str] = None
    # 只在这些协议上核实过；其余协议跳过本条、接着往下匹配。
    adapters: Optional[tuple[str, ...]] = None


def _r(
    pattern: str,
    *,
    levels: object = LMH,
    format: ThinkFormat = "standard",  # noqa: A002 - 与 Deva 字段同名
    toggle: bool = False,
    reasoning_field: bool = False,
    compat: Optional[str] = None,
    adapters: Optional[tuple[str, ...]] = None,
) -> Rule:
    return Rule(
        match=re.compile(pattern, re.I),
        levels=levels,  # type: ignore[arg-type]
        format=format,
        toggle=toggle,
        reasoning_field=reasoning_field,
        compat=compat,
        adapters=adapters,
    )


# 规则按顺序匹配（小写模型 ID，不锚定首尾——中转常加前缀 `anthropic/`、后缀 `-20251001`），首条命中即用。
# 与 Deva shared/effort.ts 的 RULES 逐条对应。
RULES: tuple[Rule, ...] = (
    # ── Anthropic：adaptive thinking + output_config.effort（4.6 起）。4.5 及更早只认 budget_tokens，未接。
    _r(r"claude-(fable|mythos)", levels=FULL),
    _r(r"claude-(opus|sonnet)-4[-.]6", levels=LMH_MAX),
    _r(r"claude-(opus|sonnet|haiku)-(4[-.][7-9]|[5-9])", levels=FULL),
    _r(r"claude", levels=None),
    # ── OpenAI：reasoning_effort（Chat）/ reasoning.effort（Responses）。chat / pro 变体先于通用规则。
    _r(r"gpt-5\.2-chat", levels={"medium": "medium", "xhigh": "xhigh"}),
    _r(r"gpt-5(\.\d+)?-chat", levels=None),
    _r(r"gpt-5-pro", levels={"high": "high"}),
    _r(r"gpt-5\.\d+-pro", levels={"medium": "medium", "high": "high", "xhigh": "xhigh"}),
    _r(r"gpt-5\.1-codex-max", levels=LMHX),
    _r(r"gpt-(5\.([6-9]|\d{2,})|[6-9])", levels=FULL),
    _r(r"gpt-5\.[2-5]", levels=LMHX),
    _r(r"gpt-5", levels=LMH),
    _r(r"gpt-oss", levels=LMH),
    _r(r"(^|[^a-z0-9])o1-mini", levels=None),
    _r(r"(^|[^a-z0-9])o[134](-|$)", levels=LMH),
    _r(r"gpt-(4|3\.5)|chatgpt", levels=None),
    # ── xAI
    _r(r"grok-4\.([6-9]|\d{2,})", levels=LMHX),
    _r(r"grok-4\.[3-5]", levels=LMH),
    _r(r"grok-3-mini", levels={"low": "low", "high": "high"}),
    _r(r"grok", levels=None),
    # ── Google（OpenAI 兼容端点认 reasoning_effort）
    _r(r"gemma-4", levels={"high": "high"}),
    _r(r"gemini", levels=LMH),
    # ── DeepSeek：thinking.type 开思考 + reasoning_effort 调档。reasoner / r1 恒在思考、无从调。
    _r(r"deepseek-(v4\.1-flash|flash)", levels=L_H_MAX, format="deepseek", reasoning_field=True),
    _r(r"deepseek-v4", levels=H_MAX, format="deepseek", reasoning_field=True),
    _r(r"deepseek-(chat|v3\.[2-9])", toggle=True, format="deepseek", reasoning_field=True),
    _r(r"deepseek", levels=None),
    # ── 智谱 GLM：thinking.type 开思考；5.2 起可附 reasoning_effort 调档。glm-4 早期型号无思考。
    _r(r"glm-5\.([3-9]|\d{2,})", levels=L_H_MAX, format="zai"),
    _r(r"glm-5-turbo", toggle=True, format="zai"),
    _r(r"glm-5", levels=H_MAX, format="zai"),
    _r(r"glm-4\.[5-9]", toggle=True, format="zai"),
    _r(r"glm", levels=None),
    # ── 通义：enable_thinking 开思考；3.8 起可附 reasoning_effort 调档。qwq 恒在思考。
    _r(r"qwen3\.([8-9]|\d{2,})", levels={"low": "low", "medium": "medium", "xhigh": "xhigh"}, format="qwen"),
    _r(r"qwq", levels=None),
    _r(r"qwen", toggle=True, format="qwen"),
    # ── Moonshot：kimi-k3 走标准 reasoning_effort（Anthropic 端点不认 thinking 参数）；
    #    k2 系用 thinking.type 开思考、不能调档。
    _r(r"kimi-k3", levels=L_H_MAX, reasoning_field=True, compat="effort"),
    _r(r"kimi-k2", toggle=True, format="deepseek"),
    # ── MiniMax：只核实了 Anthropic 端点；M3 默认不思考，须 adaptive 打开。
    _r(r"minimax-m([3-9]|\d{2,})", adapters=("anthropic", "responses"), levels=FULL, compat="adaptive"),
    # ── 豆包（火山方舟）：只核实了 Anthropic 端点，output_config.effort 各档都收。
    _r(r"doubao-seed-([2-9]|\d{2,})", adapters=("anthropic", "responses"), levels=FULL, compat="effort"),
    # ── 其余国产：参数各异、尚未核实，暂不支持
    _r(r"kimi|moonshot|minimax|doubao|ernie|hunyuan|baichuan", levels=None),
)

# 表里查不到的模型（自定义 / 中转改名）：给最通用的低 / 中 / 高三档，不认时由引擎自愈回落「默认」。
FALLBACK = _r(r"^", levels=LMH)

# 只能开不能调的模型，内部用一档 high 表示「开启」，不带档位值。
TOGGLE_MAP: LevelMap = {"high": ""}
# 同上，走 Responses 协议时：标准协议没有开关字段，发 reasoning.effort=high 表示开启。
TOGGLE_MAP_RESPONSES: LevelMap = {"high": "high"}


def _find_rule(adapter: str, model_id: str) -> Rule:
    lowered = model_id.lower()
    for rule in RULES:
        if rule.adapters and adapter not in rule.adapters:
            continue
        if rule.match.search(lowered):
            return rule
    return FALLBACK


def _endpoint_format(base_url: Optional[str]) -> Optional[ThinkFormat]:
    """按服务地址判定私有格式（官方端点）；认不出返回 None，交由模型家族决定。"""
    if not base_url:
        return None
    try:
        host = (urlparse(base_url).hostname or "").lower()
    except ValueError:
        return None
    if host == "deepseek.com" or host.endswith(".deepseek.com"):
        return "deepseek"
    if host.endswith("bigmodel.cn") or host == "z.ai" or host.endswith(".z.ai"):
        return "zai"
    if "dashscope" in host:
        return "qwen"
    return None


@dataclass(frozen=True)
class _Resolved:
    map: LevelMap
    format: ThinkFormat
    toggle: bool
    reasoning_field: bool
    thinking: Optional[str] = None


def _resolve(adapter: str, model_id: str, base_url: Optional[str] = None) -> Optional[_Resolved]:
    rule = _find_rule(adapter, model_id)
    level_map = TOGGLE_MAP if rule.toggle else rule.levels
    if level_map is None:
        return None
    family = rule.format
    if adapter == "anthropic":
        # 国产模型的 Anthropic 兼容端点用 compat；Claude 及表外模型用 Claude 原生写法。
        compat = rule.compat or ("effort" if family != "standard" else None)
        if compat is None:
            return _Resolved(level_map, "standard", False, False)
        thinking = "enabled" if rule.toggle else ("adaptive" if compat == "adaptive" else None)
        return _Resolved(level_map, "compat", rule.toggle, False, thinking)
    # Responses 是标准协议，不分家族一律发 reasoning.effort。
    if adapter == "responses":
        return _Resolved(TOGGLE_MAP_RESPONSES if rule.toggle else level_map, "standard", rule.toggle, False)
    return _Resolved(level_map, _endpoint_format(base_url) or family, rule.toggle, rule.reasoning_field)


def supported_effort_levels(adapter: str, model_id: str) -> list[str]:
    """该模型支持的档位（由低到高）；空列表 = 不支持思考等级。"""
    resolved = _resolve(adapter, model_id)
    return [level for level in THINK_LEVELS if level in resolved.map] if resolved else []


def is_toggle_effort(adapter: str, model_id: str) -> bool:
    """是否「只能开、不能调档」：选择器把唯一的一档显示为「开启」。"""
    resolved = _resolve(adapter, model_id)
    return bool(resolved and resolved.toggle)


def clamp_effort(adapter: str, model_id: str, level: str) -> str:
    """把存下的档位收敛到该模型支持的档。

    'default' 原样；支持即原样；否则先往低找最近的（省钱、不擅自加码），低处没有再往高找；
    模型不支持思考等级 → 'default'。
    """
    if level == "default":
        return "default"
    supported = supported_effort_levels(adapter, model_id)
    if level in supported:
        return level
    if level in THINK_LEVELS:
        index = THINK_LEVELS.index(level)
        for candidate in reversed(THINK_LEVELS[:index]):
            if candidate in supported:
                return candidate
        for candidate in THINK_LEVELS[index + 1:]:
            if candidate in supported:
                return candidate
    return "default"


def effort_request(
    adapter: str, model_id: str, base_url: Optional[str], level: str
) -> Optional[EffortRequest]:
    """某档（须已收敛）对应的请求参数；'default' / 不支持 → None（不发任何思考参数）。"""
    if level == "default":
        return None
    resolved = _resolve(adapter, model_id, base_url)
    if resolved is None or level not in resolved.map:
        return None
    value = resolved.map[level]
    if resolved.toggle:
        # 只能开不能调：不带档位值，必要时另发开关。
        return EffortRequest(
            format=resolved.format,
            effort=None,
            reasoning_field=resolved.reasoning_field,
            thinking=resolved.thinking or ("enabled" if resolved.format == "compat" else None),
        )
    return EffortRequest(
        format=resolved.format,
        effort=value or None,
        reasoning_field=resolved.reasoning_field,
        thinking=resolved.thinking,
    )


__all__ = [
    "EFFORT_LEVELS",
    "EffortLevel",
    "EffortRequest",
    "FALLBACK",
    "RULES",
    "THINK_LEVELS",
    "clamp_effort",
    "effort_request",
    "is_effort_level",
    "is_toggle_effort",
    "supported_effort_levels",
]
