"""技能（Skills）服务：读 `~/.deva/skills/<id>/SKILL.md`，格式与 Deva `services/skills.ts` 一致。

移植口径（逐条对齐原版）：
- 身份 = 文件夹名（id），显示名 = frontmatter `name`；
- 启用态不在 SKILL.md 里，存在 `config.json` 的 `skills.enabled[id]`，**映射里没有即启用**
  （`!= False` 判定）——模型直接落盘的技能文件夹不必再开一道开关；
- 可用角色存在 `config.json` 的 `skills.roles[id]`，**映射里没有 = 全部角色**；
- 内置元技能（create-skill / create-agent / create-mcp）在代码里合成、永不落盘、恒启用，
  且**磁盘同名目录不得影子内置技能**；
- 解析失败的目录跳过，绝不让一个坏文件拖垮扩展页。

读写范围：列表 / 单条 / 启停 / 角色白名单 / 删除。文件导入（zip 技能包）依赖解压与限额
校验，尚未接入，桥层直接显式报「未实现」（不返回假成功）。
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from mvvm.services.persona_store import is_safe_id

# 正文与描述直接照抄原版 `services/skills.ts`（同一份常量，改字会改变模型行为）。
_CREATE_SKILL_INSTRUCTIONS = """你正在帮助用户创建一个新的**技能（Skill）**。技能是技能目录（绝对路径见系统提示词【技能】段）下的一个文件夹：入口 `SKILL.md` 说明「何时用、怎么做」，复杂的技能再附带脚本、参考文档、模板等资源。启用后只有 name 与 description 常驻模型看到的技能清单；命中场景或用户输入 `/技能名` 时才加载 SKILL.md 正文；附带资源在执行中按需读取或运行。

## 原则

- **精简**：上下文是所有内容共用的。只写模型本身不知道的东西（流程、约定、专有知识、易错点），不解释常识；示例优于长篇说明。
- **约束程度随任务的容错度而定**：多种做法都可行时，写原则与判断要点；有推荐做法时，给伪代码或带参数的脚本；操作容易出错、必须严格按顺序执行时，写成固定脚本，少留参数。
- **渐进式披露**：SKILL.md 正文控制在 500 行以内；大段参考资料拆到 `references/`，并在正文里写明「什么情况下读哪个文件」；上万字的大文件再附上可供 grep 的关键词。

## 目录结构

```
<技能名>/
├── SKILL.md       （必需）frontmatter + 正文
├── scripts/       （可选）可执行脚本：每次都要重写的代码，或要求结果确定的操作
├── references/    （可选）参考文档：接口说明、数据结构、业务规则等，执行时按需 read_file
└── assets/        （可选）产出中要用到的文件：模板、图标、示例文件等，不读进上下文
```

只建用得上的子目录，不要建空目录；不要写 README、CHANGELOG、安装说明之类的附属文件。

## 步骤

1. **从具体用例弄清用途**：技能要解决什么问题、用户会怎么说来触发它、期望的产出是什么。用户已经说清楚就直接往下做；不清楚时一次只问一两个关键问题，能先提出一份具体的功能草案让用户修改，就不要连环追问。
2. **规划可复用资源**：逐个用例想一遍：哪些代码每次都会重写（放 `scripts/`），哪些资料执行时需要查阅（放 `references/`），哪些文件要用进产出（放 `assets/`）。用户手头的文档、模板等素材，请用户提供后放进对应目录。规划下来没有任何附带资源，就是单文件技能。
3. **确定名称**：只用小写字母、数字和短横线，宜用动词短语（如「Plan Mode」写成 `plan-mode`）；文件夹名与 `name` 一致。先用 list_dir 查看技能目录，避开已有的文件夹和内置技能名（create-skill、create-agent、create-mcp）。
4. **落盘**：不必先向用户复述草案、等待确认，按技能形态二选一直接写入：
   - **单文件技能**：调用 `create_skill` 工具（参数：name、description、trigger、allowedTools、instructions）。
   - **多文件技能**：在技能目录下建 `<技能名>/`，先用 write_file 写各资源文件，脚本写完**必须用 run_command 实际运行一次**确认可用，最后写 SKILL.md。用户给了现成的压缩包或仓库时，也可以用 run_command 下载并解压到该文件夹。
   - 只在技能目录内写入，不要改配置目录里的其他文件（config.json、secrets.json 等）。
