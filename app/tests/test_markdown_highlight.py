"""``markdown.highlight``：按块属性里的语言标签做词法着色。

高亮器是 ``QSyntaxHighlighter``：它只在 ``rehighlight()`` 之后才把格式写进
``QTextLayout``，所以每个用例都先挂上高亮器、再读 ``block.layout().formats()``。

配色断言取的是 highlight.js 主题的实际颜色（``LIGHT_TOKENS``/``DARK_TOKENS``），
不是「有颜色就算过」——颜色对不上原版就是没对上。
"""
from __future__ import annotations

import pytest

QtGui = pytest.importorskip("PySide6.QtGui", reason="高亮器是 Qt 类")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application


import markdown.document as document_module  # noqa: E402
import markdown.highlight as highlight_module  # noqa: E402
from markdown.document import BodyStyle, render_markdown  # noqa: E402
from markdown.highlight import (  # noqa: E402
    DARK_TOKENS,
    LANGUAGES,
    LIGHT_TOKENS,
    CodeHighlighter,
    language_for,
    token_colors,
)

QTextDocument = QtGui.QTextDocument


# ── 工具 ─────────────────────────────────────────────────────────────────
def highlighted(markdown_text: str, style=None):
    """渲染 + 挂高亮器 + rehighlight；返回 (文档, 高亮器)。"""
    document = QTextDocument()
    render_markdown(document, markdown_text, style or BodyStyle(), content_width=600.0)
    highlighter = CodeHighlighter(document, style or BodyStyle())
    highlighter.rehighlight()
    return document, highlighter


def block_text(document, text):
    block = document.begin()
    while block.isValid():
        if block.text() == text:
            return block
        block = block.next()
    raise AssertionError("no block %r" % (text,))


def coloured(block):
    """``{子串: 颜色名}``：把 layout 的格式切片按文本取出来。"""
    out = {}
    for layout_format in block.layout().formats():
        start = layout_format.start
        piece = block.text()[start:start + layout_format.length]
        out[piece] = layout_format.format.foreground().color().name()
    return out


def colour_of(block, needle):
    for layout_format in block.layout().formats():
        start = layout_format.start
        if block.text()[start:start + layout_format.length] == needle:
            return layout_format.format.foreground().color().name()
    return None


# ── 语言登记表 ───────────────────────────────────────────────────────────
def test_language_aliases_resolve_to_one_lexical_family():
    assert language_for("py").name == "python"
    assert language_for("Python").name == "python"
    assert language_for("js").name == "clike"
    assert language_for("TSX").name == "clike"
    assert language_for("sh").name == "shell"
    assert language_for("yml").name == "yaml"


def test_unknown_language_is_not_guessed():
    assert language_for("brainfuck") is None
    assert language_for("") is None
    assert language_for("   ") is None


def test_every_registered_alias_points_at_a_language_object():
    assert LANGUAGES, "登记表不能为空"
    for alias, language in LANGUAGES.items():
        assert alias == alias.lower()
        assert language.name


def test_token_colours_follow_the_theme():
    assert token_colors(dark=False) == LIGHT_TOKENS
    assert token_colors(dark=True) == DARK_TOKENS
    # 返回副本：调用方改它不能污染配色表。
    token_colors(False)["comment"] = "#badbad"
    assert LIGHT_TOKENS["comment"] != "#badbad"


# ── Python ───────────────────────────────────────────────────────────────
def test_python_keywords_numbers_and_comments_are_coloured(qapp):
    document, _ = highlighted("```python\nif x == 1:  # note\n    return 'a'\n```")
    block = block_text(document, "if x == 1:  # note")
    assert coloured(block)["if"] == LIGHT_TOKENS["keyword"]
    assert colour_of(block, "1") == LIGHT_TOKENS["number"]
    assert colour_of(block, "# note") == LIGHT_TOKENS["comment"]
    # 下一行的 `return` 与字符串同样要被着色（空行/跨块状态不能吃掉后续行）。
    following = block_text(document, "    return 'a'")
    assert colour_of(following, "return") == LIGHT_TOKENS["keyword"]
    assert colour_of(following, "'a'") == LIGHT_TOKENS["string"]


def test_python_string_is_string_coloured(qapp):
    document, _ = highlighted('```python\nname = "value"\n```')
    assert colour_of(block_text(document, 'name = "value"'), '"value"') == LIGHT_TOKENS["string"]


def test_comments_are_italic(qapp):
    document, _ = highlighted("```python\n# note\n```")
    block = block_text(document, "# note")
    formats = [f for f in block.layout().formats() if block.text()[f.start:f.start + f.length] == "# note"]
    assert formats[0].format.fontItalic() is True


def test_function_name_before_a_paren_is_a_title(qapp):
    document, _ = highlighted("```python\ndef hello(name):\n    pass\n```")
    assert colour_of(block_text(document, "def hello(name):"), "hello") == LIGHT_TOKENS["title"]


