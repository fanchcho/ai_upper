"""CommonMark 子集的解析器：块级结构与行内标记，产出与 Qt 无关的纯数据树。

覆盖范围（即正文层要渲染的全部元素）：
标题（ATX）、段落、行内代码、粗体/斜体/删除线、链接与自动链接、图片、
有序/无序/任务列表（可嵌套）、引用（可嵌套）、表格（含对齐）、围栏代码块（含语言标签）、
分隔线。

设计口径：
- **不 import Qt**：解析器是纯函数，在没有 Qt 的解释器上也能单测，Cython 也能单独编译；
- **不猜**：未闭合的标记按字面文本保留，不吞内容。宁可少渲染，不能把用户的原文吃掉；
- **保留原始行号**：每个块带 ``line``，出错时能指回源文，也方便测试断言。

行内解析采用「先切分、再递归」：扫描到 ``**``/``[`` 这类起始符时找配对结束符，配对成功
就产出一个带子节点的容器（strong/em/link/image），配对失败就退化为字面文本继续扫。
"""
from __future__ import annotations

import re
from typing import Any, Optional

# 一个块或行内节点。用普通 dict 而不是 dataclass：解析结果要能被 JSON 化
# （测试断言、跨进程传给界面层），dict 最省事，且 3.8 上没有注解求值问题。
Block = dict
Inline = dict

# 行内特殊字符：遇到它们才需要进入「找配对」逻辑。
# ``|`` 也在 CommonMark 的可转义标点里：表格单元格里写 ``\|`` 必须显示成竖线，
# 否则用户看到的是一个多余的反斜杠。
_ESCAPABLE = set("\\`*_~[]!<&|")

