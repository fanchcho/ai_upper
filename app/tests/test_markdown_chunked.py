"""分块渲染（``document._render_chunked``）的保真与边界回归。

分块渲染改变了「内容怎么写进文档」的过程：每 ``_CHUNK_BLOCKS`` 个顶层块先进一份
全新的 scratch 文档，再用 ``insertFragment`` 拼起来。这里锁的是它**看不出来**：

- 与整篇渲染逐块一致（块数、字符数、每个块的格式、每个字符片的字体/颜色、
  每张表格的形状、文档总尺寸、``toHtml()`` 全等）；
- 接缝处的块格式不掉（上一分块末块格式 → 下一分块光标继承链）；
- 阈值边界两侧都对：恰好 ``_CHUNK_BLOCKS`` 个块仍走原来的整篇路径，
  多一个块才切换，两者输出相同；
- 图片资源随分块从 scratch 文档搬到最终文档（文档级资源不随片段走）。
"""
from __future__ import annotations

import pytest

QtGui = pytest.importorskip("PySide6.QtGui", reason="正文层需要真实 Qt binding")
QtCore = pytest.importorskip("PySide6.QtCore", reason="正文层需要真实 Qt binding")


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    yield application


import markdown.document as document_module  # noqa: E402
from markdown.document import BodyStyle, parse_markdown, render_markdown  # noqa: E402

QTextDocument = QtGui.QTextDocument

TURN = """## 用户

第 {n} 轮：请整理结果。

> 引用里带 **粗体** 与 `代码`
>
> > 嵌套引用

- 一级
  - 二级

| 文件 | 类型 |
| --- | --- |
| `README.md` | 文档 |
| `src/` | 目录 |

## 助手

第 {n} 轮回复。

```python
def build_report(rows):
    return sorted(rows, key=lambda r: r["total"], reverse=True)
```
"""


def source(turns: int) -> str:
    return "\n\n".join(TURN.format(n=n) for n in range(turns))


def render(markdown_text, resolver=None):
    return render_markdown(QTextDocument(), markdown_text, BodyStyle(),
                           content_width=676.0, image_resolver=resolver)


def render_whole(markdown_text, monkeypatch, resolver=None):
    """把分块阈值提到无穷大，强制走改动前的整篇路径。"""
    monkeypatch.setattr(document_module, "_CHUNK_BLOCKS", 10 ** 9)
    return render(markdown_text, resolver)


def block_signature(block):
    fmt = block.blockFormat()
    runs = tuple(
        (spec.start, spec.length, spec.format.toImageFormat().name()
         if spec.format.isImageFormat() else None,
         spec.format.font().family(), spec.format.font().pixelSize(),
         int(spec.format.font().weight()), spec.format.font().italic(),
         spec.format.foreground().color().name() if spec.format.foreground().style() else None,
         spec.format.background().color().name() if spec.format.background().style() else None)
        for spec in block.textFormats()
    )
    return (
        block.text(),
        (round(fmt.topMargin(), 4), round(fmt.bottomMargin(), 4),
         round(fmt.leftMargin(), 4), round(fmt.rightMargin(), 4),
         round(fmt.textIndent(), 4), round(fmt.lineHeight(), 4), fmt.alignment(),
         tuple(round(tab.position, 4) for tab in fmt.tabPositions())),
        runs,
    )


def signatures(document):
    out, block = [], document.begin()
    while block.isValid():
        out.append(block_signature(block))
        block = block.next()
    return out


def table_shapes(document):
    found, stack = [], [document.rootFrame()]
    while stack:
        frame = stack.pop()
        if isinstance(frame, QtGui.QTextTable):
            found.append((frame.rows(), frame.columns(),
                          round(frame.format().width().rawValue(), 3),
                          frame.format().border(), frame.format().cellSpacing()))
        it = frame.begin()
        while not it.atEnd():
            child = it.currentFrame()
            if child is not None:
                stack.append(child)
            it += 1
    return found


def laid_out(document):
    document.setTextWidth(696.0)
    document.documentLayout()
    return document


# ── 保真 ─────────────────────────────────────────────────────────────────
CHUNK = document_module._CHUNK_BLOCKS


