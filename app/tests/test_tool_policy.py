"""工具权限判定（allow / deny）：分类、交互轮放行、挂载判据、密封轮拒绝、执行期守卫。

对照 Deva `tools.ts::toolCategory` / `needsWorkspaceMount` 与 `sealed.ts::sealedDecision` 逐条验证。
判定层是**策略**（调不调得动），执行期 `WorkspaceGuard` 是**安全底线**（落点能不能碰），
两者互不替代——本文件分别覆盖，并把「判定放行但执行期拒绝」这条组合路径显式钉住。
"""
from __future__ import annotations

import pytest

from mvvm.services.tool_policy import (
    DENY_SCAN_ROOT,
    DENY_SEALED,
    DENY_UNKNOWN,
    Decision,
    decide,
    needs_workspace_mount,
    sealed_decision,
    tool_category,
)
from mvvm.services.tool_runtime import ToolRuntime
from mvvm.services.workspace_guard import DENIED, WorkspaceGuard


# ── 分类 ────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("name", "category"),
    [
        ("read_file", "read"),
        ("list_dir", "read"),
        ("glob", "read"),
        ("grep", "read"),
        ("web_fetch", "read"),
        ("present_files", "read"),
        ("todo_write", "read"),
        ("write_file", "edit"),
        ("edit_file", "edit"),
        ("run_command", "exec"),
        # 未知 / 幻觉工具名绝不默认成 read（Deva 的「关后门」口径）。
        ("nope_tool", "mcp"),
        ("browser", "mcp"),
    ],
)
def test_tool_category_matches_deva(name, category):
    assert tool_category(name) == category


def test_unknown_tool_is_never_read():
    assert tool_category("read_file_evil") == "mcp"


# ── 挂载判据（纯机械：落点能否解析）──────────────────────────────────────────
def test_no_mount_needed_when_root_present(tmp_path):
    assert needs_workspace_mount("read_file", {"path": "a.txt"}, tmp_path) is None
    assert needs_workspace_mount("list_dir", {}, tmp_path) is None


@pytest.mark.parametrize("name", ["read_file", "write_file", "edit_file"])
def test_file_tools_with_relative_path_need_mount(name):
    need = needs_workspace_mount(name, {"path": "src/a.py"}, None)
    assert need == {"tool": name, "path": "src/a.py"}


@pytest.mark.parametrize("name", ["read_file", "write_file", "edit_file"])
def test_file_tools_with_absolute_path_do_not_need_mount(name):
    assert needs_workspace_mount(name, {"path": "/etc/hosts"}, None) is None


def test_tilde_path_is_absolute_after_expansion():
    # `~/notes.txt` 是明确的主目录落点，不缺基准，不该打断用户（Deva 同口径）。
    assert needs_workspace_mount("read_file", {"path": "~/notes.txt"}, None) is None


@pytest.mark.parametrize("name", ["list_dir", "glob", "grep"])
def test_scan_tools_need_mount_without_path(name):
    assert needs_workspace_mount(name, {}, None) == {"tool": name, "path": ""}
    assert needs_workspace_mount(name, {"path": "."}, None) == {"tool": name, "path": "."}


@pytest.mark.parametrize("name", ["list_dir", "glob", "grep"])
def test_scan_tools_with_absolute_path_do_not_need_mount(name):
    assert needs_workspace_mount(name, {"path": "/tmp"}, None) is None


def test_run_command_and_todo_never_need_mount():
    # 命令文本里的相对路径无法可靠判定；todo_write 不碰路径（Deva 同口径）。
    assert needs_workspace_mount("run_command", {"command": "ls src"}, None) is None
    assert needs_workspace_mount("todo_write", {"todos": []}, None) is None


def test_mount_need_survives_bad_arguments():
    assert needs_workspace_mount("read_file", ["not", "a", "dict"], None) is None


# ── 交互轮决策 ──────────────────────────────────────────────────────────────
def test_interactive_allows_every_registered_tool(tmp_path):
    for name in (
        "read_file",
        "list_dir",
        "glob",
        "grep",
        "web_fetch",
        "write_file",
        "edit_file",
        "run_command",
        "present_files",
        "todo_write",
    ):
        decision = decide(name, {"path": "a.txt"}, tmp_path)
        assert decision.allowed, name


