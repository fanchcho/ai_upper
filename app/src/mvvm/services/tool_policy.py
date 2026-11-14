"""工具权限判定（allow / deny）：纯函数，无 IO、无 Qt，可单测。

逐条对齐 Deva `apps/desktop/src/main/services/tools.ts` 与 `sealed.ts`：

- **敏感度分类**（`toolCategory`）：`read` 只读 / `edit` 写入 / `exec` 执行 /
  `mcp` 外部 MCP 工具与未知工具名（默认不放行）；
- **交互轮**：所有内置工具一律放行，文件读写与命令执行不设任何限制（Deva 2026-10-09 起
  的纯同步策略、零弹框）；**唯一**的拒绝是「本地工作区未挂载 + 相对路径没有基准」；
- **密封轮**（无人值守；ai_upper 暂不触发，仅预留判定）：交互/创建类工具与未知工具名拒绝，
  读写执行照常放行。

ai_upper 与 Deva 的一处刻意差异：Deva 的文件工具**不**过路径守卫；本工程所有文件类工具在
执行前必须过 `WorkspaceGuard`（见 `tool_runtime.py` 模块头）。那是执行期的安全底线，
与本模块「调不调得动」的判定是两件事，互不替代。
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

# 写入类：与 Deva `EDIT_TOOLS` 同集。
EDIT_TOOLS = frozenset({"write_file", "edit_file"})
# 执行类：与 Deva `EXEC_TOOLS` 同集（`browser` 尚未迁移，暂不加）。
EXEC_TOOLS = frozenset({"run_command"})
# 只读 / 无副作用：Deva `READ_TOOLS` 中属于 ai_upper 已注册工具的子集。
READ_TOOLS = frozenset(
    {
        "read_file",
        "list_dir",
        "glob",
        "grep",
        "web_fetch",
        "present_files",
        "todo_write",
    }
)

# 密封轮永不放行的交互/创建类工具（Deva `SEALED_FORBIDDEN` 中与本工程相关的子集）。
SEALED_FORBIDDEN = frozenset(
    {
        "ask_user",
        "run_subagent",
        "send_to_subagent",
        "create_skill",
        "propose_agent",
        "create_mcp",
        "create_task",
        "exit_plan",
        "memory_write",
        "memory_delete",
    }
)

# 单文件类工具：path 是必填落点，相对写法以工作区根为基准。
FILE_PATH_TOOLS = frozenset({"write_file", "edit_file", "read_file"})
# 扫描类工具：省略 path 即隐含「工作区根」。
SCAN_TOOLS = frozenset({"list_dir", "glob", "grep"})

DENY_POLICY = "该操作被安全策略拒绝。"
DENY_SEALED = (
    "定时任务在自动执行中，无法使用「{name}」（不支持交互/创建类操作）。"
    "请改用只读或写入/执行工具完成本次任务，或在结论中说明受限之处。"
)
DENY_UNKNOWN = "工具「{name}」当前不可用，已拒绝。"
DENY_MOUNT = (
    "未挂载工作区，无法确定相对路径「{path}」的落点，本次调用未执行。"
    "请改用**绝对路径**重试（必要时先问清用户目标目录），不要再请求挂载工作区。"
)
DENY_SCAN_ROOT = (
    "未挂载工作区，{name} 省略 path 时没有默认根可用，本次调用未执行。"
    "请显式传入**绝对路径** path 重试，不要再请求挂载工作区。"
)

# 用户已在会话里拒绝过挂载（Deva 的 `mountDeclined`）：用于「不再重复弹卡」的会话级去重。
# ai_upper 目前没有挂载卡 UI，判定照常返回 mount 需求，由调用方决定是否打断；见台账差异记录。


@dataclass(frozen=True)
class Decision:
    """一次工具调用的判定结果。"""

    allowed: bool
    category: str
    content: str = ""  # 拒绝时回灌模型的文本；放行时为空
    summary: str = ""  # 拒绝时给界面徽标的短文案
    needs_mount: Optional[dict[str, str]] = None  # 命中的挂载需求（tool/path）


def tool_category(name: str) -> str:
    """敏感度分类；未知工具名归 `mcp`（默认不放行，绝不默认成 read）。"""
    if name in EDIT_TOOLS:
        return "edit"
    if name in EXEC_TOOLS:
        return "exec"
    if name in READ_TOOLS:
        return "read"
    return "mcp"


def needs_workspace_mount(
    name: str, arguments: Any, root: Optional[Path | str]
) -> Optional[dict[str, str]]:
    """「本次调用是否缺少相对路径基准」——挂载需求的唯一判据（纯机械，零语义猜测）。

    与 Deva `needsWorkspaceMount` 同口径：
    - 已有工作区根 → 永远不缺基准；
    - 单文件类给了**相对** path → 命中；
    - 扫描类省略 path 或给了相对 path → 命中；
    - `read_file` 给绝对路径（含 `~/` 展开）→ 不命中。
    """
    if root is not None:
        return None
    raw = arguments if isinstance(arguments, dict) else {}
    value = raw.get("path")
    path = value.strip() if isinstance(value, str) else ""
    expanded = _expand_home(path) if path else ""
    if name in FILE_PATH_TOOLS:
        if expanded and not os.path.isabs(expanded):
            return {"tool": name, "path": path}
        return None
    if name in SCAN_TOOLS:
        if not os.path.isabs(expanded):
            return {"tool": name, "path": path}
        return None
    return None


def sealed_decision(name: str, is_mcp_tool: bool = False) -> Decision:
    """密封无头执行（无人值守）的判定：绝不弹窗、绝不挂起。"""
    if name in SEALED_FORBIDDEN:
        return Decision(
            allowed=False,
            category="sealed",
            content=DENY_SEALED.format(name=name),
            summary="已拒绝（安全策略）",
        )
    category = tool_category(name)
    if category in ("read", "edit", "exec"):
        return Decision(allowed=True, category=category)
    if is_mcp_tool:
        return Decision(allowed=True, category="mcp")
    return Decision(
        allowed=False,
        category="mcp",
        content=DENY_UNKNOWN.format(name=name),
        summary="已拒绝",
    )


def decide(
    name: str,
    arguments: Any,
    root: Optional[Path | str],
    *,
    interactive: bool = True,
    is_mcp_tool: bool = False,
    can_request_mount: bool = False,
) -> Decision:
    """交互轮 / 密封轮的统一判定入口。

    交互轮：命中挂载需求即拒绝（文案指向「改用绝对路径」）；否则一律放行。

    `can_request_mount` 对齐 Deva 的「谁能弹挂载卡」：只有主轮交互式、且界面真的提供挂载卡时
    才在闸门拦成挂载需求。子智能体 / 密封轮 / **尚未做挂载卡的本工程**都没有人能应答，
    此时放行到 `resolve_tool_path` 抛「未挂载工作区，相对路径没有基准：请改用绝对路径」——
    与 Deva `resolvePath` 的兜底文案一致，而不是给模型一句「请用户挂载」的无效建议。
    判定结果仍带 `needs_mount`，调用方（将来有卡时）可据此打断。

    密封轮：先过 `sealed_decision`。
    """
    if not interactive:
        return sealed_decision(name, is_mcp_tool=is_mcp_tool)
    mount = needs_workspace_mount(name, arguments, root)
    if mount is not None and can_request_mount:
        content = (
            DENY_MOUNT.format(path=mount["path"])
            if mount["path"]
            else DENY_SCAN_ROOT.format(name=name)
        )
        return Decision(
            allowed=False,
            category=tool_category(name),
            content=content,
            summary="未挂载工作区",
            needs_mount=mount,
        )
    # 交互轮：内置工具一律放行（Deva 的纯同步策略）。未知工具名由 ToolRuntime 报「未知工具」，
    # 这里不重复拦截——两处都拦会让「未知工具」的文案在判定层被吞掉。
    return Decision(
        allowed=True,
        category=tool_category(name),
        needs_mount=mount,
    )


def _expand_home(value: str) -> str:
    if value == "~":
        return str(Path.home())
    if value.startswith("~/") or value.startswith("~\\"):
        return str(Path.home() / value[2:])
    return value


__all__ = [
    "DENY_MOUNT",
    "DENY_POLICY",
    "DENY_SCAN_ROOT",
    "DENY_SEALED",
    "DENY_UNKNOWN",
    "Decision",
    "EDIT_TOOLS",
    "EXEC_TOOLS",
    "FILE_PATH_TOOLS",
    "READ_TOOLS",
    "SCAN_TOOLS",
    "SEALED_FORBIDDEN",
    "decide",
    "needs_workspace_mount",
    "sealed_decision",
    "tool_category",
]
