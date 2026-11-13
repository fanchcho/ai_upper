"""Provider 归一化、假 provider 剧本、路径守卫与 read_file 工具。

路径守卫的用例覆盖符号链接穿越：只在能建符号链接的平台跑（Linux/macOS 默认可以，
Windows 需要开发者权限），无法建立时 skip 并说明原因，而不是让测试假通过。
"""
from __future__ import annotations

import asyncio
import os

import pytest

from mvvm.models.chat_models import Message, TextPart, ToolResultPart, ToolUsePart
from mvvm.services.fake_provider import FakeProvider
from mvvm.services.provider_gateway import (
    GenerateRequest,
    NotImplementedProvider,
    StreamError,
    http_error,
    normalize_messages,
)
from mvvm.services.tool_runtime import (
    MISSING_PATH,
    NO_ROOT_RELATIVE,
    ToolRuntime,
    numbered_text,
)
from mvvm.services.workspace_guard import DENIED, WorkspaceGuard, is_inside, real_resolve


# ── provider 层 ─────────────────────────────────────────────────────────────
def test_http_error_mapping():
    assert http_error(401).kind == "auth"
    assert http_error(403).retryable is False
    assert http_error(429).kind == "rate_limit"
    assert http_error(429).retryable is True
    assert http_error(400, "context length exceeded").kind == "context_length"
    assert http_error(503).kind == "server"
    assert http_error(503).retryable is True
    assert http_error(422, "bad").kind == "invalid_request"


def test_normalize_messages_merges_consecutive_same_role():
    merged = normalize_messages(
        [
            Message(role="user", content="第一句"),
            Message(role="user", content=[TextPart(text="第二句")]),
            Message(role="assistant", content="答"),
            Message(role="user", content=[ToolResultPart(toolUseId="c1", content="结果")]),
        ]
    )
    assert [m.role for m in merged] == ["user", "assistant", "user"]
    first = merged[0].content
    assert isinstance(first, list)
    assert [p.text for p in first] == ["第一句", "第二句"]
    assert merged[2].content[0].type == "tool_result"


def test_fake_provider_first_turn_requests_read_file():
    provider = FakeProvider(tool_path="a.txt")
    request = GenerateRequest(model="m", messages=[Message(role="user", content="看看 a.txt")])
    events = asyncio.run(_collect(provider.stream(request)))
    types = [e.type for e in events]
    assert types == ["text_delta", "usage", "tool_call", "done"]
    call = [e for e in events if e.type == "tool_call"][0]
    assert call.name == "read_file"
    assert call.input == {"path": "a.txt"}
    assert [e for e in events if e.type == "done"][0].stop_reason == "tool_use"


def test_fake_provider_second_turn_summarises_tool_result():
    provider = FakeProvider(tool_path="a.txt")
    messages = [
        Message(role="user", content="看看 a.txt"),
        Message(role="assistant", content=[ToolUsePart(id="c1", name="read_file", input={})]),
        Message(role="user", content=[ToolResultPart(toolUseId="c1", content="hello")]),
    ]
    events = asyncio.run(_collect(provider.stream(GenerateRequest(model="m", messages=messages))))
    text = "".join(e.text for e in events if e.type == "text_delta")
    assert "hello" in text
    assert [e for e in events if e.type == "done"][0].stop_reason == "end_turn"


def test_fake_provider_reports_tool_error_in_summary():
    provider = FakeProvider(tool_path="a.txt")
    messages = [
        Message(role="user", content="看看"),
        Message(
            role="user",
            content=[ToolResultPart(toolUseId="c1", content=DENIED, isError=True)],
        ),
    ]
    events = asyncio.run(_collect(provider.stream(GenerateRequest(model="m", messages=messages))))
    text = "".join(e.text for e in events if e.type == "text_delta")
    assert "失败" in text and DENIED in text


def test_fake_provider_can_fail_with_stream_error():
    provider = FakeProvider(fail_with="密钥无效")
    events = asyncio.run(
        _collect(provider.stream(GenerateRequest(model="m", messages=[])))
    )
    error = [e for e in events if e.type == "error"][0]
    assert isinstance(error, StreamError)
    assert error.error.kind == "auth"
    assert [e for e in events if e.type == "done"][0].stop_reason == "error"


def test_unimplemented_provider_raises_instead_of_faking():
    provider = NotImplementedProvider("anthropic", "P1 未接入网络")

    async def run():
        async for _ in provider.stream(GenerateRequest(model="m", messages=[])):
            pass

    with pytest.raises(NotImplementedError):
        asyncio.run(run())


# ── 路径守卫 ───────────────────────────────────────────────────────────────
def test_guard_rejects_everything_without_roots(tmp_path):
    guard = WorkspaceGuard()
    assert guard.has_roots is False
    with pytest.raises(PermissionError, match=DENIED):
        guard.assert_inside(tmp_path / "a.txt")