def force_group(monkeypatch, group):
    """让 ``_chunk_plan`` 固定返回 ``group``，从而按指定分组驱动分块路径。

    分块大小现在由 ``_chunk_plan`` 按结构密度算（见 ``test_chunk_plan_*``），
    所以这里直接替换计划函数，而不是改 ``_CHUNK_BLOCKS``——后者现在是
    「整篇/分块」的规模门槛，不再决定分组大小。
    """
    monkeypatch.setattr(document_module, "_chunk_plan", lambda blocks: group)


@pytest.mark.parametrize("turns", [12, 30])
@pytest.mark.parametrize("group", [5, 25, CHUNK])
def test_chunked_render_matches_the_whole_document_block_by_block(qapp, monkeypatch, turns, group):
    markdown_text = source(turns)
    assert len(parse_markdown(markdown_text)) > group  # 确实走到了分块路径

    whole = laid_out(render_whole(markdown_text, monkeypatch))
    monkeypatch.undo()
    force_group(monkeypatch, group)
    chunked = laid_out(render(markdown_text))

    assert chunked.blockCount() == whole.blockCount()
    assert chunked.characterCount() == whole.characterCount()
    assert chunked.toPlainText() == whole.toPlainText()
    assert signatures(chunked) == signatures(whole)
    assert table_shapes(chunked) == table_shapes(whole)
    assert chunked.size().height() == whole.size().height()
    assert chunked.toHtml() == whole.toHtml()


def test_the_seam_keeps_the_block_format_of_the_previous_chunk(qapp, monkeypatch):
    """分块边界处的块格式必须与整篇一致。

    ``_table``/``_quote`` 前的空块靠 ``insertBlock()`` 不成格式、继承光标当前格式；
    新分块的光标是新的，靠把上一分块末块格式写进 scratch 延续这条链。这里让分块
    边界正好落在「带左缩进的列表」与「下一轮标题」之间，逐块核对接缝两侧的格式
    （四边距、行高、左缩进、制表位），而不是只看整体签名。
    """
    group = 6
    # 每个顶层块用唯一文案，便于在成品文档里定位接缝。
    paragraphs = ["段落 %02d" % n for n in range(group)]
    first_chunk = "\n\n".join(paragraphs) + "\n\n- 列表甲\n  - 列表乙"
    second_chunk = "## 接缝后的标题\n\n接缝后的段落"
    markdown_text = first_chunk + "\n\n" + second_chunk
    top_level = len(parse_markdown(markdown_text))
    assert top_level > group  # 确实跨了接缝

    whole = render_whole(markdown_text, monkeypatch)
    monkeypatch.undo()
    monkeypatch.setattr(document_module, "_CHUNK_BLOCKS", group)
    chunked = render(markdown_text)

    assert chunked.blockCount() == whole.blockCount()
    for text in ("段落 %02d" % (group - 1), "列表乙", "接缝后的标题", "接缝后的段落"):
        assert _format_tuple(_block_by_text(chunked, text).blockFormat()) == \
               _format_tuple(_block_by_text(whole, text).blockFormat()), text


def _format_tuple(fmt):
    return (round(fmt.topMargin(), 4), round(fmt.bottomMargin(), 4),
            round(fmt.leftMargin(), 4), round(fmt.rightMargin(), 4),
            round(fmt.textIndent(), 4), round(fmt.lineHeight(), 4), fmt.alignment(),
            tuple(round(tab.position, 4) for tab in fmt.tabPositions()))


def _block_by_text(document, text):
    for block in _iter_blocks(document):
        if text in block.text():
            return block
    raise AssertionError("no block containing %r" % text)


def _iter_blocks(document):
    block = document.begin()
    while block.isValid():
        yield block
        block = block.next()


