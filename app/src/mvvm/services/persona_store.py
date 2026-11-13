"""角色（Personas）服务：读 `~/.deva/personas/<id>.md`，格式与 Deva `services/personas.ts` 一致。

只读移植的第一步：列表 / 单条读取 / 首启种子。写入类 IPC（upsert / remove / 排序 / 头像）
尚未接入，调用会显式抛「未实现」，不做静默假成功。

落盘口径（与 Deva 逐条对齐）：
- 身份 = 文件名去 `.md`（id），显示名 = frontmatter `name`；
- 启用态不在 `.md` 里，存在 `config.json` 的 `personas.enabled[id]`，缺省关闭；
- 头像 spec 是 frontmatter `avatar`（Humation AvatarSpec 的 JSON 字符串），空则渲染层按 id 确定性生成；
- 排序：`personas.order` 中的 id 按位置在前，其余按名称本地化排序；
- 解析失败的文件跳过，绝不让一条坏文件拖垮列表。
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")

# 首启种子：与 Deva `default-personas.ts` 里的两条默认角色同源（正文即各角色提示词）。
DEFAULT_PERSONA_IDS = ("general", "xiaomajiang")


def _assets_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "assets" / "personas"


def is_safe_id(value: str) -> bool:
    """与 Deva `isSafeId` 同口径：防 `..` / 分隔符逃逸。"""
    return bool(ID_PATTERN.match(value)) and value not in (".", "..")


def _strip_quotes(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == '"' and value.endswith('"'):
        return re.sub(r'\\(["\\])', r"\1", value[1:-1])
    if len(value) >= 2 and value[0] == "'" and value.endswith("'"):
        return value[1:-1]
    return value


def parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    """极简 frontmatter：只取 `key: 标量`，其余形式保留为原文（角色文件只用标量）。"""
    text = raw.lstrip("﻿")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = -1
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end == -1:
        return {}, text
    data: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0].isspace():  # 缩进行属于列表/映射，标量解析不支持，跳过
            continue
        key, sep, value = line.partition(":")
        if not sep:
            continue
        data[key.strip()] = _strip_quotes(value)
    body = "\n".join(lines[end + 1 :])
    return data, body.lstrip("\n")


class PersonaStore:
    """角色文件的读取。不含 Qt，可纯 Python 测试。"""

    def __init__(self, home: Optional[Path | str] = None) -> None:
        self._home = Path(home) if home is not None else self._default_home()

    @staticmethod
    def _default_home() -> Path:
        override = os.environ.get("DEVA_HOME")
        return Path(override) if override else Path.home() / ".deva"

    @property
    def home(self) -> Path:
        return self._home

    @property
    def dir(self) -> Path:
        return self._home / "personas"

    def _enabled_map(self) -> dict[str, bool]:
        try:
            config = json.loads((self._home / "config.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        section = config.get("personas") if isinstance(config, dict) else None
        enabled = section.get("enabled") if isinstance(section, dict) else None
        return enabled if isinstance(enabled, dict) else {}

    def _order(self) -> list[str]:
        try:
            config = json.loads((self._home / "config.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        section = config.get("personas") if isinstance(config, dict) else None
        order = section.get("order") if isinstance(section, dict) else None
        return [item for item in order if isinstance(item, str)] if isinstance(order, list) else []

    def _parse(self, persona_id: str, raw: str, enabled: bool) -> dict[str, Any]:
        data, body = parse_frontmatter(raw)
        return {
            "id": persona_id,
            "name": data.get("name") or persona_id,
            "description": data.get("description", ""),
            "avatar": data.get("avatar", ""),
            "avatarImage": "",
            "model": data.get("model", ""),
            "prompt": body.strip(),
            "enabled": enabled,
        }

    def list_personas(self) -> list[dict[str, Any]]:
        if not self.dir.exists():
            return []
        enabled = self._enabled_map()
        records: list[dict[str, Any]] = []
        for entry in sorted(self.dir.iterdir()):
            if entry.suffix.lower() != ".md":
                continue
            persona_id = entry.stem
            if not is_safe_id(persona_id):
                continue
            try:
                raw = entry.read_text(encoding="utf-8")
            except OSError:
                continue  # 读失败跳过该文件（Deva 同口径）
            records.append(self._parse(persona_id, raw, enabled.get(persona_id) is True))
        order = self._order()
        rank = {persona_id: index for index, persona_id in enumerate(order)}
        big = float("inf")
        records.sort(key=lambda r: (rank.get(r["id"], big), r["name"]))
        return records

    def get(self, persona_id: str) -> Optional[dict[str, Any]]:
        if not is_safe_id(persona_id):
            return None
        try:
            raw = (self.dir / f"{persona_id}.md").read_text(encoding="utf-8")
        except OSError:
            return None
        return self._parse(persona_id, raw, self._enabled_map().get(persona_id) is True)

    def ensure_seeded(self) -> list[str]:
        """首启种子：缺失的默认角色从打包资产复制进来（按 id 幂等，删了不复活——见下方说明）。"""
        seeded: list[str] = []
        source = _assets_dir()
        if not source.is_dir():
            return seeded
        self.dir.mkdir(parents=True, exist_ok=True)
        for persona_id in DEFAULT_PERSONA_IDS:
            target = self.dir / f"{persona_id}.md"
            origin = source / f"{persona_id}.md"
            if target.exists() or not origin.exists():
                continue
            target.write_text(origin.read_text(encoding="utf-8"), encoding="utf-8")
            seeded.append(persona_id)
        return seeded


ALLOWED_WRITES_NOTE = "角色写入（upsert / remove / 排序 / 头像）尚未接入"


def not_implemented(what: str) -> None:
    """未接入的写入通道显式报错，不假装成功。"""
    raise NotImplementedError(f"{what}：{ALLOWED_WRITES_NOTE}")


__all__ = [
    "DEFAULT_PERSONA_IDS",
    "PersonaStore",
    "is_safe_id",
    "not_implemented",
    "parse_frontmatter",
]
