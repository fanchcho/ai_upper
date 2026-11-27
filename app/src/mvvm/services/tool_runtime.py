"""工具层：声明、执行与结果。

口径来自 Deva `apps/desktop/src/main/services/tools.ts`（19 个内置工具）。本阶段实现可离线
自足的 10 个：`read_file`（文本 / 图片 / Office）、`list_dir`、`glob`、`grep`、`web_fetch`、
`write_file`、`edit_file`、`run_command`、`present_files`、`todo_write`。其余 9 个
（`browser`、`ask_user`、`create_skill`、`memory_*`、`propose_agent`、`create_task`、
`create_mcp`、`exit_plan`）依赖尚未迁移的子系统，**不注册、不伪装可用**，见
`docs/BUILD-PROGRESS.md` 的三档清单。

## 权限模型（与 Deva 的差异，必须记住）

Deva 的工具闸门是**纯同步策略、零弹框**：所有工具一律放行，文件读写与命令执行不设任何
限制（`chat.ts` 的 `needsPermission` 对 `read` / `edit` / `exec` 全返回 false）；唯一会打断
用户的是「未挂载工作区 + 相对路径」时的挂载卡。本工程按迁移计划加了**安全底线**：
所有文件类工具执行前必须过 `WorkspaceGuard`（受信根内），越界返回与 Deva 同文案的
`拒绝访问：路径不在已打开的项目内`。这是刻意差异，不是复刻 Deva 的空闸门。

`run_command` 例外：命令内容无法用路径守卫约束（`cd /tmp && ls` 也会执行），只把工作目录
固定在项目根（未挂载时回落主目录，与 Deva 一致）。该限制如实写在工具描述里。
"""
from __future__ import annotations

import base64
import html as html_module
import json
import os
import random
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from mvvm.models.chat_models import ImagePart
from mvvm.services.glob_match import glob_to_regex, walk_files
from mvvm.services.image_prep import (
    MAX_IMAGE_SOURCE_BYTES,
    format_bytes,
    prepare_image,
    sniff_image_mime,
)
from mvvm.services.office_text import OFFICE_EXT, office_text
from mvvm.services.tool_policy import Decision, decide, is_absolute_anywhere
from mvvm.services.workspace_guard import DENIED, WorkspaceGuard

READ_DEFAULT_LINES = 2000
READ_LINE_CHARS_MAX = 2000
READ_OUTPUT_MAX = 100_000
MAX_READ_BYTES = 2 * 1024 * 1024
MAX_OFFICE_BYTES = 50 * 1024 * 1024

GLOB_RESULT_MAX = 500
GREP_MATCH_MAX = 200
GREP_CONCURRENCY = 16
GREP_LINE_CHARS_MAX = 200

WEB_FETCH_TIMEOUT_S = 30.0
WEB_FETCH_MAX_BYTES = 5 * 1024 * 1024
WEB_TEXT_MAX = 100_000
WEB_USER_AGENT = "ai_upper"

EXEC_OUTPUT_MAX = 30_000
EXEC_TIMEOUT_DEFAULT = 600_000
EXEC_TIMEOUT_MAX = 1_800_000
EXEC_CAPTURE_BYTES = 10 * 1024 * 1024

PRESENT_MAX = 20
PREVIEW_HEAD = 1500
PREVIEW_TAIL = 1500

MISSING_PATH = "缺少有效的 path 参数"
NO_ROOT_RELATIVE = "未挂载工作区，相对路径没有基准：请改用绝对路径（~/ 开头的主目录路径亦可）。"
NO_ROOT_SCAN = "未打开项目，且未提供 path"


@dataclass(frozen=True)
class ToolSpec:
    """工具声明（给模型看的 JSON Schema）。"""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    content: str
    is_error: bool = False
    summary: str = ""
    images: Optional[list[ImagePart]] = None
    delivered: Optional[list[str]] = None


READ_FILE_SPEC = ToolSpec(
    name="read_file",
    description=(
        "读取工作区内一个文本文件，返回带行号的内容（便于定位与后续精确编辑）。默认从第 1 行起"
        "最多读 2000 行，超过 2000 字符的行会被截断；可用 offset（起始行，1 起）/ limit（行数）"
        "分段读取大文件，已知目标位置时建议只读相关片段。单次返回内容过大会报错，届时请缩小范围"
        "或先用 grep 定位。path 可相对项目根或绝对。注意：用 edit_file 时 old_string 应为"
        "「去掉行号前缀」的原文。也可读取图片（png / jpg / gif / webp）：图片会随结果直接附给"
        "你查看（过大时自动缩放），offset / limit 对图片无效。Word / Excel / PowerPoint 文件"
        "（.docx / .xlsx / .pptx）返回从中提取的纯文字（不含格式与图片），同样带行号、可分段读取，"
        "但不能用 edit_file 修改。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径，相对项目根或绝对路径"},
            "offset": {"type": "integer", "description": "起始行号（1 起，含）。默认从第 1 行。"},
            "limit": {"type": "integer", "description": "读取行数。默认 2000 行。"},
        },
        "required": ["path"],
    },
)

LIST_DIR_SPEC = ToolSpec(
    name="list_dir",
    description="列出工作区内某个目录的直接子项（目录在前）。用于探索项目结构。不传 path 时默认列项目根。",
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "目录路径，相对项目根或绝对路径。省略则默认项目根。"}
        },
    },
)

GLOB_SPEC = ToolSpec(
    name="glob",
    description=(
        "按 glob 模式匹配工作区内的文件路径（支持 ** 任意层级、* 单层任意、? 单字符、{a,b} 分支，"
        "如 **/*.ts、src/**/*.{ts,tsx}），按最近修改时间倒序返回。默认忽略 node_modules/.git/dist "
        "等目录。用于按名字/类型快速定位文件。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "glob 模式，如 **/*.ts、src/**/*.{ts,tsx}"},
            "path": {"type": "string", "description": "搜索根目录，相对项目根或绝对路径。默认项目根。"},
        },
        "required": ["pattern"],
    },
)

GREP_SPEC = ToolSpec(
    name="grep",
    description=(
        "在工作区内按正则搜索文件内容，返回匹配行（格式 路径:行号: 内容）。可选 glob 限定文件范围"
        "（如 *.ts）、ignore_case 忽略大小写。默认忽略 node_modules/.git/dist 等目录及 .gitignore "
        "忽略的文件（path 直接指向被忽略的目录时照常搜索），跳过二进制与超大文件。用于快速定位代码。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "正则表达式；搜字面量时转义元字符，如 foo\\(；非法正则会退化为纯文本搜索。"},
            "path": {"type": "string", "description": "搜索根目录，相对项目根或绝对路径。默认项目根。"},
            "glob": {"type": "string", "description": "仅搜索匹配该 glob 的文件。不含 / 时只匹配文件名（*.ts 匹配任意层级的 .ts）；含 / 时匹配相对路径。可选。"},
            "ignore_case": {"type": "boolean", "description": "忽略大小写。默认 false。"},
        },
        "required": ["pattern"],
    },
)

