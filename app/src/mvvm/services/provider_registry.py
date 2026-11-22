"""服务商注册表：把 `ResolvedModel` 变成**能真正发请求的适配器**，并统一请求头与模型清单探针。

对齐 Deva `providers/index.ts`（`streamChat` 统一入口）与 `providers/opencode.ts`
（`providerHeaders` / `opencodeModelsURL`）以及 `services/provider.ts`（`provider:list-models`）：

- 密钥在最后一刻注入适配器，**绝不进入配置、日志或界面**；
- 所有服务商都带 `user-agent: deva/<版本>` 自报身份——不带就是网络库的默认 UA，
  网关与服务商后台分不出这是哪个工具在调用；
- opencode.ai 的推理端点另加 `x-opencode-session`（每个对话一个稳定值），
  该网关对缺失此头的请求直接 400；
- 模型清单地址：opencode 网关只在推理根下给 `/v1/models`，各 API 路径下没有清单，
  按常规拼法必然 404。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import metadata
from typing import Any, Optional
from urllib.parse import urlsplit

from mvvm.services.anthropic_provider import AnthropicProvider
from mvvm.services.model_resolve import ResolvedModel
from mvvm.services.openai_provider import OpenAIProvider
from mvvm.services.provider_gateway import NormalizedError, Provider
from mvvm.services.provider_headers import sanitize_headers
from mvvm.services.responses_provider import ResponsesProvider
from mvvm.services.transport import CancelToken, NetworkError, Transport

LIST_MODELS_TIMEOUT_MS = 15_000
_API_SEGMENTS = {"openai", "anthropic", "google"}


def app_version() -> str:
    """本应用版本号（用于 User-Agent 自报身份）。取不到就退回 0.0.0，不抛错。"""
    for package in ("ai_upper", "deva"):
        try:
            return metadata.version(package)
        except metadata.PackageNotFoundError:
            continue
    return "0.0.0"


def _is_opencode_inference(base_url: str) -> bool:
    """该地址是否指向 opencode.ai 的推理网关（Go 或按量计费）。"""
    try:
        parsed = urlsplit(base_url.strip())
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    if not (host == "opencode.ai" or host.endswith(".opencode.ai")):
        return False
    path = parsed.path
    return path == "/inference" or path.startswith("/inference/")


def provider_headers(
    base_url: str,
    session_id: Optional[str] = None,
    run_id: str = "",
    provider_id: str = "",
    models_section: Any = None,
) -> dict[str, str]:
    """模型请求要追加的请求头（见模块注释）。

    `provider_id` 给出时，最后并入该服务商的自定义请求头（`config.models.providers[].headers`），
    同名即覆盖前面的默认头 —— 与 Deva `providerHeaders(baseURL, providerId, sessionId)` 同语义。
    自定义头已由 `sanitize_headers` 剔掉非法 / 保留名，这里不再校验。
    """
    headers = {"user-agent": f"deva/{app_version()}"}
    if _is_opencode_inference(base_url):
        stable = (session_id or "").strip() or run_id
        if stable:
            headers["x-opencode-session"] = stable
    if provider_id:
        headers.update(provider_custom_headers(provider_id, models_section))
    return headers


def provider_custom_headers(provider_id: str, models_section: Any = None) -> dict[str, str]:
    """读某服务商的自定义请求头；未填 / 找不到 / 配置非法 → 空表，永不抛错。

    `models_section` 是 `config.json` 的 `models` 段（由调用方从 SettingsService 传入，
    与上游 `providerCustomHeaders(providerId)` 现查配置同语义：改了即对下一次请求生效）。
    """
    for provider in _provider_entries(models_section):
        if provider.get("id") == provider_id:
            return sanitize_headers(provider.get("headers"))
    return {}


def _provider_entries(models_section: Any) -> list[dict[str, Any]]:
    if not isinstance(models_section, dict):
        return []
    providers = models_section.get("providers")
    if not isinstance(providers, list):
        return []
    return [item for item in providers if isinstance(item, dict)]


def opencode_models_url(base_url: str) -> Optional[str]:
    """opencode 推理网关的模型清单地址；非网关地址返回 None（走常规拼法）。"""
    if not _is_opencode_inference(base_url):
        return None
    try:
        parsed = urlsplit(base_url.strip())
    except ValueError:
        return None
    segments = [segment for segment in parsed.path.split("/") if segment]
    try:
        at = segments.index("inference")
    except ValueError:
        return None
    following = segments[at + 1] if at + 1 < len(segments) else None
    root = f"inference/{following}" if following and following not in _API_SEGMENTS else "inference"
    return f"{parsed.scheme}://{parsed.netloc}/{root}/v1/models"


def models_url(adapter: str, base_url: str) -> str:
    """模型清单地址：Anthropic 风格 `/v1/models`，其余 `/models`。"""
    base = base_url.strip().rstrip("/")
    override = opencode_models_url(base)
    if override:
        return override
    return f"{base}/v1/models" if adapter == "anthropic" else f"{base}/models"


def auth_headers(adapter: str, api_key: str) -> dict[str, str]:
    """清单探针的鉴权头：Anthropic 用 `x-api-key`，其余 Bearer。"""
    if adapter == "anthropic":
        return {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
    return {"authorization": f"Bearer {api_key}"}


def extract_model_ids(payload: Any) -> list[str]:
    """从各家 /models 响应中抽取模型 ID（OpenAI: `data[].id`；个别实现: `models[].id/name`）。"""
    if not isinstance(payload, dict):
        return []
    array = payload.get("data")
    if not isinstance(array, list):
        array = payload.get("models")
    if not isinstance(array, list):
        return []
    ids: list[str] = []
    for item in array:
        if not isinstance(item, dict):
            continue
        value = item.get("id")
        if not isinstance(value, str):
            value = item.get("name")
        if isinstance(value, str) and value and value not in ids:
            ids.append(value)
    return sorted(ids)


def build_provider(
    resolved: ResolvedModel,
    api_key: str,
    transport: Optional[Transport] = None,
    cancel: Optional[CancelToken] = None,
    session_id: Optional[str] = None,
    run_id: str = "",
    models_section: Any = None,
) -> Provider:
    """按 adapter 构造适配器；不认识的 adapter 抛错而不是退回某个协议。

    `api_key` 为空是允许的：本地 Ollama 之类可以无钥，由目标服务决定是否放行。
    `models_section` 给定时并入该服务商的自定义请求头（见 `provider_headers`）。
    """
    headers = provider_headers(
        resolved.base_url, session_id, run_id, resolved.provider_id, models_section
    )
    common = {
        "transport": transport,
        "extra_headers": headers,
        "cancel": cancel,
    }
    if resolved.adapter == "anthropic":
        return AnthropicProvider(resolved.base_url, api_key, **common)
    if resolved.adapter == "openai":
        return OpenAIProvider(resolved.base_url, api_key, **common)
    if resolved.adapter == "responses":
        return ResponsesProvider(resolved.base_url, api_key, **common)
    raise ValueError(f"未知的 provider adapter：{resolved.adapter!r}")


@dataclass(frozen=True)
class ListModelsResult:
    """模型清单探针结果（与 Deva `provider:list-models` 的返回同形）。"""

    ok: bool
    models: tuple[str, ...] = ()
    kind: Optional[str] = None
    message: Optional[str] = None


async def list_models(
    adapter: str,
    base_url: str,
    api_key: str,
    transport: Transport,
    run_id: str = "",
    provider_id: str = "",
    models_section: Any = None,
) -> ListModelsResult:
    """拉取模型清单。失败时返回 `ok=False` 与归一化后的原因，界面据此退回手动输入。"""
    from mvvm.services.provider_gateway import http_error

    url = models_url(adapter, base_url)
    headers = {"content-type": "application/json"}
    headers.update(auth_headers(adapter, api_key))
    headers.update(provider_headers(base_url, None, run_id, provider_id, models_section))
    cancel = CancelToken()
    try:
        response = await transport.post(url, headers=headers, body=b"", cancel=cancel)
    except NetworkError as exc:
        return ListModelsResult(False, kind="network", message=str(exc))
    async with _closing(response):
        if not (200 <= response.status < 300):
            text = await response.text()
            error = http_error(response.status, text)
            return ListModelsResult(False, kind=error.kind, message=error.message)
        try:
            payload = json.loads(await response.text())
        except ValueError:
            return ListModelsResult(
                False,
                kind="invalid_request",
                message="模型清单不是合法 JSON：请确认服务地址（部分服务商需填到 /v1 为止）",
            )
    return ListModelsResult(True, models=tuple(extract_model_ids(payload)))


class _closing:  # noqa: N801 - 与上下文管理器习惯一致
    """确保响应体被关闭（探针只读一次正文）。"""

    def __init__(self, response: Any) -> None:
        self._response = response

    async def __aenter__(self) -> Any:
        return self._response

    async def __aexit__(self, *exc: Any) -> None:
        await self._response.aclose()


def normalized_not_configured(what: str = "模型服务商") -> NormalizedError:
    """统一的「没配置」错误，界面据此显示设置入口而不是技术栈堆栈。"""
    return NormalizedError("invalid_request", f"尚未配置{what}：请到设置页填写服务地址、模型与 API 密钥")


__all__ = [
    "LIST_MODELS_TIMEOUT_MS",
    "ListModelsResult",
    "app_version",
    "auth_headers",
    "build_provider",
    "extract_model_ids",
    "models_url",
    "normalized_not_configured",
    "opencode_models_url",
    "provider_custom_headers",
    "provider_headers",
]
