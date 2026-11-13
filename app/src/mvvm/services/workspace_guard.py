"""工作区路径守卫：受信根 + 真实路径越界拒绝。

移植自 Deva `apps/desktop/src/main/services/fs-guard.ts`，语义逐条对齐：

- **真实路径比较**：`realpath` 跟随符号链接，堵住「根内链接指向根外」的穿越洞；
  目标尚不存在时（将新建的文件）对最近的存在祖先做 realpath，再把尾段接回；
- **受信根是内存态**：不落盘，进程重启即清空，由装配处/打开工作区时重新登记；
- **拒绝文案与 Deva 一致**：`拒绝访问：路径不在已打开的项目内`，界面与日志都按这句匹配。

与 Deva 的一处差异：Deva 的 **agent 文件工具不走这个守卫**（2026-10-09 起不设路径
限制）。本工程按迁移计划的决定，工具执行**必须**过守卫——这是新工程的安全底线，
不是对 Deva 行为的复刻。
"""
from __future__ import annotations

import os
from pathlib import Path

DENIED = "拒绝访问：路径不在已打开的项目内"
_MAX_HOPS = 4096  # 逐级向上找真实祖先的迭代上限，防御异常路径造成的死循环


def real_resolve(target: Path | str) -> Path:
    """解析真实路径：跟随符号链接；不存在则解析最近的已存在祖先，再把尾段接回。

    任何一步解析失败都退回字面绝对路径——不因解析失败而误放行或误拦截
    （与 Deva `realResolve` 的回退策略一致）。
    """
    absolute = Path(os.path.abspath(target))
    tail: list[str] = []
    current = absolute
    for _ in range(_MAX_HOPS):
        try:
            real = Path(os.path.realpath(current))
            return real.joinpath(*tail) if tail else real
        except OSError:
            parent = current.parent
            if parent == current:
                return absolute
            tail.insert(0, current.name)
            current = parent
    return absolute


def is_inside(target: Path | str, root: Path | str) -> bool:
    """target 的真实路径是否落在 root 之内（含 root 本身）。"""
    real = real_resolve(target)
    root_real = real_resolve(root)
    if real == root_real:
        return True
    try:
        real.relative_to(root_real)
        return True
    except ValueError:
        return False


class WorkspaceGuard:
    """受信根集合与越界判定。纯 Python，不依赖 Qt。"""

    def __init__(self, roots: tuple[Path | str, ...] | list[Path | str] | None = None) -> None:
        self._roots: list[Path] = [Path(os.path.abspath(r)) for r in (roots or ())]

    def trust_root(self, directory: Path | str) -> None:
        """登记一个受信根（打开文件夹 / 挂载工作区时）。重复登记无害。"""
        resolved = Path(os.path.abspath(directory))
        if resolved not in self._roots:
            self._roots.append(resolved)

    def untrust_root(self, directory: Path | str) -> None:
        resolved = Path(os.path.abspath(directory))
        if resolved in self._roots:
            self._roots.remove(resolved)

    def list_roots(self) -> list[Path]:
        return list(self._roots)

    @property
    def has_roots(self) -> bool:
        return bool(self._roots)

    def is_inside_root(self, target: Path | str) -> bool:
        """是否落在任一受信根内。没有受信根时一切路径都在界外（默认拒绝）。"""
        return any(is_inside(target, root) for root in self._roots)

    def assert_inside(self, target: Path | str) -> Path:
        """越界即抛 PermissionError，消息与 Deva 的 DENIED 一致；返回真实路径供调用方直接使用。"""
        if not self.is_inside_root(target):
            raise PermissionError(DENIED)
        return real_resolve(target)


__all__ = [
    "DENIED",
    "WorkspaceGuard",
    "is_inside",
    "real_resolve",
]