WEB_FETCH_SPEC = ToolSpec(
    name="web_fetch",
    description=(
        "获取一个网页 / HTTP(S) 资源并转为可读文本：HTML 自动去标签、解码实体、保留正文；"
        "JSON / 纯文本原样返回。用于查在线文档、读网页、取 API 响应。仅支持 http/https，有超时与"
        "大小上限；正文超过 100000 字符时完整内容存到文件，只返回开头、结尾与文件路径。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "要获取的完整 URL（以 http:// 或 https:// 开头）"}
        },
        "required": ["url"],
    },
)

WRITE_FILE_SPEC = ToolSpec(
    name="write_file",
    description=(
        "把内容写入文件（覆盖式，不存在则创建；父目录不存在会自动创建）。多用于新建文件；改动既有"
        "文件请优先用 edit_file。单次写入内容较多（约 300 行以上）时请分段：先写入开头一部分，再用 "
        "append: true 分次追加其余部分。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径，相对项目根或绝对路径"},
            "content": {"type": "string", "description": "要写入的文本内容（覆盖时为完整内容，追加时为本段内容）"},
            "append": {"type": "boolean", "description": "为 true 时把 content 追加到文件末尾（不存在则创建），用于分段写入大文件。默认 false（覆盖）。"},
        },
        "required": ["path", "content"],
    },
)

EDIT_FILE_SPEC = ToolSpec(
    name="edit_file",
    description=(
        "对工作区内「已存在」的文件做精确替换：把 old_string 匹配到的片段替换为 new_string。"
        "默认要求 old_string 在文件中唯一出现（否则报错——请多带上下文使其唯一）；replace_all=true "
        "时替换所有匹配。这是修改代码的首选（优于覆盖式 write_file）。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "文件路径，相对项目根或绝对路径"},
            "old_string": {"type": "string", "description": "要被替换的原文（需与文件内容逐字符一致，含缩进/换行；去掉 read_file 的行号前缀）"},
            "new_string": {"type": "string", "description": "替换后的新内容"},
            "replace_all": {"type": "boolean", "description": "替换所有匹配（默认 false，仅当 old_string 唯一时替换）"},
        },
        "required": ["path", "old_string", "new_string"],
    },
)

RUN_COMMAND_SPEC = ToolSpec(
    name="run_command",
    description=(
        "执行一条 shell 命令并返回标准输出/错误与退出码（非交互、一次性）。用于构建、测试、git、脚本等。"
        "查找文件、搜索内容、阅读文件请用专用工具 glob / grep / read_file / list_dir，不要用 find、"
        "grep、cat、ls、head 之类的 shell 命令代替。修改文件请用 edit_file，写文件请用 write_file。"
        "命令在 bash/sh 中运行，请写 POSIX/bash 命令。工作目录：已挂载工作区时为项目根，未挂载时为"
        "用户主目录。非交互运行（已禁用分页器/凭据提示/颜色）；默认超时 600000ms（可用 timeout 调整，"
        "最长 1800000ms）；输出超过 30000 字符时完整内容存到文件，只返回开头、结尾与文件路径。"
        "命令本身不受路径守卫约束，破坏性操作（删除、覆盖、强推等）请先确认目标无误。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "要执行的完整命令（可含参数）。"},
            "description": {"type": "string", "description": "对该命令用途的简短说明（可选，用于界面展示）。"},
            "timeout": {"type": "integer", "description": "超时毫秒数（可选，默认 600000，最长 1800000）。"},
        },
        "required": ["command"],
    },
)

PRESENT_FILES_SPEC = ToolSpec(
    name="present_files",
    description=(
        "把本次任务产出的成品文件交付给用户：用户会看到一张交付卡。适用：生成的网页、文档、表格、"
        "演示稿、图片、音视频、数据导出等需要用户查看或使用的成品。不适用：中间产物、临时脚本，"
        "以及只是修改项目源码的编程任务。在文件全部写好后调用一次（调用时会核对文件是否存在），"
        "列出全部成品（最多 20 个）；网站等多文件产物只交付入口文件（如 index.html）。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "成品文件路径列表：绝对路径，或相对已挂载工作区的路径。",
            }
        },
        "required": ["paths"],
    },
)

TODO_WRITE_SPEC = ToolSpec(
    name="todo_write",
    description=(
        "创建并维护当前任务的待办清单，界面会实时显示进度。适用：需要 3 步及以上的多步骤任务、"
        "用户一次交代了多件事。不适用：单步或琐碎的任务、纯答疑。每次调用都传**完整**清单（整表覆盖，"
        "不是增量）；同一时刻只保留一项 in_progress；做完立即标为 completed；执行中发现新步骤随时"
        "补进清单。任务被暂停、用户转向别的事而不再进行当前清单时，传 cancel: true 取消它（无需 todos）。"
    ),
    input_schema={
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "description": "完整的待办清单，按执行顺序排列。",
                "items": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "这一项要做的事：简短的祈使句。"},
                        "status": {
                            "type": "string",
                            "enum": ["pending", "in_progress", "completed"],
                            "description": "pending=待办 / in_progress=进行中（同一时刻只一项）/ completed=已完成。",
                        },
                    },
                    "required": ["content", "status"],
                },
            },
            "title": {"type": "string", "description": "清单标题，概括这件事。新开清单时给出，更新时可省略。"},
            "new_list": {"type": "boolean", "description": "当前清单尚未完成、却要放下它另起一件新事时传 true。"},
            "cancel": {"type": "boolean", "description": "取消当前清单时传 true，此时省略 todos。"},
        },
    },
)

DEFAULT_SPECS = (
    READ_FILE_SPEC,
    LIST_DIR_SPEC,
    GLOB_SPEC,
    GREP_SPEC,
    WEB_FETCH_SPEC,
    WRITE_FILE_SPEC,
    EDIT_FILE_SPEC,
    RUN_COMMAND_SPEC,
    PRESENT_FILES_SPEC,
    TODO_WRITE_SPEC,
)


def expand_home(value: str) -> str:
    if value == "~":
        return str(Path.home())
    if value.startswith("~/") or value.startswith("~\\"):
        return str(Path.home() / value[2:])
    return value


