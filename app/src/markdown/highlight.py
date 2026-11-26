"""代码块语法高亮：``QSyntaxHighlighter`` + 原版 highlight.js 配色。

配色取自只读原版 ``deva/apps/desktop/src/renderer/src/styles/app.css:955–1075``
（highlight.js 主题的 ``.hljs-*`` 规则），浅色/深色各一套。这里只做**词法**着色，
不做语义分析：代码围栏的语言标签写在块属性 ``CODE_LANGUAGE_PROPERTY`` 上
（见 ``document._code``），高亮器逐块读它。

为什么不用 Pygments：构建产物只装 PySide6，不引额外依赖；原版配色是按
highlight.js 的 token 名（comment/keyword/string/number/title/type/attr）定义的，
直接照这些 token 名做词法扫描，颜色才能逐值对上。

多行结构用 ``setCurrentBlockState`` 跨块传递（Python 三引号、C 系块注释）。
语言不支持时不着色——不做「猜一个语法」的假高亮。
"""
from __future__ import annotations
from locale_runtime import tr

import re
from typing import Any, Dict, List, Optional, Pattern, Tuple

from markdown.document import BodyStyle, CODE_LANGUAGE_PROPERTY, DARK, LIGHT

try:  # pragma: no cover - 取决于环境有无 Qt
    from utils.qt_compat import QtGui

    QSyntaxHighlighter = QtGui.QSyntaxHighlighter
    QTextCharFormat = QtGui.QTextCharFormat
    QFont = QtGui.QFont
    QT_AVAILABLE = True
except ImportError:  # pragma: no cover
    QSyntaxHighlighter = object  # type: ignore[assignment,misc]
    QTextCharFormat = None  # type: ignore[assignment]
    QFont = None  # type: ignore[assignment]
    QT_AVAILABLE = False


# ── 配色（highlight.js 主题，浅/深两套）────────────────────────────────────
LIGHT_TOKENS = {
    "comment": "#008000",
    "keyword": "#0000ff",
    "string": "#a31515",
    "number": "#098658",
    "title": "#795e26",
    "type": "#267f99",
    "attr": "#001080",
    "meta": "#0070c1",
}
DARK_TOKENS = {
    "comment": "#6a9955",
    "keyword": "#569cd6",
    "string": "#ce9178",
    "number": "#b5cea8",
    "title": "#dcdcaa",
    "type": "#4ec9b0",
    "attr": "#9cdcfe",
    "meta": "#569cd6",
}
# 斜体只用于注释，与原版 ``.hljs-comment { font-style: italic }`` 一致。
ITALIC_TOKENS = frozenset({"comment"})


# ── 语言族 ────────────────────────────────────────────────────────────────
# 每个语言族给出：行注释、块注释、字符串定界符、关键字、类型名、是否把
# 「标识符后跟 (」当作函数名着色（highlight.js 的 title.function）。
class Language:
    __slots__ = ("name", "line_comment", "block_comment", "strings", "keywords",
                 "types", "call_is_title")

    def __init__(self, name: str, line_comment: Tuple[str, ...],
                 block_comment: Optional[Tuple[str, str]],
                 strings: Tuple[str, ...], keywords: Tuple[str, ...],
                 types: Tuple[str, ...] = (), call_is_title: bool = True) -> None:
        self.name = name
        self.line_comment = line_comment
        self.block_comment = block_comment
        self.strings = strings
        self.keywords = keywords
        self.types = types
        self.call_is_title = call_is_title


