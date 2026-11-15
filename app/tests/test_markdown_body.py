"""``markdown.body``：可复用的正文文档对象（渲染 + 高亮 + 主题 + 宽度）。

这里锁的是状态机的行为，不是排版细节（排版在 ``test_markdown_document``）：

- 设置正文 → 文档内容跟着变；纯文本与 Markdown 走不同渲染器；
- 换主题/倍率 → 重新渲染，颜色与字号真的变了，控件实例不变；
- 宽度变化只有超过 ``WIDTH_EPSILON`` 才重排，并且 ``set_width`` 的返回值说实话；
- ``attach`` 把内容重绘进 QML 的 ``QQuickTextDocument``（这里用等价的桩对象），
  ``detach`` 能回到自己的文档；``dispose`` 之后高亮器不再被引用。
"""
from __future__ import annotations

import pytest

QtGui = pytest.importorskip("PySide6.QtGui", reason="正文文档需要真实 Qt binding")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application


from markdown.body import WIDTH_EPSILON, BodyDocument, palettes  # noqa: E402
from markdown.document import DARK, LIGHT, BodyStyle  # noqa: E402
from markdown.highlight import DARK_TOKENS, LIGHT_TOKENS  # noqa: E402

QTextDocument = QtGui.QTextDocument


class QuickDocumentStub:
    """``QQuickTextDocument`` 的最小替身：只暴露 ``textDocument()``。

    真实的 ``QQuickTextDocument`` 只能从 QML 构造（构造函数要求一个 ``QQuickItem``），
    而 ``BodyDocument.attach`` 只用到 ``textDocument()`` 这一个方法——用桩对象测
    这条契约，才不会把 QML 环境拖进单测。
    """

    def __init__(self) -> None:
        self.document = QTextDocument()

    def textDocument(self) -> QTextDocument:  # noqa: N802 - Qt 命名
        return self.document


def first_fragment(document):
    block = document.begin()
    assert block.isValid()
    iterator = block.begin()
    fragment = iterator.fragment()
    assert fragment.isValid()
    return fragment


# ── 渲染 ─────────────────────────────────────────────────────────────────
def test_set_markdown_renders_into_the_owned_document(qapp):
    body = BodyDocument()
    body.set_markdown("# 标题\n\n段落 **粗**")
    assert body.source == "# 标题\n\n段落 **粗**"
    assert body.document.toPlainText() == "标题\n段落 粗"
    assert first_fragment(body.document).charFormat().font().pixelSize() == 21


def test_set_plain_text_does_not_parse_markdown(qapp):
    body = BodyDocument()
    body.set_plain_text("# 不是标题\n`不是代码`")
    assert body.document.toPlainText() == "# 不是标题\n`不是代码`"
    assert body.document.blockCount() == 1


def test_setting_a_new_source_replaces_the_old_one(qapp):
    body = BodyDocument()
    body.set_markdown("# one\n\nbody")
    body.set_markdown("second")
    assert body.document.toPlainText() == "second"
    assert body.document.blockCount() == 1


def test_the_highlighter_is_owned_so_it_survives_garbage_collection(qapp):
    body = BodyDocument()
    body.set_markdown("```python\nif x: pass\n```")
    assert body.highlighter is not None
    assert body.highlighter.document() is body.document
    # 渲染后高亮器已经跑过：代码行在 layout 里有颜色格式。
    block = body.document.begin()
    seen = False
    while block.isValid():
        if block.text() == "if x: pass":
            seen = any(
                block.text()[fmt.start:fmt.start + fmt.length] == "if"
                for fmt in block.layout().formats()
            )
        block = block.next()
    assert seen is True


def test_highlight_can_be_turned_off(qapp):
    body = BodyDocument(highlight=False)
    body.set_markdown("```python\nif x: pass\n```")
    assert body.highlighter is None
    block = body.document.begin()
    while block.isValid() and block.text() != "if x: pass":
        block = block.next()
    assert block.layout().formats() == []


# ── 主题与倍率 ───────────────────────────────────────────────────────────
def test_theme_switch_repaints_without_replacing_the_document(qapp):
    body = BodyDocument()
    body.set_markdown("text")
    owned = body.document
    assert first_fragment(owned).charFormat().foreground().color().name() == LIGHT.fg
    body.set_theme(True)
    assert body.document is owned
    assert first_fragment(owned).charFormat().foreground().color().name() == DARK.fg
    assert body.palette is DARK
    body.set_theme(False)
    assert body.palette is LIGHT


