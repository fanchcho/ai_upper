"""正文文档对象：一份 ``QTextDocument`` + 代码高亮 + 主题 + 宽度。

``document.render_markdown`` 只负责「一次渲染」。真实界面还要处理：

- 窗口宽度变了，代码块 frame 的固定宽度要跟着重算（正文段落自己换行，不用重排）；
- 主题切换要同时换正文颜色与高亮配色，不能重建控件；
- 语法高亮器是 ``QSyntaxHighlighter``，必须有自己的引用，否则 Python 侧 GC 后
  高亮静默消失；
- QML 的 ``TextEdit`` 暴露 ``QQuickTextDocument``，要能直接接管同一份文档。

这些状态集中在这里，QML 适配层只做「把槽转发过来」。

**接管方式是「渲染到自有文档 + 一次片段搬运」。** ``TextEdit`` 持有自己的
``QTextDocument``，不能替换实例，所以内容必须落进它。

早期实现是「再以目标文档重渲染一遍」，但那只在文档很小的时候成立：``QQuickTextEdit``
把文档的 ``contentsChange`` 接到自己的 size/layout 上，**每插入一块就触发一次文档级重排**，
同一份正文写进活动文档比写进普通文档慢 8~12 倍（实测 400 轮：1.8 s → 14 s，见
``out/conversation-picker-lag/REPORT.md``）。改成整篇 ``insertFragment`` 后只有一次
内容变更：格式与表格结构随片段走，代码着色由挂在目标文档上的高亮器在
``contentsChange`` 里补齐（见下）；只有文档级的属性不随片段走——图片资源要在搬运后
按名字补注册（``_copy_images``），``documentMargin`` 要显式对齐（渲染器用 0，QML
文档默认 4，差 4px 内边距）。

**高亮器挂在「当前在显示的那份文档」上。** 它是 ``QSyntaxHighlighter``，只对
``document()`` 指向的文档着色：

- 未接管时是自有文档（``render()`` 里就地重高亮）；
- 接管后是 QML 文档——``TextEdit`` 创建的文档本来就是由 ``QQuickTextEdit`` 观察的，
  ``insertFragment`` 引起的内容变更会驱动高亮器逐块跑，所以搬运后**不该再显式
  ``rehighlight()``**（实测 400 轮是白跑的 0.9~1.7 s）；
- 也因此 ``render()`` 只在「高亮器确实挂在这次渲染的目标上」时才重高亮。否则切会话时
  会先对上一份大文档全量重跑一遍（实测 2.5 s，REPORT §3.4）。

``QTextLayout`` 上的着色不属于文档内容，是**渲染/高亮这一步的产物**，跨文档搬运时
不能用 ``setFormats`` 硬塞——实测把源文档的 ``FormatRange``（或复制出的副本）塞进
目标 ``QTextLayout`` 后，那些块的高度会变成 0，代码整段不可见。让目标自己的高亮器
重新算一遍才是唯一站得住的路径。
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from markdown.document import (
    BodyPalette,
    BodyStyle,
    DARK,
    LIGHT,
    render_markdown,
    render_plain_text,
)
from markdown.highlight import CodeHighlighter

try:  # pragma: no cover - 取决于环境有无 Qt
    from utils.qt_compat import QtCore, QtGui

    QTextDocument = QtGui.QTextDocument
    QT_AVAILABLE = True
except ImportError:  # pragma: no cover
    QtCore = None  # type: ignore[assignment]
    QTextDocument = None  # type: ignore[assignment]
    QT_AVAILABLE = False


# 只有宽度变化超过这个阈值才重排代码块：抖动几个像素不该触发整篇重渲染。
WIDTH_EPSILON = 2.0


class BodyDocument:
    """一份可复用的正文文档（可以挂在自己的文档上，也可以接管 QML 的）。"""

    def __init__(self, style: Optional[BodyStyle] = None, content_width: float = 780.0,
                 highlight: bool = True) -> None:
        if not QT_AVAILABLE:  # pragma: no cover - 无 Qt 环境
            raise ImportError("BodyDocument requires a Qt binding")
        from utils.emoji_font import ensure_emoji_font
        ensure_emoji_font()
        self.document = QTextDocument()
        self.style = style or BodyStyle()
        self.content_width = float(content_width)
        self._viewports = []
        self._source = ""
        self._plain = False
        self._image_resolver: Optional[Callable[[str], Any]] = None
        self._rendered_width = self.content_width
        self._highlighter: Optional[CodeHighlighter] = None
        if highlight:
            self._highlighter = CodeHighlighter(self.document, self.style)

    # ── 状态 ──────────────────────────────────────────────────────────────
    @property
    def source(self) -> str:
        return self._source

    @property
    def palette(self) -> BodyPalette:
        return self.style.palette

    @property
    def highlighter(self) -> Optional[CodeHighlighter]:
        return self._highlighter

    # ── 渲染 ──────────────────────────────────────────────────────────────
    def set_source(self, text: str, plain: bool = False) -> None:
        """设置正文。``plain=True`` 用于用户消息与状态行（不做 Markdown 解析）。"""
        self._source = text or ""
        self._plain = bool(plain)
        self.render()

    def set_markdown(self, text: str) -> None:
        self.set_source(text, plain=False)

    def set_plain_text(self, text: str) -> None:
        self.set_source(text, plain=True)

    def render(self, document: Optional[Any] = None) -> Any:
        """重渲染进 ``document``（缺省是自己的文档）。"""
        target = document if document is not None else self.document
        if self._plain:
            render_plain_text(target, self._source, self.style, self.content_width)
        else:
            render_markdown(
                target,
                self._source,
                self.style,
                content_width=self.content_width,
                image_resolver=self._image_resolver,
            )
        self._rendered_width = self.content_width
        if self._highlighter is not None and self._highlighter.document() is target:
            # 渲染改写了整篇文档，高亮器的旧布局格式全部作废，必须重跑；不重跑时
            # 代码块保持单色，且要等到下一次文档重排才「补」上颜色（实测如此）。
            # 只在目标正是高亮器所在文档时才跑：接管 QML 后目标可能是另一份文档，
            # 对那份额外重跑高亮纯属白给（REPORT §3.4）。
            self._highlighter.rehighlight()
        return target

    # ── 主题与宽度 ────────────────────────────────────────────────────────
    def set_style(self, style: BodyStyle) -> None:
        self.style = style
        if self._highlighter is not None:
            self._highlighter.set_style(style)
        self.render()

    def set_theme(self, dark: bool) -> None:
        self.set_style(_replace_dark(self.style, dark))

    def set_scale(self, scale: float) -> None:
        scale = float(scale)
        if scale <= 0:
            raise ValueError("text scale must be positive")
        self.set_style(_replace_scale(self.style, scale))

    def set_width(self, width: float) -> bool:
        """视口宽度变化；变化明显才重排。返回是否真的重排了。"""
        width = float(width)
        if width <= 0:
            return False
        self.content_width = width
        if abs(width - self._rendered_width) < WIDTH_EPSILON:
            return False
        self.render()
        return True

    def set_image_resolver(self, resolver: Optional[Callable[[str], Any]]) -> None:
        self._image_resolver = resolver

    # ── QML 接管 ──────────────────────────────────────────────────────────
    def attach(self, quick_document: Any) -> Any:
        """把自有文档的内容**一次**搬进 ``QQuickTextDocument`` 的文档。

        ``TextEdit`` 的文档实例由 QML 持有，不能替换，只能往里写。这里用
        ``insertFragment`` 整篇替换：内容只变更一次，不会像「逐块插入」那样
        每插一块就触发一次文档级重排（实测 400 轮正文：20.5 s → 5.6 s）。
        返回目标文档。

        高亮器跟着内容走：接管后它挂在目标文档上。**换文档要先于搬运**——
        ``QSyntaxHighlighter.setDocument`` 本身不重高亮，换完之后 ``insertFragment``
        引起的内容变更才会驱动它逐块着色；反过来做，首帧的代码是单色的。
        搬运后也**不**再显式 ``rehighlight()``——同一份正文是白跑一遍（400 轮实测
        8.9 s，见 ``out/render-opt2/probe_reorder_highlight.py``）。

        注意 attach 的大头**不是**高亮：400 轮正文实测约 960 ms，其中
        ``endEditBlock`` 提交占约 750 ms（``QQuickTextEdit`` 在编辑块提交时整篇重排；
        同一片段搬进普通 ``QTextDocument`` 只要 2.7 ms），
        ``QTextDocumentFragment`` 构造约 70 ms、``insertFragment`` 约 64 ms、
        图片搬运约 41 ms、删除旧内容约 32 ms。高亮器本体只占约 112 ms，且是在提交
        过程中被 ``contentsChange`` 驱动的。拆解见 ``out/render-opt2/REPORT.md`` §4。

        ``insertFragment`` 不搬文档级图片资源，搬运后按名字补注册（``_copy_images``）；
        也不搬 ``documentMargin``，而 QML 文档的默认值是 4，渲染器用 0——不显式对齐
        的话正文四边会多出内边距、整体偏移，排版与直接渲染对不上。
        ``QTextLayout`` 里的着色不能跨文档搬（会把块高打成 0），只能由目标文档自己的
        高亮器重算，见模块文档。
        """
        for viewport in self._viewports:
            viewport.setParentItem(None)
            viewport.deleteLater()
        self._viewports = []
        target = quick_document.textDocument()
        # 渲染器把自有文档的页边距设成 0（正文块自己控制留白）。片段不搬运文档级的
        # ``documentMargin``，不显式对齐的话接管后四边会多出 4px 默认内边距，正文
        # 整体偏移、文档高度多 8px。
        target.setDocumentMargin(self.document.documentMargin())
        if self._highlighter is not None and self._highlighter.document() is not target:
            self._highlighter.setDocument(target)
        cursor = QtGui.QTextCursor(target)
        cursor.beginEditBlock()
        try:
            cursor.select(QtGui.QTextCursor.SelectionType.Document)
            cursor.removeSelectedText()
            cursor.insertFragment(QtGui.QTextDocumentFragment(self.document))
        finally:
            cursor.endEditBlock()
        self._copy_images(target)
        # Test stubs have no QQuickItem owner; actual QML keeps one shared document.
        if isinstance(quick_document, QtCore.QObject):
            from .viewport import attach_code_viewports
            self._viewports = attach_code_viewports(
                quick_document, target, QtGui.QColor(self.palette.code_bg))
        return target

    def _copy_images(self, target: Any) -> None:
        """把自有文档里的图片资源按名字补注册到 ``target``。

        ``insertFragment`` 只搬文本/格式，文档级资源不跟着走；不补的话目标文档里的
        ``<img>`` 会解析成空图。名字由渲染器生成（``document._image``），这里只搬
        目标文档实际引用到的那些，避免把整份资源表无差别复制。
        """
        source = self.document.resource
        add = target.addResource
        kind = QtGui.QTextDocument.ResourceType.ImageResource
        for url in _image_names(target):
            image = source(kind.value, url)
            if image is not None:
                add(kind.value, url, image)

    def detach(self) -> None:
        """QML 控件销毁时调用：高亮器回到自有文档，内容重绘一遍。"""
        if self._highlighter is not None and self._highlighter.document() is not self.document:
            self._highlighter.setDocument(self.document)
        self.render()

    def dispose(self) -> None:
        if self._highlighter is not None:
            self._highlighter.setDocument(QTextDocument())
            self._highlighter = None
        self.document.clear()


def _image_names(document: Any):
    """文档里实际引用到的图片资源名（按首次出现顺序，去重）。

    只看字符格式里的 ``QTextImageFormat``，不解析 ``toHtml()``：后者会把整篇正文
    序列化一遍，在大文档上是白给的毫秒级开销。
    """
    seen = set()
    block = document.begin()
    while block.isValid():
        for spec in block.textFormats():
            fmt = spec.format
            if not fmt.isImageFormat():
                continue
            name = fmt.toImageFormat().name()
            if name and name not in seen:
                seen.add(name)
                yield QtCore.QUrl(name)
        block = block.next()


def _replace_dark(style: BodyStyle, dark: bool) -> BodyStyle:
    return BodyStyle(scale=style.scale, dark=dark, sans=style.sans, mono=style.mono)


def _replace_scale(style: BodyStyle, scale: float) -> BodyStyle:
    return BodyStyle(scale=scale, dark=style.dark, sans=style.sans, mono=style.mono)


def palettes() -> tuple:
    """(浅色, 深色) 调色板，供测试与主题切换引用。"""
    return LIGHT, DARK
