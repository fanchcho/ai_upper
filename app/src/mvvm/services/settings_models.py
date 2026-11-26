"""设置页「模型 / 关于」两页的数据投影（QML 只负责画，判据都在这里）。

对应 Deva `features/settings/ModelSettings.tsx` + `ProviderAdvanced.tsx` +
`redesign/SettingsPane.tsx` 的 AboutPane。壳（`qml_shell.ShellBridge`）只做三件事：
读 `config.json` 的 `models` 段、把行整理成 QML 能直接绑的字典、把界面的改动整段写回。
纯 Python，不认识 Qt——单测（`app/tests/test_qml_settings_models.py`）直接调这里。

**为什么不在 QML 里算**：行里要判「已启用但没密钥」（`enabled && !hasKey`）、要按
`purpose`/`kind` 过滤、要把 `headers` 里的坏行标出原因。这些规则上游写在一个文件里
（`ModelSettings.tsx` 的 `visibleProviders` / `renderProviderRow`、`provider-headers.ts` 的
`headerIssue`），这里逐条对位，界面不再各写一份。
"""
from __future__ import annotations

from native_i18n import translate
import copy
from typing import Any, Callable, Dict, List, Optional

from mvvm.services.provider_headers import (
    MAX_CUSTOM_HEADERS,
    header_issue,
    sanitize_headers,
)


# ── 文案（逐字取自 Deva `i18n/messages.ts` 的 `models.*` / `common.*` / `settings.*`）──
MODELS_TEXT = {lang: {'providers': translate(locale, 'models.providers'), 'addProvider': translate(locale, 'models.addProvider'), 'noProvidersYet': translate(locale, 'models.noProvidersYet'), 'modelCount': translate(locale, 'models.modelCount'), 'enabled': translate(locale, 'models.enabled'), 'disabled': translate(locale, 'models.disabled'), 'back': translate(locale, 'chat.plan.back'), 'backTo': translate(locale, 'models.backTo'), 'deleteProvider': translate(locale, 'models.deleteProvider'), 'deleteProviderConfirm': translate(locale, 'models.deleteProviderConfirm'), 'enableProvider': translate(locale, 'extensions.enable'), 'advanced': translate(locale, 'models.advanced'), 'apiKey': translate(locale, 'models.apiKey'), 'apiKeyPlaceholder': translate(locale, 'models.apiKeyPlaceholder'), 'keyReplaceHint': translate(locale, 'models.keyReplaceHint'), 'keyConfigured': translate(locale, 'extensions.secretConfigured'), 'keySaving': translate(locale, 'extensions.secretSaving'), 'keySaved': translate(locale, 'extensions.secretSaved'), 'secretsUnavailable': translate(locale, 'models.secretsUnavailable'), 'apiHost': translate(locale, 'models.apiHost'), 'modelList': translate(locale, 'settings.models'), 'addModel': translate(locale, 'models.addModel'), 'newModelPlaceholder': translate(locale, 'models.modelIdPlaceholder'), 'add': translate(locale, 'bots.add'), 'remove': translate(locale, 'chat.attachRemove'), 'noModels': translate(locale, 'models.noModels'), 'newProviderName': translate(locale, 'models.newProviderName'), 'renameHint': translate(locale, 'models.renameHint'), 'providerNamePlaceholder': translate(locale, 'models.providerNamePlaceholder'), 'keyMissingWarn': translate(locale, 'models.keyMissingWarn'), 'headers': translate(locale, 'models.headers'), 'headersHint': translate(locale, 'models.headersHint'), 'noHeaders': translate(locale, 'models.noHeaders'), 'headerName': translate(locale, 'models.headerName'), 'headerValue': translate(locale, 'extensions.kvValue'), 'addHeader': translate(locale, 'models.addHeader'), 'removeHeader': translate(locale, 'chat.attachRemove'), 'headerIssue': {'name': translate(locale, 'models.headerIssue.name'), 'reserved': translate(locale, 'models.headerIssue.reserved'), 'value': translate(locale, 'models.headerIssue.value')}, 'delete': translate(locale, 'extensions.remove'), 'cancel': translate(locale, 'git.cancel'), 'confirm': translate(locale, 'common.confirm'), 'version': translate(locale, 'settings.version'), 'about': translate(locale, 'settings.about'), 'checkForUpdates': translate(locale, 'settings.update.check'), 'checkingUpdates': translate(locale, 'settings.update.checking'), 'latestVersion': translate(locale, 'settings.update.latest'), 'updateCheckFailed': translate(locale, 'settings.update.checkFailed'), 'newVersion': translate(locale, 'settings.update.available')} for lang, locale in (('zh', 'zh-CN'), ('en', 'en'))}


