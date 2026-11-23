"""``markdown.document``：把解析树写进 ``QTextDocument`` 的渲染器。

断言的是**文档里真实存在的格式与结构**（块格式、字符格式、表格/框架的几何），
不是「调用了哪个函数」。所以这些用例同时是排版规则的回归锁：改渲染器而排版
变了，这里会红。

两条来自实测的硬约束（见 ``document.py`` 顶部注释与 out/qml-body/ 的证据）：

1. **块级格式没有边框接口**，引用竖线只能是表格单元格背景；
2. **QML 的 ``TextEdit`` 渲染 ``border>0`` 的 ``QTextFrame`` 会段错误**（退出码
   139），所以整篇文档里不允许出现带边框的框架——``test_no_rendered_frame_has_a_border``
   对「所有元素都出现」的文档逐框架检查，防止有人为了画线又改回边框。
"""
from __future__ import annotations

import pytest

QtGui = pytest.importorskip("PySide6.QtGui", reason="正文层需要真实 Qt binding")


@pytest.fixture(scope="module")
def qapp():
    """QTextDocument 的字体度量需要 QGuiApplication；用 QApplication 兼容控件测试。"""
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application


import markdown.document as document_module  # noqa: E402
from markdown.document import (  # noqa: E402
    BodyPalette,
    BodyStyle,
    DARK,
    LIGHT,
    _Renderer,
    _font_for,
    _line_spacing,
    css_color,
    render_markdown,
    render_plain_text,
)

QTextDocument = QtGui.QTextDocument
QTextFrame = QtGui.QTextFrame
QTextTable = QtGui.QTextTable
QTextTableCellFormat = QtGui.QTextTableCellFormat


# ── 工具 ─────────────────────────────────────────────────────────────────
def render(markdown_text: str, style=None, width=600.0, resolver=None):
    document = QTextDocument()
    render_markdown(
        document,
        markdown_text,
        style or BodyStyle(),
        content_width=width,
        image_resolver=resolver,
    )
    return document


def blocks(document):
    """文档里的每个块（含表格单元格里的块），按出现顺序。"""
    out = []
    block = document.begin()
    while block.isValid():
        out.append(block)
        block = block.next()
    return out


def block_texts(document):
    return [block.text() for block in blocks(document)]


def tables(document):
    """文档里出现过的所有表格（去重，按出现顺序），含嵌套表格。"""
    found = []
    for block in blocks(document):
        table = QtGui.QTextCursor(block).currentTable()
        if table is not None and all(id(table) != id(seen) for seen in found):
            found.append(table)
    return found


def frames(document):
    """根框架下的子框架（表格也是框架）。"""
    return list(document.rootFrame().childFrames())


def first_fragment(block):
    return block.begin().fragment()


def cell_format(cell):
    return QTextTableCellFormat(cell.format())


def find_block(document, text):
    for block in blocks(document):
        if block.text() == text:
            return block
    raise AssertionError("no block with text %r in %r" % (text, block_texts(document)))


# ── 文档骨架 ─────────────────────────────────────────────────────────────
def test_an_empty_source_leaves_one_empty_block(qapp):
    document = render("")
    assert document.blockCount() == 1
    assert document.toPlainText() == ""
    assert frames(document) == []


def test_render_clears_the_previous_content(qapp):
    document = render("# first\n\nbody")
    render_markdown(document, "second", BodyStyle())
    assert document.toPlainText() == "second"
    assert document.blockCount() == 1


def test_document_margin_is_zero_so_padding_is_ours(qapp):
    """外边距由视图给（QML 的 padding），文档自己不额外缩进。"""
    assert render("text").documentMargin() == 0.0


def test_first_top_and_last_bottom_margin_collapse(qapp):
    """.md > :first-child / :last-child 的等价物。"""
    document = render("a\n\nb")
    assert document.begin().blockFormat().topMargin() == 0.0
    assert document.lastBlock().blockFormat().bottomMargin() == 0.0
    # 中间块的间距不受影响。
    assert document.begin().blockFormat().bottomMargin() > 0.0