# ── 阈值边界 ─────────────────────────────────────────────────────────────
def test_the_threshold_itself_takes_the_whole_document_path(qapp, monkeypatch):
    group = document_module._CHUNK_BLOCKS
    exactly = "\n\n".join("段落 %d" % n for n in range(group))
    assert len(parse_markdown(exactly)) == group

    calls = []
    original = document_module._render_chunked

    def spy(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(document_module, "_render_chunked", spy)
    render(exactly)
    assert calls == []

    # 阈值以上、但结构密度不足的文档仍走整篇：纯段落的整篇路径本来就是线性的，
    # 分块只会多付拼接钱（2400 块实测整篇 111.8 ms、分块 148.2 ms）。
    prose = "\n\n".join("段落 %d" % n for n in range(group + 1))
    render(prose)
    assert calls == []

    # 同样的正文比例、规模够大时（结构量 × 块数过门槛）才切到分块。
    dense = "\n\n".join(("段落 %d" % n) + ("\n\n| a | b |\n| --- | --- |\n| 1 | 2 |"
                                           if n % 2 else "")
                       for n in range(400))
    assert len(parse_markdown(dense)) > group
    render(dense)
    assert len(calls) == 1


def test_one_block_past_the_threshold_renders_the_same_as_whole(qapp, monkeypatch):
    """整篇/分块两条路径在同一份正文上逐字节一致（用结构密集正文逼出分块）。"""
    group = document_module._CHUNK_BLOCKS
    markdown_text = "\n\n".join(
        "段落 %d\n\n| a | b |\n| --- | --- |\n| 1 | 2 |" % n for n in range(group + 1))
    assert len(parse_markdown(markdown_text)) > group
    whole = render_whole(markdown_text, monkeypatch)
    monkeypatch.undo()
    chunked = render(markdown_text)
    assert chunked.blockCount() == whole.blockCount()
    assert chunked.toHtml() == whole.toHtml()


# ── 自适应分组 ───────────────────────────────────────────────────────────
def plan(markdown_text):
    blocks = parse_markdown(markdown_text)
    return document_module._chunk_plan(blocks), len(blocks), document_module._structural_load(blocks)


def prose(n):
    return "\n\n".join("段落 %d：先读 README，再看依赖。" % i for i in range(n))


def tabulated(n, every=2):
    return "\n\n".join(
        ("段落 %d" % i) + ("\n\n| a | b |\n| --- | --- |\n| 1 | 2 |" if i % every == 0 else "")
        for i in range(n))


def test_plan_keeps_pure_paragraph_documents_on_the_whole_path():
    """纯段落文档没有结构性插入，整篇就是线性的，分块只会多付拼接开销。"""
    group, count, load = plan(prose(2000))
    assert count > document_module._CHUNK_BLOCKS
    assert load == 0
    assert group == 0


def test_plan_keeps_sparse_structure_on_the_whole_path():
    """每 16 段一张表（密度 < 0.15）：1275 块实测整篇 129.0 ms、分块 140.4 ms。"""
    group, count, load = plan("\n\n".join(
        ("段落 %d" % i) + ("\n\n| a | b |\n| --- | --- |\n| 1 | 2 |" if i % 15 == 0 else "")
        for i in range(1200)))
    assert count > document_module._CHUNK_BLOCKS
    assert 0 < load / count < document_module._CHUNK_DENSITY_FLOOR
    assert group == 0


def test_plan_keeps_small_documents_on_the_whole_path():
    """密度够、但规模太小：二次成本还不够付拼接（90 块全结构整篇 48.6、分块 52.3）。"""
    dense = "\n\n".join("| a | b |\n| --- | --- |\n| %d | 2 |" % i for i in range(60))
    group, count, load = plan(dense)
    assert load / count >= document_module._CHUNK_DENSITY_FLOOR
    assert load * count < document_module._CHUNK_PRESSURE
    assert group == 0


def test_plan_uses_a_small_group_for_structure_dense_documents():
    """密度 >= 0.40 才切小分组：0.52~0.73 上 g32 与 g24/g16 互有胜负但差值 <= 1%，
    而 0.31 上小组明显吃亏（g16 113.9 vs g50 108.6），交界因此放在 0.40。

    写死 32 与阈值，避免常量被顺手改大后测试跟着变绿。
    """
    group, count, load = plan(tabulated(400, every=1))
    assert count > document_module._CHUNK_BLOCKS
    assert load / count >= document_module._CHUNK_DENSE_DENSITY
    assert document_module._CHUNK_DENSE_GROUP == 32
    assert document_module._CHUNK_DENSE_DENSITY == 0.40
    assert group == 32
    assert group < document_module._CHUNK_BLOCKS


def test_plan_keeps_moderately_dense_documents_on_the_large_group():
    """密度 0.31 属于「分块划算、但小组更慢」：700 块 g16 113.9 / g32 109.5 / g50 108.6。"""
    group, count, load = plan(tabulated(400))
    density = load / count
    assert document_module._CHUNK_DENSITY_FLOOR <= density < document_module._CHUNK_DENSE_DENSITY
    assert group == document_module._CHUNK_BLOCKS


def test_the_planned_group_actually_reaches_the_chunked_renderer(qapp, monkeypatch):
    """计划算出来的分组必须真的传进 ``_render_chunked``，且每块不超过它。"""
    captured = []
    original = document_module._render_chunked

    def spy(*args, **kwargs):
        captured.append(args[5])
        return original(*args, **kwargs)

    sizes = []
    real_render_blocks = document_module._Renderer.render_blocks

    def counting(self, blocks, cursor, indent=0.0):
        sizes.append(len(blocks))
        return real_render_blocks(self, blocks, cursor, indent)

    monkeypatch.setattr(document_module, "_render_chunked", spy)
    monkeypatch.setattr(document_module._Renderer, "render_blocks", counting)
    markdown_text = tabulated(400, every=1)
    render(markdown_text)
    assert captured == [32]
    # 每组恰好 32 个顶层块（末组可以更少）：分组真的被用了，而不是被忽略成 50。
    assert sizes and max(sizes) == 32
    assert sum(sizes) == len(parse_markdown(markdown_text))


def test_plan_uses_the_full_group_between_the_two_density_thresholds():
    """密度 0.15~0.40：分块划算但小组会多付拼接钱（密度 0.16 的 1500 块文档
    g16 283.2 ms、g50 274.5 ms），取 50。"""
    group, count, load = plan("\n\n".join(
        ("段落 %d" % i) + ("\n\n> 引用" if i % 2 == 0 else "") for i in range(1200)))
    density = load / count
    assert document_module._CHUNK_DENSITY_FLOOR <= density < document_module._CHUNK_DENSE_DENSITY
    assert load * count >= document_module._CHUNK_PRESSURE
    assert group == document_module._CHUNK_BLOCKS


def test_structural_load_weights_nested_quotes_and_ignores_other_headings():
    """引用本身是表格、内部嵌套引用再插一张，都要计数；只有 h2 带横线 frame。"""
    nested = parse_markdown("> 一层\n>\n> > 二层\n\n## 标题二\n\n### 标题三\n\n---")
    load = document_module._structural_load(nested)
    weights = document_module._STRUCTURAL_WEIGHTS
    assert load == weights["quote"] * 2 + weights["heading2"] + weights["hr"]


@pytest.mark.parametrize("expected_group,markdown_text", [
    (32, tabulated(400, every=1)),
    (document_module._CHUNK_BLOCKS, "\n\n".join(
        ("段落 %d" % i) + ("\n\n> 引用 **粗**\n\n- 项\n\n## 标题" if i % 2 == 0 else "")
        for i in range(200))),
])
def test_adaptive_groups_render_identically_to_the_whole_path(
        qapp, monkeypatch, expected_group, markdown_text):
    """任何分组都必须与整篇逐块一致：这里让判据自己选，并断言选中的正是被测档位。"""
    assert document_module._chunk_plan(parse_markdown(markdown_text)) == expected_group
    whole = laid_out(render_whole(markdown_text, monkeypatch))
    monkeypatch.undo()
    chunked = laid_out(render(markdown_text))
    assert chunked.blockCount() == whole.blockCount()
    assert signatures(chunked) == signatures(whole)
    assert table_shapes(chunked) == table_shapes(whole)
    assert chunked.toHtml() == whole.toHtml()


# ── 图片资源 ─────────────────────────────────────────────────────────────
def test_image_resources_survive_chunking(qapp, monkeypatch):
    """图片是文档级资源，``insertFragment`` 不搬；每个分块渲染完要按名字补注册。"""
    image = QtGui.QImage(12, 8, QtGui.QImage.Format.Format_RGB32)
    image.fill(0xFF3366CC)
    resolver = lambda src: image if src.startswith("my://") else None  # noqa: E731
    markdown_text = "\n\n".join("段落 %d\n\n![图](my://pic%d)" % (n, n) for n in range(80))

    force_group(monkeypatch, 10)
    document = render(markdown_text, resolver)

    names = [
        QtCore.QUrl(spec.format.toImageFormat().name())
        for block in _iter_blocks(document)
        for spec in block.textFormats() if spec.format.isImageFormat()
    ]
    assert names, "文档里应该有图片"
    kind = QTextDocument.ResourceType.ImageResource.value
    for url in names:
        assert document.resource(kind, url) is not None
