"""``markdown.parser``：纯 Python 的块级/行内解析（不 import Qt）。

这里只断言解析结果的数据形状——渲染成什么样由 ``test_markdown_document`` 负责。
解析器的约定写在 ``app/src/markdown/parser.py`` 顶部的 docstring 里，重点是
「不猜」：配对失败的标记按字面保留，绝不吞掉用户原文。
"""
from __future__ import annotations

import json

from markdown.parser import parse_inline, parse_markdown


def types(blocks):
    return [block["type"] for block in blocks]


def plain(nodes):
    """行内树 → 纯文本（只取 text 节点，用于断言内容没被吃掉）。"""
    out = []
    for node in nodes:
        if node.get("text"):
            out.append(node["text"])
        if node.get("children"):
            out.append(plain(node["children"]))
    return "".join(out)


# ── 标题、段落、分隔线 ───────────────────────────────────────────────────
def test_atx_headings_keep_their_level_and_strip_closing_hashes():
    blocks = parse_markdown("# one\n## two\n###### six ######")
    assert [(b["type"], b["level"]) for b in blocks] == [
        ("heading", 1),
        ("heading", 2),
        ("heading", 6),
    ]
    assert plain(blocks[2]["children"]) == "six"


def test_heading_without_text_is_still_a_heading():
    blocks = parse_markdown("###")
    assert blocks[0]["type"] == "heading"
    assert blocks[0]["level"] == 3
    assert blocks[0]["children"] == []


def test_paragraph_keeps_soft_line_breaks_and_joins_the_lines():
    blocks = parse_markdown("first\nsecond\n\nthird")
    assert types(blocks) == ["paragraph", "paragraph"]
    assert plain(blocks[0]["children"]) == "first\nsecond"


def test_blank_lines_do_not_produce_empty_blocks():
    assert parse_markdown("\n\n\n") == []
    assert types(parse_markdown("a\n\n\nb")) == ["paragraph", "paragraph"]


def test_horizontal_rules_accept_every_marker_and_reject_two():
    assert types(parse_markdown("***")) == ["hr"]
    assert types(parse_markdown("- - -")) == ["hr"]
    assert types(parse_markdown("___")) == ["hr"]
    # 两个横线不是分隔线，是两个字符的段落。
    assert types(parse_markdown("--")) == ["paragraph"]


def test_a_paragraph_is_interrupted_by_the_next_block():
    blocks = parse_markdown("para\n# heading\npara2\n- item")
    assert types(blocks) == ["paragraph", "heading", "paragraph", "list"]


def test_crlf_and_tabs_are_normalised():
    blocks = parse_markdown("a\r\nb\r\n\r\nc")
    assert plain(blocks[0]["children"]) == "a\nb"
    # 制表位按 4 列展开：单字符后接 tab 是 3 个空格。
    assert plain(parse_markdown("a\tb")[0]["children"]) == "a   b"


# ── 围栏代码块 ───────────────────────────────────────────────────────────
def test_fenced_code_keeps_language_and_body_verbatim():
    blocks = parse_markdown("```python\ndef f():\n    return 1\n```")
    assert blocks[0]["type"] == "code"
    assert blocks[0]["language"] == "python"
    assert blocks[0]["text"] == "def f():\n    return 1"


def test_tilde_fences_and_fences_without_language():
    blocks = parse_markdown("~~~\nraw\n~~~")
    assert blocks[0]["type"] == "code"
    assert blocks[0]["language"] == ""
    assert blocks[0]["text"] == "raw"


def test_an_unclosed_fence_runs_to_the_end_instead_of_losing_text():
    blocks = parse_markdown("```\nstill code\nlast line")
    assert blocks[0]["type"] == "code"
    assert blocks[0]["text"] == "still code\nlast line"


def test_a_shorter_fence_does_not_close_the_block():
    blocks = parse_markdown("````\n```\ninner\n````")
    assert blocks[0]["text"] == "```\ninner"


def test_code_fence_language_lowercase_is_not_rewritten_here():
    """语言标签原样保留；大小写归一化是渲染层与高亮器的事。"""
    assert parse_markdown("```PyThOn\nx\n```")[0]["language"] == "PyThOn"