def resolve_tool_path(guard: WorkspaceGuard, root: Optional[Path], raw: Any) -> Path:
    """模型给的 path → 绝对路径。

    与 Deva `resolvePath` 一致：`~` 展开、绝对路径直接用、相对路径基于工作区根；
    未挂载工作区 + 相对路径 = 没有基准，明确报错而不是落到进程 cwd。
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(MISSING_PATH)
    expanded = expand_home(raw)
    candidate = Path(expanded)
    # 与 `needs_workspace_mount` 同一口径：Windows 上 `/tmp/x`（当前盘根写法）算绝对路径。
    # 若这里退回宿主 `Path.is_absolute`，判定层说「有基准」，解析层却把它接到工作区根下，
    # 同一个 path 在两处得到不同落点。
    if not is_absolute_anywhere(expanded):
        if root is None:
            raise ValueError(NO_ROOT_RELATIVE)
        candidate = Path(root) / candidate
    return candidate


def resolve_read_dir(root: Optional[Path], raw: Any) -> Path:
    """搜索根目录（读取语义）：给了 path 用之，否则回落项目根；两者皆缺则报错。"""
    if isinstance(raw, str) and raw.strip():
        expanded = expand_home(raw)
        candidate = Path(expanded)
        return candidate if is_absolute_anywhere(expanded) else Path(root) / candidate
    if root is None:
        raise ValueError(NO_ROOT_SCAN)
    return Path(root)


def looks_binary(buf: bytes) -> bool:
    return b"\x00" in buf[:8000]


def write_text_lf(path: Path, text: str) -> None:
    """按给定的换行符逐字写盘，不跟随宿主平台的换行转换。

    `Path.write_text` 用 `open(..., newline=None)`，写出的 `\\n` 在 Windows 上会变成
    `\\r\\n`。本模块的换行语义是**文件自己的**（`dominant_eol`），不是宿主的：一个 LF
    文件在 Windows 上被 edit_file 改一行，不能整篇变成 CRLF；已经按 CRLF 拼好的结果也
    不能被再展开成 `\\r\\r\\n`。所以写入固定 `newline=""`，让调用方给出的字符原样落盘。
    """
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def dominant_eol(text: str) -> str:
    """文件的主导换行风格：CRLF 行数不少于纯 LF 行数即视为 CRLF；无换行按 LF。"""
    crlf = text.count("\r\n")
    lf_only = text.count("\n") - crlf
    return "\r\n" if crlf > 0 and crlf >= lf_only else "\n"


def norm_eol(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def head_of(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    cut = text.rfind("\n", 0, n)
    return text[: cut if cut > n / 2 else n]


def tail_of(text: str, n: int) -> str:
    if len(text) <= n:
        return text
    start = len(text) - n
    nl = text.find("\n", start)
    return text[nl + 1 if 0 <= nl < start + n / 2 else start :]


PROPOSE_AGENT_SPEC = ToolSpec('propose_agent', '生成角色名片供用户确认；不写盘、不创建角色。', {
    'type': 'object', 'properties': {'name': {'type': 'string'}, 'description': {'type': 'string'}, 'prompt': {'type': 'string'}}, 'required': ['name']})
CREATE_TASK_SPEC = ToolSpec('create_task', '生成定时任务确认名片；用户确认后才创建任务。', {
    'type': 'object', 'properties': {'title': {'type': 'string'}, 'prompt': {'type': 'string'},
        'schedule': {'type': 'object', 'properties': {'kind': {'type': 'string'}, 'at': {'type': 'string'}, 'cron': {'type': 'string'}, 'tz': {'type': 'string'}}, 'required': ['kind']}},
    'required': ['title', 'prompt', 'schedule']})

class ToolRuntime:
    """工具注册表 + 执行入口。文件类工具一律先过 `guard.assert_inside`。"""

    def __init__(
        self,
        guard: WorkspaceGuard,
        root: Optional[Path | str] = None,
        tools: Optional[dict[str, tuple[ToolSpec, Callable[..., ToolResult]]]] = None,
        *,
        home: Optional[Path | str] = None,
        session_id: str = "_misc",
    ) -> None:
        self.guard = guard
        self.root: Optional[Path] = Path(root) if root is not None else None
        # 超长输出的落点根（Deva `toolResultsDir` 的父目录）：<home>/data/tool-results/<session>/。
        self.home: Optional[Path] = Path(home) if home is not None else None
        self.session_id = session_id or "_misc"
        # todo_write 的落点由会话层注入（写会话边车、推送进度），运行时本身不碰磁盘边车。
        self.todo_sink: Optional[Callable[[str, Any], ToolResult]] = None
        self.plan_sink: Optional[Callable[[str, str, str], None]] = None
        # run_command 的取消检查：由回合层注入，返回 True 表示本轮已被用户停止。
        self.cancel_check: Optional[Callable[[], bool]] = None
        # 本轮是否交互式（有人在场）。False = 密封执行（定时任务），走 sealed_decision。
        # ai_upper 暂不触发密封轮，但判定路径必须先存在，否则将来接定时任务时是空的。
        self.interactive = True
        # 界面是否真的提供挂载卡。没有卡时（当前默认）缺失基准的调用放行到路径解析去报
        # 「请改用绝对路径」，而不是拦成一句没人能应答的挂载请求。
        self.can_request_mount = False
        # 最近一次判定的决策记录（界面 / 测试可查「为什么允许 / 为什么拒绝」）。
        self.last_decision: Optional[Decision] = None
        self.mcp = None
        self.interactions = None
        self.checkpoint = None
        self.approval_enabled: Callable[[], bool] = lambda: False
        self._tools: dict[str, tuple[ToolSpec, Callable[..., ToolResult]]] = dict(tools or {})
        for spec, handler in (
            (READ_FILE_SPEC, self._read_file),
            (LIST_DIR_SPEC, self._list_dir),
            (GLOB_SPEC, self._glob),
            (GREP_SPEC, self._grep),
            (WEB_FETCH_SPEC, self._web_fetch),
            (WRITE_FILE_SPEC, self._write_file),
            (EDIT_FILE_SPEC, self._edit_file),
            (RUN_COMMAND_SPEC, self._run_command),
            (PRESENT_FILES_SPEC, self._present_files),
            (TODO_WRITE_SPEC, self._todo_write),
            (PROPOSE_AGENT_SPEC, self._propose_agent),
            (CREATE_TASK_SPEC, self._create_task_card),
        ):
            if spec.name not in self._tools:
                self.register(spec, handler)

    def register(self, spec: ToolSpec, handler: Callable[..., ToolResult]) -> None:
        self._tools[spec.name] = (spec, handler)

    def specs(self) -> list[ToolSpec]:
        specs = [spec for spec, _ in self._tools.values()]
        if self.mcp is not None:
            specs.extend(self.mcp.specs())
        if self.interactions is not None:
            from mvvm.services.plugin_interactions import ASK_SPEC, PLAN_SPEC
            specs.append(ASK_SPEC); specs.append(PLAN_SPEC)
        return specs

    def close(self) -> None:
        if self.mcp is not None:
            self.mcp.close()

    def resolve_path(self, raw: Any) -> Path:
        return resolve_tool_path(self.guard, self.root, raw)

    def set_session(self, session_id: Optional[str]) -> None:
        self.session_id = session_id or "_misc"

    def execute(self, name: str, arguments: Any, tool_use_id: str = "") -> ToolResult:
        """执行一个工具。未知工具、参数错误、越界都返回 is_error=True 的结果（不抛给上层）。"""
        if name == 'exit_plan' and self.interactions is not None:
            if not self.interactive:
                return ToolResult('密封执行不能提交计划审阅', True)
            arguments = arguments if isinstance(arguments, dict) else {}
            result = self.interactions.plan(self.session_id, tool_use_id, arguments.get('plan', ''), self.cancel_check)
            if result.is_error:
                return result
            row = json.loads(result.content)
            decision = row.get('outcome')
            feedback = row.get('answer', '')
            if self.plan_sink is not None:
                self.plan_sink(tool_use_id, decision, feedback)
            if decision == 'approve':
                return ToolResult('用户已批准计划。现在请按已批准的计划开始执行；多步骤先用 todo_write 列清单。')
            if decision == 'keep':
                return ToolResult('用户暂不批准，对计划的回复如下：\n\n' + (feedback or '请调整计划后重新提交。'))
            if decision == 'ignore':
                return ToolResult('用户忽略了这份计划：不要执行，也不要重新提交，用一句话确认后结束本轮。')
            return ToolResult('用户取消了本次计划审阅。', True)
        if name == 'ask_user' and self.interactions is not None:
            if not self.interactive:
                return ToolResult('密封执行不能向用户提问', True)
            return self.interactions.ask(self.session_id, tool_use_id, arguments, self.cancel_check)
        entry = self._tools.get(name)
        if name.startswith('mcp__') and self.mcp is not None:
            entry = (None, lambda args: self.mcp.execute(name, args))
        if entry is None:
            return ToolResult(f"（未知工具：{name}）", True, "未知工具")
        _, handler = entry
        if not isinstance(arguments, dict):
            return ToolResult(f"（{name} 的参数必须是对象）", True, "参数错误")
        decision = decide(
            name,
            arguments,
            self.root,
            interactive=self.interactive,
            is_mcp_tool=name.startswith('mcp__'),
            can_request_mount=self.can_request_mount,
        )
        self.last_decision = decision
        if not decision.allowed:
            return ToolResult(decision.content, True, decision.summary)
        risky = name in ('run_command', 'write_file', 'edit_file', 'memory_write', 'memory_delete', 'skill_manage', 'browser') or name.startswith('mcp__')
        if risky and self.approval_enabled():
            if self.interactions is None:
                return ToolResult('审批已启用但交互控制器不可用；未执行', True)
            if not self.interactions.approve(self.session_id, tool_use_id, name, arguments, self.cancel_check):
                return ToolResult('审批未通过；未执行', True)
        try:
            invoke = (lambda: self._todo_write(arguments, tool_use_id)) if name == 'todo_write' else (lambda: handler(arguments))
            if self.home is not None:
                from mvvm.services.rewind import Rewind
                original_invoke = invoke
                invoke = lambda: Rewind(self.home, self.session_id).execute(self, name, arguments, original_invoke)
            if self.checkpoint is not None:
                return self.checkpoint.execute(self.session_id, tool_use_id, name, arguments, invoke)
            return invoke()
        except PermissionError as exc:
            return ToolResult(str(exc), True, "越界拒绝")
        except ValueError as exc:
            return ToolResult(str(exc), True, "参数错误")
        except OSError as exc:
            return ToolResult(f"执行失败：{exc.strerror or exc}", True, "执行失败")

    # ── 路径与展示 ────────────────────────────────────────────────────────
    def _propose_agent(self, arguments: dict[str, Any]) -> ToolResult:
        name = str(arguments.get('name') or '').strip()
        if not name:
            return ToolResult('缺少角色 name（角色显示名）', True, '参数无效')
        return ToolResult('已生成角色名片，等待用户在名片中查看并确认；请勿重复调用，也不要声称角色已创建。')

    def _create_task_card(self, arguments: dict[str, Any]) -> ToolResult:
        title = str(arguments.get('title') or '').strip()
        if not title:
            return ToolResult('缺少任务 title（任务标题）', True, '参数无效')
        return ToolResult('已生成定时任务确认名片，等待用户核对日程并确认创建。')

    def _guarded(self, arguments: dict[str, Any]) -> Path:
        """解析 path 并过守卫；返回真实路径。"""
        return self.guard.assert_inside(self.resolve_path(arguments.get("path")))

    def display_path(self, absolute: Path) -> str:
        """项目根内给相对 posix 路径，否则给绝对路径（与 Deva `displayPath` 一致）。"""
        if self.root is not None:
            try:
                rel = absolute.relative_to(self.root).as_posix()
                if rel:
                    return rel
            except ValueError:
                pass
        return str(absolute)

    # ── read_file ─────────────────────────────────────────────────────────
    def _read_file(self, arguments: dict[str, Any]) -> ToolResult:
        absolute = self._guarded(arguments)
        suffix = absolute.suffix.lower()
        try:
            size = absolute.stat().st_size
        except OSError as exc:
            return ToolResult(f"读取失败：{exc.strerror or exc}", True, "读取失败")

        # Word / Excel / PowerPoint：解压取文字，同文本一样带行号返回。
        if suffix in OFFICE_EXT:
            if size > MAX_OFFICE_BYTES:
                return ToolResult(f"（文件超过 {format_bytes(MAX_OFFICE_BYTES)}，未加载）", True, "文件过大")
            try:
                data = absolute.read_bytes()
            except OSError as exc:
                return ToolResult(f"读取失败：{exc.strerror or exc}", True, "读取失败")
            text = office_text(data, suffix)
            if text is None:
                return ToolResult(
                    "（无法解析这个文件：可能已加密、已损坏，或其实是旧版格式）", True, "无法解析"
                )
            return numbered_text(
                text,
                arguments,
                extra_note=(
                    f"以上是从 {suffix[1:].upper()} 文件中提取的纯文字（不含格式与图片），"
                    "不能用 edit_file 修改原文件。"
                ),
            )

        image_ext = suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}
        if image_ext and size > MAX_IMAGE_SOURCE_BYTES:
            return ToolResult(f"（图片超过 {format_bytes(MAX_IMAGE_SOURCE_BYTES)}，未加载）", True, "图片过大")
        if not image_ext and size > MAX_READ_BYTES:
            return ToolResult("（文件超过 2MB，未加载；请用 grep 定位所需内容）", True, "文件过大")
        try:
            data = absolute.read_bytes()
        except OSError as exc:
            return ToolResult(f"读取失败：{exc.strerror or exc}", True, "读取失败")

        # 图片按魔数认（扩展名只用来放宽上面的体积门槛）：以图片块随结果返回。
        mime = sniff_image_mime(data)
        if mime:
            return read_image_result(data, mime, absolute)
        if size > MAX_READ_BYTES:
            return ToolResult("（文件超过 2MB，未加载）", True, "文件过大")
        if looks_binary(data):
            return ToolResult("（疑似二进制文件，未加载）", True, "二进制")
        if not data:
            return ToolResult("（空文件）", False, "0 行")
        return numbered_text(data.decode("utf-8", errors="replace"), arguments)

    # ── list_dir ──────────────────────────────────────────────────────────
    def _list_dir(self, arguments: dict[str, Any]) -> ToolResult:
        target = self.guard.assert_inside(resolve_read_dir(self.root, arguments.get("path")))
        try:
            entries = list(target.iterdir())
        except OSError as exc:
            return ToolResult(f"列出失败：{exc.strerror or exc}", True, "列出失败")
        rows = [
            (entry.name, entry.is_dir())
            for entry in entries
            if entry.is_dir() or entry.is_file()
        ]
        rows.sort(key=lambda row: (not row[1], row[0].lower()))
        listing = "\n".join(f"{name}/" if is_dir else name for name, is_dir in rows)
        return ToolResult(listing or "（空目录）", False, f"{len(rows)} 项")

    # ── glob ──────────────────────────────────────────────────────────────
    def _glob(self, arguments: dict[str, Any]) -> ToolResult:
        pattern = arguments.get("pattern")
        pattern = pattern.strip() if isinstance(pattern, str) else ""
        if not pattern:
            return ToolResult("缺少 pattern 参数", True, "参数无效")
        directory = self.guard.assert_inside(resolve_read_dir(self.root, arguments.get("path")))
        regex = glob_to_regex(pattern)
        matched = _collect_files(directory)
        stated = []
        for absolute, rel in matched:
            if not regex.match(rel):
                continue
            try:
                mtime = absolute.stat().st_mtime
            except OSError:
                mtime = 0.0
            stated.append((mtime, self.display_path(absolute)))
        stated.sort(key=lambda item: item[0], reverse=True)
        shown = stated[:GLOB_RESULT_MAX]
        listing = "\n".join(path for _, path in shown)
        if len(stated) > len(shown):
            listing += f"\n…（共 {len(stated)} 个，仅列前 {GLOB_RESULT_MAX}）"
        return ToolResult(listing or "（无匹配文件）", False, f"{len(stated)} 个文件")

    # ── grep ──────────────────────────────────────────────────────────────
    def _grep(self, arguments: dict[str, Any]) -> ToolResult:
        raw_pattern = arguments.get("pattern")
        pattern = raw_pattern if isinstance(raw_pattern, str) else ""
        if not pattern:
            return ToolResult("缺少 pattern 参数", True, "参数无效")
        regex, note = compile_grep_pattern(pattern, arguments.get("ignore_case") is True)
        target = self.guard.assert_inside(resolve_read_dir(self.root, arguments.get("path")))
        if not target.exists():
            return ToolResult(f"路径不存在：{target.name}", True, "路径不存在")

        glob_re = None
        glob_base = False
        raw_glob = arguments.get("glob")
        if isinstance(raw_glob, str) and raw_glob.strip():
            normalized = raw_glob.strip().replace("\\", "/")
            glob_re = glob_to_regex(normalized)
            # 不含 / 的 glob（如 *.ts）只匹配文件名，与 ripgrep 一致。
            glob_base = "/" not in normalized

        if target.is_file():
            candidates: Iterator[tuple[Path, str]] = iter([(target, target.name)])
        else:
            candidates = walk_files(target, gitignore=True)

        rows: list[str] = []
        truncated = False
        for absolute, rel in candidates:
            probe = Path(rel).name if glob_base else rel
            if glob_re is not None and not glob_re.match(probe):
                continue
            for line in _search_file(absolute, regex):
                rows.append(f"{self.display_path(absolute)}:{line[0]}: {line[1]}")
                if len(rows) >= GREP_MATCH_MAX:
                    truncated = True
                    break
            if truncated:
                break
        body = "\n".join(rows)
        if truncated:
            body += f"\n…（匹配过多，仅列前 {GREP_MATCH_MAX} 处）"
        content = (f"{note}\n" if note else "") + (body or "（无匹配）")
        summary = f"{len(rows)}+ 处" if truncated else (f"{len(rows)} 处" if rows else "无匹配")
        return ToolResult(content, False, summary)

    # ── web_fetch ─────────────────────────────────────────────────────────
    def _web_fetch(self, arguments: dict[str, Any]) -> ToolResult:
        import httpx

        url = arguments.get("url")
        url = url.strip() if isinstance(url, str) else ""
        if not url:
            return ToolResult("缺少 url 参数", True, "参数无效")
        lowered = url.lower()
        if not (lowered.startswith("http://") or lowered.startswith("https://")):
            return ToolResult(f"仅支持 http/https（收到 {url.split(':', 1)[0]}）", True, "协议不支持")

        from mvvm.services.http_client import ProxyConfig  # 局部导入：HTTP 层可选

        # 与 SSE / 模型请求同一套代理口径：默认直连，认 HTTPS_PROXY 等环境变量。
        proxy = ProxyConfig.from_env().for_url(url)
        try:
            with httpx.Client(
                timeout=WEB_FETCH_TIMEOUT_S,
                follow_redirects=True,
                proxy=proxy,
                trust_env=False,
                headers={
                    "user-agent": WEB_USER_AGENT,
                    "accept": "text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.8",
                },
            ) as client:
                with client.stream("GET", url) as response:
                    content_type = (response.headers.get("content-type") or "").lower()
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in response.iter_bytes():
                        chunks.append(chunk)
                        total += len(chunk)
                        if total >= WEB_FETCH_MAX_BYTES:
                            break
                    data = b"".join(chunks)
                    status = response.status_code
                    reason = response.reason_phrase or ""
                    final_url = str(response.url)
        except httpx.TimeoutException:
            return ToolResult(f"请求超时（>{int(WEB_FETCH_TIMEOUT_S)}s）", True, "超时")
        except httpx.HTTPError as exc:
            return ToolResult(f"获取失败：{describe_net_error(exc)}", True, "获取失败")

        if status >= 400:
            return ToolResult(f"HTTP {status} {reason}".strip(), True, f"HTTP {status}")
        textual = any(
            key in content_type
            for key in ("html", "json", "xml", "text", "javascript")
        ) or content_type == ""
        if not textual and looks_binary(data):
            return ToolResult(f"（非文本内容：{content_type or '未知类型'}，未加载）", True, "非文本")
        raw = data.decode("utf-8", errors="replace")
        is_html = "html" in content_type or bool(re.match(r"^\s*(?:<!doctype html|<html)", raw, re.I))
        if is_html:
            title, text = html_to_text(raw)
        else:
            title, text = None, raw
        header = f"URL: {final_url}\n" + (f"标题: {title}\n" if title else "") + f"类型: {content_type or '未知'}"
        body = text.strip() or "（无可读文本内容）"
        content = f"{header}\n\n{self.spill_long_output(body, WEB_TEXT_MAX, 'web')}"
        return ToolResult(content, False, title[:40] if title else f"{len(body)} 字符")

    # ── write_file ────────────────────────────────────────────────────────
    def _write_file(self, arguments: dict[str, Any]) -> ToolResult:
        absolute = self._guarded(arguments)
        content = arguments.get("content")
        content = content if isinstance(content, str) else ""
        try:
            absolute.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return ToolResult(f"写入失败：{exc.strerror or exc}", True, "写入失败")
        if arguments.get("append") is True:
            # 读原始字节再解码：`read_text` 默认做通用换行转换（\r\n → \n），会把 CRLF 文件误判成 LF，
            # 追加的那段就会与文件原有风格不一致。
            try:
                previous = absolute.read_bytes().decode("utf-8", errors="replace")
            except OSError:
                previous = ""
            body = (
                norm_eol(content).replace("\n", "\r\n")
                if dominant_eol(previous) == "\r\n"
                else content
            )
            try:
                with absolute.open("a", encoding="utf-8", newline="") as handle:
                    handle.write(body)
            except OSError as exc:
                return ToolResult(f"写入失败：{exc.strerror or exc}", True, "写入失败")
            return ToolResult(f"已追加 {len(body.encode('utf-8'))} 字节", False, "已追加")
        # 原文件带 UTF-8 BOM 而新内容没有时补回：丢了 BOM，Windows PowerShell 5.1 会按 ANSI 读。
        output = content
        if content and not content.startswith("﻿") and _has_utf8_bom(absolute):
            output = "﻿" + content
        try:
            write_text_lf(absolute, output)
        except OSError as exc:
            return ToolResult(f"写入失败：{exc.strerror or exc}", True, "写入失败")
        return ToolResult(f"已写入 {len(output.encode('utf-8'))} 字节", False, "已写入")

    # ── edit_file ─────────────────────────────────────────────────────────
    def _edit_file(self, arguments: dict[str, Any]) -> ToolResult:
        absolute = self._guarded(arguments)
        old = arguments.get("old_string")
        old = old if isinstance(old, str) else ""
        new = arguments.get("new_string")
        new = new if isinstance(new, str) else ""
        if not old:
            return ToolResult("old_string 不能为空；新建文件请用 write_file", True, "参数无效")
        if old == new:
            return ToolResult("old_string 与 new_string 相同，无需编辑", True, "无变化")
        try:
            data = absolute.read_bytes()
        except OSError:
            return ToolResult(f"文件不存在或无法读取：{arguments.get('path')}", True, "不存在")
        if looks_binary(data):
            return ToolResult("（疑似二进制文件，拒绝编辑）", True, "二进制")
        text = data.decode("utf-8", errors="replace")
        eol = dominant_eol(text)
        count = text.count(old)
        work_text, work_old = text, old
        work_new = norm_eol(new).replace("\n", eol) if eol == "\r\n" else new
        normalized = False
        if count == 0:
            normalized_text = norm_eol(text)
            normalized_old = norm_eol(old)
            count_n = normalized_text.count(normalized_old)
            if count_n > 0:
                normalized = True
                count = count_n
                work_text, work_old = normalized_text, normalized_old
                work_new = norm_eol(new)
        if count == 0:
            return ToolResult("未找到 old_string（需与文件内容逐字符一致，含缩进/换行）", True, "未找到")
        replace_all = arguments.get("replace_all") is True
        if count > 1 and not replace_all:
            return ToolResult(
                f"old_string 匹配到 {count} 处，不唯一。请多带上下文使其唯一，或传 replace_all。",
                True,
                "不唯一",
            )
        # split/join 逐字面量替换：绕开 re.sub 对反斜杠与 \g 的特殊解释。
        result = work_text.replace(work_old, work_new)
        if normalized and eol == "\r\n":
            result = result.replace("\n", "\r\n")
        if result == text:
            return ToolResult(
                "old_string 与 new_string 仅换行符不同；换行符跟随文件原有风格，文件无变化",
                True,
                "无变化",
            )
        try:
            write_text_lf(absolute, result)
        except OSError as exc:
            return ToolResult(f"写入失败：{exc.strerror or exc}", True, "写入失败")
        replaced = count if replace_all else 1
        note = "（已按换行规范匹配）" if normalized else ""
        return ToolResult(f"已替换 {replaced} 处{note}", False, f"已替换 {replaced} 处" if replace_all else "已编辑")

    # ── run_command ───────────────────────────────────────────────────────
    def _run_command(self, arguments: dict[str, Any]) -> ToolResult:
        raw = arguments.get("command")
        command = raw.strip() if isinstance(raw, str) else ""
        if not command:
            return ToolResult("缺少有效的 command 参数", True, "参数无效")
        cwd = self.root if self.root is not None and self.root.exists() else Path.home()
        timeout_ms = _clamp_timeout(_to_int(arguments.get("timeout")))
        outcome = _exec_capture(command, cwd, timeout_ms, self.cancel_check)
        body = self.spill_long_output(outcome.out, EXEC_OUTPUT_MAX, "command")
        if outcome.spawn_error:
            status, summary = f"（无法执行：{outcome.spawn_error}）", "无法执行"
        elif outcome.capped:
            status, summary = f"（输出超过 {EXEC_CAPTURE_BYTES // 1024 // 1024}MB，已停止命令）", "输出过多"
        elif outcome.aborted:
            status, summary = "（已中止）", "已中止"
        elif outcome.timed_out:
            status, summary = f"（超时 >{timeout_ms}ms，已强制结束）", "超时"
        else:
            status, summary = f"（退出码：{outcome.code}）", f"退出码 {outcome.code}"
        is_error = bool(
            outcome.spawn_error or outcome.capped or outcome.aborted or outcome.timed_out
            or outcome.code != 0
        )
        hint = ""
        if is_error and self.root is None:
            hint = (
                f"\n（提示：当前未挂载工作区，命令在用户主目录 {cwd} 下执行。如需在某个项目下运行，"
                "请在命令里用绝对路径或先 cd，或请用户挂载该项目为工作区。）"
            )
        content = (body + "\n" if body else "") + status + hint
        return ToolResult(content, is_error, summary)

    # ── present_files ─────────────────────────────────────────────────────
    def _present_files(self, arguments: dict[str, Any]) -> ToolResult:
        raw_paths = arguments.get("paths")
        listed = raw_paths if isinstance(raw_paths, list) else []
        if not listed:
            return ToolResult("缺少 paths 参数：请列出要交付的文件路径。", True, "参数无效")
        if len(listed) > PRESENT_MAX:
            return ToolResult(f"一次最多交付 {PRESENT_MAX} 个文件，请只列出最主要的成品。", True, "文件过多")
        files: list[str] = []
        bad: list[str] = []
        seen: set[str] = set()
        for item in listed:
            try:
                absolute = self.guard.assert_inside(resolve_tool_path(self.guard, self.root, item))
            except (ValueError, PermissionError) as exc:
                bad.append(f"{item}：{exc}")
                continue
            key = str(absolute)
            if key in seen:
                continue
            seen.add(key)
            if not absolute.exists():
                bad.append(f"{key}：文件不存在")
            elif not absolute.is_file():
                bad.append(f"{key}：不是文件（目录请改为交付其中的入口文件，如 index.html）")
            else:
                files.append(key)
        if bad:
            lines = "\n".join(f"- {line}" for line in bad)
            return ToolResult(
                f"以下路径无法交付，请修正后重新调用（本次未向用户展示任何文件）：\n{lines}",
                True,
                f"{len(bad)} 个路径无效",
            )
        merged = "（重复的路径已合并为一个。）" if len(listed) > len(files) else ""
        return ToolResult(
            f"已交付 {len(files)} 个文件，交付卡将在本轮回复结束后显示在回复末尾。{merged}",
            False,
            f"{len(files)} 个文件",
            delivered=files,
        )

    # ── todo_write ────────────────────────────────────────────────────────
    def _todo_write(self, arguments: dict[str, Any], tool_use_id: str) -> ToolResult:
        if self.todo_sink is None:
            return ToolResult("当前环境不提供待办清单；请直接完成任务。", True, "不可用")
        return self.todo_sink(tool_use_id or f"t_{int(time.time() * 1000)}", arguments)

    # ── 超长输出落盘 ──────────────────────────────────────────────────────
    def spill_long_output(self, text: str, limit: int, label: str) -> str:
        """超过 limit 字符时全文存文件，返回「说明 + 路径 + 开头结尾预览」（Deva 同口径）。"""
        if len(text) <= limit:
            return text
        path = self._write_result_file(label, text)
        if path is None:
            head = head_of(text, limit // 2)
            tail = tail_of(text, limit // 2)
            omitted = len(text) - len(head) - len(tail)
            return (
                f"输出过长（共 {len(text)} 字符），且未能保存完整内容，以下只保留开头和结尾，其余已丢弃。"
                f"如果工具能筛选或分页，请重新执行取需要的部分。\n\n{head}\n"
                f"[……中间省略 {omitted} 字符……]\n{tail}"
            )
        head = head_of(text, PREVIEW_HEAD)
        tail = tail_of(text, PREVIEW_TAIL)
        omitted = len(text) - len(head) - len(tail)
        return (
            f"输出过长（共 {len(text)} 字符），完整内容已保存到：{path}\n"
            f"需要细看时用 read_file 分段读取，或用 grep 搜索。\n\n"
            f"预览（开头和结尾）：\n{head}\n[……中间省略 {omitted} 字符……]\n{tail}"
        )

    def _write_result_file(self, label: str, text: str) -> Optional[str]:
        if self.home is None:
            return None
        safe_session = re.sub(r"[^A-Za-z0-9_-]", "", self.session_id) or "_misc"
        directory = self.home / "data" / "tool-results" / safe_session
        name = f"{re.sub(r'[^A-Za-z0-9_-]', '', label)}-{int(time.time() * 1000):x}-{random.randrange(0xFFFFFF):06x}"
        try:
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / f"{name}.txt"
            target.write_text(text, encoding="utf-8")
        except OSError:
            return None
        return str(target)


# ── 各工具共用的纯函数 ───────────────────────────────────────────────────────
@dataclass
class ExecOutcome:
    out: str = ""
    code: Optional[int] = None
    timed_out: bool = False
    aborted: bool = False
    spawn_error: str = ""
    capped: bool = False


def numbered_text(
    text: str, arguments: dict[str, Any], extra_note: Optional[str] = None
) -> ToolResult:
    """带行号的文本结果（Deva `numberedText` 的 Python 版，规则逐条对齐）。"""
    lines = _split_lines(text)
    if lines and lines[-1] == "" and len(lines) > 1:
        lines.pop()  # 末尾换行产生的幽灵空行
    total = len(lines)
    start = min(max(1, _to_int(arguments.get("offset")) or 1), max(total, 1))
    limit = _to_int(arguments.get("limit"))
    end = min(start - 1 + (limit if limit and limit > 0 else READ_DEFAULT_LINES), total)

    clipped = 0
    numbered: list[str] = []
    for index, line in enumerate(lines[start - 1 : end]):
        if len(line) > READ_LINE_CHARS_MAX:
            clipped += 1
            line = f"{line[:READ_LINE_CHARS_MAX]}…（本行共 {len(line)} 字符，已截断）"
        numbered.append(f"{start + index:>6}\t{line}")
    body = "\n".join(numbered)
    if len(body) > READ_OUTPUT_MAX:
        return ToolResult(
            f"（第 {start}–{end} 行共约 {len(body)} 字符，超过单次读取上限 "
            f"{READ_OUTPUT_MAX} 字符，未返回；请用 offset/limit 缩小范围）",
            True,
            "读取范围过大",
        )
    notes: list[str] = []
    if end < total:
        notes.append(f"仅显示第 {start}–{end} 行（共 {total} 行）；如需后续内容，用 offset={end + 1} 继续读取。")
    if clipped:
        notes.append(f"有 {clipped} 行超过 {READ_LINE_CHARS_MAX} 字符，已截断显示。")
    if extra_note:
        notes.append(extra_note)
    content = body or "（空文件）"
    if notes:
        content += f"\n\n（{''.join(notes)}）"
    ranged = start > 1 or end < total
    summary = f"第 {start}–{end}/{total} 行" if ranged else f"{total} 行"
    return ToolResult(content, False, summary)


def read_image_result(buf: bytes, mime: str, absolute: Path) -> ToolResult:
    """read_file 的图片分支：整形（必要时缩放）后作为图片块返回，content 只留一句文字说明。"""
    prepared = prepare_image(buf, mime, absolute.name)
    if not prepared.ok:
        return ToolResult(f"（{prepared.reason}）", True, "图片无法发送")
    dims = f"{prepared.width}×{prepared.height}" if prepared.width and prepared.height else ""
    sent = (
        f"，已缩放为 {prepared.sent_width}×{prepared.sent_height}（{format_bytes(prepared.sent_bytes)}）发送"
        if prepared.resized
        else ""
    )
    content = (
        f"[图片] {absolute}（{mime}{'，' + dims if dims else ''}，{format_bytes(len(buf))}{sent}）。"
        "图片内容已随本结果附上。"
    )
    return ToolResult(
        content,
        False,
        f"图片 {dims}" if dims else "图片",
        images=[prepared.part] if prepared.part else None,
    )


def compile_grep_pattern(pattern: str, ignore_case: bool) -> tuple["re.Pattern[str]", str]:
    """宽容地编译 grep 的 pattern（Deva `compileGrepPattern` 的 Python 版）。

    - 前缀 `(?i)` 转为忽略大小写；
    - 先按普通正则编译，失败则转义后按纯文本搜索，并在结果里注明。
    """
    source = pattern
    flags = re.IGNORECASE if ignore_case else 0
    if source.startswith("(?i)") and len(source) > 4:
        source = source[4:]
        flags |= re.IGNORECASE
    try:
        return re.compile(source, flags), ""
    except re.error as exc:
        return (
            re.compile(re.escape(source), flags),
            f"（pattern 不是合法的正则：{exc}；已按纯文本搜索）",
        )


def html_to_text(html: str) -> tuple[Optional[str], str]:
    """手写 HTML → 纯文本（零依赖），与 Deva `htmlToText` 规则一致。"""
    title_match = re.search(r"<title[^>]*>([\s\S]*?)</title>", html, re.I)
    title = (
        html_module.unescape(title_match.group(1)).strip() if title_match else None
    )
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<noscript[\s\S]*?</noscript>", " ", text, flags=re.I)
    text = re.sub(r"<!--[\s\S]*?-->", " ", text)
    text = re.sub(r"<head[\s\S]*?</head>", " ", text, flags=re.I)
    text = re.sub(
        r"</?(?:br|p|div|li|tr|h[1-6]|section|article|header|footer|ul|ol|table|blockquote|pre)[^>]*>",
        "\n",
        text,
        flags=re.I,
    )
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_module.unescape(text)
    text = re.sub(r"[ \t\f\v\r]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return title, text.strip()


def describe_net_error(exc: BaseException) -> str:
    """网络错误 → 一句可操作的中文原因（Deva `describeNetError` 的降级版）。"""
    name = type(exc).__name__
    message = str(exc).strip().splitlines()[0] if str(exc).strip() else name
    mapping = {
        "ConnectError": "连接失败：目标地址不可达或拒绝连接（设置了代理环境变量吗？）",
        "ProxyError": "经代理连接失败：请检查代理是否在运行",
        "ConnectTimeout": "连接超时",
        "ReadTimeout": "读取超时：连接长时间没有数据",
        "TooManyRedirects": "重定向次数过多",
        "InvalidURL": "URL 无效",
    }
    return mapping.get(name, message or name)


def _collect_files(root: Path) -> list[tuple[Path, str]]:
    return list(walk_files(root))


def _search_file(absolute: Path, regex: "re.Pattern[str]") -> list[tuple[int, str]]:
    try:
        size = absolute.stat().st_size
        if size > MAX_READ_BYTES:
            return []
        data = absolute.read_bytes()
    except OSError:
        return []
    if looks_binary(data):
        return []
    lines = _split_lines(data.decode("utf-8", errors="replace"))
    hits: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if regex.search(line):
            hits.append((index + 1, line.strip()[:GREP_LINE_CHARS_MAX]))
            if len(hits) >= GREP_MATCH_MAX:
                break
    return hits


def _exec_capture(
    command: str,
    cwd: Path,
    timeout_ms: int,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> ExecOutcome:
    """执行一条 shell 命令：超时截断、输出上限截断、可取消。永不上抛。"""
    env = dict(os.environ)
    env.update({"GIT_PAGER": "cat", "PAGER": "cat", "GIT_TERMINAL_PROMPT": "0", "NO_COLOR": "1"})
    try:
        process = subprocess.Popen(  # noqa: S603 - 这是模型驱动的一次性命令执行工具
            command,
            shell=True,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
    except OSError as exc:
        return ExecOutcome(spawn_error=str(exc))

    deadline = time.monotonic() + timeout_ms / 1000
    output = ""
    timed_out = aborted = capped = False
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            if cancel_check is not None and cancel_check():
                aborted = True
                break
            try:
                chunk, _ = process.communicate(timeout=min(0.2, remaining))
            except subprocess.TimeoutExpired:
                continue
            output = chunk.decode("utf-8", errors="replace")
            break
    finally:
        if process.poll() is None:
            _kill_tree(process)
    if timed_out or aborted:
        try:
            chunk, _ = process.communicate(timeout=2)
            output += chunk.decode("utf-8", errors="replace")
        except (subprocess.TimeoutExpired, OSError):
            pass
    if len(output.encode("utf-8")) > EXEC_CAPTURE_BYTES:
        capped = True
        output = output.encode("utf-8")[:EXEC_CAPTURE_BYTES].decode("utf-8", errors="replace")
    return ExecOutcome(
        out=output,
        code=process.returncode,
        timed_out=timed_out,
        aborted=aborted,
        capped=capped,
    )


def _kill_tree(process: "subprocess.Popen[bytes]") -> None:
    """结束整个进程组（命令以 start_new_session 启动，pgid = pid）。"""
    try:
        os.killpg(process.pid, 9)
    except (OSError, AttributeError):
        try:
            process.kill()
        except OSError:
            pass


def _has_utf8_bom(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(3) == b"\xef\xbb\xbf"
    except OSError:
        return False


def _clamp_timeout(value: Optional[int]) -> int:
    if value is None:
        return EXEC_TIMEOUT_DEFAULT
    return min(max(value, 1000), EXEC_TIMEOUT_MAX)


def _split_lines(text: str) -> list[str]:
    """\\r\\n、孤立 \\r、\\n 一律视为换行（与 Deva 一致），行内容不含 \\r。"""
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _to_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


__all__ = [
    "DEFAULT_SPECS",
    "DENIED",
    "EDIT_FILE_SPEC",
    "EXEC_OUTPUT_MAX",
    "ExecOutcome",
    "GLOB_SPEC",
    "GREP_MATCH_MAX",
    "GREP_SPEC",
    "LIST_DIR_SPEC",
    "MAX_OFFICE_BYTES",
    "MAX_READ_BYTES",
    "NO_ROOT_RELATIVE",
    "NO_ROOT_SCAN",
    "PRESENT_FILES_SPEC",
    "READ_FILE_SPEC",
    "RUN_COMMAND_SPEC",
    "TODO_WRITE_SPEC",
    "ToolResult",
    "ToolRuntime",
    "ToolSpec",
    "WEB_FETCH_SPEC",
    "WRITE_FILE_SPEC",
    "compile_grep_pattern",
    "decide",
    "Decision",
    "html_to_text",
    "looks_binary",
    "numbered_text",
    "read_image_result",
    "resolve_read_dir",
    "resolve_tool_path",
]
