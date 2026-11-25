"""服务商装配：把 config.json、密钥库与模型引用解析接成「本轮要用的 provider」。

这是 Deva `providers/index.ts` 的 `streamChat(cfg, req)` 在 Python 侧的对位物：
上层（ViewModel）只说「这一轮用哪个模型」，由这里负责

1. 解析模型引用（`session.model` → 全局默认 `models.activeModelId`，两端都无 → 明确报「未配置」）；
2. 到密钥库取该服务商的密钥（取不到按空串继续——本地 Ollama 之类本来就可以无钥）；
3. 按 adapter 构造适配器，并把取消标记、会话 id、服务商专有头一起带上。

密钥只在本层出现一次，注入适配器后不再被读；`describe()` 之类对外接口只回布尔值。
"""
from __future__ import annotations

from typing import Any, Optional

from mvvm.services.compaction import CompactModel, compaction_config
from mvvm.services.effort import effort_request
from mvvm.services.http_client import ProxyConfig
from mvvm.services.model_resolve import ResolvedModel, resolve_default_model, resolve_ref
from mvvm.services.provider_gateway import Provider
from mvvm.services.provider_registry import (
    ListModelsResult,
    build_provider,
    list_models,
    normalized_not_configured,
)
from mvvm.services.provider_gateway import ProviderError
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.settings_service import SettingsService
from mvvm.services.transport import CancelToken, HttpxTransport, Transport

# 会话没定格思考等级时的全局兜底（Deva `resolveDefaultEffort`）。
DEFAULT_EFFORT = "default"


def build_transport(proxy: Optional[str] = None) -> Transport:
    """真实网络传输：代理按 Deva 口径判定（环境变量，`config.proxy` 优先覆盖）。"""
    if proxy:
        return HttpxTransport(lambda url: proxy)
    proxy_config = ProxyConfig.from_env()
    return HttpxTransport(proxy_config.for_url)