# ── 标题 ─────────────────────────────────────────────────────────────────
@pytest.mark.parametrize(
    "markdown_text,level,size_px",
    [
        ("# h", 1, 21),
        ("## h", 2, 18),
        ("### h", 3, 16),
        ("#### h", 4, 14),
        ("##### h", 5, 13),
        ("###### h", 6, 13),
    ],
)
def test_heading_sizes_follow_the_scale_table(qapp, markdown_text, level, size_px):
    document = render(markdown_text + "\n\ntail")
    fragment = first_fragment(document.begin())
    assert document.begin().text() == "h"
    assert fragment.charFormat().font().pixelSize() == size_px
    assert fragment.charFormat().font().bold() is True


def test_deep_headings_use_the_muted_foreground(qapp):
    """原版 h5/h6 是 --fg-muted，与 h1–h4 的 --fg 不同。"""
    document = render("##### h5\n\n# h1")
    assert first_fragment(find_block(document, "h5")).charFormat().foreground().color().name() == LIGHT.fg_muted
    assert first_fragment(find_block(document, "h1")).charFormat().foreground().color().name() == LIGHT.fg


def test_headings_get_16px_top_margin_but_the_first_one_is_flattened(qapp):
    document = render("# first\n\n## second\n\ntail")
    second = find_block(document, "second")
    assert second.blockFormat().topMargin() == 16.0


def test_h2_gets_a_one_pixel_hairline_after_it(qapp):
    document = render("## h2\n\ntail")
    lines = [frame for frame in frames(document) if not isinstance(frame, QTextTable)]
    assert len(lines) == 1
    height = lines[0].frameFormat().height()
    assert height.type() == QtGui.QTextLength.Type.FixedLength
    assert height.rawValue() == 1.0
    assert lines[0].frameFormat().background().color().name() == LIGHT.border


def test_horizontal_rule_is_a_one_pixel_frame_with_spacing_on_the_neighbours(qapp):
    document = render("before\n\n---\n\nafter")
    lines = [frame for frame in frames(document) if not isinstance(frame, QTextTable)]
    assert len(lines) == 1
    assert lines[0].frameFormat().height().rawValue() == 1.0
    # 间距写在相邻块上：frame 自己的 margin 会被背景一起涂成色带。
    assert find_block(document, "before").blockFormat().bottomMargin() == 16.0 + 12.0
    assert find_block(document, "after").blockFormat().topMargin() == 16.0


# ── 行内格式 ─────────────────────────────────────────────────────────────
def test_paragraph_text_and_soft_breaks_use_line_separator(qapp):
    document = render("first\nsecond\n\nthird")
    assert block_texts(document) == ["first second", "third"]


def test_strong_em_and_strikethrough_map_to_font_flags(qapp):
    document = render("a **bold** *em* ~~gone~~")
    weights = {}
    block = document.begin()
    iterator = block.begin()
    while not iterator.atEnd():
        fragment = iterator.fragment()
        if fragment.isValid():
            weights[fragment.text()] = fragment.charFormat()
        iterator += 1
    assert weights["bold"].fontWeight() == QtGui.QFont.Weight.DemiBold
    assert weights["em"].fontItalic() is True
    assert weights["gone"].fontStrikeOut() is True
    assert weights["gone"].foreground().color().name() == LIGHT.fg_subtle


def test_inline_code_switches_to_the_mono_family_and_inset_background(qapp):
    document = render("text `inline` tail")
    block = document.begin()
    iterator = block.begin()
    formats = []
    while not iterator.atEnd():
        fragment = iterator.fragment()
        if fragment.isValid():
            formats.append((fragment.text(), fragment.charFormat()))
        iterator += 1
    code_text, code = [(text, fmt) for text, fmt in formats if "inline" in text][0]
    # Qt 的字符格式没有 CSS padding：左右各用一个 U+2002 EN SPACE 模拟
    # ``.md-code`` 的 5px 内边距，视觉宽度与 deva 一致。
    assert code_text == "\u2002inline\u2002"
    assert code.font().families()[0] == "Cascadia Code"
    assert code.font().pixelSize() == 12  # 14 * 0.88 取整
    assert code.background().color().name() == LIGHT.bg_inset


