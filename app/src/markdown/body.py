"""正文文档对象：一份 ``QTextDocument`` + 代码高亮 + 主题 + 宽度。

``document.render_markdown`` 只负责「一次渲染」。真实界面还要处理：

- 窗口宽度变了，代码块 frame 的固定宽度要跟着重算（正文段落自己换行，不用重排）；
- 主题切换要同时换正文颜色与高亮配色，不能重建控件；
- 语法高亮器是 ``QSyntaxHighlighter``，必须有自己的引用，否则 Python 侧 GC 后
  高亮静默消失；
- QML 的 ``TextEdit`` 暴露 ``QQuickTextDocument``，要能直接接管同一份文档。

这些状态集中在这里，QML 适配层只做「把槽转发过来」。

**接管方式是把内容重新渲染进目标文档，不是搬块。** ``TextEdit`` 持有自己的
``QTextDocument``，不能替换实例；而把一份文档的块逐块 ``insertFragment`` 到另一份
里，图片资源（文档级）与表格结构都可能丢。渲染器本来就接受任意 ``document``
参数，直接以目标文档重渲染一遍最可靠，代价是一次排版（毫秒级）。
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
    from utils.qt_compat import QtGui

    QTextDocument = QtGui.QTextDocument
    QT_AVAILABLE = True
except ImportError:  # pragma: no cover
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
        self.document = QTextDocument()
        self.style = style or BodyStyle()
        self.content_width = float(content_width)
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
        if self._highlighter is not None:
            # 渲染改写了整篇文档，高亮器的旧布局格式全部作废，必须重跑；不重跑时
            # 代码块保持单色，且要等到下一次文档重排才「补」上颜色（实测如此）。
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
        """把内容渲染进 ``QQuickTextDocument`` 的文档，并让高亮器接管它。

        ``TextEdit`` 的文档实例由 QML 持有，所以这里是「往它的文档里重绘一遍」；
        高亮器通过 ``setDocument`` 移到同一份文档上。返回目标文档。
        """
        target = quick_document.textDocument()
        if self._highlighter is not None and target is not self.document:
            # QSyntaxHighlighter.setDocument 会把高亮器从旧文档摘下来挂到新文档。
            self._highlighter.setDocument(target)
        self.render(target)
        if self._highlighter is not None:
            self._highlighter.rehighlight()
        return target

    def detach(self) -> None:
        """回到自己的文档（QML 控件销毁时调用，避免高亮器挂在死文档上）。"""
        if self._highlighter is not None:
            self._highlighter.setDocument(self.document)
        self.render()

    def dispose(self) -> None:
        if self._highlighter is not None:
            self._highlighter.setDocument(QTextDocument())
            self._highlighter = None
        self.document.clear()


def _replace_dark(style: BodyStyle, dark: bool) -> BodyStyle:
    return BodyStyle(scale=style.scale, dark=dark, sans=style.sans, mono=style.mono)


def _replace_scale(style: BodyStyle, scale: float) -> BodyStyle:
    return BodyStyle(scale=scale, dark=style.dark, sans=style.sans, mono=style.mono)


def palettes() -> tuple:
    """(浅色, 深色) 调色板，供测试与主题切换引用。"""
    return LIGHT, DARK
