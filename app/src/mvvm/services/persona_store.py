"""角色（Personas）服务：读写 `<数据目录>/personas/<id>.md`（缺省 `~/.ai_upper`），格式与 Deva `services/personas.ts` 一致。

读写范围：列表 / 单条读取 / 首启种子 / upsert / 删除 / 启用位 / 排序 / 头像图片。
所有写路径都对齐原版语义（含「忽略非法 id 但仍回成功」「写异常吞掉仍返回记录」这类
看起来像 bug 但界面依赖的行为），逐条注释说明来源。

落盘口径（与 Deva 逐条对齐）：
- 身份 = 文件名去 `.md`（id），显示名 = frontmatter `name`；
- 启用态不在 `.md` 里，存在 `config.json` 的 `personas.enabled[id]`，缺省关闭；
- 头像 spec 是 frontmatter `avatar`（Humation AvatarSpec 的 JSON 字符串），空则渲染层按 id 确定性生成；
- 排序：`personas.order` 中的 id 按位置在前，其余按名称本地化排序；
- 解析失败的文件跳过，绝不让一条坏文件拖垮列表。
"""
from __future__ import annotations
from locale_runtime import tr

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

from mvvm.services.avatar_image import clear_avatar_image, read_avatar_image, write_avatar_image

ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")

# 首启种子：与 Deva `default-personas.ts` 里的两条默认角色同源（正文即各角色提示词）。
DEFAULT_PERSONA_IDS = ("general", "xiaomajiang")