_PY_KEYWORDS = (
    "and", "as", "assert", "async", "await", "break", "class", "continue", "def",
    "del", "elif", "else", "except", "False", "finally", "for", "from", "global",
    "if", "import", "in", "is", "lambda", "None", "nonlocal", "not", "or", "pass",
    "raise", "return", "True", "try", "while", "with", "yield", "self", "cls",
)
_PY_TYPES = (
    "bool", "bytes", "dict", "float", "int", "list", "object", "set", "str",
    "tuple", "type", "Exception", "ValueError", "TypeError", "KeyError",
)
_C_KEYWORDS = (
    "abstract", "as", "async", "await", "break", "case", "catch", "class", "const",
    "continue", "default", "delete", "do", "else", "enum", "export", "extends",
    "final", "finally", "for", "from", "function", "goto", "if", "implements",
    "import", "in", "instanceof", "interface", "let", "namespace", "new", "of",
    "package", "private", "protected", "public", "return", "static", "struct",
    "super", "switch", "this", "throw", "throws", "try", "typedef", "typeof",
    "var", "void", "while", "with", "yield", "def", "elif", "lambda", "None",
    "True", "False", "fn", "mut", "pub", "use", "impl", "trait", "match", "loop",
    "go", "defer", "chan", "func", "range", "select", "type",
)
_SH_KEYWORDS = (
    "case", "do", "done", "elif", "else", "esac", "fi", "for", "function", "if",
    "in", "select", "then", "until", "while", "time", "export", "local", "return",
    "set", "source", "alias", "echo", "cd", "sudo", "git", "pip", "python",
    "python3", "npm", "yarn", "pnpm", "node", "curl",
)
_SQL_KEYWORDS = (
    "SELECT", "FROM", "WHERE", "INSERT", "INTO", "VALUES", "UPDATE", "SET",
    "DELETE", "CREATE", "TABLE", "INDEX", "DROP", "ALTER", "JOIN", "LEFT",
    "RIGHT", "INNER", "OUTER", "ON", "GROUP", "BY", "ORDER", "HAVING", "LIMIT",
    "OFFSET", "AND", "OR", "NOT", "NULL", "AS", "DISTINCT", "UNION", "ALL",
    "select", "from", "where", "insert", "into", "values", "update", "set",
    "delete", "create", "table", "join", "on", "group", "by", "order", "limit",
    "and", "or", "not", "null", "as", "distinct",
)
_YAML_KEYWORDS = ("true", "false", "null", "yes", "no", "on", "off")

LANGUAGES: Dict[str, Language] = {}


def _register(names: Tuple[str, ...], language: Language) -> None:
    for name in names:
        LANGUAGES[name] = language


_register(
    ("python", "py", "python3", "py3"),
    Language("python", ("#",), None, ('"""', "'''", '"', "'"), _PY_KEYWORDS, _PY_TYPES),
)
_register(
    ("javascript", "js", "jsx", "typescript", "ts", "tsx", "java", "c", "cpp",
     "c++", "cc", "h", "hpp", "cs", "csharp", "go", "golang", "rust", "rs",
     "kotlin", "kt", "swift", "php", "scala", "dart"),
    Language("clike", ("//",), ("/*", "*/"), ('"', "'", "`"), _C_KEYWORDS),
)
_register(
    ("bash", "sh", "shell", "zsh", "console", "shellsession", "dockerfile",
     "makefile", "make"),
    Language("shell", ("#",), None, ('"', "'"), _SH_KEYWORDS, (), False),
)
_register(
    ("json", "jsonc", "json5"),
    Language("json", ("//",), None, ('"',), ("true", "false", "null"), (), False),
)
_register(
    ("sql", "sqlite", "postgres", "postgresql", "mysql"),
    Language("sql", ("--",), ("/*", "*/"), ("'", '"'), _SQL_KEYWORDS, (), False),
)
_register(
    ("yaml", "yml", "toml", "ini"),
    Language("yaml", ("#",), None, ('"', "'"), _YAML_KEYWORDS, (), False),
)
_register(
    ("html", "xml", "svg", "xhtml"),
    Language("html", ("//",), ("<!--", "-->"), ('"', "'"), (), (), False),
)
_register(
    ("css", "scss", "less"),
    Language("css", ("//",), ("/*", "*/"), ('"', "'"), (), (), False),
)


def language_for(tag: str) -> Optional[Language]:
    """语言标签 → 词法族；未知标签返回 None（不着色）。"""
    return LANGUAGES.get((tag or "").strip().lower())


# ── 行内 token 的正则（按优先级拼成一条交替式）─────────────────────────────
def _escape(text: str) -> str:
    return re.escape(text)