def test_interactive_mount_denial_only_when_ui_can_ask():
    # 没有挂载卡：放行到路径解析（和 Deva 的 resolvePath 兜底同文案），判定仍带 needs_mount。
    decision = decide("read_file", {"path": "a.txt"}, None)
    assert decision.allowed is True
    assert decision.needs_mount == {"tool": "read_file", "path": "a.txt"}

    # 有挂载卡（将来接 UI 时）：在闸门拦成挂载需求。
    denied = decide("read_file", {"path": "a.txt"}, None, can_request_mount=True)
    assert denied.allowed is False
    assert denied.needs_mount == {"tool": "read_file", "path": "a.txt"}
    assert "绝对路径" in denied.content
    assert denied.summary == "未挂载工作区"


def test_interactive_scan_denial_when_ui_can_ask():
    decision = decide("grep", {"pattern": "x"}, None, can_request_mount=True)
    assert decision.allowed is False
    assert "没有默认根可用" in decision.content
    assert DENY_SCAN_ROOT.format(name="grep") == decision.content


def test_unknown_tool_is_not_blocked_by_policy_layer():
    # 未知工具归 ToolRuntime 的「未知工具」错误；判定层不抢文案。
    assert decide("nope", {}, None).allowed is True


# ── 密封轮决策 ──────────────────────────────────────────────────────────────
def test_sealed_allows_read_write_exec(tmp_path):
    for name in ("read_file", "write_file", "edit_file", "run_command", "todo_write"):
        assert sealed_decision(name).allowed, name


def test_sealed_denies_interactive_and_creation_tools():
    for name in ("ask_user", "create_skill", "create_task", "memory_write", "exit_plan"):
        verdict = sealed_decision(name)
        assert verdict.allowed is False, name
        assert verdict.content == DENY_SEALED.format(name=name)
        assert verdict.summary == "已拒绝（安全策略）"


def test_sealed_denies_unknown_names():
    verdict = sealed_decision("hallucinated_tool")
    assert verdict.allowed is False
    assert verdict.content == DENY_UNKNOWN.format(name="hallucinated_tool")


def test_sealed_allows_connected_mcp_tools():
    assert sealed_decision("server__tool", is_mcp_tool=True).allowed is True


def test_non_interactive_decide_routes_to_sealed(tmp_path):
    assert decide("ask_user", {}, tmp_path, interactive=False).allowed is False
    assert decide("read_file", {"path": "a.txt"}, tmp_path, interactive=False).allowed is True


# ── 与执行期守卫的组合：判定放行 ≠ 能碰界外文件 ──────────────────────────────
def test_policy_allow_then_guard_denies(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("x", encoding="utf-8")
    runtime = ToolRuntime(WorkspaceGuard([work]), work)

    result = runtime.execute("read_file", {"path": str(outside)})
    assert result.is_error is True
    assert result.content == DENIED
    # 判定层确实放行了（交互轮全放行），拒绝发生在执行期守卫——两件事不能混为一谈。
    assert runtime.last_decision is not None
    assert runtime.last_decision.allowed is True


def test_runtime_records_denied_decision(tmp_path):
    runtime = ToolRuntime(WorkspaceGuard(), None)
    runtime.can_request_mount = True
    result = runtime.execute("read_file", {"path": "notes.txt"})
    assert result.is_error is True
    assert result.summary == "未挂载工作区"
    assert runtime.last_decision is not None
    assert runtime.last_decision.allowed is False
    assert isinstance(runtime.last_decision, Decision)


def test_unregistered_tool_reports_unknown_before_policy(tmp_path):
    runtime = ToolRuntime(WorkspaceGuard([tmp_path]), tmp_path)
    runtime.interactive = False
    result = runtime.execute("ask_user", {"questions": []})
    # 未注册 → 「未知工具」，判定层不参与（否则「未知工具」文案会被策略拒绝吞掉）。
    assert result.is_error is True
    assert "未知工具" in result.content
    assert runtime.last_decision is None


def test_runtime_sealed_mode_denies_registered_tool(tmp_path, monkeypatch):
    from mvvm.services import tool_runtime as module

    runtime = ToolRuntime(WorkspaceGuard([tmp_path]), tmp_path)
    runtime.interactive = False
    spec = module.ToolSpec(name="ask_user", description="x", input_schema={"type": "object"})
    runtime.register(spec, lambda args: module.ToolResult("should not run"))
    result = runtime.execute("ask_user", {})
    assert result.is_error is True
    assert result.content == DENY_SEALED.format(name="ask_user")