def test_links_become_real_anchors_with_the_accent_colour(qapp):
    document = render("[label](https://example.com/x)")
    char_format = first_fragment(document.begin()).charFormat()
    assert char_format.isAnchor() is True
    assert char_format.anchorHref() == "https://example.com/x"
    assert char_format.foreground().color().name() == LIGHT.accent


def test_autolinks_show_the_url_itself(qapp):
    document = render("<https://example.com>")
    assert document.begin().text() == "https://example.com"
    assert first_fragment(document.begin()).charFormat().anchorHref() == "https://example.com"


def test_hard_break_becomes_a_line_separator(qapp):
    assert render("a  \nb").begin().text() == "a b"


# ── 列表 ─────────────────────────────────────────────────────────────────
def test_unordered_items_use_a_hanging_indent_and_a_bullet(qapp):
    document = render("- a\n- b")
    texts = block_texts(document)
    assert texts == ["\t•\ta", "\t•\tb"]
    fmt = document.begin().blockFormat()
    assert fmt.leftMargin() == 21.0
    assert fmt.textIndent() == -21.0


def test_ordered_items_number_from_the_source_start(qapp):
    document = render("3. c\n4. d")
    assert block_texts(document) == ["\t3.\tc", "\t4.\td"]


def test_task_items_use_checkbox_glyphs(qapp):
    document = render("- [ ] todo\n- [x] done")
    assert block_texts(document) == ["\t☐\ttodo", "\t☑\tdone"]


def test_nested_list_indents_by_the_parents_marker_column(qapp):
    document = render("- outer\n  - inner")
    inner = find_block(document, "\t•\tinner")
    assert inner.blockFormat().leftMargin() == 42.0


def test_list_markers_are_subtle_coloured(qapp):
    document = render("- a")
    block = document.begin()
    iterator = block.begin()
    first = iterator.fragment()
    assert first.charFormat().foreground().color().name() == LIGHT.fg_subtle


# ── 引用 ─────────────────────────────────────────────────────────────────
def test_quote_is_a_two_column_table_with_a_filled_bar(qapp):
    document = render("> quoted")
    found = tables(document)
    assert len(found) == 1
    table = found[0]
    assert (table.rows(), table.columns()) == (1, 2)
    widths = table.format().columnWidthConstraints()
    assert widths[0].type() == QtGui.QTextLength.Type.FixedLength
    assert widths[0].rawValue() == 3.0
    assert table.format().width().type() == QtGui.QTextLength.Type.PercentageLength
    assert cell_format(table.cellAt(0, 0)).background().color().name() == LIGHT.border_strong
    assert cell_format(table.cellAt(0, 1)).leftPadding() == 12.0


def test_quote_body_text_uses_the_muted_foreground(qapp):
    document = render("> quoted")
    block = find_block(document, "quoted")
    assert first_fragment(block).charFormat().foreground().color().name() == LIGHT.fg_muted


def test_nested_quote_is_a_table_inside_the_body_cell(qapp):
    document = render("> outer\n>\n> > inner")
    found = tables(document)
    assert len(found) == 2
    outer, inner = found
    assert outer.cellAt(0, 1).firstCursorPosition().block().text() == "outer"
    # 内层引用落在内层表格的正文列里。
    assert inner.cellAt(0, 1).firstCursorPosition().block().text() == "inner"


def test_a_quote_holds_multiple_blocks_in_one_cell(qapp):
    document = render("> first\n>\n> second")
    found = tables(document)
    assert len(found) == 1
    text = found[0].cellAt(0, 1).firstCursorPosition()
    a = text.block().text()
    b = text.block().next().text() if text.block().next().isValid() else ""
    assert (a, b) == ("first", "second")


# ── 表格 ─────────────────────────────────────────────────────────────────
def test_table_header_is_panel_coloured_and_bold(qapp):
    document = render("| a | b |\n| - | - |\n| 1 | 2 |")
    table = tables(document)[0]
    assert (table.rows(), table.columns()) == (2, 2)
    header = cell_format(table.cellAt(0, 0))
    assert header.background().color().name() == LIGHT.bg_panel
    assert first_fragment(table.cellAt(0, 0).firstCursorPosition().block()).charFormat().font().bold() is True