class ModelGateway:
    """把「配置 + 密钥 + 传输」装配成本轮可用的 provider。纯 Python，不认识 Qt。"""

    def __init__(
        self,
        settings: SettingsService,
        vault: SecretsVault,
        transport: Optional[Transport] = None,
    ) -> None:
        self.settings = settings
        self.vault = vault
        self._transport = transport

    # ── 解析 ──────────────────────────────────────────────────────────────
    def turn_model(self, model_ref: Optional[str] = None) -> ResolvedModel:
        """本轮模型：会话里定格的引用优先，空/悬空回落全局默认；都没有则抛「未配置」。

        与 Deva `resolveModelRef(session.model, model)` 同语义——删除的模型自动回落默认，
        而不是让对话带着一个不存在的模型继续跑。
        """
        from mvvm.services.plugin_settings import PluginSettings
        direct = PluginSettings(self.settings, self.vault).route()
        if direct is not None:
            return direct
        section = self.settings.models_section()
        resolved = resolve_ref(model_ref, section) or resolve_default_model(section)
        if resolved is None:
            raise ProviderError(normalized_not_configured("可用的模型（请在设置中选定默认模型）"))
        return resolved

    def compact_model(self, model_ref: Optional[str] = None) -> Optional[CompactModel]:
        """压缩用的模型配置；没有可用模型时返回 None（= 本回合不压缩，而不是报错）。"""
        try:
            resolved = self.turn_model(model_ref)
        except ProviderError:
            return None
        return CompactModel(
            adapter=resolved.adapter,
            provider_id=resolved.provider_id,
            base_url=resolved.base_url,
            model=resolved.model,
        )

    def effort_level(self, session_effort: Optional[str]) -> str:
        """思考等级：会话定格值 > 全局最近使用 > 默认（不发思考参数）。"""
        if isinstance(session_effort, str) and session_effort:
            return session_effort
        models = self.settings.models_section()
        value = models.get("activeEffort")
        return value if isinstance(value, str) and value else DEFAULT_EFFORT

    # ── 构造 ──────────────────────────────────────────────────────────────
    def api_key(self, provider_id: str) -> str:
        """取该服务商的密钥；未配置 / 取不出返回空串（由目标服务决定是否放行）。"""
        try:
            return self.vault.get_secret(provider_id) or ""
        except Exception:  # noqa: BLE001 - 密钥库异常不该让整个回合崩掉
            return ""

    def build(
        self,
        resolved: ResolvedModel,
        cancel: Optional[CancelToken] = None,
        session_id: Optional[str] = None,
    ) -> Provider:
        return build_provider(
            resolved,
            self.api_key(resolved.provider_id),
            transport=self._transport or build_transport(self.settings.proxy()),
            cancel=cancel,
            session_id=session_id,
            models_section=self.settings.models_section(),
        )

    def provider_for_turn(
        self,
        model_ref: Optional[str] = None,
        cancel: Optional[CancelToken] = None,
        session_id: Optional[str] = None,
    ) -> tuple[Provider, ResolvedModel]:
        resolved = self.turn_model(model_ref)
        return self.build(resolved, cancel, session_id), resolved

    def turn_provider(
        self,
        cancel: Optional[CancelToken],
        session_model: Optional[str],
        session_id: Optional[str] = None,
    ) -> tuple[Provider, str]:
        """`ChatViewModel` 的 turn_factory：返回（适配器，模型 id）。"""
        provider, resolved = self.provider_for_turn(session_model, cancel, session_id)
        return provider, resolved.model

    def provider_factory(
        self,
        session_id: Optional[str] = None,
        model_ref: Optional[str] = None,
    ):
        """给压缩模块用的工厂：每次尝试都造一个新适配器（超时/取消能真正掐断请求）。"""

        def factory(cancel: CancelToken) -> Provider:
            return self.build(self.turn_model(model_ref), cancel, session_id)

        return factory

    def effort_for(self, adapter: str, model: str, base_url: str, level: str) -> Any:
        return effort_request(adapter, model, base_url, level)

    def model_key(self, model_ref: Optional[str] = None) -> tuple[str, str, str]:
        """当前生效模型的（adapter, model, base_url），供思考等级判定。没有可用模型时给出空值。"""
        try:
            resolved = self.turn_model(model_ref)
        except ProviderError:
            return ("", "", "")
        return (resolved.adapter, resolved.model, resolved.base_url)

    def effort_parameter(self, session_effort: Optional[str], model_ref: Optional[str] = None) -> Any:
        """会话档位 → 本轮请求的思考参数；未配置模型或默认档返回 None。"""
        adapter, model, base_url = self.model_key(model_ref)
        if not adapter:
            return None
        return effort_request(adapter, model, base_url, self.effort_level(session_effort))

    async def list_models(
        self,
        provider_id: str,
        adapter: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> ListModelsResult:
        """拉某个服务商的模型清单（设置页「拉取模型」按钮）。

        地址与适配器默认从配置里现查；探针失败只回 `ok=False`，界面据此退回手动输入。
        """
        target = self._provider_entry(provider_id)
        adapter = adapter or target.get("adapter") or "anthropic"
        base_url = base_url or target.get("apiHost") or ""
        return await list_models(
            adapter,
            base_url,
            self.api_key(provider_id),
            self._transport or build_transport(self.settings.proxy()),
            run_id=f"models-{provider_id}",
            provider_id=provider_id,
            models_section=self.settings.models_section(),
        )

    def _provider_entry(self, provider_id: str) -> dict[str, Any]:
        models = self.settings.models_section()
        providers = models.get("providers")
        if isinstance(providers, list):
            for provider in providers:
                if isinstance(provider, dict) and provider.get("id") == provider_id:
                    return provider
        return {}

    def compaction_settings(self) -> Any:
        """`config.json` 的 compaction 段 → 配置对象（非法值回落默认）。"""
        return compaction_config(self.settings.get("compaction"))


__all__ = ["DEFAULT_EFFORT", "ModelGateway", "build_transport"]
