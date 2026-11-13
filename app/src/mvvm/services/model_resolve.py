"""模型引用解析：`"providerId:modelId"` → 可发请求的三元组。

逐条对齐 Deva `services/model-resolve.ts`：

- 引用格式 `"providerId:modelId"`，按**首个冒号**切分——providerId 由本应用生成、不含冒号，
  而模型 id 可以带冒号（Ollama 的 `qwen3:8b`）；用 `split(':')` 解包会把模型 id 截断成 `qwen3`，
  于是每一条 Ollama 模型都「找不到」，界面误报「尚未选择模型」；
- 解析**永不抛错**：空引用 / 非法 / 悬空一律返回 None，由调用方决定回落还是报错；
- 只读 `config.json` 的 `models.providers`（明文非敏感项）；API 密钥不在这里出现。

这里只做纯数据解析，不认识 Qt、不读磁盘（配置由调用方传进来，便于测试）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# 与 Deva shared/context.ts 同口径
CONTEXT_WINDOW_RANGE = (1_000, 20_000_000)
MAX_OUTPUT_RANGE = (256, 2_000_000)

ADAPTERS = ("anthropic", "openai", "responses")


@dataclass(frozen=True)
class ResolvedModel:
    """一次请求要用的完整模型配置。"""

    adapter: str
    provider_id: str
    base_url: str
    model: str

    @property
    def ref(self) -> str:
        return f"{self.provider_id}:{self.model}"


def valid_limit(value: Any, bounds: tuple[int, int]) -> bool:
    """配置里存的覆盖值是否可用（整数、落在范围内）。"""
    return isinstance(value, int) and not isinstance(value, bool) and bounds[0] <= value <= bounds[1]


def _providers(models_section: Any) -> list[dict[str, Any]]:
    if not isinstance(models_section, dict):
        return []
    providers = models_section.get("providers")
    return [p for p in providers if isinstance(p, dict)] if isinstance(providers, list) else []


def _adapter_of(provider: dict[str, Any]) -> str:
    adapter = provider.get("adapter")
    return adapter if adapter in ADAPTERS else "anthropic"


def split_ref(ref: Any) -> Optional[tuple[str, str]]:
    """按首个冒号切分 `"providerId:modelId"`；无效返回 None。"""
    if not isinstance(ref, str):
        return None
    index = ref.find(":")
    if index <= 0:
        return None
    provider_id = ref[:index].strip()
    model_id = ref[index + 1:].strip()
    return (provider_id, model_id) if provider_id and model_id else None


def resolve_ref(ref: Any, models_section: Any) -> Optional[ResolvedModel]:
    """严格解析引用；空 / 非法 / 找不到 / 配置异常一律 None（永不抛错）。"""
    parts = split_ref(ref)
    if parts is None:
        return None
    provider_id, model_id = parts
    provider = next((p for p in _providers(models_section) if p.get("id") == provider_id), None)
    if provider is None:
        return None
    models = provider.get("models")
    model = next(
        (m for m in models if isinstance(m, dict) and m.get("id") == model_id), None
    ) if isinstance(models, list) else None
    if model is None:
        return None
    base_url = provider.get("apiHost")
    return ResolvedModel(
        adapter=_adapter_of(provider),
        provider_id=provider_id,
        base_url=base_url if isinstance(base_url, str) else "",
        model=str(model["id"]),
    )


def resolve_model_ref(ref: Any, models_section: Any, fallback: ResolvedModel) -> ResolvedModel:
    """解析引用；失败回落 fallback（子智能体「跟随主对话」的口径）。"""
    return resolve_ref(ref, models_section) or fallback


def resolve_default_model(models_section: Any) -> Optional[ResolvedModel]:
    """全局默认模型（`models.activeModelId`，即用户最近一次选定的模型）。"""
    if not isinstance(models_section, dict):
        return None
    return resolve_ref(models_section.get("activeModelId"), models_section)


@dataclass(frozen=True)
class ModelOverrides:
    """用户在模型详情页填的上下文窗口 / 输出上限；未填即「自动」。"""

    context_window: Optional[int] = None
    max_output: Optional[int] = None


def model_overrides(provider_id: str, model_id: str, models_section: Any) -> ModelOverrides:
    """按 providerId + 模型 ID 现查覆盖值；未填 / 非法 / 找不到 → 对应字段缺省。"""
    provider = next((p for p in _providers(models_section) if p.get("id") == provider_id), None)
    if provider is None:
        return ModelOverrides()
    models = provider.get("models")
    model = next(
        (m for m in models if isinstance(m, dict) and m.get("id") == model_id), None
    ) if isinstance(models, list) else None
    if model is None:
        return ModelOverrides()
    context_window = model.get("contextWindow")
    max_output = model.get("maxOutput")
    return ModelOverrides(
        context_window=context_window if valid_limit(context_window, CONTEXT_WINDOW_RANGE) else None,
        max_output=max_output if valid_limit(max_output, MAX_OUTPUT_RANGE) else None,
    )


def usable_models(models_section: Any) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """可在对话里选用的模型：已启用服务商（purpose 缺省视为 llm）× 已启用模型。"""
    out: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for provider in _providers(models_section):
        if provider.get("enabled") is not True:
            continue
        if provider.get("purpose", "llm") != "llm":
            continue
        models = provider.get("models")
        for model in models if isinstance(models, list) else []:
            if isinstance(model, dict) and model.get("enabled") is True and isinstance(model.get("id"), str):
                out.append((str(provider["id"]), provider, model))
    return out


def has_usable_model(models_section: Any) -> bool:
    return bool(usable_models(models_section))


__all__ = [
    "ADAPTERS",
    "CONTEXT_WINDOW_RANGE",
    "MAX_OUTPUT_RANGE",
    "ModelOverrides",
    "ResolvedModel",
    "has_usable_model",
    "model_overrides",
    "resolve_default_model",
    "resolve_model_ref",
    "resolve_ref",
    "split_ref",
    "usable_models",
    "valid_limit",
]