def test_table_body_text_is_not_bold_while_the_header_is(qapp):
    """表头与正文共用一份缓存的字符格式时，键必须区分表头：正文不能继承粗体。"""
    document = render("| 头 | b |\n| - | - |\n| 正文 | 2 |")
    table = tables(document)[0]
    header_font = first_fragment(
        table.cellAt(0, 0).firstCursorPosition().block()).charFormat().font()
    body_font = first_fragment(
        table.cellAt(1, 0).firstCursorPosition().block()).charFormat().font()
    assert header_font.bold() is True
    assert body_font.bold() is False


def test_table_cells_use_text_indent_and_fixed_row_height(qapp):
    """CSS 的 10×6 padding 由块格式实现，保证 QML 背景铺满整格。

    QQuickTextEdit 只画块背景、不画单元格背景；因此单元格 padding 归零，
    左右 10px 改用 textIndent，行高用 34.45px（13×1.65 + 12 + 1）固定。
    """
    document = render("| a |\n| - |\n| 1 |")
    cell = cell_format(tables(document)[0].cellAt(1, 0))
    assert (cell.leftPadding(), cell.rightPadding()) == (0.0, 0.0)
    assert (cell.topPadding(), cell.bottomPadding()) == (0.0, 0.0)
    block = tables(document)[0].cellAt(1, 0).firstCursorPosition().blockFormat()
    # Qt 的块背景只覆盖行框，不覆盖块边距；10px 左内边距改用 textIndent，
    # 行高由单元格内一个全透明的 23px 零宽字符撑到约 34px 后再留 1px 边框。
    assert (block.leftMargin(), block.rightMargin()) == (0.0, 0.0)
    assert block.textIndent() == 10.0
    assert block.lineHeightType() == QtGui.QTextBlockFormat.LineHeightTypes.FixedHeight.value
    assert block.lineHeight() == 34.45


def test_every_cell_draws_its_own_one_pixel_border(qapp):
    document = render("| a |\n| - |\n| 1 |")
    cell = cell_format(tables(document)[0].cellAt(0, 0))
    for edge in (cell.leftBorder(), cell.rightBorder(), cell.topBorder(), cell.bottomBorder()):
        assert edge == 1.0


def test_alignment_marker_is_applied_per_cell(qapp):
    document = render("| l | c | r |\n|:--|:-:|--:|\n| 1 | 2 | 3 |")
    table = tables(document)[0]
    alignments = [table.cellAt(1, column).firstCursorPosition().blockFormat().alignment()
                  for column in range(3)]
    assert alignments == [
        QtGui.QTextCursor(document).blockFormat().alignment().__class__.AlignLeft,
        QtGui.QTextCursor(document).blockFormat().alignment().__class__.AlignHCenter,
        QtGui.QTextCursor(document).blockFormat().alignment().__class__.AlignRight,
    ]


def test_even_rows_carry_the_hover_background(qapp):
    document = render("| a |\n| - |\n| 1 |\n| 2 |\n| 3 |")
    table = tables(document)[0]
    # row 0 表头、row 1 奇、row 2 偶（带背景）、row 3 奇。
    assert cell_format(table.cellAt(2, 0)).background().style() != QtGui.Qt.BrushStyle.NoBrush
    assert cell_format(table.cellAt(3, 0)).background().style() == QtGui.Qt.BrushStyle.NoBrush


# ── 代码块 ───────────────────────────────────────────────────────────────
def test_code_block_is_a_table_with_a_language_head(qapp):
    document = render("```python\nx = 1\n\ny = 2\n```")
    table = tables(document)[0]
    assert table.rows() == 2
    assert table.cellAt(0, 0).firstCursorPosition().block().text() == "python"
    assert cell_format(table.cellAt(0, 0)).background().color().name() == LIGHT.code_head_bg
    assert cell_format(table.cellAt(1, 0)).background().color().name() == LIGHT.code_bg


def test_code_without_a_language_has_no_head_row(qapp):
    document = render("```\nx\n```")
    assert tables(document)[0].rows() == 1


