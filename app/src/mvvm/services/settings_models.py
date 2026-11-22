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

import copy
from typing import Any, Callable, Dict, List, Optional

from mvvm.services.provider_headers import (
    MAX_CUSTOM_HEADERS,
    header_issue,
    sanitize_headers,
)


# ── 文案（逐字取自 Deva `i18n/messages.ts` 的 `models.*` / `common.*` / `settings.*`）──
MODELS_TEXT: Dict[str, Dict[str, Any]] = {
    "zh": {
        "providers": "模型服务商",
        "addProvider": "添加提供方",
        "noProvidersYet": "还没有可用的服务商，点右上角 + 添加",
        "modelCount": "{count} 个模型",
        "enabled": "已启用",
        "disabled": "未启用",
        "back": "返回",
        "backTo": "返回 {name}",
        "deleteProvider": "删除服务商",
        "deleteProviderConfirm": "删除该服务商及其密钥？此操作不可撤销。",
        "enableProvider": "启用",
        "advanced": "高级设置",
        "apiKey": "API 密钥",
        "apiKeyPlaceholder": "在此填写 API Key",
        "keyReplaceHint": "已配置密钥（如需更换请重新输入）",
        "keyConfigured": "已配置",
        "keySaving": "保存中…",
        "keySaved": "已保存",
        "secretsUnavailable": "当前系统不支持安全加密存储，暂无法保存密钥",
        "apiHost": "API 地址",
        "modelList": "模型",
        "addModel": "添加模型",
        "newModelPlaceholder": "模型 ID，如 gpt-4o",
        "add": "添加",
        "remove": "移除",
        "noModels": "暂无模型，点击「添加模型」新增",
        "newProviderName": "自定义服务商",
        "renameHint": "点击修改名称",
        "providerNamePlaceholder": "服务商名称",
        "keyMissingWarn": "已启用但未配置密钥，对话将失败",
        "headers": "自定义请求头",
        "headersHint": "随每个请求发送，同名时覆盖默认值（如 User-Agent）。",
        "noHeaders": "暂无请求头，点击「添加请求头」新增",
        "headerName": "名称，如 originator",
        "headerValue": "值",
        "addHeader": "添加请求头",
        "removeHeader": "移除",
        "headerIssue": {
            "name": "名称含不支持的字符，不会发送。",
            "reserved": "该请求头由应用管理，不会发送。",
            "value": "值仅支持英文、数字和符号，不会发送。",
        },
        "delete": "删除",
        "cancel": "取消",
        "confirm": "确定",
        "version": "版本",
        "about": "关于",
        "checkForUpdates": "检查更新",
        "checkingUpdates": "正在检查…",
        "latestVersion": "已是最新版本",
        "updateCheckFailed": "检查更新失败",
        "newVersion": "发现新版本 {version}",
    },
    "en": {
        "providers": "Providers",
        "addProvider": "Add provider",
        "noProvidersYet": "No providers yet — click + to add one",
        "modelCount": "{count} models",
        "enabled": "Enabled",
        "disabled": "Disabled",
        "back": "Back",
        "backTo": "Back to {name}",
        "deleteProvider": "Delete provider",
        "deleteProviderConfirm": "Delete this provider and its key? This cannot be undone.",
        "enableProvider": "Enabled",
        "advanced": "Advanced settings",
        "apiKey": "API Key",
        "apiKeyPlaceholder": "Enter your API key",
        "keyReplaceHint": "Key configured (re-enter to replace)",
        "keyConfigured": "Configured",
        "keySaving": "Saving…",
        "keySaved": "Saved",
        "secretsUnavailable": "Secure encrypted storage is unavailable on this system; keys cannot be saved",
        "apiHost": "API Host",
        "modelList": "Models",
        "addModel": "Add model",
        "newModelPlaceholder": "Model ID, e.g. gpt-4o",
        "add": "Add",
        "remove": "Remove",
        "noModels": 'No models yet — click "Add model"',
        "newProviderName": "Custom Provider",
        "renameHint": "Click to rename",
        "providerNamePlaceholder": "Provider name",
        "keyMissingWarn": "Enabled but no API key set — chat will fail",
        "headers": "Custom headers",
        "headersHint": "Sent with every request; same-name headers replace the defaults (e.g. User-Agent).",
        "noHeaders": 'No headers yet — click "Add header"',
        "headerName": "Name, e.g. originator",
        "headerValue": "Value",
        "addHeader": "Add header",
        "removeHeader": "Remove",
        "headerIssue": {
            "name": "Unsupported characters in the name. Not sent.",
            "reserved": "This header is managed by the app. Not sent.",
            "value": "Only ASCII letters, digits and symbols are supported. Not sent.",
        },
        "delete": "Delete",
        "cancel": "Cancel",
        "confirm": "OK",
        "version": "Version",
        "about": "About",
        "checkForUpdates": "Check for updates",
        "checkingUpdates": "Checking…",
        "latestVersion": "You’re on the latest version",
        "updateCheckFailed": "Couldn’t check for updates",
        "newVersion": "New version {version} available",
    },
}


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