# ── 引用 ─────────────────────────────────────────────────────────────────
def test_quote_parses_its_content_as_blocks():
    blocks = parse_markdown("> one\n> two\n>\n> - item")
    assert types(blocks) == ["quote"]
    assert types(blocks[0]["children"]) == ["paragraph", "list"]
    assert plain(blocks[0]["children"][0]["children"]) == "one\ntwo"


def test_nested_quote_becomes_a_quote_inside_a_quote():
    outer = parse_markdown("> q1\n> > nested\n>\n> back")[0]
    assert types(outer["children"]) == ["paragraph", "quote", "paragraph"]
    assert types(outer["children"][1]["children"]) == ["paragraph"]
    assert plain(outer["children"][1]["children"][0]["children"]) == "nested"


def test_quote_marker_without_space_is_accepted():
    assert plain(parse_markdown(">tight")[0]["children"][0]["children"]) == "tight"


# ── 列表 ─────────────────────────────────────────────────────────────────
def test_unordered_list_accepts_every_marker_in_one_list():
    blocks = parse_markdown("+ a\n* b\n- c")
    assert types(blocks) == ["list"]
    assert blocks[0]["ordered"] is False
    assert [plain(item["children"][0]["children"]) for item in blocks[0]["items"]] == ["a", "b", "c"]


def test_ordered_list_keeps_its_start_number():
    blocks = parse_markdown("3. c\n4. d")
    assert blocks[0]["ordered"] is True
    assert blocks[0]["start"] == 3
    assert len(blocks[0]["items"]) == 2


def test_blank_lines_inside_a_list_continue_it_when_the_next_item_matches():
    blocks = parse_markdown("1. one\n\n2. two")
    assert types(blocks) == ["list"]
    assert len(blocks[0]["items"]) == 2


def test_different_list_kind_after_a_blank_line_starts_a_new_list():
    blocks = parse_markdown("- a\n- b\n\n1. x\n2. y")
    assert types(blocks) == ["list", "list"]
    assert [block["ordered"] for block in blocks] == [False, True]


def test_task_items_record_their_state():
    blocks = parse_markdown("- [ ] todo\n- [x] done\n- plain")
    assert blocks[0]["task"] is True
    assert [item["task"] for item in blocks[0]["items"]] == [False, True, None]
    assert plain(blocks[0]["items"][0]["children"][0]["children"]) == "todo"


def test_nested_list_is_a_child_block_of_its_item():
    blocks = parse_markdown("- outer\n  - inner\n  - inner2\n- second")
    outer = blocks[0]
    assert len(outer["items"]) == 2
    nested = outer["items"][0]["children"][1]
    assert nested["type"] == "list"
    assert [plain(item["children"][0]["children"]) for item in nested["items"]] == ["inner", "inner2"]
    # 嵌套列表不挂在第二项上。
    assert [child["type"] for child in outer["items"][1]["children"]] == ["paragraph"]


def test_item_with_both_text_and_nested_list_is_flagged_loose():
    blocks = parse_markdown("- outer\n  - inner")
    assert blocks[0]["items"][0]["loose"] is True
    assert parse_markdown("- only text")[0]["items"][0]["loose"] is False


def test_a_list_item_can_be_empty():
    blocks = parse_markdown("-\n- b")
    assert types(blocks) == ["list"]
    assert blocks[0]["items"][0]["children"] == []


# ── 表格 ─────────────────────────────────────────────────────────────────
def test_table_records_header_rows_and_alignment():
    blocks = parse_markdown("| a | b | c |\n|:--|:-:|--:|\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |")
    table = blocks[0]
    assert table["type"] == "table"
    assert table["align"] == ["left", "center", "right"]
    assert [plain(cell) for cell in table["header"]] == ["a", "b", "c"]
    assert [[plain(cell) for cell in row] for row in table["rows"]] == [["1", "2", "3"], ["4", "5", "6"]]


def test_table_without_outer_pipes_and_short_rows():
    blocks = parse_markdown("a | b\n--- | ---\n1 | 2")
    assert types(blocks) == ["table"]
    assert blocks[0]["rows"][0][0][0]["text"] == "1"


def test_a_short_row_is_padded_with_empty_cells():
    blocks = parse_markdown("| a | b |\n| - | - |\n| 1 |")
    assert len(blocks[0]["rows"][0]) == 2
    assert blocks[0]["rows"][0][1] == []