def test_code_lines_are_not_wrapped_and_record_the_language(qapp):
    document = render("```python\nshort\nlong line\n```")
    code_blocks = [block for block in blocks(document)
                   if block.blockFormat().property(document_module.CODE_LANGUAGE_PROPERTY) == "python"]
    assert [block.text() for block in code_blocks] == ["short", "long line"]
    assert all(block.blockFormat().nonBreakableLines() for block in code_blocks)
    assert all(block.blockFormat().leftMargin() == 12.0 for block in code_blocks)


def test_code_block_fills_the_content_width_when_it_is_short(qapp):
    document = render("```\nx\n```", width=600.0)
    table = tables(document)[0]
    assert table.format().width().type() == QtGui.QTextLength.Type.FixedLength
    assert table.format().width().rawValue() == 598.0  # 600 - 2px 外框


def test_code_block_grows_to_the_longest_line(qapp):
    document = render("```\n" + "y" * 250 + "\n```", width=600.0)
    table = tables(document)[0]
    assert table.format().width().rawValue() > 600.0


def test_code_body_is_12px_mono_on_both_sides(qapp):
    document = render("```\nx\n```")
    block = find_block(document, "x")
    assert block.blockFormat().leftMargin() == 12.0
    assert block.blockFormat().rightMargin() == 12.0
    char_format = first_fragment(block).charFormat()
    assert char_format.font().pixelSize() == 12  # 12.5 四舍六入到偶数
    assert char_format.font().families()[0] == "Cascadia Code"


# ── 图片与占位 ───────────────────────────────────────────────────────────
def test_missing_image_renders_an_explicit_placeholder(qapp):
    document = render("![说明](missing.png)")
    assert document.toPlainText() == "［图片：说明］"
    assert first_fragment(document.begin()).charFormat().foreground().color().name() == LIGHT.fg_subtle


def test_resolved_image_is_inserted_at_its_natural_size(qapp):
    image = QtGui.QImage(40, 20, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor("#ff0000"))
    document = render("![p](a.png)", resolver=lambda src: image)
    char_format = first_fragment(document.begin()).charFormat()
    assert char_format.isImageFormat() is True
    image_format = char_format.toImageFormat()
    assert (image_format.width(), image_format.height()) == (40.0, 20.0)


def test_wide_image_is_clamped_to_the_content_width(qapp):
    image = QtGui.QImage(2000, 1000, QtGui.QImage.Format.Format_ARGB32)
    image.fill(QtGui.QColor("#ff0000"))
    document = render("![p](a.png)", width=500.0, resolver=lambda src: image)
    image_format = first_fragment(document.begin()).charFormat().toImageFormat()
    assert image_format.width() == 500.0
    assert image_format.height() == 250.0


# ── 纯文本渲染（用户消息）────────────────────────────────────────────────
def test_plain_text_renderer_keeps_newlines_without_markdown(qapp):
    document = QTextDocument()
    render_plain_text(document, "# not a heading\n`not code`")
    assert document.blockCount() == 1
    # 文档内部用 U+2028（块内换行），toPlainText 把它投影回 "\n"。
    assert document.toPlainText() == "# not a heading\n`not code`"
    assert chr(0x2028) in document.begin().text()


# ── 主题与倍率 ───────────────────────────────────────────────────────────
def test_dark_theme_only_changes_colours(qapp):
    light = render("text\n\n```\nx\n```")
    dark = render("text\n\n```\nx\n```", style=BodyStyle(dark=True))
    assert first_fragment(light.begin()).charFormat().foreground().color().name() == LIGHT.fg
    assert first_fragment(dark.begin()).charFormat().foreground().color().name() == DARK.fg
    # 结构不变：深色下代码块照样是「语言头 + 正文」两行（这里没有语言，1 行）。
    assert len(tables(light)) == len(tables(dark)) == 1
    assert cell_format(tables(dark)[0].cellAt(0, 0)).background().color().name() == DARK.code_bg


def test_text_scale_multiplies_the_base_size(qapp):
    document = render("text", style=BodyStyle(scale=2.0))
    assert first_fragment(document.begin()).charFormat().font().pixelSize() == 28


