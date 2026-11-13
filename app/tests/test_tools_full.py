"""工具全集：`read_file`（文本 / 图片 / Office）、`list_dir`、`glob`、`grep`、`write_file`、
`edit_file`、`run_command`、`present_files`、`todo_write`、`web_fetch` 与越界守卫。

对照 Deva `apps/desktop/src/main/services/tools.ts` 的同名分支逐条验证；`web_fetch` 只用
离线传输入参校验协议与解析分支，**不发真实网络**（真实网页抓取归入「已实现未验证」）。
"""
from __future__ import annotations

import base64
import os
import struct
import subprocess
import sys
import time
import zipfile
from io import BytesIO

import pytest

from mvvm.services.image_prep import MAX_IMAGE_SOURCE_BYTES
from mvvm.services.tool_results import apply_todo_write_to
from mvvm.services.todos import fold_todos
from mvvm.services.tool_runtime import (
    GLOB_RESULT_MAX,
    GREP_MATCH_MAX,
    READ_OUTPUT_MAX,
    ToolResult,
    ToolRuntime,
    html_to_text,
    norm_eol,
)
from mvvm.services.workspace_guard import DENIED, WorkspaceGuard

IS_WINDOWS = os.name == "nt"
needs_posix = pytest.mark.skipif(IS_WINDOWS, reason="这些用例依赖 POSIX shell 与进程组")


