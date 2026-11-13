"""设置页 ViewModel：服务商 / 模型 / 密钥 / 默认模型与思考等级。

对齐 Deva 渲染层 `store/models.tsx` 的语义：

- `config.json` 的 `models` 段**整块**写回（`config:set` 只做顶层浅合并，漏写兄弟字段即被清掉）；
- 模型引用是 `"providerId:modelId"`，按**首个冒号**切分（Ollama 的 `qwen3:8b` 不能丢）；
- API 密钥不进本类：只经 `SecretsVault` 交给密钥库，界面只拿 `has_key` 布尔；
- 删除服务商 → 连带删除其密钥、清空悬空默认模型；禁用服务商 / 删除模型同理清理默认；
- 拉模型清单失败只回结果，不抛错（界面据此退回手动输入）。

本类不认识 Qt，可纯 Python 测试。
"""
from __future__ import annotations

import copy
import time
from typing import Any, Optional

from mvvm.core import BaseViewModel, PropertyFactory, RelayCommand
from mvvm.services.provider_registry import ListModelsResult
from mvvm.services.provider_setup import ModelGateway
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.settings_service import SettingsService

ADAPTERS = ("anthropic", "openai", "responses")
ADAPTER_LABELS = {
    "anthropic": "Anthropic 协议",
    "openai": "OpenAI Chat 协议",
    "responses": "OpenAI Responses 协议",
}
EFFORT_LEVELS = ("default", "low", "medium", "high", "xhigh", "max")


def split_ref(ref: Any) -> Optional[tuple[str, str]]:
    """按首个冒号切分 `providerId:modelId`；无效返回 None（与 model_resolve 同口径）。"""
    if not isinstance(ref, str):
        return None
    index = ref.find(":")
    if index <= 0:
        return None
    provider_id, model_id = ref[:index].strip(), ref[index + 1:].strip()
    return (provider_id, model_id) if provider_id and model_id else None


def _model_entry(model: dict[str, Any]) -> dict[str, Any]:
    identifier = str(model.get("id") or "")
    return {
        "id": identifier,
        "name": str(model.get("name") or identifier),
        "enabled": model.get("enabled") is True,
        "context_window": model.get("contextWindow"),
        "max_output": model.get("maxOutput"),
    }


def _provider_entry(provider: dict[str, Any], active_id: str, selected: bool) -> dict[str, Any]:
    identifier = str(provider.get("id") or "")
    adapter = provider.get("adapter") if provider.get("adapter") in ADAPTERS else "anthropic"
    models = provider.get("models")
    model_list = [_model_entry(m) for m in models if isinstance(m, dict)] if isinstance(models, list) else []
    return {
        "id": identifier,
        "name": str(provider.get("name") or identifier),
        "adapter": adapter,
        "adapter_label": ADAPTER_LABELS[adapter],
        "base_url": str(provider.get("apiHost") or ""),
        "enabled": provider.get("enabled") is True,
        "models": model_list,
        "active": selected,
    }