def test_body_style_derives_the_palette_from_dark_flag():
    assert BodyStyle().palette is LIGHT
    assert BodyStyle(dark=True).palette is DARK
    assert BodyStyle(scale=1.25).base_px == pytest.approx(17.5)
    assert isinstance(LIGHT, BodyPalette)


def test_css_colours_parse_hex_rgba_and_fall_back_to_black():
    assert css_color("#ff0000").name() == "#ff0000"
    assert css_color("#abc").name() == "#aabbcc"
    assert css_color("rgba(0, 0, 255, 0.5)").getRgb() == (0, 0, 255, 128)
    assert css_color("not-a-colour").name() == "#000000"
    assert css_color("").name() == "#000000"


def test_css_colour_cache_does_not_change_what_callers_get(qapp):
    """``css_color`` 带缓存：同一输入两次必须给出等价颜色，且不串色。"""
    first = css_color("#123456")
    second = css_color("#123456")
    assert first == second
    assert second.getRgb() == (0x12, 0x34, 0x56, 255)
    assert css_color("#654321").getRgb() == (0x65, 0x43, 0x21, 255)
    assert css_color("#123456").getRgb() == (0x12, 0x34, 0x56, 255)


def test_css_colour_is_memoised_per_source_string(qapp):
    """缓存键是原字符串：重复取命中、不同取不命中（命中就是这份优化的全部收益）。"""
    css_color.cache_clear()
    css_color("#abcdef")
    css_color("#abcdef")
    info = css_color.cache_info()
    assert info.misses == 1 and info.hits == 1
    css_color("#fedcba")
    assert css_color.cache_info().misses == 2


def test_renderer_font_and_line_height_are_stable_across_calls(qapp):
    """字体与行高按「族 + 像素 + 粗 + 等宽 + 斜」/「族 + 像素」缓存，值必须不变。"""
    renderer = _Renderer(QtGui.QTextDocument(), BodyStyle(), 676.0, None)
    font = renderer.font(14.0, bold=True, mono=True, italic=True)
    assert renderer.font(14.0, bold=True, mono=True, italic=True) == font
    assert font.pixelSize() == 14 and font.bold() and font.italic()
    assert font.families() == list(BodyStyle().mono)
    # 不同键不能撞到同一个值
    assert renderer.font(14.0).pixelSize() == 14
    assert renderer.font(14.0).bold() is False
    assert renderer.font(28.0).pixelSize() == 28
    assert renderer.line_height(14.0, 1.65) == renderer.line_height(14.0, 1.65)

    # ``line_height`` 返回的是**百分比**（``ProportionalHeight`` 相对字体行距），
    # 不是像素。契约是 ``spacing * pct / 100 == px * factor``；而字体行距与字号
    # 成正比，所以 14px 与 28px 的百分比本来就该几乎相同（实测都是 113.986…，
    # 见 out/final-close/logs/19-line-height-rootcause.log）。旧断言用
    # ``pct(28) != pct(14)`` 当「不同键不撞值」的锁，锁错了量纲——它在字体行距
    # 严格线性的机器上必然红，是断言缺陷而非渲染回归。缓存键的真正覆盖由下面的
    # ``test_font_and_line_height_caches_are_keyed_on_their_inputs`` 用 cache_info 锁住。
    # 这里改锁值本身：百分比必须满足 ``spacing * pct / 100 == px * factor``，
    # 且必须随字号单调（同一倍率下 28px 的目标像素就是 14px 的两倍）。
    pixels = {}
    for px in (14.0, 28.0, 56.0):
        pct = renderer.line_height(px, 1.65)
        font = QtGui.QFont()
        font.setFamilies(list(BodyStyle().sans))
        font.setPixelSize(int(px))
        spacing = QtGui.QFontMetricsF(font).lineSpacing()
        assert spacing > 0
        got = spacing * pct / 100.0
        assert got == pytest.approx(px * 1.65, rel=1e-9), (px, got)
        pixels[px] = got
    assert pixels[28.0] == pytest.approx(2 * pixels[14.0], rel=1e-9)
    assert pixels[56.0] == pytest.approx(4 * pixels[14.0], rel=1e-9)
    # 倍率是公式里的真实因子：不同倍率不能给出同一个百分比。
    assert renderer.line_height(14.0, 1.65) != renderer.line_height(14.0, 2.0)