def test_separator_row_cell_count_must_match_the_header():
    # 只有一列分隔符却有两列表头：不是表格，按段落原样保留。
    blocks = parse_markdown("| a | b |\n| --- |\n| 1 | 2 |")
    assert types(blocks)[0] == "paragraph"


def test_escaped_pipe_stays_inside_its_cell():
    blocks = parse_markdown("| a \\| b | c |\n| - | - |\n| 1 | 2 |")
    assert plain(blocks[0]["header"][0]) == "a | b"


# ── 行内 ─────────────────────────────────────────────────────────────────
def kinds(nodes):
    return [node["type"] for node in nodes]


def test_inline_strong_em_and_strikethrough():
    nodes = parse_inline("a **b** *c* __d__ ~~e~~")
    assert kinds(nodes) == ["text", "strong", "text", "em", "text", "strong", "text", "del"]
    assert plain(nodes) == "a b c d e"


def test_nested_inline_markup_recurses():
    nodes = parse_inline("**bold *inner* here**")
    assert kinds(nodes) == ["strong"]
    assert kinds(nodes[0]["children"]) == ["text", "em", "text"]


def test_underscores_inside_a_word_are_not_emphasis():
    nodes = parse_inline("snake_case_word and _real_ emphasis")
    assert kinds(nodes) == ["text", "em", "text"]
    assert plain([nodes[0]]) == "snake_case_word and "
    assert kinds(nodes[1]["children"]) == ["text"]


def test_unclosed_markers_survive_as_literal_text():
    assert plain(parse_inline("unclosed **bold")) == "unclosed **bold"
    assert plain(parse_inline("a `open")) == "a `open"
    assert plain(parse_inline("[not a link")) == "[not a link"


def test_backslash_escapes_markdown_punctuation_only():
    assert plain(parse_inline("a\\*b")) == "a*b"
    assert plain(parse_inline("a\\qb")) == "a\\qb"


def test_inline_code_is_opaque_and_strips_one_space_padding():
    nodes = parse_inline("`a*b*c`")
    assert nodes == [{"type": "code", "text": "a*b*c"}]
    assert parse_inline("`` a`b ``")[0]["text"] == "a`b"
    # 只有两端各一个空格才剥，且内容不能全是空格。
    assert parse_inline("`  x  `")[0]["text"] == " x "


def test_link_with_title_and_angle_bracket_target():
    link = parse_inline('[x](http://a.b "T")')[0]
    assert link["type"] == "link"
    assert link["href"] == "http://a.b"
    assert link["title"] == "T"
    assert parse_inline("[x](<http://a.b/c d>)")[0]["href"] == "http://a.b/c d"


def test_link_label_may_contain_inline_markup():
    link = parse_inline("[**b**](u)")[0]
    assert kinds(link["children"]) == ["strong"]


def test_image_keeps_src_and_flattens_alt():
    image = parse_inline("![a **b**](s.png)")[0]
    assert image["type"] == "image"
    assert image["src"] == "s.png"
    assert image["alt"] == "a b"


def test_autolinks_for_urls_and_addresses():
    nodes = parse_inline("<https://z.z> <a@b.cc>")
    assert nodes[0] == {"type": "autolink", "href": "https://z.z"}
    assert nodes[2] == {"type": "autolink", "href": "mailto:a@b.cc"}


def test_a_bare_angle_bracket_that_is_not_a_link_stays_text():
    assert plain(parse_inline("<not a link>")) == "<not a link>"


def test_two_trailing_spaces_are_a_hard_break():
    assert kinds(parse_inline("a  \nb")) == ["text", "br", "text"]
    # 一个空格不是硬换行，软换行作为文本保留。
    assert kinds(parse_inline("a \nb")) == ["text"]


# ── 与界面无关的保证 ─────────────────────────────────────────────────────
def test_parse_results_are_json_serialisable():
    """解析结果是纯数据（界面层/跨进程都按 dict 消费）。"""
    blocks = parse_markdown("# h\n\n> q\n\n| a |\n| - |\n| 1 |")
    assert json.loads(json.dumps(blocks)) == blocks


def test_every_block_and_item_carries_a_source_line():
    blocks = parse_markdown("# h\n\npara\n\n- item\n\n```\ncode\n```")
    for block in blocks:
        assert isinstance(block["line"], int)
        for item in block.get("items", []):
            assert isinstance(item["line"], int)