def test_triple_quoted_string_spans_blocks(qapp):
    document, _ = highlighted('```python\nx = """\ninside\n"""\n```')
    assert colour_of(block_text(document, 'x = """'), '"""') == LIGHT_TOKENS["string"]
    assert colour_of(block_text(document, "inside"), "inside") == LIGHT_TOKENS["string"]
    assert colour_of(block_text(document, '"""'), '"""') == LIGHT_TOKENS["string"]
    # 三引号块结束后回到普通着色：后面的代码不能继续算字符串。
    document, _ = highlighted('```python\ns = """doc"""\nvalue = 1\n```')
    assert colour_of(block_text(document, "value = 1"), "1") == LIGHT_TOKENS["number"]


# ── 其他语言族 ───────────────────────────────────────────────────────────
def test_clike_block_comment_spans_blocks(qapp):
    document, _ = highlighted("```c\n/* start\n   middle\n   end */\nint x;\n```")
    assert colour_of(block_text(document, "/* start"), "/* start") == LIGHT_TOKENS["comment"]
    assert colour_of(block_text(document, "   middle"), "   middle") == LIGHT_TOKENS["comment"]
    assert colour_of(block_text(document, "   end */"), "   end */") == LIGHT_TOKENS["comment"]
    # 注释结束后的行回到普通着色。
    assert colour_of(block_text(document, "int x;"), "x") != LIGHT_TOKENS["comment"]


def test_shell_comments_are_hash_lines(qapp):
    document, _ = highlighted("```bash\nls -la # listing\n```")
    assert colour_of(block_text(document, "ls -la # listing"), "# listing") == LIGHT_TOKENS["comment"]


def test_json_literals_and_strings(qapp):
    document, _ = highlighted('```json\n{"a": true}\n```')
    block = block_text(document, '{"a": true}')
    assert colour_of(block, '"a"') == LIGHT_TOKENS["string"]
    assert colour_of(block, "true") == LIGHT_TOKENS["keyword"]


def test_sql_keywords_are_case_insensitive_both_ways(qapp):
    document, _ = highlighted("```sql\nSELECT * FROM t\nselect * from t\n```")
    assert colour_of(block_text(document, "SELECT * FROM t"), "SELECT") == LIGHT_TOKENS["keyword"]
    assert colour_of(block_text(document, "select * from t"), "select") == LIGHT_TOKENS["keyword"]


def test_unsupported_language_leaves_the_code_uncoloured(qapp):
    document, _ = highlighted("```brainfuck\n++[>+<-]\n```")
    assert block_text(document, "++[>+<-]").layout().formats() == []


def test_code_without_a_language_tag_is_not_coloured(qapp):
    document, _ = highlighted("```\nplain text\n```")
    assert block_text(document, "plain text").layout().formats() == []


# ── 主题与开关 ───────────────────────────────────────────────────────────
def test_dark_theme_uses_the_dark_token_palette(qapp):
    document, _ = highlighted("```python\nif x: pass\n```", BodyStyle(dark=True))
    assert colour_of(block_text(document, "if x: pass"), "if") == DARK_TOKENS["keyword"]
    assert DARK_TOKENS["keyword"] != LIGHT_TOKENS["keyword"]


def test_set_style_repaints_with_the_new_palette(qapp):
    document, highlighter = highlighted("```python\nif x: pass\n```")
    bare = QTextDocument()
    render_markdown(bare, "```python\nif x: pass\n```", BodyStyle(), content_width=600.0)
    other = CodeHighlighter(bare, BodyStyle())
    other.set_style(BodyStyle(dark=True))
    assert colour_of(block_text(bare, "if x: pass"), "if") == DARK_TOKENS["keyword"]


def test_default_language_applies_to_untagged_blocks(qapp):
    document = QTextDocument()
    render_markdown(document, "```\nif x: pass\n```", BodyStyle(), content_width=600.0)
    highlighter = CodeHighlighter(document, BodyStyle())
    assert block_text(document, "if x: pass").layout().formats() == []
    highlighter.set_language_default("python")
    assert colour_of(block_text(document, "if x: pass"), "if") == LIGHT_TOKENS["keyword"]
    highlighter.set_language_default("")
    assert block_text(document, "if x: pass").layout().formats() == []


def test_attach_helper_returns_the_object_the_caller_must_hold(qapp):
    document = QTextDocument()
    render_markdown(document, "```python\nx = 1\n```", BodyStyle(), content_width=600.0)
    highlighter = highlight_module.attach(document, BodyStyle())
    highlighter.rehighlight()
    assert isinstance(highlighter, CodeHighlighter)
    assert colour_of(block_text(document, "x = 1"), "1") == LIGHT_TOKENS["number"]


def test_language_property_is_read_from_the_block_format(qapp):
    """语言标签写在块属性上；高亮器不解析 Markdown。"""
    document, _ = highlighted("```python\nx = 1\n```")
    block = block_text(document, "x = 1")
    assert block.blockFormat().property(document_module.CODE_LANGUAGE_PROPERTY) == "python"