def test_theme_switch_also_repaints_the_highlighter(qapp):
    body = BodyDocument()
    body.set_markdown("```python\nif x: pass\n```")
    body.set_theme(True)
    block = body.document.begin()
    while block.isValid() and block.text() != "if x: pass":
        block = block.next()
    colours = {block.text()[f.start:f.start + f.length]: f.format.foreground().color().name()
               for f in block.layout().formats()}
    assert colours["if"] == DARK_TOKENS["keyword"]


def test_scale_change_rerenders_in_the_new_size(qapp):
    body = BodyDocument()
    body.set_markdown("text")
    body.set_scale(2.0)
    assert body.style.scale == 2.0
    assert first_fragment(body.document).charFormat().font().pixelSize() == 28
    with pytest.raises(ValueError):
        body.set_scale(0)


def test_set_style_keeps_scale_theme_and_families(qapp):
    body = BodyDocument()
    body.set_style(BodyStyle(scale=1.25, dark=True, sans="Noto Sans", mono="Cascadia Code"))
    assert body.style.scale == 1.25
    assert body.style.dark is True
    assert body.style.sans == "Noto Sans"
    # 未给的字段取默认值，不会被前一次样式悄悄继承。
    assert body.style.mono == "Cascadia Code"


# ── 宽度 ─────────────────────────────────────────────────────────────────
def test_width_change_below_the_epsilon_does_not_rerender(qapp):
    body = BodyDocument(content_width=500.0)
    body.set_markdown("text")
    assert body.set_width(500.5) is False
    assert body.set_width(501.0) is False
    assert body.content_width == 501.0
    assert body.set_width(600.0) is True
    assert body.content_width == 600.0


def test_width_change_recomputes_the_code_block_width(qapp):
    body = BodyDocument(content_width=600.0)
    body.set_markdown("```\nx\n```")
    tables = []
    block = body.document.begin()
    while block.isValid():
        table = QtGui.QTextCursor(block).currentTable()
        if table is not None:
            tables.append(table)
        block = block.next()
    assert tables and tables[0].format().width().rawValue() == 576.0
    body.set_width(440.0)
    block = body.document.begin()
    table = None
    while block.isValid():
        found = QtGui.QTextCursor(block).currentTable()
        if found is not None:
            table = found
            break
        block = block.next()
    assert table is not None and table.format().width().rawValue() == 440.0 - 24.0


def test_non_positive_width_is_ignored(qapp):
    body = BodyDocument()
    assert body.set_width(0) is False
    assert body.set_width(-10) is False


def test_epsilon_is_a_two_pixel_threshold():
    assert WIDTH_EPSILON == 2.0


# ── QML 接管 ─────────────────────────────────────────────────────────────
def test_attach_renders_into_the_qml_document_and_moves_the_highlighter(qapp):
    body = BodyDocument()
    body.set_markdown("```python\nif x: pass\n```")
    quick = QuickDocumentStub()
    target = body.attach(quick)
    assert target is quick.document
    # 有语言标签的代码块是两行表格（语言头 + 代码），纯文本会多出表头与空行。
    assert "if x: pass" in target.toPlainText()
    assert "python" in target.toPlainText()
    assert body.highlighter.document() is target
    block = target.begin()
    while block.isValid() and block.text() != "if x: pass":
        block = block.next()
    assert {block.text()[f.start:f.start + f.length]: f.format.foreground().color().name()
            for f in block.layout().formats()}["if"] == LIGHT_TOKENS["keyword"]


def test_detach_returns_the_highlighter_to_the_owned_document(qapp):
    body = BodyDocument()
    body.set_markdown("text")
    quick = QuickDocumentStub()
    body.attach(quick)
    body.detach()
    assert body.highlighter.document() is body.document
    assert body.document.toPlainText() == "text"


def test_dispose_drops_the_highlighter_and_clears_the_document(qapp):
    body = BodyDocument()
    body.set_markdown("text")
    body.dispose()
    assert body.highlighter is None
    assert body.document.toPlainText() == ""


def test_palettes_returns_the_light_and_dark_pair():
    light, dark = palettes()
    assert light is LIGHT
    assert dark is DARK
    assert light is not dark