5. **校验**（多文件技能逐项检查，单文件技能由 create_skill 负责）：
   - SKILL.md 位于文件夹根目录，第一行是 `---`，frontmatter 以 `---` 结束；
   - `name` 存在且与文件夹名一致；`description` 存在且只占一行；
   - 正文不超过 500 行，引用的每个相对路径都真实存在，没有残留的 TODO；
   - 没有多余文件。发现问题先修好，再告知用户。
6. **告知结果**：技能落盘即自动启用，下一轮对话起进入技能清单。向用户列出 description 原文（它决定技能何时被调用）和文件清单（每个文件一句话说明），告诉用户可以用 `/技能名` 触发，也可以在「扩展」页查看或关闭；有不合意之处或实际用下来发现不足，再据此修改。

## SKILL.md 写法

```
---
name: pdf-tools
description: 处理 PDF 文件：旋转、合并、拆分、提取文字。用户要编辑或转换 PDF 时使用。
trigger: （可选）触发方式的补充说明
allowed-tools: run_command, read_file
---

# PDF 工具

（一两句话说明这个技能能做什么）

## 用法

（操作步骤，用祈使句写）

## 资源

- `scripts/rotate.py`：旋转页面，用法 `python <技能文件夹>/scripts/rotate.py <输入文件> <角度>`
- `references/forms.md`：处理表单字段时读取
```

- **description 决定何时触发**：只有它常驻技能清单，模型靠它判断要不要加载技能。写清做什么、什么时候用（场景、文件类型、用户的典型说法）。**必须写在一行内**，不支持 YAML 的多行写法（`|`、`>`）。
- `trigger`、`allowed-tools` 可选；`allowed-tools` 只是建议，不授予任何权限。
- 正文写给执行任务的模型看，用祈使句，不必重复 description。
- 引用文件写**相对技能文件夹**的路径；加载技能时会给出文件夹的绝对路径，届时用 read_file 读取、用 run_command 运行。
- 脚本的输出要便于模型阅读：成功或失败信息明确，长输出截断或分页，不要输出整屏的错误堆栈。脚本语言优先选用户机器上已有的（先用 run_command 查 `python --version` 或 `node -v`），并兼顾 Windows 与 macOS。"""

_CREATE_AGENT_INSTRUCTIONS = """你正在帮助用户创建一个新的**角色（Agent / 性格身份）**。角色是一个带专属系统提示词的对话身份——它决定助手的性格、语气、专长与行为准则；创建并启用后，用户可在角色列表里选它发起对话。

请按以下步骤引导用户：

1. **弄清用途（最多问一次）**：用一次 ask_user 问清这个角色是干什么的——面向什么任务/领域、期望怎样的性格与语气，名字和该做/不该做的准则可设为选填。用户的话里已说清用途和性格时不必再问。
2. **拟定要素**：据用户的回答拟定，用户没给的按用途合理补全：
   - `name`：角色显示名（如「代码审查员」「产品经理小美」）。
   - `description`：一句话专长/定位，会显示在名片与角色资料上。
   - `prompt`：**系统提示词**——角色的核心。用 Markdown 写清性格、语气、专长、行为准则；这决定角色「是谁、怎么说话、怎么做事」。
   - ⚠️ **不要设置 model**：你无法可靠得知可用的模型 id，留空即可（角色跟随默认模型，用户可在编辑器里自己选）。
   - ⚠️ **不要设置头像**：头像由系统按角色名自动生成，用户接受名片后可在编辑器里挑部件与配色。
3. **生成名片**：拿到回答后**直接调用 `propose_agent` 工具**（参数：name、description、prompt）。**不要先复述草案、也不要再用 ask_user 确认**——名片本身就是给用户确认的草案，用户可点开查看、在编辑器里微调后再接受。
   - ⚠️ 该工具**只是生成一张「角色名片」供用户确认，并不会真正创建角色**；不要用 `create_skill`/`write_file` 等去创建角色。
4. **告知结果**：调用后**不要声称角色已创建**。应告诉用户：「角色名片已生成，请点开名片查看——你还能在里面微调，满意后点『接受』即可加入角色列表。」