def test_font_and_line_height_caches_are_keyed_on_their_inputs(qapp):
    """缓存键必须包含决定结果的每一项：键不全会把不同字号/字重串成同一个值。"""
    renderer = _Renderer(QtGui.QTextDocument(), BodyStyle(), 676.0, None)
    _font_for.cache_clear()
    renderer.font(14.0, bold=True)
    renderer.font(14.0, bold=True)
    renderer.font(14.0, bold=False)   # 只有粗体不同：必须是新键
    renderer.font(14.0, mono=True)    # 只有等宽不同：必须是新键
    renderer.font(28.0, bold=True)    # 只有字号不同：必须是新键
    info = _font_for.cache_info()
    assert info.hits == 1 and info.misses == 4

    _line_spacing.cache_clear()
    renderer.line_height(14.0, 1.65)
    renderer.line_height(14.0, 1.65)
    renderer.line_height(28.0, 1.65)  # 只有字号不同：必须是新键
    info = _line_spacing.cache_info()
    assert info.hits == 1 and info.misses == 2


# ── 段错误守卫 ───────────────────────────────────────────────────────────
SEGFAULT_MARKDOWN = """# 标题

段落 **粗体** *斜体* ~~删除~~ `行内` [链接](https://e.x) <https://a.b>

## 二级

> 引用
>
> > 嵌套

| 列 | 列 |
|:--|--:|
| 1 | 2 |

```python
def f():
    return 1
```

- 列表
  1. 嵌套

- [x] 任务

---

![图](missing.png)
"""


def test_no_rendered_frame_has_a_border(qapp):
    """QML 的 TextEdit 渲染 ``border>0`` 的 QTextFrame 会段错误（退出码 139）。

    ``QTextFrameFormat`` 的边框在 ``QQuickTextEdit`` 里走到的绘制路径会崩，
    ``QTextTable`` 不会。所以整篇文档（含每个元素）里都不许出现带边框的框架：
    线只能由「1px 固定高度 + 背景色」或表格边框/单元格背景表达。

    复现脚本与退出码见 out/qml-body/bordered_frame_segfault.py / *.log。
    """
    document = render(SEGFAULT_MARKDOWN)

    def walk(frame):
        yield frame
        for child in frame.childFrames():
            for nested in walk(child):
                yield nested

    offenders = []
    for frame in walk(document.rootFrame()):
        if isinstance(frame, QTextTable):
            # 表格走另一条绘制路径，不会段错误，而且**必须**带 1px 表格级边框：
            # QQuickTextEdit 不画单元格级边框，只画表格级边框（见下一条用例）。
            continue
        border = frame.frameFormat().border()
        if border and border > 0:
            offenders.append((type(frame).__name__, border))
    assert offenders == []


def test_table_carries_a_one_pixel_table_border_for_qml(qapp):
    """表格级 1px 边框是 QML 侧能画出网格的唯一途径。

    实测（QQuickTextEdit + grabWindow）：单元格级边框不绘制，表格级 ``setBorder(1)``
    + ``setBorderCollapse(True)`` 会画出完整 1px 网格，且合并模式下与单元格级 1px
    合并、不会叠成 2px。
    """
    document = render("| a | b |\n| --- | --- |\n| 1 | 2 |\n")
    table = tables(document)[0]
    fmt = table.format()
    assert fmt.border() == 1.0
    assert fmt.borderCollapse() is True
    assert fmt.borderBrush().color().name() == LIGHT.border


def test_a_document_with_every_construct_renders(qapp):
    """全元素文档能渲染、能取纯文本——任何一类元素把排版搞崩都会在这里暴露。"""
    document = render(SEGFAULT_MARKDOWN)
    text = document.toPlainText()
    for needle in ("标题", "引用", "嵌套", "def f():", "任务", "［图片：图］"):
        assert needle in text
    assert len(tables(document)) >= 3  # 引用 + 嵌套引用 + 表格 + 代码块