class SettingsViewModel(BaseViewModel):
    """设置页的状态与命令。数据落 `config.json` 与密钥库，界面只读展示投影。"""

    def __init__(
        self,
        settings: SettingsService,
        vault: SecretsVault,
        gateway: Optional[ModelGateway] = None,
    ) -> None:
        self.settings = settings
        self.vault = vault
        self.gateway = gateway
        self._selected_id = ""
        super().__init__()
        self.refresh()

    # ── 属性 ──────────────────────────────────────────────────────────────
    def _initialize_properties(self) -> None:
        self.providers_property = PropertyFactory.create([], "providers")
        self._register_property("providers", self.providers_property)

        self.active_model_property = PropertyFactory.create("", "active_model")
        self._register_property("active_model", self.active_model_property)

        self.active_effort_property = PropertyFactory.create("default", "active_effort")
        self._register_property("active_effort", self.active_effort_property)

        self.message_property = PropertyFactory.create("", "message")
        self._register_property("message", self.message_property)

        self.save_command = RelayCommand(execute=self.save_models)

    # ── 只读视图 ──────────────────────────────────────────────────────────
    @property
    def providers(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.providers_property.get_value() or [])

    @property
    def active_model(self) -> str:
        return str(self.active_model_property.get_value() or "")

    @property
    def active_effort(self) -> str:
        return str(self.active_effort_property.get_value() or "default")

    @property
    def message(self) -> str:
        return str(self.message_property.get_value() or "")

    @property
    def selected_id(self) -> str:
        return self._selected_id

    # ── 读 ────────────────────────────────────────────────────────────────
    def refresh(self) -> int:
        """从 `config.json` 重建展示投影（含每个服务商的密钥状态布尔）。"""
        models = self.settings.models_section()
        active = models.get("activeModelId")
        active_ref = active if isinstance(active, str) else ""
        providers = models.get("providers")
        entries = [
            _provider_entry(p, active_ref, p.get("id") == self._selected_id)
            for p in (providers if isinstance(providers, list) else [])
            if isinstance(p, dict)
        ]
        self.providers_property.set_value(entries)
        self.active_model_property.set_value(active_ref)
        effort = models.get("activeEffort")
        self.active_effort_property.set_value(
            effort if isinstance(effort, str) and effort else "default"
        )
        return len(entries)

    def provider(self, provider_id: str) -> Optional[dict[str, Any]]:
        return next((p for p in self.providers if p["id"] == provider_id), None)

    def has_key(self, provider_id: str) -> bool:
        try:
            return bool(self.vault.has_secret(provider_id))
        except Exception:  # noqa: BLE001 - 密钥库异常按「未配置」处理，不炸设置页
            return False

    def models_of(self, provider_id: str) -> list[dict[str, Any]]:
        entry = self.provider(provider_id)
        return entry["models"] if entry else []

    # ── 写：服务商 ────────────────────────────────────────────────────────
    def add_provider(
        self,
        name: str,
        base_url: str = "https://",
        adapter: str = "openai",
        provider_id: Optional[str] = None,
    ) -> str:
        """新建自定义服务商。返回 id。

        与 Deva `addCustomProvider` 同口径：默认**未启用**、地址先给 `https://` 占位、
        对话模型默认 OpenAI 兼容协议；用户填完地址与密钥后（写密钥会自动启用）才可用。
        """
        models = self._models()
        identifier = provider_id or self._fresh_provider_id(models)
        entry = {
            "id": identifier,
            "name": str(name or identifier),
            "adapter": adapter if adapter in ADAPTERS else "openai",
            "apiHost": str(base_url or "https://"),
            "enabled": False,
            "models": [],
        }
        models.setdefault("providers", []).append(entry)
        self._write(models)
        return identifier

    def update_provider(
        self,
        provider_id: str,
        *,
        name: Optional[str] = None,
        base_url: Optional[str] = None,
        adapter: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> bool:
        """改服务商字段；禁用时清空属于它的默认模型（与 Deva 一致）。"""
        models = self._models()
        entry = self._find(models, provider_id)
        if entry is None:
            return False
        if name is not None:
            entry["name"] = str(name)
        if base_url is not None:
            entry["apiHost"] = str(base_url)
        if adapter is not None and adapter in ADAPTERS:
            entry["adapter"] = adapter
        if enabled is not None:
            entry["enabled"] = bool(enabled)
            if not enabled:
                self._clear_active_of(models, provider_id)
        self._write(models)
        return True

    def remove_provider(self, provider_id: str) -> bool:
        """删除服务商：连带删除密钥、清空悬空默认模型（与 Deva `removeProvider` 一致）。"""
        models = self._models()
        providers = models.get("providers")
        if not isinstance(providers, list):
            return False
        before = len(providers)
        models["providers"] = [p for p in providers if not (isinstance(p, dict) and p.get("id") == provider_id)]
        if len(models["providers"]) == before:
            return False
        self._clear_active_of(models, provider_id)
        self._write(models)
        try:
            self.vault.delete_secret(provider_id)
        except Exception:  # noqa: BLE001 - 密钥删除失败不阻断服务商移除，但要说出来
            self.message_property.set_value("服务商已移除，但密钥删除失败（请手动清理）")
        if self._selected_id == provider_id:
            self._selected_id = ""
        return True

    # ── 写：模型 ──────────────────────────────────────────────────────────
    def add_model(self, provider_id: str, model_id: str) -> bool:
        """新增模型并启用（顺带启用所属服务商）：刚加的模型立即可选。"""
        model_id = str(model_id or "").strip()
        if not model_id:
            return False
        models = self._models()
        entry = self._find(models, provider_id)
        if entry is None:
            return False
        existing = entry.setdefault("models", [])
        if any(isinstance(m, dict) and m.get("id") == model_id for m in existing):
            return False
        existing.append({"id": model_id, "name": model_id, "enabled": True})
        entry["enabled"] = True
        self._write(models)
        return True

    def add_models(self, provider_id: str, ids: list[str]) -> int:
        """批量添加：跳过空串、已存在与本批次内重复；返回新增条数。"""
        added = 0
        seen: set[str] = set()
        for raw in ids:
            candidate = str(raw or "").strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            if self.add_model(provider_id, candidate):
                added += 1
        return added

    def toggle_model(self, provider_id: str, model_id: str) -> bool:
        models = self._models()
        model = self._find_model(models, provider_id, model_id)
        if model is None:
            return False
        model["enabled"] = not (model.get("enabled") is True)
        self._write(models)
        return True

    def update_model(
        self,
        provider_id: str,
        model_id: str,
        *,
        name: Optional[str] = None,
        context_window: Optional[int] = None,
        max_output: Optional[int] = None,
        clear: bool = False,
    ) -> bool:
        """改模型详情（显示名 / 上下文窗口 / 输出上限）。

        `clear=True` 表示「恢复自动」：把上下文窗口与输出上限**删键**，而不是留 `null`
        （与 Deva `updateModel` 的 undefined 语义一致，落盘文件里不残留空字段）。
        """
        models = self._models()
        model = self._find_model(models, provider_id, model_id)
        if model is None:
            return False
        if name is not None:
            model["name"] = str(name) or model_id
        if clear:
            model.pop("contextWindow", None)
            model.pop("maxOutput", None)
        else:
            if context_window is not None:
                model["contextWindow"] = max(1, int(context_window))
            if max_output is not None:
                model["maxOutput"] = max(1, int(max_output))
        self._write(models)
        return True

    def remove_model(self, provider_id: str, model_id: str) -> bool:
        """删除模型；若它正是默认模型则清空默认（不留悬空引用）。"""
        models = self._models()
        entry = self._find(models, provider_id)
        if entry is None:
            return False
        before = entry.get("models") or []
        entry["models"] = [m for m in before if not (isinstance(m, dict) and m.get("id") == model_id)]
        if len(entry["models"]) == len(before):
            return False
        if models.get("activeModelId") == f"{provider_id}:{model_id}":
            models["activeModelId"] = None
        self._write(models)
        return True

    # ── 写：默认模型与思考等级 ────────────────────────────────────────────
    def set_active_model(self, provider_id: str, model_id: str) -> bool:
        """记录「最近使用的模型」；服务商或模型不存在时拒绝，避免写入悬空引用。"""
        models = self._models()
        if self._find_model(models, provider_id, model_id) is None:
            return False
        models["activeModelId"] = f"{provider_id}:{model_id}"
        self._write(models)
        return True

    def set_active_effort(self, level: str) -> bool:
        if level not in EFFORT_LEVELS:
            return False
        models = self._models()
        models["activeEffort"] = level
        self._write(models)
        return True

    # ── 密钥（明文不经本类留存）───────────────────────────────────────────
    def set_api_key(self, provider_id: str, key: str) -> bool:
        """写密钥库；空串视为删除。明文只在这一行里出现，不进配置、不进属性。

        与 Deva 一致：**填入了密钥就自动启用该服务商**（省一次手动开关）；清空密钥不动启用态。
        """
        text = str(key or "").strip()
        try:
            if text:
                self.vault.set_secret(provider_id, text)
            else:
                self.vault.delete_secret(provider_id)
        except Exception as exc:  # noqa: BLE001 - 密钥库不可用时界面要能提示
            self.message_property.set_value(f"密钥保存失败：{exc}")
            return False
        if text:
            self.update_provider(provider_id, enabled=True)
        self.refresh()
        return True

    # ── 拉模型清单 ────────────────────────────────────────────────────────
    async def fetch_models(self, provider_id: str) -> ListModelsResult:
        """设置页「拉取模型」：结果只回给界面；不自动写入配置（用户勾选后再加）。"""
        if self.gateway is None:
            return ListModelsResult(False, kind="invalid_request", message="未装配模型网关")
        result = await self.gateway.list_models(provider_id)
        if not result.ok:
            self.message_property.set_value(result.message or "拉取模型清单失败")
        return result

    # ── 保存 ──────────────────────────────────────────────────────────────
    def save_models(self, parameter: Any = None) -> bool:
        """把内存里的 models 段整块写回（界面改完字段后显式调用）。"""
        self._write(self._models())
        return True

    # ── 内部 ──────────────────────────────────────────────────────────────
    def _models(self) -> dict[str, Any]:
        return self.settings.models_section()

    def _write(self, models: dict[str, Any]) -> None:
        # models 段整块替换：config:set 只做顶层浅合并，漏写兄弟字段即被清掉。
        # 值为 None 的键直接不写（对齐 Deva：`undefined` 字段不会被 JSON 序列化出来），
        # 避免磁盘上留下 `"activeModelId": null` 这种半截状态。
        cleaned = {key: value for key, value in models.items() if value is not None}
        self.settings.set_config({"models": cleaned})
        self.refresh()

    def _find(self, models: dict[str, Any], provider_id: str) -> Optional[dict[str, Any]]:
        providers = models.get("providers")
        if not isinstance(providers, list):
            return None
        return next((p for p in providers if isinstance(p, dict) and p.get("id") == provider_id), None)

    def _find_model(
        self, models: dict[str, Any], provider_id: str, model_id: str
    ) -> Optional[dict[str, Any]]:
        entry = self._find(models, provider_id)
        if entry is None:
            return None
        models_list = entry.get("models")
        if not isinstance(models_list, list):
            return None
        return next(
            (m for m in models_list if isinstance(m, dict) and m.get("id") == model_id), None
        )

    def _clear_active_of(self, models: dict[str, Any], provider_id: str) -> None:
        active = models.get("activeModelId")
        if isinstance(active, str) and active.split(":", 1)[0] == provider_id:
            models["activeModelId"] = None

    def _fresh_provider_id(self, models: dict[str, Any]) -> str:
        """新服务商 id：`custom-<毫秒时间戳>`（与 Deva `addCustomProvider` 同形）。

        不用「最小空闲序号」：服务商删掉后若密钥清理失败，序号复用会让新服务商
        继承旧密钥。时间戳单调递增，天然不复用。
        """
        existing = {
            str(p.get("id"))
            for p in (models.get("providers") or [])
            if isinstance(p, dict)
        }
        stamp = int(time.time() * 1000)
        while f"custom-{stamp}" in existing:
            stamp += 1
        return f"custom-{stamp}"


__all__ = ["ADAPTERS", "ADAPTER_LABELS", "EFFORT_LEVELS", "SettingsViewModel", "split_ref"]