def models_text(language: str) -> Dict[str, Any]:
    return copy.deepcopy(MODELS_TEXT.get(language, MODELS_TEXT["en"]))


# ── 读 ────────────────────────────────────────────────────────────────────
def provider_entries(models_section: Any) -> List[Dict[str, Any]]:
    """`models.providers` 里形状合法的条目（原样引用，调用方要改请先 deepcopy）。"""
    providers = models_section.get("providers") if isinstance(models_section, dict) else None
    if not isinstance(providers, list):
        return []
    return [p for p in providers if isinstance(p, dict) and p.get("id")]


def visible_providers(models_section: Any, has_key: Callable[[str], bool]) -> List[Dict[str, Any]]:
    """列表态只列「在用」的服务商：已启用 / 已配密钥 / 自定义（上游 `visibleProviders` 同）。

    决策模型（`purpose == 'decision'`）整体隐藏：它不生成文本，当前也没有新建入口。
    """
    rows: List[Dict[str, Any]] = []
    for provider in provider_entries(models_section):
        if (provider.get("purpose") or "llm") != "llm":
            continue
        provider_id = str(provider.get("id"))
        enabled = provider.get("enabled") is True
        if not (enabled or has_key(provider_id) or provider.get("kind") == "custom"):
            continue
        rows.append(provider)
    return rows


def provider_row(provider: Dict[str, Any], has_key: Callable[[str], bool], language: str) -> Dict[str, Any]:
    """一条服务商行（原版 `renderProviderRow`）：启用点 / 名称 / `N models` / 警告 / 箭头。"""
    text = MODELS_TEXT.get(language, MODELS_TEXT["en"])
    provider_id = str(provider.get("id"))
    enabled = provider.get("enabled") is True
    models = provider.get("models")
    count = len(models) if isinstance(models, list) else 0
    return {
        "id": provider_id,
        "name": str(provider.get("name") or provider_id),
        "enabled": enabled,
        "detail": text["modelCount"].replace("{count}", str(count)),
        # 已启用却还没配密钥：行尾给告警三角（本地 Ollama 之类可无钥，只提示不阻断）。
        "warn": enabled and not has_key(provider_id),
    }


def provider_rows(models_section: Any, has_key: Callable[[str], bool], language: str) -> List[Dict[str, Any]]:
    return [provider_row(p, has_key, language) for p in visible_providers(models_section, has_key)]


def has_provider(models_section: Any, provider_id: str) -> bool:
    return any(str(p.get("id")) == provider_id for p in provider_entries(models_section))


def find_provider(models_section: Any, provider_id: str) -> Optional[Dict[str, Any]]:
    for provider in provider_entries(models_section):
        if str(provider.get("id")) == provider_id:
            return provider
    return None