def _assets_dir() -> Path:
    """首启种子目录：开发态 app/assets/personas，打包后 <bundle>/assets/personas。"""
    from utils.paths import assets_root

    return assets_root() / "personas"


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
        from utils.app_home import app_home

        return app_home()

    @property
    def home(self) -> Path:
        return self._home

    @property
    def dir(self) -> Path:
        return self._home / "personas"

    @property
    def avatars_dir(self) -> Path:
        return self.dir / "avatars"

    def _avatar_image(self, persona_id: str) -> str:
        """读自定义头像 → data URI；没有则空串（渲染层按 id 确定性生成）。"""
        return read_avatar_image(self.avatars_dir, persona_id)

    def _write_section(self, section: dict[str, Any]) -> None:
        """把 `config.json` 的 `personas` 段整体写回（原版走 `setConfig` 的顶层浅合并）。

        写失败**不抛**：原版 `persist()` 吞异常，界面不该因为一次排序写盘失败而报错。
        """
        path = self._home / "config.json"
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(config, dict):
                config = {}
        except (OSError, ValueError):
            config = {}
        config["personas"] = section
        try:
            self._home.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass  # 原版同口径：写失败静默

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
            "avatarImage": self._avatar_image(persona_id),
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

    # ── 写（Deva `personas:upsert` / `remove` / `set-enabled` / `reorder` / 头像）──
    def upsert(self, payload: Any) -> dict[str, Any]:
        """新建或覆盖一个角色文件，返回读回的记录（原版 `upsertPersona`）。

        边界（逐条照原版）：
        - `name` trim 后为空 → `未命名提示词`；
        - 入参 id 通过 `isSafeId` 且文件存在 → 覆盖该文件；否则按名称生成新 id；
        - 写文件异常被吞掉，仍返回记录（原版 `catch {}`）；
        - `enabled` 为布尔才写启用位；新建且未传 → 不写（缺省关闭）。
        """
        data = payload if isinstance(payload, dict) else {}
        name = " ".join(str(data.get("name") or "").split()) or "未命名提示词"
        requested = str(data.get("id") or "")
        existing = requested if is_safe_id(requested) and (self.dir / f"{requested}.md").exists() else ""
        persona_id = existing or make_id(name, set(self._existing_ids()))
        record = {
            "name": name,
            "description": str(data.get("description") or ""),
            "avatar": str(data.get("avatar") or ""),
            "model": str(data.get("model") or ""),
            "prompt": str(data.get("prompt") or ""),
        }
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / f"{persona_id}.md").write_text(
                compose_persona_md(**record), encoding="utf-8"
            )
        except OSError:
            pass  # 原版同口径：写失败吞掉，仍返回记录
        if isinstance(data.get("enabled"), bool):
            self.set_enabled(persona_id, data["enabled"])
        saved = self.get(persona_id)
        return saved if saved is not None else {**record, "id": persona_id, "avatarImage": self._avatar_image(persona_id), "enabled": data.get("enabled") is True}

    def remove(self, persona_id: Any) -> dict[str, bool]:
        """删除角色文件、头像与索引项；非法 id 什么也不做但恒回 ok:true（原版语义）。"""
        key = str(persona_id or "")
        if is_safe_id(key):
            (self.dir / f"{key}.md").unlink(missing_ok=True)
            self.clear_avatar_image(key)
            section = self._personas_section()
            enabled = section.get("enabled") if isinstance(section.get("enabled"), dict) else {}
            enabled.pop(key, None)
            order = [x for x in (section.get("order") or []) if x != key]
            self._write_section({**section, "enabled": enabled, "order": order})
        return {"ok": True}

    def set_enabled(self, persona_id: Any, enabled: Any) -> dict[str, bool]:
        """写启用位；非法 id 什么也不做但恒回 ok:true（原版语义）。"""
        key = str(persona_id or "")
        if is_safe_id(key):
            section = self._personas_section()
            current = section.get("enabled") if isinstance(section.get("enabled"), dict) else {}
            self._write_section({**section, "enabled": {**current, key: bool(enabled)}})
        return {"ok": True}

    def reorder(self, ids: Any) -> dict[str, bool]:
        """写排序；非数组按 `[]`，逐项过滤非字符串 / 非法 id / 重复项（原版语义）。"""
        seen: list[str] = []
        for item in ids if isinstance(ids, list) else []:
            if isinstance(item, str) and is_safe_id(item) and item not in seen:
                seen.append(item)
        self._write_section({**self._personas_section(), "order": seen})
        return {"ok": True}

    def set_avatar_image(self, persona_id: Any, data_uri: Any) -> str:
        """写自定义头像，返回落盘后读回的 data URI；非法入参或写失败回空串（原版语义）。

        白名单：MIME 仅 webp/png/jpeg（含 image/jpg），解码后 1..2MB；写入前删掉同名其它
        后缀，保证一个 id 只有一张图。
        """
        key = str(persona_id or "")
        if not is_safe_id(key):
            return ""
        return write_avatar_image(self.avatars_dir, key, str(data_uri or ""))

    def clear_avatar_image(self, persona_id: Any) -> dict[str, bool]:
        """删除角色的三种扩展名头像；非法 id 什么也不做，恒回 ok:true。"""
        key = str(persona_id or "")
        if is_safe_id(key):
            clear_avatar_image(self.avatars_dir, key)
        return {"ok": True}

    def _existing_ids(self) -> list[str]:
        try:
            return [p.stem for p in self.dir.glob("*.md")]
        except OSError:
            return []

    def _personas_section(self) -> dict[str, Any]:
        try:
            config = json.loads((self._home / "config.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        section = config.get("personas") if isinstance(config, dict) else None
        return dict(section) if isinstance(section, dict) else {}


ALLOWED_WRITES_NOTE = "角色写入（upsert / remove / 排序 / 头像）尚未接入"


def not_implemented(what: str) -> None:
    """未接入的写入通道显式报错，不假装成功。"""
    raise NotImplementedError(tr('legacy.b2fd20806334' ,p0=what, p2=ALLOWED_WRITES_NOTE))


def make_id(name: str, taken: Any) -> str:
    """按名称生成角色 id：slug + 8 位随机 hex，避开已存在的文件（Deva `makeId`）。"""
    import secrets

    slug = re.sub(r"[^A-Za-z0-9]+", "-", name.strip().lower()).strip("-")[:32] or "persona"
    for _ in range(64):
        candidate = f"{slug}-{secrets.token_hex(4)}"
        if is_safe_id(candidate) and candidate not in taken:
            return candidate
    raise RuntimeError(tr('legacy.251ab7ed8779'))


def compose_persona_md(
    *, name: str, description: str = "", avatar: str = "", model: str = "", prompt: str = ""
) -> str:
    """角色文件正文：frontmatter（只写非空标量）+ 提示词（Deva `composePersonaMd`）。

    值里的换行会被压成空格：frontmatter 解析器只认单行标量，写进去就再也读不回来。
    """
    def scalar(value: str) -> str:
        return " ".join(str(value).split())

    lines = ["---", f"name: {scalar(name)}"]
    if description:
        lines.append(f"description: {scalar(description)}")
    if avatar:
        lines.append(f"avatar: {avatar}")
    if model:
        lines.append(f"model: {scalar(model)}")
    lines.append("---")
    return "\n".join(lines) + "\n" + (prompt.rstrip("\n") + "\n" if prompt else "")


__all__ = [
    "DEFAULT_PERSONA_IDS",
    "PersonaStore",
    "compose_persona_md",
    "is_safe_id",
    "make_id",
    "not_implemented",
    "parse_frontmatter",
]
