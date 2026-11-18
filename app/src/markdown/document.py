"""Markdown → ``QTextDocument``：正文层唯一的渲染器。

输入是 ``markdown.parser.parse_markdown`` 的纯数据树，输出是一份排好版的
``QTextDocument``。几何与颜色取自原版 CSS（见 docs/audit/qml-shell-audit.md §5.3），
单位是设备无关像素（``QTextDocument`` 按逻辑像素排版，HiDPI 由场景图缩放）。

关键排版决策与实测事实（每一条都在本文件对应一个实现）：

1. **块级格式在 Qt 6 里没有任何边框接口**。实测
   ``hasattr(QTextBlockFormat(), "setBorder") is False``；块背景也不会画进左边距。
   因此：
   - 引用（原版 ``border-left: 3px`` + ``padding-left: 12px``）用「1 行 2 列、
     左列固定 3px 填边框色」的表格实现，竖线随内容高度自然贯穿；
   - 分隔线与 h2 下边框用「固定 1px 行高 + 背景色」的空块实现，宽度随容器。
2. **框架（``QTextFrame``）不带边框，代码块也用表格实现**。实测在 QML 的
   ``TextEdit``（``QQuickTextEdit``）里渲染 ``setBorder(1.0)`` 的 ``QTextFrame``
   会让整个进程段错误（退出码 139），``border(0)`` 正常；同样的文档在
   ``QTextEdit`` 控件里没事。所以代码块的底色、圆角替代与语言头全部用「单列
   表格 + 单元格背景/逐边 1px 边框」表达（见 ``_code``）。复现脚本与三种对照
   的退出码见 ``out/qml-body/bordered_frame_segfault.py`` 与同名日志。
3. **表格边框逐单元格逐边画**。``QTextTableFormat`` 的整表边框在合并模式下会把
   相邻单元格的 1px 叠成 2px；``QTextTableCellFormat`` 才有逐边
   ``setLeftBorder``/``setPadding`` 接口，逐边设好再合并，网格才是均匀 1px。
   ``cellSpacing`` 恒为 0，相邻单元格共用一条边。边框与内边距/底色在
   ``_table_row`` 的同一次 ``setFormat`` 里写完，不再整表补第二遍。
4. **主题切换只换色与字**：每次渲染都重建颜色；字体族/字号来自 ``BodyStyle``，
   切主题或改字号时按原文重新渲染即可（见 ``markdown.body``）。
5. **代码块的语言标签写在块属性里**（``CODE_LANGUAGE_PROPERTY``），
   ``markdown.highlight`` 的高亮器据此逐行着色；渲染器本身不关心语法。
6. **首块上边距、末块下边距归零**，对应原版 ``.md > :first-child / :last-child``。
7. **长文档分块渲染再拼装**。结构性插入（``insertTable``/``appendRows``/
   ``insertFrame``）的单价随插入时文档规模线性增长，整篇渲染是 O(块数²)；
   超过 ``_CHUNK_BLOCKS`` 个顶层块时改成分块进 scratch 文档、再 ``insertFragment``
   拼装，输出与整篇渲染逐块一致（见 ``_render_chunked``）。

不支持的部分（显式记录，不用假效果糊过去）：行内代码/图片的圆角（QTextCharFormat
没有圆角接口）、代码块圆角（QTextFrameFormat 同样没有）、字号 650（Qt 只有
离散字重，用 DemiBold=600 近似）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional, Tuple

from markdown.parser import parse_inline, parse_markdown

NEWLINE = chr(10)
ZERO_WIDTH = chr(0x200B)
LINE_SEPARATOR = chr(0x2028)

# QTextFormat.UserProperty == 0x100000；自增的块属性用来记代码块语言。
CODE_LANGUAGE_PROPERTY = 0x100000 + 1

try:  # pragma: no cover - 取决于环境有无 Qt
    # Qt 只能经 utils.qt_compat 进入（app/tests/test_qt_compat.py 锁住这条）。
    from utils.qt_compat import QtCore, QtGui

    Qt, QUrl = QtCore.Qt, QtCore.QUrl
    QColor, QFont, QFontMetricsF = QtGui.QColor, QtGui.QFont, QtGui.QFontMetricsF
    QGuiApplication, QImage = QtGui.QGuiApplication, QtGui.QImage
    QTextBlockFormat, QTextCharFormat = QtGui.QTextBlockFormat, QtGui.QTextCharFormat
    QTextCursor, QTextDocument = QtGui.QTextCursor, QtGui.QTextDocument
    QTextFrameFormat, QTextImageFormat = QtGui.QTextFrameFormat, QtGui.QTextImageFormat
    QTextLength, QTextOption = QtGui.QTextLength, QtGui.QTextOption
    QTextTableCellFormat, QTextTableFormat = QtGui.QTextTableCellFormat, QtGui.QTextTableFormat

    QT_AVAILABLE = True
except ImportError:  # pragma: no cover
    QT_AVAILABLE = False
    QColor = QFont = QFontMetricsF = QGuiApplication = QImage = None  # type: ignore[assignment]
    QTextBlockFormat = QTextCharFormat = QTextCursor = QTextDocument = None  # type: ignore[assignment]
    QTextFrameFormat = QTextImageFormat = None  # type: ignore[assignment]
    QTextLength = QTextOption = QTextTableCellFormat = QTextTableFormat = None  # type: ignore[assignment]
    Qt = QUrl = None  # type: ignore[assignment]


# ── 设计 token（原版 tokens.css 浅色/深色 + app.css 的 .md 规则）──────────────
SANS_STACK = (
    "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Microsoft YaHei",
    "Noto Sans CJK SC", "Roboto", "Helvetica", "Arial", "sans-serif",
)
MONO_STACK = (
    "Cascadia Code", "JetBrains Mono", "DejaVu Sans Mono", "Consolas",
    "Courier New", "monospace",
)


@dataclass(frozen=True)
class BodyPalette:
    """正文用到的颜色集合。缺省是浅色；``DARK`` 是深色覆盖。"""

    fg: str = "#1f1f24"
    fg_muted: str = "#5c5c66"
    fg_subtle: str = "#8a8a94"
    bg: str = "#ffffff"
    bg_panel: str = "#f7f7f8"
    bg_inset: str = "#f0f0f2"
    bg_hover: str = "rgba(0,0,0,0.045)"
    border: str = "#e6e6ea"
    border_strong: str = "#d5d5db"
    accent: str = "#5b5bd6"
    code_bg: str = "#f0f0f2"
    code_border: str = "#e6e6ea"
    code_head_bg: str = "#f7f7f8"
    error_fg: str = "#b42318"
    error_bg: str = "#fef3f2"
    selection: str = "rgba(91,91,214,0.20)"


LIGHT = BodyPalette()
DARK = BodyPalette(
    # 逐项取自原版深色主题的真实计算值（CDP 实测，见 out/qml-shell/dom/dark-chat.json）：
    # mdCode bg #191919 / border #2f2f33、mdCodeHead bg #252528、mdQuote 左边框 #3d3d42、
    # mdHr #2f2f33。
    fg="#e4e4e7",
    fg_muted="#a1a1aa",
    fg_subtle="#71717a",
    bg="#1e1e20",
    bg_panel="#252528",
    bg_inset="#191919",
    bg_hover="rgba(255,255,255,0.06)",
    border="#2f2f33",
    border_strong="#3d3d42",
    accent="#7c7cf0",
    code_bg="#191919",
    code_border="#2f2f33",
    code_head_bg="#252528",
    error_fg="#f2a7a0",
    error_bg="#3a1d1c",
    selection="rgba(124,124,240,0.30)",
)


@dataclass(frozen=True)
class BodyStyle:
    """字与度量。``scale`` 对应原版 ``--cs`` 文本倍率（Small/Default/Large/Extra）。"""

    scale: float = 1.0
    dark: bool = False
    sans: Tuple[str, ...] = SANS_STACK
    mono: Tuple[str, ...] = MONO_STACK

    @property
    def palette(self) -> BodyPalette:
        return DARK if self.dark else LIGHT

    @property
    def base_px(self) -> float:
        return 14.0 * self.scale

    @property
    def line_height(self) -> float:
        return 1.65


@lru_cache(maxsize=256)
def css_color(value: str) -> Any:
    """CSS 颜色 → QColor；无法识别时回落黑色（坏色不应中断整篇渲染）。

    **结果按原字符串缓存并直接返回同一个实例。** 渲染器对每个字符片都调一次，
    400 轮正文实测 19600 次，而实际取值只有主题里的十几项（单次解析 2.413 µs、
    查表 0.073 µs，见 out/render-opt3/micro_cache.log）。所以这里不做防御性拷贝：
    拷贝一次要 1.835 µs，几乎抵掉全部收益。调用方只把它交给 ``setForeground`` /
    ``setBackground`` / ``QBrush(...)``，三者都是值拷贝，不会改到缓存里的实例。
    """
    text = (value or "").strip()
    match = re.match(r"^rgba?\((.*)\)$", text)
    if match:
        parts = [piece.strip() for piece in match.group(1).split(",")]
        if len(parts) >= 3:
            red, green, blue = (int(float(piece)) for piece in parts[:3])
            alpha = 255
            if len(parts) >= 4:
                alpha = int(round(float(parts[3]) * 255))
            return QColor(red, green, blue, alpha)
    color = QColor(text)
    if not color.isValid():
        color = QColor("#000000")
    return color


@lru_cache(maxsize=512)
def _font_for(families: tuple, pixel_size: int, bold: bool, italic: bool) -> Any:
    """按「字体族 + 像素 + 粗 + 斜」缓存 QFont。

    QFont 是隐式共享的值类型，``setFont``/``QTextCharFormat(fmt)`` 都只做浅拷贝，
    所以同一个实例可以安全地交给多处使用。400 轮正文实测 20400 次构造、单次
    5.001 µs（out/render-opt3/micro_cache.log）；拷贝已有实例只要 1.5 µs。
    """
    font = QFont()
    font.setFamilies(list(families))
    font.setPixelSize(pixel_size)
    font.setBold(bold)
    font.setItalic(italic)
    return font


@lru_cache(maxsize=64)
def _line_spacing(families: tuple, pixel_size: int) -> float:
    """字体行距（``QFontMetricsF.lineSpacing()``），只取决于字体族与像素大小。"""
    font = QFont()
    font.setFamilies(list(families))
    font.setPixelSize(pixel_size)
    return QFontMetricsF(font).lineSpacing()


ALIGN_LEFT = Qt.AlignmentFlag.AlignLeft if QT_AVAILABLE else 1
ALIGN_CENTER = Qt.AlignmentFlag.AlignHCenter if QT_AVAILABLE else 4
ALIGN_RIGHT = Qt.AlignmentFlag.AlignRight if QT_AVAILABLE else 2


def _alignment(value: str) -> Any:
    """表格单元格对齐。Qt6 的对齐常量在 Qt 命名空间，QTextFormat 上没有 Align*。"""
    return {"center": ALIGN_CENTER, "right": ALIGN_RIGHT}.get(value, ALIGN_LEFT)


def _measure(font: Any, text: str) -> float:
    """按字体实测宽度；没有 GUI 应用时退回估算（单测可在无字体环境跑）。"""
    if QGuiApplication.instance() is not None:
        return QFontMetricsF(font).horizontalAdvance(text)
    return len(text) * max(1.0, font.pixelSize()) * 0.6


def _plain(nodes: list) -> str:
    parts = []
    for node in nodes or []:
        if node.get("text"):
            parts.append(str(node["text"]))
        if node.get("children"):
            parts.append(_plain(node["children"]))
    return "".join(parts)


# ── 分块计划 ──────────────────────────────────────────────────────────────
# 顶层块数不超过 ``_CHUNK_BLOCKS`` 时走整篇路径：这个规模下二次成本可以忽略，
# 而分块要付每块的新文档与拼接开销（纯段落 2400 块实测整篇 111.8 ms、分块
# 148.2 ms，分块反而慢 36.4 ms）。
_CHUNK_BLOCKS = 50

# 会触发结构性插入的块种类及其相对成本（以表格为 1.0）。系数来自同一份正文
# 在两个规模（1500 / 3000 块）下整篇耗时的二次项拟合：表格 2.42e-4、代码
# 1.44e-4、引用 1.42e-4、分隔线 0.93e-4、h2 横线 1.05e-4 ms/(块·规模)。
_STRUCTURAL_WEIGHTS = {
    "table": 1.0,
    "code": 0.6,
    "quote": 0.59,
    "hr": 0.38,
    "heading2": 0.43,
}

# 走分块的两个门槛 + 分组大小，全部来自实测（out/render-opt3/ 下的
# group_calib.log / group_sweep.log / dense_groups.log / group_boundary.log）：
# - 结构密度（加权结构块 / 顶层块）低于 ``_CHUNK_DENSITY_FLOOR`` 时整篇更快：
#   每 16 段一张表的文档（密度 0.06）在 1275 块上整篇 129.0 ms、分块 140.4 ms；
# - 加权结构量 × 块数低于 ``_CHUNK_PRESSURE`` 时二次成本还不够付拼接开销：
#   90 块的全结构文档（密度 0.73）整篇 48.6 ms、分块 52.3 ms；
# - 分组大小随密度变化：密度 >= 0.40 用 32，0.15~0.40 用 50。交界放在 0.40 这段
#   平台上：密度 0.31 的 700 块文档小组都吃亏（g16 115.3 / g32 111.4 / g50
#   110.2 ms），密度 0.44 的 1200 块文档反过来 32 组最好（g16 234.5 / g32 228.6 /
#   g50 231.0 ms），而 0.365 与 0.40 两点上 24/32/50 只差 0.2~0.8%（落在抖动内），
#   所以交界落在这两者之间任意位置都行，取整到 0.40。
#   高密度用 32 而不是 16：0.44 上 g16 每档多花 1.5~2.6%，0.52 与 0.73 上
#   16/24/32 互有胜负但差值 <= 1.0%。
#   48 份实测正文里，这套判据选中的档与逐档最优相差不超过 1.4%（plan_check.log，
#   容差 2%）。
_CHUNK_DENSITY_FLOOR = 0.15
_CHUNK_PRESSURE = 45000
_CHUNK_DENSE_GROUP = 32
_CHUNK_DENSE_DENSITY = 0.40


def _structural_load(blocks: list) -> float:
    """加权结构量：只数会走结构性插入的块（引用内部递归计数）。

    ``quote`` 本身是表格，内部的嵌套引用又会再插一张，所以递归；``heading`` 只有
    level 2 会加 1px 横线 frame，其余级别是纯块格式。
    """
    total = 0.0
    for block in blocks:
        kind = block.get("type")
        if kind == "quote":
            total += _STRUCTURAL_WEIGHTS["quote"]
            total += _structural_load(block.get("children") or [])
        elif kind == "heading":
            if int(block.get("level") or 1) == 2:
                total += _STRUCTURAL_WEIGHTS["heading2"]
        elif kind in _STRUCTURAL_WEIGHTS:
            total += _STRUCTURAL_WEIGHTS[kind]
    return total


def _chunk_plan(blocks: list) -> int:
    """返回每组的顶层块数；0 表示整篇渲染。

    判据只看「会不会亏」：结构性插入的二次成本随规模线性增长，纯段落与稀疏结构
    文档的整篇路径本来就是线性的，分块只会多付拼接钱。
    """
    count = len(blocks)
    if count <= _CHUNK_BLOCKS:
        return 0
    load = _structural_load(blocks)
    if load <= 0:
        return 0
    density = load / count
    if density < _CHUNK_DENSITY_FLOOR or load * count < _CHUNK_PRESSURE:
        return 0
    if density >= _CHUNK_DENSE_DENSITY:
        return min(_CHUNK_DENSE_GROUP, _CHUNK_BLOCKS)
    return _CHUNK_BLOCKS


def render_markdown(
    document: Any,
    markdown_text: str,
    style: Optional[BodyStyle] = None,
    content_width: float = 780.0,
    image_resolver: Optional[Any] = None,
) -> Any:
    """把一份 Markdown 渲染进 ``document``（先清空）。

    ``image_resolver(src)`` 返回 ``QImage`` 或 None：正文里的 ``![](path)`` 与
    ``![alt](data:image/png;base64,...)`` 都走它。解析不到时画占位文字，不静默丢图。
    """
    body = style or BodyStyle()
    document.clear()
    document.setDocumentMargin(0)
    blocks = parse_markdown(markdown_text)
    group = _chunk_plan(blocks)
    if group <= 0:
        renderer = _Renderer(document, body, content_width, image_resolver)
        renderer.render_blocks(blocks, QTextCursor(document))
    else:
        _render_chunked(document, blocks, body, content_width, image_resolver, group)
    _collapse_edge_margins(document)
    return document


def _render_chunked(document: Any, blocks: list, body: Any, content_width: float,
                    image_resolver: Optional[Any], group: int = 0) -> None:
    """分块渲染再拼装：把「结构性插入」的二次成本摊平成线性。

    Qt 里 ``insertTable``/``appendRows``/``insertFrame`` 的单价**只跟插入那一刻
    文档已有规模有关**（实测 500 块时 0.24 ms、16000 块时 1.36 ms，插在开头还是
    结尾一样），所以整篇渲染是 O(块数²)。这里每 ``group`` 个顶层块渲染进一份全新
    的 scratch 文档（各自都从零开始，单价恒定），再按顺序用一次 ``insertFragment``
    拼进目标文档。``group`` 由 ``_chunk_plan`` 按结构密度给出；显式传入时才用 0 以外
    的值，0 表示沿用 ``_CHUNK_BLOCKS``（测试与探针按分组大小驱动这条路径用）。

    两条继承链必须显式搬运，否则分块边界会掉格式：

    1. **末块格式**：``_table``/``_quote`` 等结构性块前面的空块是靠 ``insertBlock()``
       不带格式、继承光标当前格式得来的。新分块的光标是新的，所以先把上一分块的
       末块格式 ``setBlockFormat`` 到 scratch 的初始块上，渲染器才能拿到同一条链。
    2. **首块格式**：``insertFragment`` 会让片段首块继承目标文档当前的块格式。
       拼完把源首块格式回填到目标的首块上。

    图片资源是文档级的，不随片段走：每块渲染完按名字从 scratch 搬到目标文档。
    """
    cursor = QTextCursor(document)
    size = group or _CHUNK_BLOCKS
    cursor.beginEditBlock()
    try:
        pending_top = 0.0
        carry = None
        first = True
        for index in range(0, len(blocks), size):
            scratch = QTextDocument()
            scratch_cursor = QTextCursor(scratch)
            if carry is not None:
                scratch_cursor.setBlockFormat(carry)
            renderer = _Renderer(scratch, body, content_width, image_resolver)
            renderer._pending_top = pending_top
            renderer.render_blocks(blocks[index:index + size], scratch_cursor)
            pending_top = renderer._pending_top
            carry = scratch.lastBlock().blockFormat()
            if not first:
                # 干净的空块：不先断块的话，片段首块会和上一分块的末块合成一块。
                # 判据必须是「第几块」而不是光标位置——上一分块的回填会把光标留在
                # 该分块首块上，位置判据从第二块起就失效，每组静默少一块。
                cursor.movePosition(QTextCursor.MoveOperation.End)
                cursor.insertBlock(QTextBlockFormat())
            start = cursor.position()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            cursor.insertFragment(QtGui.QTextDocumentFragment(scratch))
            source_first = scratch.begin().blockFormat()
            cursor.setPosition(start)
            QTextCursor(cursor.block()).setBlockFormat(source_first)
            _copy_resources(scratch, document)
            first = False
    finally:
        cursor.endEditBlock()


def _copy_resources(source: Any, target: Any) -> None:
    """把 ``source`` 里被引用到的图片资源搬到 ``target``（文档级资源不随片段走）。"""
    kind = QTextDocument.ResourceType.ImageResource
    seen = set()
    block = source.begin()
    while block.isValid():
        for spec in block.textFormats():
            fmt = spec.format
            if not fmt.isImageFormat():
                continue
            name = fmt.toImageFormat().name()
            if not name or name in seen:
                continue
            seen.add(name)
            image = source.resource(kind.value, QUrl(name))
            if image is not None:
                target.addResource(kind.value, QUrl(name), image)
        block = block.next()


def render_plain_text(document: Any, text: str, style: Optional[BodyStyle] = None,
                      content_width: float = 780.0) -> Any:
    """纯文本（不做 Markdown 解析），用于用户消息/状态行：保留换行，照常排版。"""
    body = style or BodyStyle()
    document.clear()
    document.setDocumentMargin(0)
    renderer = _Renderer(document, body, content_width, None)
    cursor = QTextCursor(document)
    fmt = QTextBlockFormat()
    fmt.setLineHeight(renderer.line_height(body.base_px, body.line_height),
                      QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
    cursor.setBlockFormat(fmt)
    char_fmt = QTextCharFormat()
    char_fmt.setFont(renderer.font(body.base_px))
    char_fmt.setForeground(css_color(body.palette.fg))
    cursor.insertText(text.replace(NEWLINE, LINE_SEPARATOR), char_fmt)
    return document


def _collapse_edge_margins(document: Any) -> None:
    """首块 top margin、末块 bottom margin 归零（.md > :first-child/:last-child）。

    ``QTextBlock`` 没有 setBlockFormat；改块格式要走一个指向该块的光标。
    """
    for block, attr in ((document.begin(), "top"), (document.lastBlock(), "bottom")):
        if not block.isValid():
            continue
        cursor = QTextCursor(block)
        fmt = block.blockFormat()
        if attr == "top":
            fmt.setTopMargin(0.0)
        else:
            fmt.setBottomMargin(0.0)
        cursor.setBlockFormat(fmt)


class _Renderer:
    """把块/行内树写进文档。所有几何集中在这里，便于测试核对。"""

    def __init__(self, document: Any, style: BodyStyle, content_width: float,
                 image_resolver: Optional[Any]) -> None:
        self.doc = document
        self.style = style
        self.palette = style.palette
        self.content_width = content_width
        self.image_resolver = image_resolver
        self._has_content = False
        self._quote_text = False
        self._pending_top = 0.0
        # 表格逐格格式只跟「表头/斑马行」「对齐」有关，一份正文里取值极少：
        # 按行型缓存后每格只做一次浅拷贝式 ``setFormat``（见 ``_table_row``）。
        self._cell_formats = {}
        self._cell_block_formats = {}
        self._cell_char_formats = {}

    # ── 基础 ──────────────────────────────────────────────────────────────
    def color(self, value: str) -> Any:
        return css_color(value)

    def font(self, px: float, bold: bool = False, mono: bool = False,
             italic: bool = False) -> Any:
        return _font_for(tuple(self.style.mono if mono else self.style.sans),
                         max(1, int(round(px))), bool(bold), bool(italic))

    def line_height(self, px: float, factor: float) -> float:
        """把 CSS 行高（``px * factor``）换算成 ``ProportionalHeight`` 的百分比。

        Qt 的比例行高是相对**字体行距**（``QFontMetricsF.lineSpacing()``），不是字号：
        Noto Sans 14px 的行距约 16.9px，直接写 165 会得到 27.8px 而不是 CSS 的 23.1px。
        目标像素值除以字体行距再乘 100 才能与浏览器一致。

        字体行距只取决于「字体族 + 字号」，按这两个键缓存（倍率是纯算术，不必入键）：
        未缓存时每次都要新建 ``QFont`` 再构造 ``QFontMetricsF``，而度量本身单次
        1.302 µs（out/render-opt3/micro_cache.log），400 轮正文调用 9600 次；
        ``line_height`` 在插桩下整条路径占 186.1 ms（含缓存命中后的查表与算术），
        见 out/render-opt3/hot_paths.log——缓存省掉的是其中「新建 QFont + 度量」
        那一段，不是整条 186.1 ms。
        """
        if QGuiApplication.instance() is None:
            return factor * 100.0
        spacing = _line_spacing(tuple(self.style.sans), max(1, int(round(px))))
        if spacing <= 0:
            return factor * 100.0
        return (px * factor) / spacing * 100.0

    def _block_format(self, top: float, bottom: float) -> Any:
        fmt = QTextBlockFormat()
        fmt.setTopMargin(top + self._pending_top)
        self._pending_top = 0.0
        fmt.setBottomMargin(bottom)
        fmt.setLineHeight(self.line_height(self.style.base_px, self.style.line_height),
                          QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        return fmt

    def _begin(self, cursor: Any, fmt: Any) -> Any:
        """开始一个新块：已有内容就先断块，再套格式。"""
        if self._has_content:
            cursor.insertBlock()
        cursor.setBlockFormat(fmt)
        self._has_content = True
        return cursor

    def _after_frame(self, cursor: Any, frame_end: int) -> None:
        """把光标挪到 frame/表格之后，并标记「下一块需另起」。"""
        cursor.setPosition(frame_end)
        self._has_content = True

    # ── 块分派 ────────────────────────────────────────────────────────────
    def render_blocks(self, blocks: list, cursor: Any, indent: float = 0.0) -> None:
        for block in blocks:
            kind = block.get("type")
            if kind == "heading":
                self._heading(cursor, block)
            elif kind == "paragraph":
                self._paragraph(cursor, block, indent)
            elif kind == "list":
                self._list(cursor, block, indent)
            elif kind == "quote":
                self._quote(cursor, block)
            elif kind == "table":
                self._table(cursor, block)
            elif kind == "code":
                self._code(cursor, block)
            elif kind == "hr":
                self._rule(cursor)

    # ── 标题 ──────────────────────────────────────────────────────────────
    def _heading(self, cursor: Any, block: dict) -> None:
        level = int(block.get("level") or 1)
        scale = {1: 1.5, 2: 1.3, 3: 1.15, 4: 1.0, 5: 0.9, 6: 0.9}.get(level, 1.0)
        px = self.style.base_px * scale
        fmt = QTextBlockFormat()
        fmt.setTopMargin(16.0)
        # 原版 h2 的 padding-bottom: 0.2em 由下面的 1px 下边框前的间距承担。
        fmt.setBottomMargin(0.0 if level == 2 else 8.0)
        fmt.setLineHeight(self.line_height(px, 1.3),
                          QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        self._begin(cursor, fmt)
        char_fmt = QTextCharFormat()
        char_fmt.setFont(self.font(px, bold=True))
        char_fmt.setForeground(self.color(self.palette.fg_muted if level >= 5 else self.palette.fg))
        self._inline(cursor, block.get("children") or [], char_fmt)
        if level == 2:
            self._hairline(cursor, gap_before=px * 0.2, gap_after=8.0)

    def _hairline(self, cursor: Any, gap_before: float = 0.0, gap_after: float = 0.0,
                  inside_frame: bool = False) -> None:
        """1px 实线：固定高度 1px 的空 frame（块格式没有边框接口，行高压不住字高）。

        实测：``QTextBlockFormat`` 的 ``FixedHeight`` 只约束行框，块里塞 1px 字体仍会被
        撑到 2~3px；而 ``QTextFrameFormat.setHeight(FixedLength, 1)`` 正好画出 1px。

        **间距不能放在 frame 自己的 margin 上**：frame 的背景会把 margin 一起涂上，
        1px 线会变成十几像素的色带（实测 16px margin 画出 31px 色带）。所以间距分别
        记到前一块的 bottom margin 与后一块的 top margin（``_pending_top``）。
        """
        if gap_before and cursor.position() > 0:
            # 只改前一块的格式，不移动主光标（否则会把内容切到 frame 后面）。
            block_cursor = QTextCursor(cursor.block())
            fmt = block_cursor.blockFormat()
            fmt.setBottomMargin(fmt.bottomMargin() + gap_before)
            block_cursor.setBlockFormat(fmt)
        frame_fmt = QTextFrameFormat()
        frame_fmt.setBorder(0.0)
        frame_fmt.setPadding(0.0)
        frame_fmt.setMargin(0.0)
        frame_fmt.setHeight(QTextLength(QTextLength.Type.FixedLength, 1.0))
        frame_fmt.setBackground(self.color(self.palette.border))
        frame = cursor.insertFrame(frame_fmt)
        # 必须 +1 才是 frame 之后的位置；停在 lastPosition 上会把后续内容排进 1px 高的 frame。
        cursor.setPosition(frame.lastPosition() + 1)
        self._pending_top = gap_after
        self._has_content = True

    def _rule(self, cursor: Any) -> None:
        self._hairline(cursor, gap_before=16.0, gap_after=16.0)

    # ── 段落 ──────────────────────────────────────────────────────────────
    def _paragraph(self, cursor: Any, block: dict, indent: float) -> None:
        fmt = self._block_format(0.0, 12.0)
        if indent:
            fmt.setLeftMargin(indent)
        self._begin(cursor, fmt)
        char_fmt = QTextCharFormat()
        char_fmt.setFont(self.font(self.style.base_px))
        char_fmt.setForeground(self.color(self.palette.fg_muted if self._quote_text else self.palette.fg))
        self._inline(cursor, block.get("children") or [], char_fmt)

    # ── 引用：1 行 2 列表格，左列 3px 填边框色 ────────────────────────────
    def _quote(self, cursor: Any, block: dict) -> None:
        """引用是整行块（原版 ``border-left`` + padding），宽度必须撑满容器。

        表格默认按内容收缩（实测 120px 单元格），嵌套引用的正文会被挤成一字一行。
        设成 100% 宽度后，单元格宽度 = 容器宽度 - 边框 - 内边距，嵌套时逐层收 27px
        （3px 竖线 + 12px 内边距 + 12px 表格外边距），与浏览器一致。
        """
        if self._has_content:
            cursor.insertBlock()
        table_fmt = QTextTableFormat()
        table_fmt.setBorder(0.0)
        table_fmt.setCellSpacing(0.0)
        table_fmt.setCellPadding(0.0)
        table_fmt.setBorderCollapse(True)
        # 引用表外边距 6px（不是段落用的 12px）：原版 `border-left` 直接贴正文列，
        # 实测 12px 时竖线比原版右 8px、二级引用右 19px；6px 与 12/0/4/5/7/8 逐档
        # 实拍比对，聊天页差异 57264 → 56373 像素，是这几档里最小的。
        table_fmt.setMargin(6.0)
        table_fmt.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100.0))
        table_fmt.setColumnWidthConstraints(
            [
                QTextLength(QTextLength.Type.FixedLength, 3.0),
                QTextLength(QTextLength.Type.VariableLength, 100.0),
            ]
        )
        table = cursor.insertTable(1, 2, table_fmt)
        bar = table.cellAt(0, 0)
        bar_fmt = QTextTableCellFormat()
        bar_fmt.setBackground(self.color(self.palette.border_strong))
        bar.setFormat(bar_fmt)
        body = table.cellAt(0, 1)
        body_fmt = QTextTableCellFormat()
        body_fmt.setLeftPadding(12.0)
        body_fmt.setTopPadding(2.0)
        body_fmt.setBottomPadding(2.0)
        body.setFormat(body_fmt)
        inner = body.firstCursorPosition()
        saved_content, saved_quote = self._has_content, self._quote_text
        self._has_content, self._quote_text = False, True
        self.render_blocks(block.get("children") or [], inner)
        self._has_content, self._quote_text = saved_content, saved_quote
        self._after_frame(cursor, table.lastPosition() + 1)

    # ── 列表 ──────────────────────────────────────────────────────────────
    def _list(self, cursor: Any, block: dict, indent: float) -> None:
        ordered = bool(block.get("ordered"))
        start = int(block.get("start") or 1)
        for offset, item in enumerate(block.get("items") or []):
            column = self._list_item(cursor, item, ordered, start + offset, indent)
            nested = [
                child
                for child in (item.get("children") or [])
                if child.get("type") != "paragraph"
            ]
            if nested:
                # 子列表从父条目的正文列开始，宽度跟父条目的标记列一致。
                self.render_blocks(nested, cursor, indent + column)

    def _list_item(self, cursor: Any, item: dict, ordered: bool, number: int,
                   indent: float) -> float:
        """条目用「两个左对齐 tab 位」做悬挂缩进。

        原版是 ``padding-left: 1.5em`` + 浏览器自动排的 ``::marker``，标记右缘贴着
        正文列。直接写 ``"1. "`` + ``textIndent(-21)`` 会把标记推到块左边界之外
        （实测 x=1 起笔、首行起点 x=-21），多位数列表更会整段溢出。这里改成：
        第一个 tab 位把标记右对齐到 ``column - marker_width - 1``，第二个 tab 位把
        正文钉在 ``column``。``column`` 取 ``max(21, marker_width + 5)``，所以 ``100.``
        这类宽标记会自己把列撑宽，而不是被裁。

        必须留 1px 余量：``lead + marker_width`` 如果**正好**等于 tab 位，Qt 的浮点
        比较会认为已经越过该制表位，转而跳到下一个默认制表位（实测 80px），正文
        整段右移 59px。
        """
        marker_fmt = QTextCharFormat()
        marker_fmt.setFont(self.font(self.style.base_px))
        marker_fmt.setForeground(self.color(self.palette.fg_subtle))
        task = item.get("task")
        if task is None:
            marker = ("%d." % number) if ordered else "•"
        else:
            marker = "☑" if task else "☐"
        marker_width = _measure(marker_fmt.font(), marker)
        column = max(21.0, marker_width + 5.0)
        lead = max(0.0, column - marker_width - 1.0)

        fmt = self._block_format(2.0, 2.0)
        fmt.setLeftMargin(indent + column)
        fmt.setTextIndent(-column)
        fmt.setTabPositions([
            QTextOption.Tab(lead, QTextOption.TabType.LeftTab),
            QTextOption.Tab(column, QTextOption.TabType.LeftTab),
        ])
        self._begin(cursor, fmt)
        cursor.insertText("\t" + marker + "\t", marker_fmt)
        text_fmt = QTextCharFormat()
        text_fmt.setFont(self.font(self.style.base_px))
        text_fmt.setForeground(self.color(self.palette.fg))
        first = True
        for child in item.get("children") or []:
            if child.get("type") != "paragraph":
                continue
            if not first:
                cursor.insertBlock(fmt)
            first = False
            self._inline(cursor, child.get("children") or [], text_fmt)
        return column

    # ── 表格 ──────────────────────────────────────────────────────────────
    def _table(self, cursor: Any, block: dict) -> None:
        header = block.get("header") or []
        rows = block.get("rows") or []
        if not header:
            return
        align = list(block.get("align") or ["left"] * len(header))
        if self._has_content:
            cursor.insertBlock()
        table_fmt = QTextTableFormat()
        # 表格级 1px 边框必须设：QML 的 `TextEdit`（QQuickTextEdit 的文本节点）**不画**
        # 单元格级边框，只画表格级边框（实测 out/qml-shell/probe 见 docs 审计 §正文）。
        # 合并模式下（BorderCollapse=True）表格级 1px 与单元格级 1px 会合并成 1px，
        # 不会叠成 2px，所以在 QTextEdit 控件路径上仍然是 1px 网格。
        table_fmt.setBorder(1.0)
        table_fmt.setBorderBrush(QtGui.QBrush(self.color(self.palette.border)))
        table_fmt.setCellSpacing(0.0)
        table_fmt.setCellPadding(0.0)
        table_fmt.setBorderCollapse(True)
        table_fmt.setMargin(12.0)
        table_fmt.setAlignment(ALIGN_LEFT)
        # 一次插满所有行。``insertTable(1, n)`` + 逐行 ``appendRows(1)`` 是每行一次
        # 结构性插入，每次都要按「插入时文档规模」重排；400 轮文档整篇渲染实测
        # 5101.1 → 2773.2 ms（交替 A/B 七次中位数，out/render-opt2/）。
        # 形状不变：``parser`` 已把每行补齐到表头列数，所以直接按行数一次建表。
        table = cursor.insertTable(1 + len(rows), len(header), table_fmt)
        self._table_row(table, 0, header, align, header_row=True)
        for row_index, row in enumerate(rows, start=1):
            self._table_row(table, row_index, row, align, header_row=False)
        self._after_frame(cursor, table.lastPosition() + 1)

    def _table_row(self, table: Any, row_index: int, cells: list, align: list[str], *,
                   header_row: bool) -> None:
        """写一行单元格。三种格式按「决定它们的输入」缓存后复用。

        一份正文里表格的单元格格式只有两种（表头 / 偶数行 / 奇数行，共三种组合）、
        块格式只有对齐方式那么几种、字符格式只有表头与否两种，但 400 轮文档有 8800
        个单元格。原先每格都新建并写 ~20 个属性，现在每类只构造一次，其余走
        ``QTextFormat`` 的隐式共享浅拷贝。400 轮正文、分组 32、五轮交替取最小：
        逐格新建格式要 660.3 ms，复用后 568.2 ms（``toHtml()`` / 高度全等，
        out/render-opt3/cell_levels.log）；A/B 复核 701.8 → 596.0 ms
        （out/render-opt3/cell_reuse.log）。
        """
        border = self.color(self.palette.border)
        solid = QTextFrameFormat.BorderStyle_Solid
        line_height = self.line_height(13.0 * self.style.scale, self.style.line_height)
        cell_key = (header_row, row_index % 2 == 0)
        cell_fmt = self._cell_formats.get(cell_key)
        if cell_fmt is None:
            cell_fmt = QTextTableCellFormat()
            cell_fmt.setLeftPadding(10.0 * self.style.scale)
            cell_fmt.setRightPadding(10.0 * self.style.scale)
            cell_fmt.setTopPadding(6.0 * self.style.scale)
            cell_fmt.setBottomPadding(6.0 * self.style.scale)
            if header_row:
                cell_fmt.setBackground(self.color(self.palette.bg_panel))
            elif row_index % 2 == 0:
                cell_fmt.setBackground(self.color(self.palette.bg_hover))
            # 逐单元格逐边 1px：整表 1px 在合并模式下会叠成 2px。与内边距/底色写在
            # 同一次 ``setFormat`` 里，省掉原先「整表再遍历一遍、逐格读-改-写」的
            # 第二趟（400 轮文档 8800 格，交替 A/B 七次中位数实测再省 38.3 ms，
            # 逐格单元格格式与 toHtml() 全等，out/render-opt2/）。
            cell_fmt.setBorder(0.0)
            for setter in (cell_fmt.setLeftBorder, cell_fmt.setRightBorder,
                           cell_fmt.setTopBorder, cell_fmt.setBottomBorder):
                setter(1.0)
            for setter in (cell_fmt.setLeftBorderBrush, cell_fmt.setRightBorderBrush,
                           cell_fmt.setTopBorderBrush, cell_fmt.setBottomBorderBrush):
                setter(border)
            for setter in (cell_fmt.setLeftBorderStyle, cell_fmt.setRightBorderStyle,
                           cell_fmt.setTopBorderStyle, cell_fmt.setBottomBorderStyle):
                setter(solid)
            self._cell_formats[cell_key] = cell_fmt
        char_fmt = self._cell_char_formats.get(header_row)
        if char_fmt is None:
            char_fmt = QTextCharFormat()
            char_fmt.setFont(self.font(13.0 * self.style.scale, bold=header_row))
            char_fmt.setForeground(self.color(self.palette.fg))
            self._cell_char_formats[header_row] = char_fmt
        for column, cell_nodes in enumerate(cells):
            cell = table.cellAt(row_index, column)
            cell.setFormat(cell_fmt)
            cell_cursor = cell.firstCursorPosition()
            alignment = align[column] if column < len(align) else "left"
            block_fmt = self._cell_block_formats.get(alignment)
            if block_fmt is None:
                block_fmt = QTextBlockFormat()
                block_fmt.setAlignment(_alignment(alignment))
                block_fmt.setLineHeight(
                    line_height, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
                self._cell_block_formats[alignment] = block_fmt
            cell_cursor.setBlockFormat(block_fmt)
            self._inline(cell_cursor, cell_nodes or [], char_fmt)

    # ── 代码块 ────────────────────────────────────────────────────────────
    def _code(self, cursor: Any, block: dict) -> None:
        """代码块 = 单列表格（语言头一行 + 代码一行），宽度取「容器宽」与「最宽行」大者。

        原版 ``.md-code`` 是块级元素（宽度撑满），``pre`` 只有内容超宽时才 ``overflow-x``
        滚动。表格宽度写死成内容宽会让短代码块缩成一小条（实测 134px），所以取
        ``max(最宽行 + 左右内边距 + 边框, 容器宽 - 左右外边距)``：短代码块与正文同宽，
        长代码块撑到最宽行、由视图横向滚动。

        **不能用 ``QTextFrame``。** 实测在 QML 的 ``TextEdit``（``QQuickTextEdit``）里
        插入 ``setBorder(1.0)`` 的 frame 会让整个进程段错误（退出码 139），无论 frame
        里有没有内容、边框是 0.5/1/2 像素都不例外；同样的文档在 ``QTextEdit`` 控件里
        正常。表格没有这个问题（``QTextTable`` 走的是另一条排版路径），所以边框、
        底色、语言头全部用单元格属性表达：逐边设 1px 边框，只有首行带上边框、末行带
        下边框，内部接缝才正好 1px 而不是 2px。

        语言标签同时写进代码行的块属性（``CODE_LANGUAGE_PROPERTY``），高亮器逐块读。
        """
        text = str(block.get("text") or "")
        language = str(block.get("language") or "").strip().lower()
        code_px = 12.5 * self.style.scale
        mono_font = self.font(code_px, mono=True)
        lines = text.split(NEWLINE) if text else [""]
        widest = max([_measure(mono_font, line) for line in lines] + [0.0])
        # 左右各 12px 正文内边距 + 2px 边框；再加 2px 余量，避免最宽行贴边触发无谓滚动。
        natural = widest + 24.0 + 4.0
        frame_width = max(natural, self.content_width - 24.0)
        rows = 2 if language else 1
        first_code_row = 1 if language else 0

        if self._has_content:
            cursor.insertBlock()
        table_fmt = QTextTableFormat()
        table_fmt.setBorder(0.0)
        table_fmt.setCellSpacing(0.0)
        table_fmt.setCellPadding(0.0)
        table_fmt.setBorderCollapse(True)
        table_fmt.setMargin(12.0)
        table_fmt.setAlignment(ALIGN_LEFT)
        table_fmt.setWidth(QTextLength(QTextLength.Type.FixedLength, frame_width))
        table_fmt.setColumnWidthConstraints(
            [QTextLength(QTextLength.Type.FixedLength, frame_width)]
        )
        table = cursor.insertTable(rows, 1, table_fmt)

        if language:
            self._code_head(table, language)

        code_cell = table.cellAt(first_code_row, 0)
        cell_fmt = QTextTableCellFormat()
        cell_fmt.setBackground(self.color(self.palette.code_bg))
        cell_fmt.setLeftPadding(0.0)
        cell_fmt.setRightPadding(0.0)
        cell_fmt.setTopPadding(0.0)
        cell_fmt.setBottomPadding(0.0)
        # 只有最外圈有边框：首行上方、代码行下方；左右每行都画。
        self._cell_edges(cell_fmt, top=first_code_row == 0, bottom=True, left=True, right=True)
        code_cell.setFormat(cell_fmt)

        cell_cursor = code_cell.firstCursorPosition()
        char_fmt = QTextCharFormat()
        char_fmt.setFont(mono_font)
        char_fmt.setForeground(self.color(self.palette.fg))
        for index, line in enumerate(lines):
            fmt = QTextBlockFormat()
            fmt.setLeftMargin(12.0)
            fmt.setRightMargin(12.0)
            fmt.setTopMargin(12.0 if index == 0 else 0.0)
            fmt.setBottomMargin(12.0 if index == len(lines) - 1 else 0.0)
            fmt.setLineHeight(self.line_height(code_px, 1.55),
                              QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            fmt.setNonBreakableLines(True)
            fmt.setProperty(CODE_LANGUAGE_PROPERTY, language)
            if index == 0:
                cell_cursor.setBlockFormat(fmt)
            else:
                cell_cursor.insertBlock(fmt)
            cell_cursor.insertText(line, char_fmt)
        self._after_frame(cursor, table.lastPosition() + 1)

    def _cell_edges(self, fmt: Any, **edges: bool) -> None:
        """逐边给单元格设 1px 实线边框（只给要求的那几条边）。"""
        border = self.color(self.palette.code_border)
        solid = QTextFrameFormat.BorderStyle_Solid
        pairs = (
            ("top", fmt.setTopBorder, fmt.setTopBorderBrush, fmt.setTopBorderStyle),
            ("bottom", fmt.setBottomBorder, fmt.setBottomBorderBrush, fmt.setBottomBorderStyle),
            ("left", fmt.setLeftBorder, fmt.setLeftBorderBrush, fmt.setLeftBorderStyle),
            ("right", fmt.setRightBorder, fmt.setRightBorderBrush, fmt.setRightBorderStyle),
        )
        for name, set_width, set_brush, set_style in pairs:
            if not edges.get(name):
                continue
            set_width(1.0)
            set_brush(border)
            set_style(solid)

    def _code_head(self, table: Any, language: str) -> None:
        """代码块语言头行：满宽浅色条 + 1px 下边框。"""
        cell = table.cellAt(0, 0)
        cell_fmt = QTextTableCellFormat()
        cell_fmt.setBackground(self.color(self.palette.code_head_bg))
        cell_fmt.setLeftPadding(12.0 * self.style.scale)
        cell_fmt.setRightPadding(12.0 * self.style.scale)
        cell_fmt.setTopPadding(4.0)
        cell_fmt.setBottomPadding(4.0)
        self._cell_edges(cell_fmt, top=True, bottom=True, left=True, right=True)
        cell.setFormat(cell_fmt)
        label_fmt = QTextCharFormat()
        label_fmt.setFont(self.font(11.0 * self.style.scale, mono=True))
        label_fmt.setForeground(self.color(self.palette.fg_muted))
        cell.firstCursorPosition().insertText(language, label_fmt)

    # ── 行内 ──────────────────────────────────────────────────────────────
    def _inline(self, cursor: Any, nodes: list, base: Any) -> None:
        for node in nodes or []:
            kind = node.get("type")
            if kind == "text":
                # 段落内的软换行是 U+2028（块内换行）；直接写 "\n" 会被当成新块。
                cursor.insertText(str(node.get("text") or "").replace(NEWLINE, LINE_SEPARATOR), base)
            elif kind == "br":
                cursor.insertText(LINE_SEPARATOR, base)  # 块内换行
            elif kind == "code":
                fmt = QTextCharFormat(base)
                fmt.setFont(self.font(self.style.base_px * 0.88, mono=True))
                fmt.setBackground(self.color(self.palette.bg_inset))
                fmt.setForeground(self.color(self.palette.fg))
                cursor.insertText(str(node.get("text") or ""), fmt)
            elif kind in ("strong", "em", "del"):
                fmt = QTextCharFormat(base)
                if kind == "strong":
                    fmt.setFontWeight(QFont.Weight.DemiBold)
                elif kind == "em":
                    fmt.setFontItalic(True)
                else:
                    fmt.setFontStrikeOut(True)
                    fmt.setForeground(self.color(self.palette.fg_subtle))
                self._inline(cursor, node.get("children") or [], fmt)
            elif kind in ("link", "autolink"):
                fmt = QTextCharFormat(base)
                fmt.setForeground(self.color(self.palette.accent))
                href = str(node.get("href") or "")
                if href:
                    fmt.setAnchor(True)
                    fmt.setAnchorHref(href)
                if kind == "autolink":
                    cursor.insertText(href, fmt)
                else:
                    self._inline(cursor, node.get("children") or [], fmt)
            elif kind == "image":
                self._image(cursor, node, base)
            elif node.get("children"):
                self._inline(cursor, node.get("children") or [], base)
            elif "text" in node:
                cursor.insertText(str(node.get("text") or ""), base)

    def _image(self, cursor: Any, node: dict, base: Any) -> None:
        src = str(node.get("src") or "")
        alt = str(node.get("alt") or "")
        image = self.image_resolver(src) if self.image_resolver is not None else None
        if image is None:
            # 解析不到时保留 alt 文本并加标记：用户能看出这里有图，而不是被吞掉。
            fmt = QTextCharFormat(base)
            fmt.setForeground(self.color(self.palette.fg_subtle))
            cursor.insertText("［图片%s］" % ("：" + alt if alt else ""), fmt)
            return
        name = "md-image:%d" % id(image)
        self.doc.addResource(QTextDocument.ResourceType.ImageResource.value,
                             QUrl(name), image)
        fmt = QTextImageFormat()
        fmt.setName(name)
        width = float(image.width())
        if width > self.content_width:
            fmt.setWidth(self.content_width)
            fmt.setHeight(width and float(image.height()) * self.content_width / width)
        else:
            fmt.setWidth(width)
            fmt.setHeight(float(image.height()))
        cursor.insertImage(fmt)