def provider_detail(
    models_section: Any,
    provider_id: str,
    language: str,
    has_key: Callable[[str], bool] = lambda _provider_id: False,
) -> Optional[Dict[str, Any]]:
    """详情页的整页投影（原版 `selectedProvider` 直接读 store，这里在桥里拼好）。

    名字 / 协议 / 地址 / 模型清单 / 请求头都取自配置原文；`warn` 与列表行同一条判定；
    `advanced` 是否给扳手入口 = `purpose !== 'decision'`（决策模型不经 providerHeaders）。
    """
    provider = find_provider(models_section, provider_id)
    if provider is None:
        return None
    text = MODELS_TEXT.get(language, MODELS_TEXT["en"])
    purpose = provider.get("purpose") or "llm"
    models = provider.get("models")
    model_rows: List[Dict[str, Any]] = []
    for model in models if isinstance(models, list) else []:
        if not isinstance(model, dict) or not model.get("id"):
            continue
        model_id = str(model.get("id"))
        model_rows.append(
            {
                "id": model_id,
                "name": str(model.get("name") or model_id),
                # 改过显示名时行内附真实 ID（原版 `mo.name !== mo.id`）。
                "showId": bool(model.get("name")) and str(model.get("name")) != model_id,
                "enabled": model.get("enabled") is True,
            }
        )
    return {
        "id": str(provider.get("id")),
        "name": str(provider.get("name") or provider.get("id")),
        "kind": str(provider.get("kind") or ""),
        "purpose": purpose,
        "adapter": str(provider.get("adapter") or ""),
        "apiHost": str(provider.get("apiHost") or ""),
        "enabled": provider.get("enabled") is True,
        "models": model_rows,
        "headers": header_rows(provider.get("headers"), language),
        "advanced": purpose != "decision",
        # 详情页的「已启用但未配置密钥」提醒；与列表行同一条判定，界面不另算。
        "warn": provider.get("enabled") is True and not has_key(str(provider.get("id"))),
        "canRename": str(provider.get("kind") or "") == "custom",
        "modelList": text["modelList"],
    }


def header_rows(raw: Any, language: str) -> List[Dict[str, str]]:
    """请求头的行投影：`{name, value, issue}`；`issue` 非空 = 该行不会发出（行下注明原因）。

    只列配置里真实存着的条目（上游 `Object.entries(headers)` 同口径：存的是已整理过的表）。
    """
    text = MODELS_TEXT.get(language, MODELS_TEXT["en"])
    issues = text["headerIssue"]
    rows: List[Dict[str, str]] = []
    if not isinstance(raw, dict):
        return rows
    for name, value in raw.items():
        row_name = str(name)
        row_value = "" if value is None else str(value)
        issue = header_issue(row_name, row_value) or ""
        rows.append(
            {
                "name": row_name,
                "value": row_value,
                "issue": issue,
                # QML 直接显示这个字符串，不在界面里拼 i18n 键。
                "issueText": issues.get(issue, "") if issue else "",
            }
        )
    return rows


def max_headers() -> int:
    return MAX_CUSTOM_HEADERS


# ── 写（整段回写 `models` 段；`config:set` 只做顶层浅合并）────────────────────
def _clone(models_section: Any) -> Dict[str, Any]:
    return copy.deepcopy(models_section) if isinstance(models_section, dict) else {}


def _write_provider(models: Dict[str, Any], provider: Dict[str, Any]) -> None:
    providers = models.get("providers")
    if not isinstance(providers, list):
        providers = []
        models["providers"] = providers
    for index, current in enumerate(providers):
        if isinstance(current, dict) and str(current.get("id")) == str(provider.get("id")):
            providers[index] = provider
            return
    providers.append(provider)