def _string_patterns(delimiters: Tuple[str, ...]) -> List[Tuple[str, str]]:
    """每个定界符一条 ``(组名, 正则)``。

    正则的组名不能重复（``re`` 直接拒绝），所以每条模式有自己的组名
    ``string0``/``string1``…，着色时按前缀归回 ``string`` 这个 token。
    """
    patterns: List[Tuple[str, str]] = []
    for index, delimiter in enumerate(delimiters):
        body = r"(?:\\.|[^%s\\])*" % _escape(delimiter)
        patterns.append(("string%d" % index,
                         "%s%s%s" % (_escape(delimiter), body, _escape(delimiter))))
        # 未闭合的字符串：吃到行尾，着色到行尾（浏览器里也是这个观感）。
        patterns.append(("stringu%d" % index, "%s%s" % (_escape(delimiter), body)))
    return patterns


def _token_of(group: str) -> str:
    """正则组名 → 配色 token（``stringu2`` → ``string``）。"""
    return "string" if group.startswith("string") else group


_NUMBER = r"(?:\b0[xX][0-9a-fA-F]+|\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)"
_IDENT = r"[A-Za-z_$][A-Za-z0-9_$]*"

_CACHE: Dict[Tuple[str, bool], Pattern[str]] = {}


def _compiled(language: Language, call_is_title: bool) -> Pattern[str]:
    key = (language.name, call_is_title)
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    parts: List[str] = []
    for comment in language.line_comment:
        parts.append("(?P<comment>%s[^\\n]*)" % _escape(comment))
    for name, pattern in _string_patterns(language.strings):
        parts.append("(?P<%s>%s)" % (name, pattern))
    parts.append("(?P<number>%s)" % _NUMBER)
    if language.keywords:
        words = "|".join(_escape(word) for word in sorted(language.keywords, key=len, reverse=True))
        parts.append("(?P<keyword>\\b(?:%s)\\b)" % words)
    if language.types:
        words = "|".join(_escape(word) for word in sorted(language.types, key=len, reverse=True))
        parts.append("(?P<type>\\b(?:%s)\\b)" % words)
    if call_is_title:
        parts.append("(?P<title>\\b%s(?=\\s*\\())" % _IDENT)
    parts.append("(?P<attr>\\b%s\\b)" % _IDENT)
    pattern = re.compile("|".join(parts))
    _CACHE[key] = pattern
    return pattern