保持简洁友好，一次问清关键信息即可，不要连环追问。"""

_CREATE_MCP_INSTRUCTIONS = """你正在帮助用户接入一个新的 **MCP 服务（Model Context Protocol server）**。MCP 服务对外暴露一组工具/资源；接入并连接后，其工具会自动出现在助手的可用工具里。

请按以下步骤引导用户：

1. **弄清用途**：先问清用户想接入哪个 MCP 服务、它提供什么能力、从哪里获取（官方文档 / npm 包名 / 服务地址）。
2. **确定传输方式**（这是关键分叉）：
   - `stdio`（本地子进程，最常见）：需要 `command`（如 `npx`、`uvx`、`node`）与 `args`（参数清单，如 `["-y", "@modelcontextprotocol/server-filesystem", "/some/path"]`）。
   - `sse` / `http`（远程服务）：需要 `url`（服务地址）。
3. **收集要素**（逐项与用户确认，不要臆造包名/命令）：
   - stdio：`command`、`args`、非敏感环境变量 `env`（明文键值）。
   - sse/http：`url`、非敏感请求头 `headers`（明文键值）。
   - **密钥（API Key / Token 等）**：⚠️ **绝不要向用户索要、也绝不要把真实密钥值写进工具参数或对话**。你只需问清「有哪些字段是密钥」，把这些**字段名**放进 `secretEnv`（环境变量名，如 `GITHUB_TOKEN`）或 `secretHeaders`（请求头名，如 `Authorization`）。工具只写占位符，真实值由用户稍后在「扩展」页加密填入。
4. **复述草案**：先在回复正文里完整列出整理好的要素（传输方式、命令/地址、参数、哪些字段是密钥），再用 ask_user 请用户确认或修改——问题卡片里看不到你没写出来的内容。
5. **落盘**：用户确认后，**调用 `create_mcp` 工具**写入。
   - ⚠️ **不要用 `write_file` 或 `run_command` 直接写 mcp.json**——`create_mcp` 会校验配置并写入密钥占位符，直接写会绕过这些。
6. **告知结果**：创建成功后服务会**自动启用并在后台连接**，连上后其工具从用户的**下一条消息**起可用。若存在密钥占位字段，务必提醒用户：**去「扩展」页为该服务填写这些密钥（加密存储）**，填好后会自动连接，无需其他操作。