def update_provider(models_section: Any, provider_id: str, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """改一个服务商的字段，返回新的 `models` 段；provider 不存在返回 None（不伪造）。"""
    models = _clone(models_section)
    provider = find_provider(models, provider_id)
    if provider is None:
        return None
    for key, value in patch.items():
        if value is None:
            provider.pop(key, None)
        else:
            provider[key] = copy.deepcopy(value)
    return models


def remove_provider(models_section: Any, provider_id: str) -> Optional[Dict[str, Any]]:
    """删服务商（原版 `removeProvider`：连同 `activeModelId` 指向它时的清理一起做）。"""
    models = _clone(models_section)
    providers = models.get("providers")
    if not isinstance(providers, list) or not any(
        isinstance(p, dict) and str(p.get("id")) == provider_id for p in providers
    ):
        return None
    models["providers"] = [
        p for p in providers if not (isinstance(p, dict) and str(p.get("id")) == provider_id)
    ]
    active = models.get("activeModelId")
    if isinstance(active, str) and active.split(":", 1)[0] == provider_id:
        models.pop("activeModelId", None)
    return models


def add_provider(models_section: Any, provider: Dict[str, Any]) -> Dict[str, Any]:
    """追加一个自定义服务商（调用方负责生成唯一 id / 默认名）。"""
    models = _clone(models_section)
    _write_provider(models, copy.deepcopy(provider))
    return models


def set_headers(models_section: Any, provider_id: str, raw: Any) -> Optional[Dict[str, Any]]:
    """写入自定义请求头：先按上游规则整理；整理后为空则删掉 `headers` 键（上游传 undefined）。"""
    providers = (models_section or {}).get("providers") if isinstance(models_section, dict) else None
    if not isinstance(providers, list):
        return None
    cleaned = sanitize_headers(raw)
    return update_provider(models_section, provider_id, {"headers": cleaned or None})


def set_model_enabled(
    models_section: Any, provider_id: str, model_id: str, enabled: bool
) -> Optional[Dict[str, Any]]:
    models = _clone(models_section)
    provider = find_provider(models, provider_id)
    if provider is None:
        return None
    models_list = provider.get("models")
    if not isinstance(models_list, list):
        return None
    for model in models_list:
        if isinstance(model, dict) and str(model.get("id")) == model_id:
            model["enabled"] = bool(enabled)
            return models
    return None


def add_model(models_section: Any, provider_id: str, model_id: str, name: str = "") -> Optional[Dict[str, Any]]:
    """加一个模型（原版 `addModel`）：同名去重、默认启用。模型 id 为空返回 None。"""
    model_id = (model_id or "").strip()
    if not model_id:
        return None
    models = _clone(models_section)
    provider = find_provider(models, provider_id)
    if provider is None:
        return None
    models_list = provider.get("models")
    if not isinstance(models_list, list):
        models_list = []
        provider["models"] = models_list
    if any(isinstance(m, dict) and str(m.get("id")) == model_id for m in models_list):
        return None
    models_list.append({"id": model_id, "name": (name or model_id), "enabled": True})
    return models


def remove_model(models_section: Any, provider_id: str, model_id: str) -> Optional[Dict[str, Any]]:
    models = _clone(models_section)
    provider = find_provider(models, provider_id)
    if provider is None:
        return None
    models_list = provider.get("models")
    if not isinstance(models_list, list):
        return None
    kept = [m for m in models_list if not (isinstance(m, dict) and str(m.get("id")) == model_id)]
    if len(kept) == len(models_list):
        return None
    provider["models"] = kept
    active = models.get("activeModelId")
    if isinstance(active, str) and active == f"{provider_id}:{model_id}":
        models.pop("activeModelId", None)
    return models


def new_provider(models_section: Any, provider_id: str, name: str, accent: str = "#8a8a94") -> Dict[str, Any]:
    """新建自定义服务商的最小形状（原版 `addCustomProvider`）；id 由调用方保证唯一。"""
    return {
        "id": provider_id,
        "name": name,
        "kind": "custom",
        "purpose": "llm",
        "accent": accent,
        "adapter": "openai",
        "apiHost": "",
        "enabled": True,
        "models": [],
    }


__all__ = [
    "MAX_CUSTOM_HEADERS",
    "MODELS_TEXT",
    "add_model",
    "add_provider",
    "find_provider",
    "has_provider",
    "header_rows",
    "max_headers",
    "models_text",
    "new_provider",
    "provider_detail",
    "provider_entries",
    "provider_row",
    "provider_rows",
    "remove_model",
    "remove_provider",
    "set_headers",
    "set_model_enabled",
    "update_provider",
    "visible_providers",
]