def test_guard_accepts_inside_and_rejects_outside(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    (root / "notes.txt").write_text("hi", encoding="utf-8")
    outside = tmp_path / "secret.txt"
    outside.write_text("no", encoding="utf-8")

    guard = WorkspaceGuard([root])
    assert guard.assert_inside(root / "notes.txt") == real_resolve(root / "notes.txt")
    with pytest.raises(PermissionError):
        guard.assert_inside(outside)
    # 不存在的目标也按真实祖先判定：根内新文件放行，根外新文件拒绝
    assert guard.is_inside_root(root / "new" / "file.txt")
    assert not guard.is_inside_root(tmp_path / "out" / "file.txt")


def test_guard_rejects_dotdot_escape(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    guard = WorkspaceGuard([root])
    with pytest.raises(PermissionError):
        guard.assert_inside(root / ".." / "outside.txt")


def test_guard_follows_symlink_out_of_root(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("no", encoding="utf-8")
    link = root / "link"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError) as exc:  # pragma: no cover - 平台限制
        pytest.skip(f"该平台无法创建符号链接：{exc}")

    guard = WorkspaceGuard([root])
    assert not guard.is_inside_root(link / "secret.txt")
    with pytest.raises(PermissionError):
        guard.assert_inside(link / "secret.txt")


def test_guard_trust_and_untrust(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    guard = WorkspaceGuard()
    guard.trust_root(root)
    guard.trust_root(root)  # 重复登记无害
    assert guard.list_roots() == [root]
    guard.untrust_root(root)
    assert guard.list_roots() == []


def test_is_inside_does_not_treat_sibling_prefix_as_inside(tmp_path):
    """`/a/w` 不能把 `/a/w2` 判成在内（前缀比较必须带分隔符）。"""
    root = tmp_path / "w"
    root.mkdir()
    sibling = tmp_path / "w2"
    sibling.mkdir()
    assert is_inside(sibling, root) is False


# ── 工具 ───────────────────────────────────────────────────────────────────
@pytest.fixture()
def workspace(tmp_path):
    root = tmp_path / "work"
    root.mkdir()
    (root / "notes.txt").write_text("第一行\n第二行\n第三行\n", encoding="utf-8")
    return root


def test_read_file_returns_numbered_content(workspace):
    tools = ToolRuntime(WorkspaceGuard([workspace]), workspace)
    result = tools.execute("read_file", {"path": "notes.txt"})
    assert result.is_error is False
    assert result.content.splitlines() == [
        "     1\t第一行",
        "     2\t第二行",
        "     3\t第三行",
    ]
    assert result.summary == "3 行"


def test_read_file_honours_offset_and_limit(workspace):
    tools = ToolRuntime(WorkspaceGuard([workspace]), workspace)
    result = tools.execute("read_file", {"path": "notes.txt", "offset": 2, "limit": 1})
    assert result.content.startswith("     2\t第二行")
    assert "仅显示第 2–2 行（共 3 行）" in result.content
    assert result.summary == "第 2–2/3 行"


def test_read_file_outside_root_is_denied(workspace):
    outside = workspace.parent / "secret.txt"
    outside.write_text("机密", encoding="utf-8")
    tools = ToolRuntime(WorkspaceGuard([workspace]), workspace)

    result = tools.execute("read_file", {"path": str(outside)})
    assert result.is_error is True
    assert result.content == DENIED
    assert result.summary == "越界拒绝"


def test_read_file_relative_escape_is_denied(workspace):
    tools = ToolRuntime(WorkspaceGuard([workspace]), workspace)
    result = tools.execute("read_file", {"path": "../secret.txt"})
    assert result.is_error is True
    assert result.content == DENIED


def test_read_file_without_root_rejects_relative_path(workspace):
    tools = ToolRuntime(WorkspaceGuard(), None)
    result = tools.execute("read_file", {"path": "notes.txt"})
    assert result.is_error is True
    assert result.content == NO_ROOT_RELATIVE


def test_read_file_missing_path_argument(workspace):
    tools = ToolRuntime(WorkspaceGuard([workspace]), workspace)
    assert tools.execute("read_file", {}).content == MISSING_PATH
    assert tools.execute("read_file", {"path": "   "}).content == MISSING_PATH


def test_unknown_tool_is_an_error_result(workspace):
    tools = ToolRuntime(WorkspaceGuard([workspace]), workspace)
    result = tools.execute("rm_rf", {})
    assert result.is_error is True
    assert "未知工具" in result.content


def test_read_file_missing_file_reports_error(workspace):
    tools = ToolRuntime(WorkspaceGuard([workspace]), workspace)
    result = tools.execute("read_file", {"path": "nope.txt"})
    assert result.is_error is True
    assert result.content.startswith("读取失败")


def test_numbered_text_clips_long_lines_and_guards_output_size():
    long_line = "x" * 2500
    result = numbered_text(long_line, {})
    assert "本行共 2500 字符，已截断" in result.content
    assert "有 1 行超过 2000 字符" in result.content

    huge = "\n".join("y" * 100 for _ in range(1500))
    blocked = numbered_text(huge, {})
    assert blocked.is_error is True
    assert "超过单次读取上限" in blocked.content


def test_tool_specs_are_advertised():
    tools = ToolRuntime(WorkspaceGuard())
    specs = tools.specs()
    assert [s.name for s in specs] == ["read_file"]
    assert specs[0].input_schema["required"] == ["path"]


async def _collect(iterator):
    out = []
    async for event in iterator:
        out.append(event)
    return out
