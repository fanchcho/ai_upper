"""工具层：声明、执行与结果。

P1 只实现一个工具 `read_file`，但把它做成可扩展的形状：工具声明（JSON Schema）
与执行函数分离，执行前**必须**经过 `WorkspaceGuard` 的路径校验。越界不是「返回空」，
而是明确错误（文案与 Deva 一致），并且这条错误会作为 `isError=True` 的 tool_result
回灌给模型——模型能读到失败原因，用户也能在界面上看到。

口径来自 Deva `apps/desktop/src/main/services/tools.ts`：
- `read_file` 文本结果带 6 位右对齐行号 + Tab，默认最多 2000 行，单行超 2000 字符截断，
  单次输出超 100000 字符报错要求缩小范围；
- 路径规则：`~` / `~/` 展开，绝对路径直接用，相对路径基于工作区根；未挂载工作区时
  相对路径直接报错（不偷偷落到进程 cwd）。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from mvvm.services.workspace_guard import DENIED, WorkspaceGuard

READ_DEFAULT_LINES = 2000
READ_LINE_CHARS_MAX = 2000
READ_OUTPUT_MAX = 100_000
MAX_READ_BYTES = 2 * 1024 * 1024

MISSING_PATH = "缺少有效的 path 参数"
NO_ROOT_RELATIVE = "未挂载工作区，相对路径没有基准：请改用绝对路径（~/ 开头的主目录路径亦可）。"


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


READ_FILE_SPEC = ToolSpec(
    name="read_file",
    description=(
        "读取工作区内一个文本文件，返回带行号的内容。默认从第 1 行起最多读 2000 行，"
        "超过 2000 字符的行会被截断；可用 offset / limit 分段读取。"
        "path 可相对项目根或绝对路径。"
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
    if not candidate.is_absolute():
        if root is None:
            raise ValueError(NO_ROOT_RELATIVE)
        candidate = Path(root) / candidate
    return Path(candidate)


class ToolRuntime:
    """工具注册表 + 执行入口。所有执行都先过 `guard.assert_inside`。"""

    def __init__(
        self,
        guard: WorkspaceGuard,
        root: Optional[Path | str] = None,
        tools: Optional[dict[str, tuple[ToolSpec, Callable[..., ToolResult]]]] = None,
    ) -> None:
        self.guard = guard
        self.root: Optional[Path] = Path(root) if root is not None else None
        self._tools: dict[str, tuple[ToolSpec, Callable[..., ToolResult]]] = dict(tools or {})
        if "read_file" not in self._tools:
            self.register(READ_FILE_SPEC, self._read_file)

    def register(self, spec: ToolSpec, handler: Callable[..., ToolResult]) -> None:
        self._tools[spec.name] = (spec, handler)

    def specs(self) -> list[ToolSpec]:
        return [spec for spec, _ in self._tools.values()]

    def resolve_path(self, raw: Any) -> Path:
        return resolve_tool_path(self.guard, self.root, raw)

    def execute(self, name: str, arguments: Any) -> ToolResult:
        """执行一个工具。未知工具、参数错误、越界都返回 is_error=True 的结果（不抛给上层）。"""
        entry = self._tools.get(name)
        if entry is None:
            return ToolResult(f"（未知工具：{name}）", True, "未知工具")
        _, handler = entry
        if not isinstance(arguments, dict):
            return ToolResult(f"（{name} 的参数必须是对象）", True, "参数错误")
        return handler(arguments)

    # ── 内置工具 ──────────────────────────────────────────────────────────
    def _read_file(self, arguments: dict[str, Any]) -> ToolResult:
        try:
            candidate = self.resolve_path(arguments.get("path"))
        except ValueError as exc:
            return ToolResult(str(exc), True, "参数错误")
        try:
            absolute = self.guard.assert_inside(candidate)
        except PermissionError as exc:
            return ToolResult(str(exc), True, "越界拒绝")

        try:
            size = absolute.stat().st_size
        except OSError as exc:
            return ToolResult(f"读取失败：{exc.strerror or exc}", True, "读取失败")
        if size > MAX_READ_BYTES:
            return ToolResult(
                f"（文件 {size} 字节，超过单次读取上限 {MAX_READ_BYTES} 字节，未读取）",
                True,
                "文件过大",
            )
        try:
            text = absolute.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return ToolResult(f"读取失败：{exc.strerror or exc}", True, "读取失败")
        return numbered_text(text, arguments)


def numbered_text(text: str, arguments: dict[str, Any]) -> ToolResult:
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
    for index, line in enumerate(lines[start - 1:end]):
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
    content = body or "（空文件）"
    if notes:
        content += f"\n\n（{''.join(notes)}）"
    ranged = start > 1 or end < total
    summary = f"第 {start}–{end}/{total} 行" if ranged else f"{total} 行"
    return ToolResult(content, False, summary)


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
    return None


__all__ = [
    "DENIED",
    "MAX_READ_BYTES",
    "READ_FILE_SPEC",
    "ToolResult",
    "ToolRuntime",
    "ToolSpec",
    "numbered_text",
    "resolve_tool_path",
]
