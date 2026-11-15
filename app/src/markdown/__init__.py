"""Markdown → QTextDocument 的正文层。

两层：
- ``parser``：纯 Python 的 CommonMark 子集解析器（不 import Qt，可在无 Qt 的解释器上单测）；
- ``document``：把解析结果写进 ``QTextDocument``（标题、列表、表格、代码块、图片等）。

为什么不用 ``QTextDocument.setMarkdown()``：Qt 自带的 Markdown 导入不保留代码块的语言标签
（无法接语法高亮）、表格边框/单元格内边距不可控、嵌套引用的缩进与设计稿对不上。
用户选定的路线是「正文用 QTextDocument」，没规定必须用 Qt 自带的解析器；自建解析器
才能逐条对齐原版 CSS 的排版规则（见 docs/audit/qml-shell-audit.md §5.3）。
"""
from markdown.parser import Block, Inline, parse_inline, parse_markdown

__all__ = ["Block", "Inline", "parse_inline", "parse_markdown"]