# ── 表格：一次插满所有行 + 边框与内边距同一次写入 ────────────────────────
# 这两条锁的是 `_table`/`_table_row` 的实现约束，不是排版渐变：
#
# 1. `insertTable(1, n)` + 逐行 `appendRows(1)` 的每次结构性插入都按「当前文档
#    规模」重排，400 轮正文实测 5101.1 → 2773.2 ms（交替 A/B 七次中位数，
#    `out/render-opt2/ab_alternating.log`）；换成一次插满行后必须逐行内容
#    与逐格边框都在位，否则「快」只是少写了东西。
# 2. 边框必须逐格写。实测把边框只写在表格格式上、指望单元格继承，`toHtml()`
#    与逐格写不等价（单元格格式里没有边框），QML 侧会退回无线框的表格。

TABLE_MANY_ROWS = (
    "| 列一 | 列二 |\n| --- | --- |\n"
    + "\n".join("| r%d-a | r%d-b |" % (index, index) for index in range(1, 9))
)


def test_a_table_with_many_rows_fills_every_row_and_column(qapp):
    document = render(TABLE_MANY_ROWS)
    table = tables(document)[0]
    assert (table.rows(), table.columns()) == (9, 2)
    for row in range(table.rows()):
        for column in range(table.columns()):
            expected = ("列一", "列二")[column] if row == 0 else "r%d-%s" % (row, "ab"[column])
            # 每个单元格首字符是撑行高的透明零宽字符，不属于可见文本。
            text = table.cellAt(row, column).firstCursorPosition().block().text()
            assert text.lstrip("\u200b") == expected


def test_every_cell_gets_its_own_border_brush_and_style(qapp):
    """逐格逐边写必须落实到每一格：边框宽度、画刷、样式、内边距、底色都要在。"""
    document = render(TABLE_MANY_ROWS)
    table = tables(document)[0]
    solid = QtGui.QTextFrameFormat.BorderStyle_Solid
    for row in range(table.rows()):
        for column in range(table.columns()):
            cell = cell_format(table.cellAt(row, column))
            # `QTextTableCellFormat` 没有 `border()` 读接口（它继承字符格式而非框架
            # 格式），只能逐边读；四条边都是 1px 就说明没写成「整表统一 1」——
            # 那种写法在合并模式下会让相邻边叠成 2px。
            for edge in (cell.leftBorder(), cell.rightBorder(),
                         cell.topBorder(), cell.bottomBorder()):
                assert edge == 1.0
            for brush in (cell.leftBorderBrush(), cell.rightBorderBrush(),
                          cell.topBorderBrush(), cell.bottomBorderBrush()):
                assert brush.color().name() == LIGHT.border
            for style in (cell.leftBorderStyle(), cell.rightBorderStyle(),
                          cell.topBorderStyle(), cell.bottomBorderStyle()):
                assert style == solid
            assert (cell.leftPadding(), cell.rightPadding()) == (0.0, 0.0)
            assert (cell.topPadding(), cell.bottomPadding()) == (0.0, 0.0)
            expected_bg = (
                LIGHT.bg_panel if row == 0
                else LIGHT.bg_hover if row % 2 == 0
                else None
            )
            if expected_bg:
                # `bg_hover` 是半透明 rgba，`QColor.name()` 丢掉 alpha 只留 #000000；
                # 而且渲染器是把 QColor 直接交给 `setBackground(QBrush)`，QTextDocument
                # 在单元格格式里存的是预乘过的 RGB（实测 alpha 0.045 会变成 11/255
                # 的灰度）。所以这里只断言「底色确实设了、且不是另一种主题色」，
                # 逐值比对交给保真矩阵（`out/render-opt2/probe_table_before_after.py`）。
                assert cell.background().style() != QtGui.Qt.BrushStyle.NoBrush
                if row == 0:
                    assert cell.background().color().name() == LIGHT.bg_panel
            else:
                assert cell.background().style() == QtGui.Qt.BrushStyle.NoBrush