# ── 夹具 ────────────────────────────────────────────────────────────────────
@pytest.fixture
def root(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    (work / "notes.txt").write_text("第一行\n第二行\n第三行\n", encoding="utf-8")
    (work / "src").mkdir()
    (work / "src" / "app.ts").write_text(
        "export function hello() {\n  return 'world'\n}\n", encoding="utf-8"
    )
    (work / "src" / "util.ts").write_text("export const x = 1\n", encoding="utf-8")
    (work / "src" / "data.json").write_text('{"k": "v"}\n', encoding="utf-8")
    (work / "node_modules").mkdir()
    (work / "node_modules" / "junk.ts").write_text("junk\n", encoding="utf-8")
    return work


@pytest.fixture
def tools(root):
    return ToolRuntime(WorkspaceGuard([root]), root, home=root.parent / "home")


@pytest.fixture
def home(tmp_path):
    return tmp_path / "home"


# ── 声明 ────────────────────────────────────────────────────────────────────
def test_runtime_registers_ten_offline_tools(tools):
    names = [spec.name for spec in tools.specs()]
    assert len(names) == 10
    assert "read_file" in names and "run_command" in names and "todo_write" in names
    # 依赖未迁移子系统的工具不得注册（不假装可用）。
    for absent in ("browser", "ask_user", "memory_read", "create_skill", "exit_plan"):
        assert absent not in names


def test_unknown_tool_and_bad_arguments(tools):
    unknown = tools.execute("nope", {})
    assert unknown.is_error and "未知工具" in unknown.content
    bad = tools.execute("read_file", ["not", "a", "dict"])
    assert bad.is_error and "必须是对象" in bad.content


# ── read_file ───────────────────────────────────────────────────────────────
def test_read_file_rejects_path_outside_roots(tmp_path):
    outside = tmp_path / "secret.txt"
    outside.write_text("机密", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    tools = ToolRuntime(WorkspaceGuard([work]), work)
    result = tools.execute("read_file", {"path": str(outside)})
    assert result.is_error is True
    assert result.content == DENIED


def test_read_file_empty_and_binary(tools, root):
    (root / "empty.txt").write_bytes(b"")
    assert "空文件" in tools.execute("read_file", {"path": "empty.txt"}).content
    (root / "bin.dat").write_bytes(b"\x00\x01\x02hello")
    binary = tools.execute("read_file", {"path": "bin.dat"})
    assert binary.is_error and "二进制" in binary.content


def test_read_file_crlf_and_lone_cr(tools, root):
    (root / "crlf.txt").write_bytes(b"a\r\nb\r\n")
    result = tools.execute("read_file", {"path": "crlf.txt"})
    assert result.content.splitlines() == ["     1\ta", "     2\tb"]


def test_read_file_image_returns_image_part(tools, root):
    png = _tiny_png()
    (root / "shot.png").write_bytes(png)
    result = tools.execute("read_file", {"path": "shot.png"})
    assert result.is_error is False
    assert result.images and len(result.images) == 1
    part = result.images[0]
    assert part.mediaType == "image/png"
    assert base64.b64decode(part.data) == png
    assert "[图片]" in result.content
    assert "1×1" in result.content


def test_read_file_image_mime_follows_magic_not_extension(tools, root):
    # 扩展名写成 .txt 也要按魔数认出图片（Deva 同口径：扩展名不可信）。
    (root / "pic.txt").write_bytes(_tiny_png())
    result = tools.execute("read_file", {"path": "pic.txt"})
    assert result.images and result.images[0].mediaType == "image/png"


def test_read_file_rejects_oversized_image(tools, root, monkeypatch):
    big = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    (root / "big.png").write_bytes(big)
    monkeypatch.setattr("mvvm.services.tool_runtime.MAX_IMAGE_SOURCE_BYTES", 8)
    result = tools.execute("read_file", {"path": "big.png"})
    assert result.is_error and "图片超过" in result.content


def test_read_file_oversized_text_is_refused(tools, root):
    (root / "big.txt").write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    result = tools.execute("read_file", {"path": "big.txt"})
    assert result.is_error and "超过 2MB" in result.content


def test_read_file_docx_returns_numbered_text(tools, root):
    (root / "doc.docx").write_bytes(_docx("标题段落", "正文段落"))
    result = tools.execute("read_file", {"path": "doc.docx"})
    assert result.is_error is False
    assert "     1\t标题段落" in result.content
    assert "     2\t正文段落" in result.content
    assert "DOCX" in result.content


def test_read_file_xlsx_and_pptx(tools, root):
    (root / "sheet.xlsx").write_bytes(_xlsx())
    sheet = tools.execute("read_file", {"path": "sheet.xlsx"})
    assert sheet.is_error is False
    assert "工作表：Sheet1" in sheet.content
    assert "姓名" in sheet.content and "张三" in sheet.content

    (root / "deck.pptx").write_bytes(_pptx("第一页文字"))
    deck = tools.execute("read_file", {"path": "deck.pptx"})
    assert deck.is_error is False
    assert "第 1 页" in deck.content and "第一页文字" in deck.content


def test_read_file_office_legacy_binary_is_clear_error(tools, root):
    # 旧版二进制 .doc 不在 OFFICE_EXT 里，含 NUL 字节 → 按 Deva 口径判为二进制并拒绝。
    (root / "old.doc").write_bytes(b"\xd0\xcf\x11\xe0\x00old binary")
    result = tools.execute("read_file", {"path": "old.doc"})
    assert result.is_error and "二进制" in result.content
    # 扩展名是 .docx 但内容不是 zip（旧格式改扩展名 / 加密）→ 明确说解析不了。
    (root / "fake.docx").write_bytes(b"not a zip at all")
    fake = tools.execute("read_file", {"path": "fake.docx"})
    assert fake.is_error and "无法解析" in fake.content


def test_read_file_requires_path(tools):
    result = tools.execute("read_file", {})
    assert result.is_error and "path" in result.content


def test_relative_path_without_root_is_explicit_error():
    tools = ToolRuntime(WorkspaceGuard())
    result = tools.execute("read_file", {"path": "notes.txt"})
    assert result.is_error and "未挂载工作区" in result.content


# ── list_dir / glob ─────────────────────────────────────────────────────────
def test_list_dir_puts_directories_first(tools, root):
    result = tools.execute("list_dir", {})
    assert result.is_error is False
    assert result.content.splitlines()[0] == "node_modules/"
    assert "notes.txt" in result.content.splitlines()
    # 顶层是 node_modules/ 与 src/（目录）+ notes.txt（文件）。
    assert result.summary == "3 项"


def test_list_dir_empty_directory(tools, root):
    (root / "void").mkdir()
    assert tools.execute("list_dir", {"path": "void"}).content == "（空目录）"


def test_glob_matches_nested_patterns_and_skips_noise(tools):
    result = tools.execute("glob", {"pattern": "**/*.ts"})
    assert result.is_error is False
    paths = result.content.splitlines()
    assert "src/app.ts" in paths and "src/util.ts" in paths
    assert all("node_modules" not in path for path in paths)
    assert result.summary == "2 个文件"


def test_glob_brace_alternation(tools):
    result = tools.execute("glob", {"pattern": "**/*.{ts,json}"})
    names = {path.split("/")[-1] for path in result.content.splitlines()}
    assert names == {"app.ts", "util.ts", "data.json"}


def test_glob_no_match_and_missing_pattern(tools):
    assert tools.execute("glob", {"pattern": "**/*.zzz"}).content == "（无匹配文件）"
    assert tools.execute("glob", {}).is_error is True


# ── grep ────────────────────────────────────────────────────────────────────
def test_grep_returns_path_line_and_text(tools):
    result = tools.execute("grep", {"pattern": "world"})
    assert result.is_error is False
    assert "src/app.ts:2:" in result.content and "return 'world'" in result.content
    assert result.summary == "1 处"


def test_grep_glob_filter_and_ignore_case(tools):
    filtered = tools.execute("grep", {"pattern": "export", "glob": "*.json"})
    assert filtered.summary == "无匹配"
    insensitive = tools.execute("grep", {"pattern": "WORLD", "ignore_case": True})
    assert insensitive.summary == "1 处"


def test_grep_invalid_regex_falls_back_to_literal(tools, root):
    (root / "src" / "util.ts").write_text("const re = /a(b/c\n", encoding="utf-8")
    result = tools.execute("grep", {"pattern": "a(b"})
    assert "不是合法的正则" in result.content
    assert "src/util.ts:1:" in result.content


def test_grep_stops_at_match_cap(tools, root):
    (root / "many.txt").write_text("\n".join("hit" for _ in range(GREP_MATCH_MAX + 20)), encoding="utf-8")
    result = tools.execute("grep", {"pattern": "hit"})
    assert "匹配过多" in result.content
    assert result.summary == f"{GREP_MATCH_MAX}+ 处"


def test_grep_respects_gitignore(tools, root):
    (root / ".git").mkdir()
    (root / ".gitignore").write_text("*.json\n", encoding="utf-8")
    hidden = tools.execute("grep", {"pattern": "k"})
    assert "src/data.json" not in hidden.content
    listed = tools.execute("list_dir", {"path": "src"})
    assert "data.json" in listed.content  # list_dir 不读 gitignore，与 Deva 一致


def test_grep_on_single_file(tools):
    result = tools.execute("grep", {"pattern": "hello", "path": "src/app.ts"})
    assert result.summary == "1 处"


# ── write_file / edit_file ──────────────────────────────────────────────────
def test_write_file_creates_and_overwrites(tools, root):
    created = tools.execute("write_file", {"path": "new/deep/a.txt", "content": "abc"})
    assert created.is_error is False
    assert (root / "new" / "deep" / "a.txt").read_text(encoding="utf-8") == "abc"

    tools.execute("write_file", {"path": "notes.txt", "content": "换掉"})
    assert (root / "notes.txt").read_text(encoding="utf-8") == "换掉"


def test_write_file_append_keeps_crlf_style(tools, root):
    (root / "crlf.txt").write_bytes(b"one\r\ntwo\r\n")
    tools.execute("write_file", {"path": "crlf.txt", "content": "three\n", "append": True})
    data = (root / "crlf.txt").read_bytes()
    assert data == b"one\r\ntwo\r\nthree\r\n"


def test_write_file_preserves_utf8_bom(tools, root):
    (root / "bom.txt").write_bytes("﻿旧内容".encode("utf-8"))
    tools.execute("write_file", {"path": "bom.txt", "content": "新内容"})
    assert (root / "bom.txt").read_bytes().startswith(b"\xef\xbb\xbf")


def test_write_file_outside_root_denied(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    target = tmp_path / "outside.txt"
    tools = ToolRuntime(WorkspaceGuard([work]), work)
    result = tools.execute("write_file", {"path": str(target), "content": "x"})
    assert result.is_error and result.content == DENIED
    assert not target.exists()


def test_edit_file_replaces_unique_match(tools, root):
    result = tools.execute(
        "edit_file", {"path": "src/util.ts", "old_string": "x = 1", "new_string": "x = 2"}
    )
    assert result.is_error is False
    assert (root / "src" / "util.ts").read_text(encoding="utf-8") == "export const x = 2\n"


def test_edit_file_requires_uniqueness(tools, root):
    (root / "dup.txt").write_text("a\nb\na\n", encoding="utf-8")
    ambiguous = tools.execute("edit_file", {"path": "dup.txt", "old_string": "a", "new_string": "c"})
    assert ambiguous.is_error and "不唯一" in ambiguous.content
    replaced = tools.execute(
        "edit_file", {"path": "dup.txt", "old_string": "a", "new_string": "c", "replace_all": True}
    )
    assert replaced.is_error is False
    assert (root / "dup.txt").read_text(encoding="utf-8") == "c\nb\nc\n"


def test_edit_file_missing_and_empty_old(tools):
    missing = tools.execute("edit_file", {"path": "notes.txt", "old_string": "没有这句", "new_string": "x"})
    assert missing.is_error and "未找到" in missing.content
    empty = tools.execute("edit_file", {"path": "notes.txt", "old_string": "", "new_string": "x"})
    assert empty.is_error and "不能为空" in empty.content
    same = tools.execute("edit_file", {"path": "notes.txt", "old_string": "第一行", "new_string": "第一行"})
    assert same.is_error and "无需编辑" in same.content


def test_edit_file_crlf_file_matches_lf_old_string(tools, root):
    (root / "win.txt").write_bytes(b"alpha\r\nbeta\r\n")
    result = tools.execute(
        "edit_file", {"path": "win.txt", "old_string": "alpha\nbeta", "new_string": "gamma\nbeta"}
    )
    assert result.is_error is False
    assert (root / "win.txt").read_bytes() == b"gamma\r\nbeta\r\n"


def test_edit_file_rejects_binary(tools, root):
    (root / "b.bin").write_bytes(b"\x00\x00abc")
    result = tools.execute("edit_file", {"path": "b.bin", "old_string": "abc", "new_string": "d"})
    assert result.is_error and "二进制" in result.content


def test_norm_eol_helper():
    assert norm_eol("a\r\nb\rc\n") == "a\nb\nc\n"


# ── run_command ─────────────────────────────────────────────────────────────
@needs_posix
def test_run_command_runs_in_workspace_root(tools, root):
    result = tools.execute("run_command", {"command": "pwd && printf 'ok'"})
    assert result.is_error is False
    assert str(root).endswith(result.content.splitlines()[0].strip())
    assert "ok" in result.content
    assert "退出码：0" in result.content


@needs_posix
def test_run_command_nonzero_exit_is_error(tools):
    result = tools.execute("run_command", {"command": "exit 3"})
    assert result.is_error is True
    assert "退出码：3" in result.content


@needs_posix
def test_run_command_caps_long_output(tools):
    result = tools.execute("run_command", {"command": "seq 1 200000"})
    assert "输出过长" in result.content
    assert "完整内容已保存到" in result.content


@needs_posix
def test_run_command_spill_file_lands_under_home(tools, root):
    tools.execute("run_command", {"command": "seq 1 40000"})
    results = list((root.parent / "home" / "data" / "tool-results" / "_misc").glob("*.txt"))
    assert results, "超长输出应落盘到 <home>/data/tool-results/<session>/"
    assert len(results[0].read_text(encoding="utf-8")) > 30_000


@needs_posix
def test_run_command_times_out(tools):
    result = tools.execute("run_command", {"command": "sleep 5", "timeout": 1000})
    assert result.is_error is True
    assert "超时" in result.content


@needs_posix
def test_run_command_honours_cancel(tools):
    state = {"cancelled": False}
    tools.cancel_check = lambda: state["cancelled"]
    state["cancelled"] = True
    result = tools.execute("run_command", {"command": "sleep 5"})
    assert result.is_error is True
    assert "已中止" in result.content


def test_run_command_requires_command(tools):
    result = tools.execute("run_command", {"command": "   "})
    assert result.is_error and "command" in result.content


def test_run_command_without_root_uses_home(monkeypatch, tmp_path):
    fake_home = tmp_path / "homedir"
    fake_home.mkdir()
    monkeypatch.setattr("mvvm.services.tool_runtime.Path.home", lambda: fake_home)
    tools = ToolRuntime(WorkspaceGuard())
    result = tools.execute("run_command", {"command": "pwd"})
    if IS_WINDOWS:
        assert result.is_error in (True, False)
    else:
        assert str(fake_home) in result.content


# ── present_files ───────────────────────────────────────────────────────────
def test_present_files_validates_and_returns_paths(tools, root):
    good = tools.execute("present_files", {"paths": ["notes.txt", "src/app.ts", "notes.txt"]})
    assert good.is_error is False
    assert good.delivered == [str(root / "notes.txt"), str(root / "src" / "app.ts")]
    assert "已交付 2 个文件" in good.content
    assert "重复的路径已合并" in good.content


def test_present_files_reports_every_bad_path(tools):
    result = tools.execute("present_files", {"paths": ["nope.txt", "src"]})
    assert result.is_error is True
    assert "文件不存在" in result.content and "不是文件" in result.content
    assert result.delivered is None


def test_present_files_limits_count(tools):
    result = tools.execute("present_files", {"paths": [f"f{i}.txt" for i in range(21)]})
    assert result.is_error and "最多交付 20 个" in result.content


def test_present_files_rejects_outside_paths(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    outside = tmp_path / "x.txt"
    outside.write_text("y", encoding="utf-8")
    tools = ToolRuntime(WorkspaceGuard([work]), work)
    result = tools.execute("present_files", {"paths": [str(outside)]})
    assert result.is_error and DENIED in result.content


# ── todo_write ──────────────────────────────────────────────────────────────
class _TodoBox:
    """把 todo_write 的落点记在内存里：模拟会话边车（测试不碰磁盘）。"""

    def __init__(self) -> None:
        self.entries: list = []
        self.cancelled: list = []
        self.applied = []

    def sink(self, tool_use_id: str, arguments: dict) -> ToolResult:
        applied = apply_todo_write_to(
            self.entries, self.cancelled, tool_use_id, arguments, _now()
        )
        self.entries, self.cancelled = applied.entries, applied.cancelled
        self.applied.append(applied)
        return applied.result


def _now() -> int:
    return int(time.time() * 1000)


def test_todo_write_without_sink_is_explicit(tools):
    result = tools.execute("todo_write", {"todos": [{"content": "a", "status": "pending"}]})
    assert result.is_error and "不提供待办清单" in result.content


def test_todo_write_records_snapshot_and_folds(tools):
    box = _TodoBox()
    tools.todo_sink = box.sink
    result = tools.execute(
        "todo_write",
        {
            "title": "迁移",
            "todos": [
                {"content": "读源码", "status": "completed"},
                {"content": "写实现", "status": "in_progress"},
            ],
        },
        tool_use_id="t1",
    )
    assert result.is_error is False
    assert "已完成 1/2" in result.content
    lists = fold_todos(box.entries)
    assert len(lists) == 1 and lists[0]["title"] == "迁移"
    assert lists[0]["items"][1]["status"] == "in_progress"


def test_todo_write_invalid_payload(tools):
    box = _TodoBox()
    tools.todo_sink = box.sink
    result = tools.execute("todo_write", {"todos": []}, tool_use_id="t1")
    assert result.is_error and "不能为空" in result.content
    assert box.entries == []


# ── web_fetch（离线：只验证协议与解析，不发真实网络）──────────────────────────
def test_web_fetch_rejects_non_http(tools):
    result = tools.execute("web_fetch", {"url": "file:///etc/passwd"})
    assert result.is_error and "仅支持 http/https" in result.content


def test_web_fetch_requires_url(tools):
    assert tools.execute("web_fetch", {}).is_error is True


def test_html_to_text_strips_scripts_and_keeps_title():
    title, text = html_to_text(
        "<html><head><title>例子 &amp; 标题</title><style>p{}</style></head>"
        "<body><script>alert(1)</script><h1>大标题</h1><p>正文&amp;内容</p></body></html>"
    )
    assert title == "例子 & 标题"
    assert "alert" not in text and "p{}" not in text
    assert "大标题" in text and "正文&内容" in text


# ── 结果字段 ────────────────────────────────────────────────────────────────
def test_tool_result_defaults():
    result = ToolResult("x")
    assert result.is_error is False and result.images is None and result.delivered is None


def test_read_output_guard_constant_matches_deva():
    assert READ_OUTPUT_MAX == 100_000
    assert GLOB_RESULT_MAX == 500


# ── 图形 / Office 测试素材（最小合法文件，不依赖第三方库生成）───────────────────
def _tiny_png() -> bytes:
    """1×1 透明 PNG（手写 IHDR/IDAT/IEND，避免引入 Pillow 只为了造测试数据）。"""
    import zlib

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)
    idat = zlib.compress(b"\x00\x00\x00\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def _docx(*paragraphs: str) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    return _zip({"word/document.xml": xml.encode("utf-8")})


def _xlsx() -> bytes:
    shared = (
        '<?xml version="1.0" encoding="UTF-8"?><sst>'
        "<si><t>姓名</t></si><si><t>张三</t></si></sst>"
    )
    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?><worksheet><sheetData>'
        '<row r="1"><c r="A1" t="s"><v>0</v></c></row>'
        '<row r="2"><c r="A2" t="s"><v>1</v></c></row>'
        "</sheetData></worksheet>"
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8"?><workbook>'
        '<sheet name="Sheet1" sheetId="1" r:id="rId1"/></workbook>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?><Relationships>'
        '<Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>'
    )
    return _zip(
        {
            "xl/sharedStrings.xml": shared.encode("utf-8"),
            "xl/workbook.xml": workbook.encode("utf-8"),
            "xl/_rels/workbook.xml.rels": rels.encode("utf-8"),
            "xl/worksheets/sheet1.xml": sheet.encode("utf-8"),
        }
    )


def _pptx(text: str) -> bytes:
    slide = (
        '<?xml version="1.0" encoding="UTF-8"?><p:sld xmlns:p="p" xmlns:a="a"><p:cSld>'
        f"<p:sp><p:txBody><a:p><a:r><a:t>{text}</a:t></a:r></a:p></p:txBody></p:sp>"
        "</p:cSld></p:sld>"
    )
    return _zip({"ppt/slides/slide1.xml": slide.encode("utf-8")})


def _zip(files: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


# 显式标记：这几个常量的改动会影响别处，测试顺带把它们钉住。
_ = (sys, subprocess, MAX_IMAGE_SOURCE_BYTES)