保持简洁友好，一次问清关键信息即可，不要连环追问。"""

BUILTIN_SKILLS: list[dict[str, Any]] = [
    {
        "id": "create-skill",
        "name": "create-skill",
        "description": (
            "引导用户从零创建一个新技能：从用例规划脚本、参考文档、模板等资源，落盘、校验并启用"
            "（单文件调 create_skill，多文件直接写进技能目录）。"
        ),
        "trigger": "输入 /create-skill，或表达「帮我做/创建一个技能」时触发。",
        "allowedTools": ["create_skill", "list_dir", "write_file", "read_file", "run_command"],
        "license": "",
        "compatibility": "",
        "metadata": {},
        "instructions": _CREATE_SKILL_INSTRUCTIONS,
        "enabled": True,
        "roles": None,
        "source": "builtin",
    },
    {
        "id": "create-agent",
        "name": "create-agent",
        "description": "引导用户用对话创建一个新角色：最多问一次厘清用途，随即调 propose_agent 生成名片供确认。",
        "trigger": "输入 /create-agent，或表达「帮我做/创建一个角色/性格/身份」时触发。",
        "allowedTools": ["propose_agent"],
        "license": "",
        "compatibility": "",
        "metadata": {},
        "instructions": _CREATE_AGENT_INSTRUCTIONS,
        "enabled": True,
        "roles": None,
        "source": "builtin",
    },
    {
        "id": "create-mcp",
        "name": "create-mcp",
        "description": (
            "引导用户用对话接入一个 MCP 服务：厘清用途与传输方式、收集要素（密钥仅收字段名）、"
            "确认后调 create_mcp 工具落盘并启用。"
        ),
        "trigger": "输入 /create-mcp，或表达「帮我接入/添加/创建一个 MCP（服务）」时触发。",
        "allowedTools": ["create_mcp"],
        "license": "",
        "compatibility": "",
        "metadata": {},
        "instructions": _CREATE_MCP_INSTRUCTIONS,
        "enabled": True,
        "roles": None,
        "source": "builtin",
    },
]

RESERVED_IDS = {skill["id"] for skill in BUILTIN_SKILLS}


class SkillStore:
    """读取技能目录，返回与 Deva `SkillRecord[]` 同形状的列表。"""

    def __init__(self, home: Path) -> None:
        self.home = Path(home)

    @property
    def dir(self) -> Path:
        return self.home / "skills"

    # ── 配置 ──────────────────────────────────────────────────────────────
    def _section(self, name: str) -> dict[str, Any]:
        path = self.home / "config.json"
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        section = config.get(name) if isinstance(config, dict) else None
        return section if isinstance(section, dict) else {}

    def _enabled_map(self) -> dict[str, bool]:
        enabled = self._section("skills").get("enabled")
        return enabled if isinstance(enabled, dict) else {}

    def _roles_map(self) -> dict[str, list[str]]:
        roles = self._section("skills").get("roles")
        if not isinstance(roles, dict):
            return {}
        return {
            key: [x for x in value if isinstance(x, str)]
            for key, value in roles.items()
            if isinstance(value, list)
        }

    # ── 列表 / 单条 ────────────────────────────────────────────────────────
    def list_skills(self) -> list[dict[str, Any]]:
        """目录尚未创建时也返回内置技能——它们不依赖磁盘，否则扩展页首启会误显空态。"""
        if not self.dir.exists():
            return [dict(skill) for skill in BUILTIN_SKILLS]
        try:
            entries = [p.name for p in self.dir.iterdir()]
        except OSError:
            return []
        enabled = self._enabled_map()
        roles = self._roles_map()
        out: list[dict[str, Any]] = []
        for skill_id in entries:
            if not is_safe_id(skill_id) or skill_id in RESERVED_IDS:
                continue
            folder = self.dir / skill_id
            try:
                if not folder.is_dir():
                    continue
                raw = (folder / "SKILL.md").read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue  # 无 SKILL.md / 读失败 → 跳过该目录
            out.append(
                parse_skill(skill_id, raw, enabled.get(skill_id) is not False, roles.get(skill_id))
            )
        # 原版是 `a.name.localeCompare(b.name)`：默认（ICU en-US）按基字母排、大小写只作末位。
        # ASCII 名与 casefold 排序等价；中文等非 ASCII 名在终端默认排序下可能与此不同（已记入台账）。
        from functools import cmp_to_key
        from utils.qt_compat import QtCore
        collator = QtCore.QCollator(QtCore.QLocale('en_US'))
        out.sort(key=cmp_to_key(lambda a, b: collator.compare(a['name'], b['name'])))
        return [dict(skill) for skill in BUILTIN_SKILLS] + out

    def get(self, skill_id: str) -> dict[str, Any] | None:
        for skill in BUILTIN_SKILLS:
            if skill["id"] == skill_id:
                return dict(skill)
        if not is_safe_id(skill_id):
            return None
        try:
            raw = (self.dir / skill_id / "SKILL.md").read_text(encoding="utf-8")
        except OSError:
            return None
        return parse_skill(
            skill_id,
            raw,
            self._enabled_map().get(skill_id) is not False,
            self._roles_map().get(skill_id),
        )


    # ── 写（Deva `skills:set-enabled` / `set-roles` / `remove`）──────────────
    def _write_section(self, section: dict[str, Any]) -> None:
        """写 `config.json` 的 `skills` 段（原版走 `setConfig` 顶层浅合并，失败静默）。"""
        path = self.home / "config.json"
        try:
            config = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(config, dict):
                config = {}
        except (OSError, ValueError):
            config = {}
        config["skills"] = section
        try:
            self.home.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass  # 原版同口径：persist 吞异常

    def _skills_section(self) -> dict[str, Any]:
        section = self._section("skills")
        return dict(section)

    def set_enabled(self, skill_id: Any, enabled: Any) -> dict[str, bool]:
        """写启用位；内置技能与非法 id 一律 no-op，恒回 `{ok:true}`（原版语义）。"""
        key = str(skill_id or "")
        if key and is_safe_id(key) and key not in RESERVED_IDS:
            section = self._skills_section()
            current = section.get("enabled") if isinstance(section.get("enabled"), dict) else {}
            self._write_section({**section, "enabled": {**current, key: enabled is True}})
        return {"ok": True}

    def set_roles(self, skill_id: Any, roles: Any) -> dict[str, bool]:
        """写可用角色；内置 / 非法 id → `{ok:false}`；`roles` 非数组按 `null`（= 全部角色）。

        数组会去重并剔除空串与非字符串；`null` 时删除该键（原版 `setRoles`）。
        """
        key = str(skill_id or "")
        if not key or not is_safe_id(key) or key in RESERVED_IDS:
            return {"ok": False}
        section = self._skills_section()
        current = section.get("roles") if isinstance(section.get("roles"), dict) else {}
        cleaned: list[str] | None = None
        if isinstance(roles, list):
            cleaned = []
            for item in roles:
                if isinstance(item, str) and item and item not in cleaned:
                    cleaned.append(item)
        next_roles = {k: v for k, v in current.items() if k != key}
        if cleaned is not None:
            next_roles[key] = cleaned
        self._write_section({**section, "roles": next_roles})
        return {"ok": True}

    def import_file(self, path: Any) -> dict[str, Any]:
        """从 .md / .zip 导入技能（Deva `skills.ts:627-639`），成功自动启用。"""
        import zipfile
        source = Path(str(path or ""))
        lower = source.name.lower()
        if lower.endswith(".md"):
            try:
                return self._write_imported(source.read_text(encoding="utf-8"), [])
            except (OSError, UnicodeError):
                return {"ok": False, "error": "import-failed"}
        if lower.endswith(".zip"):
            try:
                with zipfile.ZipFile(source) as archive:
                    files = {n: archive.read(n) for n in archive.namelist() if not n.endswith("/") and not n.startswith("__MACOSX/")}
            except (OSError, zipfile.BadZipFile):
                return {"ok": False, "error": "bad-zip"}
            if "SKILL.md" in files:
                base = ""
            else:
                depth1 = [n for n in files if re.fullmatch(r"[^/]+/SKILL\.md", n)]
                if len(depth1) != 1:
                    return {"ok": False, "error": "no-skill-md"}
                base = depth1[0][:-len("SKILL.md")]
            if len(files) > 200:
                return {"ok": False, "error": "too-many-files"}
            total = sum(len(v) for v in files.values())
            if total > 20 * 1024 * 1024:
                return {"ok": False, "error": "too-large"}
            try:
                raw = files[base + "SKILL.md"].decode("utf-8")
            except (KeyError, UnicodeError):
                return {"ok": False, "error": "no-skill-md"}
            extra = []
            for name, data in files.items():
                if name == base + "SKILL.md":
                    continue
                rel = name[len(base):]
                parts = rel.split("/")
                if any(part in ("", ".", "..") or "\\" in part or ":" in part for part in parts):
                    return {"ok": False, "error": "unsafe-path"}
                extra.append((rel, data))
            return self._write_imported(raw, extra)
        return {"ok": False, "error": "unsupported-type"}

    def _write_imported(self, raw: str, extra: list[tuple[str, bytes]]) -> dict[str, Any]:
        data, _ = parse_frontmatter(raw)
        name = fm_string(data, "name").strip()
        if not name:
            return {"ok": False, "error": "missing-name"}
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "skill"
        if not is_safe_id(slug) or slug in RESERVED_IDS:
            return {"ok": False, "error": "invalid-name"}
        folder = self.dir / slug
        try:
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "SKILL.md").write_text(raw, encoding="utf-8")
            for rel, payload in extra:
                target = (folder / rel).resolve()
                if folder.resolve() not in target.parents:
                    return {"ok": False, "error": "unsafe-path"}
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
        except OSError:
            return {"ok": False, "error": "write-failed"}
        self.set_enabled(slug, True)
        return {"ok": True, "id": slug, "name": name}

    def remove(self, skill_id: Any) -> dict[str, bool]:
        """删除自定义技能目录；内置 / 非法 id → `{ok:false}`；目录本不存在视为成功。

        成功时连带删 `skills.enabled[id]` 与 `skills.roles[id]`（原版 `deleteSkill`）。
        原版用 `shell.trashItem` 移入回收站；这里直接删除目录（Linux 上无统一回收站接口，
        差异已记入台账）。
        """
        key = str(skill_id or "")
        if not key or not is_safe_id(key) or key in RESERVED_IDS:
            return {"ok": False}
        folder = self.dir / key
        try:
            if folder.exists():
                shutil.rmtree(folder)
        except OSError:
            return {"ok": False}
        section = self._skills_section()
        enabled = section.get("enabled") if isinstance(section.get("enabled"), dict) else {}
        enabled.pop(key, None)
        roles = section.get("roles") if isinstance(section.get("roles"), dict) else {}
        roles.pop(key, None)
        self._write_section({**section, "enabled": enabled, "roles": roles})
        return {"ok": True}


# ── frontmatter 解析（照抄 Deva `services/frontmatter.ts` 的四类条目）──────────
_FM_KEY = re.compile(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$")
_FM_ITEM = re.compile(r"^\s*-\s+(.*)$")
_FM_SUB = re.compile(r"^\s+([A-Za-z0-9_.-]+)\s*:\s*(.*)$")


def _strip_quotes(value: str) -> str:
    s = value.strip()
    if len(s) >= 2 and s[0] == '"' and s.endswith('"'):
        return re.sub(r'\\(["\\])', r"\1", s[1:-1])
    if len(s) >= 2 and s[0] == "'" and s.endswith("'"):
        return s[1:-1]
    return s


def parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    """返回 (data, body)。无有效 `---` 头部时 data 为空、body 为原文（容错，绝不抛错）。"""
    text = raw.lstrip("﻿")
    lines = re.split(r"\r?\n", text)
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = -1
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end = index
            break
    if end == -1:
        return {}, text

    data: dict[str, Any] = {}
    i = 1
    while i < end:
        line = lines[i]
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            i += 1
            continue
        match = _FM_KEY.match(line)
        if not match:
            i += 1
            continue
        key, rest = match.group(1), match.group(2).strip()
        if rest.startswith("[") and rest.endswith("]"):
            inner = rest[1:-1]
            data[key] = [v for v in (_strip_quotes(x) for x in inner.split(",")) if v]
            i += 1
        elif rest == "":
            items: list[str] = []
            sub: dict[str, str] = {}
            j = i + 1
            while j < end:
                item = _FM_ITEM.match(lines[j])
                if item:
                    value = _strip_quotes(item.group(1))
                    if value:
                        items.append(value)
                    j += 1
                    continue
                nested = _FM_SUB.match(lines[j])
                if not nested:
                    break
                sub[nested.group(1)] = _strip_quotes(nested.group(2))
                j += 1
            data[key] = items if items or not sub else sub
            i = j
        else:
            data[key] = _strip_quotes(rest)
            i += 1

    body_start = end + 1
    if body_start < len(lines) and lines[body_start].strip() == "":
        body_start += 1
    return data, "\n".join(lines[body_start:])


def fm_string(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return ""


def fm_array(data: dict[str, Any], key: str) -> list[str]:
    """字符串数组；标量按逗号 / 空白拆分，括号内的空白与逗号不拆（`Bash(git add:*)`）。"""
    value = data.get(key)
    if isinstance(value, list):
        return [str(x) for x in value]
    if not isinstance(value, str):
        return []
    out: list[str] = []
    cur = ""
    depth = 0
    for ch in value:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if depth == 0 and (ch == "," or ch.isspace()):
            if cur.strip():
                out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def fm_map(data: dict[str, Any], key: str) -> dict[str, str]:
    value = data.get(key)
    return dict(value) if isinstance(value, dict) else {}


def parse_skill(
    skill_id: str, raw: str, enabled: bool, roles: list[str] | None
) -> dict[str, Any]:
    data, body = parse_frontmatter(raw)
    return {
        "id": skill_id,
        "name": fm_string(data, "name") or skill_id,
        "description": fm_string(data, "description"),
        "trigger": fm_string(data, "trigger"),
        "allowedTools": fm_array(data, "allowed-tools"),
        "license": fm_string(data, "license"),
        "compatibility": fm_string(data, "compatibility"),
        "metadata": fm_map(data, "metadata"),
        "instructions": body.strip(),
        "enabled": enabled,
        "roles": roles,
        "source": "custom",
    }


__all__ = ["BUILTIN_SKILLS", "RESERVED_IDS", "SkillStore", "parse_frontmatter", "parse_skill"]