class CodeHighlighter(QSyntaxHighlighter):
    """按块属性里的语言标签着色；主题切换只换 ``QTextCharFormat``。"""

    # 跨块状态：块注释与 Python 三引号。0 表示行内起始。
    STATE_NONE = 0
    STATE_BLOCK_COMMENT = 1
    STATE_TRIPLE_DOUBLE = 2
    STATE_TRIPLE_SINGLE = 3

    def __init__(self, document: Any, style: Optional[BodyStyle] = None) -> None:
        if not QT_AVAILABLE:  # pragma: no cover - 无 Qt 时不该构造
            raise ImportError(tr('legacy.f528c08df47d'))
        super().__init__(document)
        self.style = style or BodyStyle()
        self._formats: Dict[str, Any] = {}
        self._language_name = ""
        self.set_style(self.style)

    # ── 主题 ──────────────────────────────────────────────────────────────
    def set_style(self, style: BodyStyle) -> None:
        self.style = style
        palette = DARK_TOKENS if style.dark else LIGHT_TOKENS
        formats: Dict[str, Any] = {}
        for token, color in palette.items():
            fmt = QTextCharFormat()
            fmt.setForeground(QtGui.QColor(color))
            if token in ITALIC_TOKENS:
                fmt.setFontItalic(True)
            formats[token] = fmt
        self._formats = formats
        self.rehighlight()

    def set_language_default(self, language: str) -> None:
        """没有语言标签的块使用这个语言（默认不着色）。"""
        self._language_name = language or ""
        self.rehighlight()

    # ── 逐块 ──────────────────────────────────────────────────────────────
    def highlightBlock(self, text: str) -> None:
        block = self.currentBlock()
        tag = ""
        if block.isValid():
            value = block.blockFormat().property(CODE_LANGUAGE_PROPERTY)
            # 空标签在 QString 属性里往返后可能不是 ""（PySide 会给出空列表），
            # 所以只认非空字符串；其余一律当作「没有标签」，交给默认语言。
            if isinstance(value, str):
                tag = value.strip()
        tag = tag or self._language_name
        language = language_for(tag)
        if language is None:
            self.setCurrentBlockState(self.STATE_NONE)
            return

        state = self.previousBlockState()
        if state < 0:
            state = self.STATE_NONE
        start = 0
        # 续接上一块未闭合的结构。
        if state == self.STATE_BLOCK_COMMENT and language.block_comment:
            start = self._consume_until(text, 0, language.block_comment[1],
                                        self.STATE_BLOCK_COMMENT, "comment")
        elif state == self.STATE_TRIPLE_DOUBLE:
            start = self._consume_until(text, 0, '"""', self.STATE_TRIPLE_DOUBLE, "string")
        elif state == self.STATE_TRIPLE_SINGLE:
            start = self._consume_until(text, 0, "'''", self.STATE_TRIPLE_SINGLE, "string")
        if start < 0:  # 结构在行尾仍未闭合
            return

        if language.block_comment:
            opened = self._scan_block_comment(text, start, language)
            if opened < 0:
                return
            start = opened

        if language.name == "python":
            opened = self._scan_triple(text, start)
            if opened < 0:
                return
            start = opened

        self._paint(text, start, language)
        self.setCurrentBlockState(self.STATE_NONE)

    # ── 辅助 ──────────────────────────────────────────────────────────────
    def _consume_until(self, text: str, start: int, terminator: str, state: int,
                       token: str) -> int:
        """从 ``start`` 起着色到 ``terminator``（含）；未闭合则整行着色并保持状态。"""
        index = text.find(terminator, start)
        if index < 0:
            if start < len(text):
                self.setFormat(start, len(text) - start, self._formats[token])
            self.setCurrentBlockState(state)
            return -1
        end = index + len(terminator)
        self.setFormat(start, end - start, self._formats[token])
        return end

    def _scan_block_comment(self, text: str, start: int, language: Language) -> int:
        opener, closer = language.block_comment  # type: ignore[misc]
        index = text.find(opener, start)
        if index < 0:
            return start
        return self._consume_until(text, index, closer, self.STATE_BLOCK_COMMENT, "comment")

    def _scan_triple(self, text: str, start: int) -> int:
        """Python 三引号字符串：跨块着色，其余单行规则照常。"""
        best = -1
        best_terminator = ""
        best_state = self.STATE_NONE
        for terminator, state in (('"""', self.STATE_TRIPLE_DOUBLE),
                                  ("'''", self.STATE_TRIPLE_SINGLE)):
            index = text.find(terminator, start)
            if index >= 0 and (best < 0 or index < best):
                best = index
                best_terminator = terminator
                best_state = state
        if best < 0:
            return start
        # 三引号之前的片段正常着色，之后按照字符串处理。结束符要从开定界符
        # **之后**开始找，否则找到的是同一个开定界符，三引号字符串永远不会进入
        # 跨块状态（下一行会被当成普通代码着成 attr 色）。
        self._paint(text, start, language_for("python"), limit=best)  # type: ignore[arg-type]
        self.setFormat(best, len(best_terminator), self._formats["string"])
        after = self._consume_until(text, best + len(best_terminator), best_terminator,
                                    best_state, "string")
        if after < 0:
            return -1
        return after

    def _paint(self, text: str, start: int, language: Optional[Language], limit: int = -1) -> None:
        if language is None:
            return
        end = len(text) if limit < 0 else limit
        if end <= start:
            return
        for match in _compiled(language, language.call_is_title).finditer(text, start, end):
            group = match.lastgroup
            if group is None:
                continue
            fmt = self._formats.get(_token_of(group))
            if fmt is not None:
                self.setFormat(match.start(), match.end() - match.start(), fmt)


def attach(document: Any, style: Optional[BodyStyle] = None) -> CodeHighlighter:
    """给文档挂一个高亮器；返回的对象必须由调用方持有（否则被 GC）。"""
    return CodeHighlighter(document, style)


def token_colors(dark: bool) -> Dict[str, str]:
    """测试与文档用：当前主题的 token → 颜色。"""
    return dict(DARK_TOKENS if dark else LIGHT_TOKENS)