_CODE_FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})\s*([^\s`]*)\s*$")
_HEADING = re.compile(r"^( {0,3})(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
_HRULE = re.compile(r"^ {0,3}((\*[ \t]*){3,}|(-[ \t]*){3,}|(_[ \t]*){3,})$")
_UL_ITEM = re.compile(r"^( *)([-+*])(?:[ \t]+(.*))?$")
_OL_ITEM = re.compile(r"^( *)(\d{1,9})([.)])(?:[ \t]+(.*))?$")
_TASK = re.compile(r"^\[([ xX])\][ \t]+(.*)$", re.DOTALL)
_QUOTE = re.compile(r"^ {0,3}>[ \t]?(.*)$")
_TABLE_SEP = re.compile(r"^ {0,3}\|?[ \t]*:?-{1,}:?[ \t]*(\|[ \t]*:?-{1,}:?[ \t]*)*\|?[ \t]*$")


# ── 块级 ──────────────────────────────────────────────────────────────────
def parse_markdown(source: str) -> list[Block]:
    """源文 → 块列表。空行分块；容器块（列表/引用）递归解析其内容行。"""
    text = source.replace("\r\n", "\n").replace("\r", "\n").expandtabs(4)
    lines = text.split("\n")
    blocks, _ = _parse_blocks(lines)
    return blocks


def _parse_blocks(lines: list[str]) -> tuple[list[Block], int]:
    """解析到列表结束；返回（块列表，消耗的行数）。

    容器块递归时把子行切出来再调本函数，因此这里只处理「一行行往下吃」的扁平逻辑。
    """
    blocks: list[Block] = []
    index = 0
    total = len(lines)
    while index < total:
        line = lines[index]
        if not line.strip():
            index += 1
            continue

        fence = _CODE_FENCE.match(line)
        if fence:
            index = _consume_fence(lines, index, fence, blocks)
            continue

        heading = _HEADING.match(line)
        if heading:
            blocks.append(
                {
                    "type": "heading",
                    "level": len(heading.group(2)),
                    "children": parse_inline((heading.group(3) or "").strip()),
                    "line": index,
                }
            )
            index += 1
            continue

        if _HRULE.match(line):
            blocks.append({"type": "hr", "line": index})
            index += 1
            continue

        if _QUOTE.match(line):
            index = _consume_quote(lines, index, blocks)
            continue

        if _is_table_start(lines, index):
            index = _consume_table(lines, index, blocks)
            continue

        if _UL_ITEM.match(line) or _OL_ITEM.match(line):
            index = _consume_list(lines, index, blocks)
            continue

        index = _consume_paragraph(lines, index, blocks)
    return blocks, index


def _consume_fence(lines: list[str], index: int, fence: Any, blocks: list[Block]) -> int:
    """围栏代码块：```` ```lang ```` 开头，直到同种字符、长度不短于开头的围栏。"""
    marker = fence.group(2)
    language = (fence.group(3) or "").strip()
    body: list[str] = []
    cursor = index + 1
    while cursor < len(lines):
        candidate = lines[cursor]
        if re.match(r"^ {0,3}%s{%d,}\s*$" % (re.escape(marker[0]), len(marker)), candidate):
            cursor += 1
            break
        body.append(candidate)
        cursor += 1
    blocks.append(
        {
            "type": "code",
            "language": language,
            "text": "\n".join(body),
            "line": index,
        }
    )
    return cursor


def _consume_quote(lines: list[str], index: int, blocks: list[Block]) -> int:
    """引用：连续 ``>`` 行（含空引用行）成一个块，内部再按块级规则解析（支持嵌套）。"""
    inner: list[str] = []
    cursor = index
    while cursor < len(lines):
        match = _QUOTE.match(lines[cursor])
        if match is None:
            break
        inner.append(match.group(1))
        cursor += 1
    children, _ = _parse_blocks(inner)
    blocks.append({"type": "quote", "children": children, "line": index})
    return cursor


def _split_row(line: str) -> list[str]:
    """表格行切单元格：去掉首尾竖线，按未转义的 ``|`` 切。"""
    text = line.strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|") and not text.endswith("\\|"):
        text = text[:-1]
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    for char in text:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            current.append(char)
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
            continue
        current.append(char)
    cells.append("".join(current).strip())
    return cells


def _is_table_start(lines: list[str], index: int) -> bool:
    """表头行 + 分隔行。分隔行的单元格数必须与表头一致（GFM 的判定口径）。"""
    if index + 1 >= len(lines):
        return False
    if "|" not in lines[index]:
        return False
    if not _TABLE_SEP.match(lines[index + 1]):
        return False
    header = _split_row(lines[index])
    separator = _split_row(lines[index + 1])
    if not header or len(header) != len(separator):
        return False
    return all(re.match(r"^:?-+:?$", cell) for cell in separator)


def _alignment(cell: str) -> str:
    left = cell.startswith(":")
    right = cell.endswith(":")
    if left and right:
        return "center"
    if right:
        return "right"
    return "left"


def _consume_table(lines: list[str], index: int, blocks: list[Block]) -> int:
    header = _split_row(lines[index])
    aligns = [_alignment(cell) for cell in _split_row(lines[index + 1])]
    rows: list[list[list[Inline]]] = []
    cursor = index + 2
    while cursor < len(lines):
        line = lines[cursor]
        if not line.strip() or "|" not in line:
            break
        cells = _split_row(line)
        if len(cells) < len(header):
            cells += [""] * (len(header) - len(cells))
        rows.append([parse_inline(cell) for cell in cells[: len(header)]])
        cursor += 1
    blocks.append(
        {
            "type": "table",
            "align": aligns,
            "header": [parse_inline(cell) for cell in header],
            "rows": rows,
            "line": index,
        }
    )
    return cursor


def _consume_list(lines: list[str], index: int, blocks: list[Block]) -> int:
    """列表：同一缩进的连续项成一组；有序/无序/任务用 ``ordered``/``task`` 标记。

    嵌套的判断口径是缩进：子项缩进大于本项内容起点，就归到本项的内部行里递归解析。
    """
    first = _UL_ITEM.match(lines[index]) or _OL_ITEM.match(lines[index])
    ordered = _UL_ITEM.match(lines[index]) is None
    base_indent = len(first.group(1))
    start = int(first.group(2)) if ordered else 1
    items: list[dict[str, Any]] = []
    cursor = index

    while cursor < len(lines):
        line = lines[cursor]
        if not line.strip():
            # 列表项之间的空行：后面还有同缩进项就继续，否则列表结束。
            look = cursor + 1
            while look < len(lines) and not lines[look].strip():
                look += 1
            if look < len(lines) and _same_list(lines[look], ordered, base_indent):
                cursor = look
                continue
            break
        item = _UL_ITEM.match(line) or _OL_ITEM.match(line)
        if item is None or len(item.group(1)) != base_indent:
            # 缩进更深的行属于上一项的内部内容（嵌套列表/续行）。
            if items and (len(line) - len(line.lstrip())) > base_indent:
                items[-1]["inner"].append(line)
                cursor += 1
                continue
            break
        if (item.re is _UL_ITEM and ordered) or (item.re is _OL_ITEM and not ordered):
            break
        # 无序项的分组：(缩进, 标记, 正文)；有序项多一个分隔符分组，正文在第 4 组。
        content = (item.group(4) if ordered else item.group(3)) or ""
        task = None
        task_match = _TASK.match(content)
        if task_match:
            task = task_match.group(1) in "xX"
            content = task_match.group(2)
        items.append(
            {
                "text": content,
                "task": task,
                "inner": [],
                "line": cursor,
            }
        )
        cursor += 1
        # 紧接着的、缩进大于列表基线的行也是本项内部内容。
        while cursor < len(lines):
            follow = lines[cursor]
            if not follow.strip():
                break
            indent = len(follow) - len(follow.lstrip())
            if indent > base_indent:
                items[-1]["inner"].append(follow)
                cursor += 1
                continue
            break

    for item in items:
        children = (
            [{"type": "paragraph", "children": parse_inline(item["text"]), "line": item["line"]}]
            if item["text"].strip()
            else []
        )
        if item["inner"]:
            nested, _ = _parse_blocks(_dedent(item["inner"], base_indent + 2))
            children.extend(nested)
        item["children"] = children
        item["loose"] = len(children) > 1

    blocks.append(
        {
            "type": "list",
            "ordered": ordered,
            "start": start,
            "task": any(item["task"] is not None for item in items),
            "items": [
                {
                    "task": item["task"],
                    "children": item["children"],
                    "loose": item["loose"],
                    "line": item["line"],
                }
                for item in items
            ],
            "line": index,
        }
    )
    return cursor


def _same_list(line: str, ordered: bool, indent: int) -> bool:
    match = (_OL_ITEM if ordered else _UL_ITEM).match(line)
    return match is not None and len(match.group(1)) == indent


def _dedent(lines: list[str], amount: int) -> list[str]:
    out: list[str] = []
    for line in lines:
        strip = min(amount, len(line) - len(line.lstrip()))
        out.append(line[strip:])
    return out


def _consume_paragraph(lines: list[str], index: int, blocks: list[Block]) -> int:
    """段落：吃到空行或下一个块起始为止（与 CommonMark 的「段落中断」一致）。"""
    body: list[str] = []
    cursor = index
    while cursor < len(lines):
        line = lines[cursor]
        if not line.strip():
            break
        if body and _starts_block(lines, cursor):
            break
        body.append(line.strip())
        cursor += 1
    blocks.append(
        {
            "type": "paragraph",
            "children": parse_inline("\n".join(body)),
            "line": index,
        }
    )
    return cursor


def _starts_block(lines: list[str], index: int) -> bool:
    line = lines[index]
    return bool(
        _CODE_FENCE.match(line)
        or _HEADING.match(line)
        or _HRULE.match(line)
        or _QUOTE.match(line)
        or _UL_ITEM.match(line)
        or _OL_ITEM.match(line)
        or _is_table_start(lines, index)
    )


# ── 行内 ──────────────────────────────────────────────────────────────────
# 行内节点形状（``type`` + 内容）：
#   {"type": "text", "text": str}
#   {"type": "code", "text": str}
#   {"type": "strong"|"em"|"del", "children": [...]}
#   {"type": "link", "href": str, "title": str, "children": [...]}
#   {"type": "image", "src": str, "alt": str, "title": str}
#   {"type": "autolink", "href": str}       —— 裸 URL 与 <a@b.c> 形式
#   {"type": "br"}                          —— 行内硬换行
def parse_inline(text: str) -> list[Inline]:
    """行内标记解析。反斜杠转义优先，其次代码段（内容不再解析），再是成对标记。"""
    out: list[Inline] = []
    buffer: list[str] = []
    index = 0
    length = len(text)

    def flush() -> None:
        if buffer:
            out.append({"type": "text", "text": "".join(buffer)})
            buffer.clear()

    while index < length:
        char = text[index]

        # 反斜杠转义：只对 Markdown 的 ASCII 标点生效，其余保留反斜杠。
        if char == "\\" and index + 1 < length and text[index + 1] in _ESCAPABLE:
            buffer.append(text[index + 1])
            index += 2
            continue

        # 行内代码：等长反引号配对，内部不解析。
        if char == "`":
            run = _run_length(text, index, "`")
            close = _find_run(text, index + run, "`", run)
            if close != -1:
                flush()
                code = text[index + run : close]
                if code.startswith(" ") and code.endswith(" ") and code.strip():
                    code = code[1:-1]
                out.append({"type": "code", "text": code})
                index = close + run
                continue
            buffer.append(char)
            index += 1
            continue

        # 图片 / 链接：[text](href) 与 ![alt](src)。
        if char == "!" and index + 1 < length and text[index + 1] == "[":
            parsed = _parse_link(text, index + 1)
            if parsed is not None:
                flush()
                node, index = parsed
                node["type"] = "image"
                node["src"] = node.pop("href")
                node["alt"] = _plain_text(node.pop("children"))
                out.append(node)
                continue
        if char == "[":
            parsed = _parse_link(text, index)
            if parsed is not None:
                flush()
                node, index = parsed
                node["type"] = "link"
                out.append(node)
                continue

        # 自动链接：<https://…> / <a@b.c>
        if char == "<":
            close = text.find(">", index + 1)
            if close != -1:
                inner = text[index + 1 : close]
                if inner.startswith(("http://", "https://", "mailto:")) or (
                    "@" in inner and " " not in inner and "." in inner
                ):
                    flush()
                    href = inner if "://" in inner or inner.startswith("mailto:") else "mailto:" + inner
                    out.append({"type": "autolink", "href": href})
                    index = close + 1
                    continue

        # 粗体 / 斜体 / 删除线：** / __ / * / _ / ~~。双字符优先。
        for marker, node_type in (("**", "strong"), ("__", "strong"), ("~~", "del"), ("*", "em"), ("_", "em")):
            if not text.startswith(marker, index):
                continue
            # 下划线类标记要求**两侧**都不是单词字符：只看结束符会把
            # ``snake_case_word`` 里的第一个下划线当成开标记，吞掉半个标识符。
            if marker[0] == "_" and index > 0 and text[index - 1].isalnum():
                continue
            close = _find_marker(text, index + len(marker), marker)
            if close == -1:
                continue
            inner = text[index + len(marker) : close]
            if not inner.strip():
                continue
            flush()
            out.append({"type": node_type, "children": parse_inline(inner)})
            index = close + len(marker)
            break
        else:
            # 硬换行：行尾两个空格或反斜杠 + 换行。
            if char == "\n":
                if buffer and "".join(buffer).endswith("  "):
                    while buffer and "".join(buffer).endswith(" "):
                        buffer.pop()
                    flush()
                    out.append({"type": "br"})
                else:
                    buffer.append(char)
                index += 1
                continue
            buffer.append(char)
            index += 1
            continue
        # 上面 for 的 break 分支已前进 index；这里不再额外处理。
    flush()
    return out


def _parse_link(text: str, start: int) -> Optional[tuple[Inline, int]]:
    """从 ``[`` 起解析 ``[label](href "title")``；不成立返回 None（按字面处理）。"""
    depth = 0
    cursor = start
    while cursor < len(text):
        if text[cursor] == "\\":
            cursor += 2
            continue
        if text[cursor] == "[":
            depth += 1
        elif text[cursor] == "]":
            depth -= 1
            if depth == 0:
                break
        cursor += 1
    if cursor >= len(text) or depth != 0:
        return None
    label = text[start + 1 : cursor]
    if cursor + 1 >= len(text) or text[cursor + 1] != "(":
        return None
    close = _matching_paren(text, cursor + 1)
    if close == -1:
        return None
    target = text[cursor + 2 : close].strip()
    title = ""
    match = re.match(r'^(\S+)\s+"([^"]*)"\s*$', target)
    if match:
        target, title = match.group(1), match.group(2)
    elif target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    return (
        {"type": "link", "href": target, "title": title, "children": parse_inline(label)},
        close + 1,
    )


def _matching_paren(text: str, start: int) -> int:
    depth = 0
    cursor = start
    while cursor < len(text):
        char = text[cursor]
        if char == "\\":
            cursor += 2
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return cursor
        cursor += 1
    return -1


def _find_marker(text: str, start: int, marker: str) -> int:
    """找配对结束位置；下划线类标记要求两侧不是单词字符（避免 snake_case 被吃掉）。"""
    cursor = start
    while cursor < len(text):
        found = text.find(marker, cursor)
        if found == -1:
            return -1
        if text[found - 1] == "\\":
            cursor = found + len(marker)
            continue
        if marker[0] == "_":
            before = text[found - 1] if found > 0 else ""
            after = text[found + len(marker)] if found + len(marker) < len(text) else ""
            if before.isalnum() and after.isalnum():
                cursor = found + len(marker)
                continue
        return found
    return -1


def _run_length(text: str, start: int, char: str) -> int:
    cursor = start
    while cursor < len(text) and text[cursor] == char:
        cursor += 1
    return cursor - start


def _find_run(text: str, start: int, char: str, length: int) -> int:
    cursor = start
    while cursor < len(text):
        found = text.find(char, cursor)
        if found == -1:
            return -1
        run = _run_length(text, found, char)
        if run == length:
            return found
        cursor = found + run
    return -1


def _plain_text(nodes: list[Inline]) -> str:
    """行内树的纯文本投影（图片 alt、链接文字做标题用）。"""
    parts: list[str] = []
    for node in nodes:
        if "text" in node:
            parts.append(str(node["text"]))
        if node.get("children"):
            parts.append(_plain_text(node["children"]))
    return "".join(parts)


__all__ = ["Block", "Inline", "parse_inline", "parse_markdown"]
