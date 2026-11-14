"""数据根目录的单一判定：`AI_UPPER_HOME` 优先，缺省 `~/.ai_upper`。

这个模块存在的原因只有一个：数据目录原先由五个服务各自读一遍 `DEVA_HOME`，
改名时必然漂移（读写落在两个目录、用户配置静默丢失）。现在只有这一份实现，
服务层全部经由它取默认值。

旧路径兼容（不丢用户数据）：

- 环境变量：`AI_UPPER_HOME` 优先；未设时仍认旧的 `DEVA_HOME`；
- 缺省目录：`~/.ai_upper` 不存在而旧的 `~/.deva` 存在时，继续用旧目录
  （旧目录里的 config.json / chats / personas / secrets.enc 原样可读）。
  两个都存在时用新目录——那说明用户已经在新目录里工作，旧目录保持不动，
  需要合并时手工拷贝即可（迁移步骤见 README「数据目录」）。
"""
from __future__ import annotations

import os
from pathlib import Path

HOME_ENV = "AI_UPPER_HOME"
LEGACY_HOME_ENV = "DEVA_HOME"
DEFAULT_DIR_NAME = ".ai_upper"
LEGACY_DEFAULT_DIR_NAME = ".deva"


def _override() -> str:
    return (os.environ.get(HOME_ENV) or os.environ.get(LEGACY_HOME_ENV) or "").strip()


def app_home() -> Path:
    """当前生效的数据根目录。只读判定，不创建目录。"""
    override = _override()
    if override:
        return Path(override)
    preferred = Path.home() / DEFAULT_DIR_NAME
    legacy = Path.home() / LEGACY_DEFAULT_DIR_NAME
    if not preferred.exists() and legacy.exists():
        return legacy
    return preferred


__all__ = [
    "DEFAULT_DIR_NAME",
    "HOME_ENV",
    "LEGACY_DEFAULT_DIR_NAME",
    "LEGACY_HOME_ENV",
    "app_home",
]
