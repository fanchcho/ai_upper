"""glob 编译、`.gitignore` 分层与目录遍历。

移植自 Deva `apps/desktop/src/main/services/tools.ts` 的 `globToRegExp` / `walkFiles` /
`loadIgnoreLayer` / `isIgnoredBy` / `ancestorIgnoreLayers`。与 Deva 一样：

- glob 只支持 `**`（跨目录）、`*`（单层）、`?`（单字符）、`{a,b}`（字面量分支）这一子集，
  足够覆盖 `**/*.ts`、`src/**/*.{ts,tsx}` 这类日常写法；
- 遍历默认跳过 `node_modules` / `.git` / `dist` 等噪音目录，文件数上限 20000；
- `glob` 工具**不**读 `.gitignore`（与 Deva 一致：只有 `grep` 走 gitignore）；
- `grep` 的 `.gitignore` 按「由浅到深逐层套用、深层覆盖浅层」的 git 语义。

与 Deva 的已知差异（如实记录，不假装等价）：Deva 用 npm `ignore` 包做完整 gitignore 解析，
这里自己实现一个子集——支持注释、空行、`!` 反选、尾部 `/` 仅目录、前导 `/` 锚定、
`*` / `?` / `**` / 字符类；不支持转义空格与 `\\#` 这类少见写法。遇到它们会按字面量处理，
可能把本该忽略的文件列出来（只会多列，不会漏列源码）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator, Optional

WALK_MAX = 20_000

# 遍历时直接跳过、不进入的噪音目录（与 Deva `IGNORE_DIRS` 逐条一致）。
IGNORE_DIRS = frozenset(
    {
        "node_modules",
        ".git",
        "dist",
        "out",
        "build",
        ".next",
        "coverage",
        ".cache",
        ".turbo",
        ".output",
        "target",
        ".venv",
        "__pycache__",
        ".idea",
        ".vscode",
    }
)


def _escape(text: str) -> str:
    return re.escape(text)


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """glob → 锚定的正则（匹配 posix 相对路径）。规则与 Deva `globToRegExp` 相同。"""
    g = pattern.replace("\\", "/")
    out: list[str] = []
    i = 0
    while i < len(g):
        ch = g[i]
        if ch == "*":
            if g[i + 1 : i + 2] == "*":
                if g[i + 2 : i + 3] == "/":
                    out.append("(?:[^/]*/)*")
                    i += 3
                else:
                    out.append(".*")
                    i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        elif ch == "{":
            end = g.find("}", i)
            if end == -1:
                out.append(r"\{")
                i += 1
            else:
                parts = [_escape(s) for s in g[i + 1 : end].split(",")]
                out.append("(?:" + "|".join(parts) + ")")
                i = end + 1
        else:
            out.append(_escape(ch))
            i += 1
    return re.compile("^" + "".join(out) + "$")


class _Rule:
    """一条 .gitignore 规则。"""

    __slots__ = ("regex", "negated", "dir_only")

    def __init__(self, regex: re.Pattern[str], negated: bool, dir_only: bool) -> None:
        self.regex = regex
        self.negated = negated
        self.dir_only = dir_only


def _ignore_pattern_to_regex(pattern: str) -> re.Pattern[str]:
    """gitignore 模式 → 正则。

    - 含 `/`（尾部除外）的模式锚定到规则所在目录；
    - 其余模式匹配任意层级的同名路径段（`*.log` 命中 `a/b/x.log`）；
    - `**/` 匹配零或多段目录，`**` 匹配任意字符（含 `/`）。
    """
    anchored = pattern.startswith("/") or "/" in pattern.rstrip("/")
    body = pattern.lstrip("/")
    out: list[str] = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "*":
            if body[i + 1 : i + 2] == "*":
                if body[i + 2 : i + 3] == "/":
                    out.append("(?:.*/)?")
                    i += 3
                else:
                    out.append(".*")
                    i += 2
            else:
                out.append("[^/]*")
                i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        elif ch == "[":
            end = body.find("]", i + 1)
            if end == -1:
                out.append(r"\[")
                i += 1
            else:
                cls = body[i : end + 1].replace("\\", "\\\\")
                out.append(cls)
                i = end + 1
        else:
            out.append(_escape(ch))
            i += 1
    prefix = "" if anchored else "(?:.*/)?"
    return re.compile("^" + prefix + "".join(out) + "$")


def parse_gitignore(text: str) -> list[_Rule]:
    rules: list[_Rule] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        negated = line.startswith("!")
        if negated:
            line = line[1:]
        if not line:
            continue
        dir_only = line.endswith("/")
        if dir_only:
            line = line[:-1]
        if not line:
            continue
        rules.append(_Rule(_ignore_pattern_to_regex(line), negated, dir_only))
    return rules


class IgnoreLayer:
    """一层 .gitignore：规则相对其所在目录匹配。"""

    __slots__ = ("base", "rules")

    def __init__(self, base: Path, rules: list[_Rule]) -> None:
        self.base = base
        self.rules = rules


def load_ignore_layer(directory: Path) -> Optional[IgnoreLayer]:
    try:
        text = (directory / ".gitignore").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return IgnoreLayer(directory, parse_gitignore(text))


def is_ignored_by(layers: list[IgnoreLayer], target: Path, is_dir: bool) -> bool:
    """按 git 的叠加语义判定：由浅到深逐层套用，深层的命中（含 `!` 反选）覆盖浅层。"""
    ignored = False
    for layer in layers:
        try:
            rel = target.relative_to(layer.base).as_posix()
        except ValueError:
            continue
        if is_dir:
            rel += "/"
        for rule in layer.rules:
            probe = rel[:-1] if rule.dir_only and rel.endswith("/") else rel
            if rule.dir_only and not is_dir:
                continue
            if rule.regex.match(probe):
                ignored = not rule.negated
    return ignored


def ancestor_ignore_layers(directory: Path) -> list[IgnoreLayer]:
    """`directory` 的祖先目录（仓库根 → 父目录）上的 .gitignore 层。

    不在 git 仓库内则为空：上溯不越过仓库根，免得套用无关上层目录（如用户主目录）的规则。
    """
    chain: list[Path] = []
    current = Path(directory).resolve()
    in_repo = (current / ".git").exists()
    while not in_repo:
        parent = current.parent
        if parent == current:
            return []
        current = parent
        chain.insert(0, current)
        in_repo = (current / ".git").exists()
    layers = [load_ignore_layer(path) for path in chain]
    return [layer for layer in layers if layer is not None]


def walk_files(
    root: Path,
    *,
    gitignore: bool = False,
    max_files: int = WALK_MAX,
) -> Iterator[tuple[Path, str]]:
    """逐个产出 root 下的文件（绝对路径，posix 相对路径），跳过噪音目录，至多 max_files 个。

    边走边产出：调用方够数即可停下。`gitignore=True` 时遵守搜索根及其下各层的 .gitignore，
    在 git 仓库内还套用上层目录（至仓库根）的规则；搜索根本身被上层忽略时（如直接搜 build/）
    不套上层规则，照常搜索。
    """
    root = Path(root)
    count = 0
    base: list[IgnoreLayer] = []
    if gitignore:
        base = ancestor_ignore_layers(root)
        if is_ignored_by(base, root, True):
            base = []

    def walk(directory: Path, rel: str, layers: list[IgnoreLayer]) -> Iterator[tuple[Path, str]]:
        nonlocal count
        try:
            entries = sorted(directory.iterdir(), key=lambda p: p.name)
        except OSError:
            return
        if gitignore:
            own = load_ignore_layer(directory)
            if own is not None:
                layers = [*layers, own]
        for entry in entries:
            if count >= max_files:
                return
            child_rel = f"{rel}/{entry.name}" if rel else entry.name
            try:
                is_dir = entry.is_dir()
                is_file = entry.is_file()
            except OSError:
                continue
            if is_dir:
                if entry.name in IGNORE_DIRS:
                    continue
                if layers and is_ignored_by(layers, entry, True):
                    continue
                yield from walk(entry, child_rel, layers)
            elif is_file:
                if layers and is_ignored_by(layers, entry, False):
                    continue
                count += 1
                yield entry, child_rel

    yield from walk(root, "", base)


__all__ = [
    "IGNORE_DIRS",
    "WALK_MAX",
    "IgnoreLayer",
    "ancestor_ignore_layers",
    "glob_to_regex",
    "is_ignored_by",
    "load_ignore_layer",
    "parse_gitignore",
    "walk_files",
]
