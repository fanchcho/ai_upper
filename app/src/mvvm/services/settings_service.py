"""应用配置：明文 `config.json`，顶层浅合并。

对应 Deva `apps/desktop/src/main/services/config.ts` 的 `config:get-sync` / `config:get` / `config:set`。
语义逐条对齐：

- 根目录 `AI_UPPER_HOME` 优先，缺省 `~/.ai_upper`（旧 `DEVA_HOME` / `~/.deva` 兼容）；
- 整个文件是一份 JSON 对象，**顶层浅合并**：`set({"models": {...}})` 整段替换 `models`，
  不是深层合并。这条必须照搬——渲染层依赖它整段写回模型配置（Deva `store/models.tsx:195`）；
- 值写成 `None` 等于删除该键（Deva 的 `undefined` 语义在 Python 里没有对应物，用 `None`）；
- 文件不存在 / 解析失败视为空配置，不阻断启动；但**写失败不静默**——Deva 的 `persist()`
  吞掉异常，本工程改为抛出，由界面显示「保存失败」，否则用户以为改的设置生效了。

敏感信息绝不进这里：API 密钥走 `secrets_vault`。
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from typing import Any, Optional

from mvvm.models.chat_models import now_ms
from mvvm.services.chat_session_store import write_file_atomic

CONFIG_FILE = "config.json"

# 本工程真正读取的配置键（其余键原样保留，供 Deva 两侧共用同一个数据目录）。
THEME_KEY = "theme"
LANGUAGE_KEY = "language"
LAYOUT_KEY = "layout"
MODELS_KEY = "models"
DATA_DIR_KEY = "dataDir"
PROXY_KEY = "proxy"


def default_home() -> Path:
    """`AI_UPPER_HOME` 优先，缺省 `~/.ai_upper`（旧 `DEVA_HOME` / `~/.deva` 仍被读取）。"""
    from utils.app_home import app_home

    return app_home()


class SettingsService:
    """读/写 `config.json`。纯 Python，不认识 Qt。"""

    def __init__(self, home: Optional[Path | str] = None) -> None:
        self._home = Path(home) if home is not None else default_home()
        self._config: Optional[dict[str, Any]] = None
        self._loaded_raw: Optional[str] = None

    @property
    def home(self) -> Path:
        return self._home

    @property
    def path(self) -> Path:
        return self._home / CONFIG_FILE

    # ── 读 ────────────────────────────────────────────────────────────────
    def _ensure_loaded(self) -> dict[str, Any]:
        if self._config is not None:
            return self._config
        try:
            self._loaded_raw = self.path.read_text(encoding="utf-8")
            parsed = json.loads(self._loaded_raw)
            self._config = parsed if isinstance(parsed, dict) else {}
        except (OSError, ValueError):
            self._config = {}  # 首次运行 / 手改坏了：按空配置继续，不让启动失败
        return self._config

    def get_config_sync(self) -> dict[str, Any]:
        """整份配置的**只读快照**（深拷贝：调用方改不动内存态）。"""
        return copy.deepcopy(self._ensure_loaded())

    get_config = get_config_sync

    def get(self, key: str, default: Any = None) -> Any:
        return copy.deepcopy(self._ensure_loaded().get(key, default))

    # ── 写 ────────────────────────────────────────────────────────────────
    def set_config(self, patch: dict[str, Any]) -> dict[str, bool]:
        """顶层浅合并；值 `None` 删除该键。落盘失败抛 OSError（不静默）。"""
        if not isinstance(patch, dict):
            raise TypeError("config 补丁必须是对象")
        config = self._ensure_loaded()
        # deva-agent desktop-models.mjs: expectedRaw prevents stale desktop mirrors
        # from overwriting an external model/configuration edit.
        try:
            current_raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            current_raw = None
        if current_raw != self._loaded_raw:
            raise OSError("Configuration changed externally; reload before saving")
        for key, value in patch.items():
            if value is None:
                config.pop(key, None)
            else:
                config[key] = copy.deepcopy(value)
        self._persist()
        return {"ok": True}

    def _persist(self) -> None:
        assert self._config is not None
        self._home.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(self._config, ensure_ascii=False, indent=2)
        write_file_atomic(self.path, raw)
        self._loaded_raw = raw

    def reload(self) -> None:
        """丢弃内存态，下次读取重新落盘读（外部工具手改 config.json 时用）。"""
        self._config = None
        self._loaded_raw = None

    # ── 本工程直接消费的强类型读取（值非法一律回落缺省，不抛错）──────────
    def theme(self) -> str:
        value = self._ensure_loaded().get(THEME_KEY)
        return value if value in ("light", "dark", "system") else "system"

    def language(self) -> str:
        value = self._ensure_loaded().get(LANGUAGE_KEY)
        return value if value in ("zh", "en") else "zh"

    def layout(self) -> dict[str, Any]:
        value = self._ensure_loaded().get(LAYOUT_KEY)
        return dict(value) if isinstance(value, dict) else {}

    def data_dir(self) -> Optional[str]:
        value = self._ensure_loaded().get(DATA_DIR_KEY)
        return value if isinstance(value, str) and value.strip() else None

    def proxy(self) -> Optional[str]:
        value = self._ensure_loaded().get(PROXY_KEY)
        return value if isinstance(value, str) and value.strip() else None

    def models_section(self) -> dict[str, Any]:
        value = self._ensure_loaded().get(MODELS_KEY)
        return copy.deepcopy(value) if isinstance(value, dict) else {}


__all__ = [
    "CONFIG_FILE",
    "DATA_DIR_KEY",
    "LANGUAGE_KEY",
    "LAYOUT_KEY",
    "MODELS_KEY",
    "PROXY_KEY",
    "THEME_KEY",
    "SettingsService",
    "default_home",
    "now_ms",
]
