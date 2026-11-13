"""从 Office Open XML（.docx / .xlsx / .pptx）里取出纯文字。

逐条移植自 Deva `apps/desktop/src/main/services/office-text.ts`：三种格式都是 zip 包里的
XML，只解压需要的那几项、按标签取文字，不保留格式、不含图片。旧版二进制格式
（.doc / .xls / .ppt）与加密文件不是 zip，解析失败返回 None。

只用标准库 `zipfile` + `re`，不引入 python-docx / openpyxl 之类的依赖（Deva 用的是
`fflate` 解压，同样零业务依赖）。
"""
from __future__ import annotations

import re
import zipfile
from io import BytesIO
from typing import Optional

OFFICE_EXT = frozenset({".docx", ".xlsx", ".pptx"})

_ENTITY = re.compile(r"&(lt|gt|amp|quot|apos|#\d+|#x[0-9a-fA-F]+);")


def decode_xml(text: str) -> str:
    """XML 实体解码（文字节点里的 &lt; &amp; &#20013; 等）。"""

    def repl(match: "re.Match[str]") -> str:
        name = match.group(1)
        if name == "lt":
            return "<"
        if name == "gt":
            return ">"
        if name == "amp":
            return "&"
        if name == "quot":
            return '"'
        if name == "apos":
            return "'"
        code = int(name[2:], 16) if name[1] in "xX" else int(name[1:], 10)
        return chr(code) if 0 <= code <= 0x10FFFF else match.group(0)

    return _ENTITY.sub(repl, text)


def tidy(text: str) -> str:
    """收尾：去掉行尾空白，连续空行最多留一个。"""
    lines = [line.rstrip(" \t") for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _by_number(name: str) -> int:
    match = re.search(r"(\d+)\.xml$", name)
    return int(match.group(1)) if match else 0


_PARAGRAPH_RE = {
    "w": re.compile(
        r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>"
        r"|<w:tab/>"
        r"|<w:(?:br|cr)\b[^>]*/>"
        r"|</w:p>"
        r"|<w:tbl(?:\s[^>]*)?>"
        r"|</w:tbl>"
        r"|</w:tc>"
        r"|</w:tr>"
    ),
    "a": re.compile(
        r"<a:t(?:\s[^>]*)?>([^<]*)</a:t>"
        r"|<a:tab/>"
        r"|<a:(?:br|cr)\b[^>]*/>"
        r"|</a:p>"
        r"|<a:tbl(?:\s[^>]*)?>"
        r"|</a:tbl>"
        r"|</a:tc>"
        r"|</a:tr>"
    ),
}


def paragraph_text(xml: str, ns: str) -> str:
    """段落类文字（Word 正文、PowerPoint 页面）。

    文字节点拼接，段落结束换行；表格里一行一行写，单元格之间用「 | 」。ns 是标签前缀：
    Word 为 ``w``，DrawingML（PowerPoint）为 ``a``。
    """
    pattern = _PARAGRAPH_RE[ns]
    out: list[str] = []
    depth = 0
    for match in pattern.finditer(xml):
        tag = match.group(0)
        if match.group(1) is not None:
            out.append(match.group(1))
        elif tag == f"<{ns}:tab/>":
            out.append("\t")
        elif (
            tag.startswith(f"<{ns}:br")
            or tag.startswith(f"<{ns}:cr")
            or tag == f"</{ns}:p>"
        ):
            out.append(" " if depth else "\n")
        elif tag.startswith(f"<{ns}:tbl"):
            depth += 1
            if out and not out[-1].endswith("\n"):
                out.append("\n")
        elif tag == f"</{ns}:tbl>":
            depth = max(0, depth - 1)
        elif tag == f"</{ns}:tc>":
            joined = "".join(out).rstrip(" ")
            out = [joined, " | "]
        elif tag == f"</{ns}:tr>":
            joined = "".join(out)
            if joined.endswith(" | "):
                joined = joined[: -len(" | ")]
            out = [joined, "\n"]
    return tidy(decode_xml("".join(out)))


def docx_text(files: dict[str, bytes]) -> Optional[str]:
    doc = files.get("word/document.xml")
    return paragraph_text(doc.decode("utf-8", errors="replace"), "w") if doc else None


def pptx_text(files: dict[str, bytes]) -> Optional[str]:
    slides = sorted(
        (name for name in files if re.match(r"^ppt/slides/slide\d+\.xml$", name)),
        key=_by_number,
    )
    if not slides:
        return None
    parts = []
    for index, name in enumerate(slides):
        body = paragraph_text(files[name].decode("utf-8", errors="replace"), "a")
        parts.append(f"## 第 {index + 1} 页\n{body}".strip())
    return "\n\n".join(parts)


_RUN_TEXT = re.compile(r"<t(?:\s[^>]*)?>([^<]*)</t>")


def runs_text(xml: str) -> str:
    return decode_xml("".join(match.group(1) for match in _RUN_TEXT.finditer(xml)))


def col_index(ref: str) -> int:
    """「AB12」→ 列下标（A = 0）。"""
    match = re.match(r"^[A-Z]+", ref)
    letters = match.group(0) if match else ""
    value = 0
    for ch in letters:
        value = value * 26 + (ord(ch) - 64)
    return value - 1


def xlsx_text(files: dict[str, bytes]) -> Optional[str]:
    shared: list[str] = []
    ss = files.get("xl/sharedStrings.xml")
    if ss:
        for match in re.finditer(r"<si>([\s\S]*?)</si>", ss.decode("utf-8", errors="replace")):
            shared.append(runs_text(match.group(1)))

    # 工作表名与对应文件：workbook.xml 的 <sheet name r:id> → 关系文件里的 Target；
    # 对不上的按文件名顺序补。
    sheets: list[tuple[str, str]] = []
    wb_bytes = files.get("xl/workbook.xml")
    rels_bytes = files.get("xl/_rels/workbook.xml.rels")
    wb = wb_bytes.decode("utf-8", errors="replace") if wb_bytes else ""
    rels = rels_bytes.decode("utf-8", errors="replace") if rels_bytes else ""
    targets: dict[str, str] = {}
    for match in re.finditer(r"<Relationship\b([^>]*)/?>", rels):
        attrs = match.group(1)
        rid = re.search(r'\bId="([^"]+)"', attrs)
        target = re.search(r'\bTarget="([^"]+)"', attrs)
        if rid and target:
            targets[rid.group(1)] = re.sub(r"^/?(xl/)?", "xl/", target.group(1))
    for match in re.finditer(r"<sheet\b([^>]*)/?>", wb):
        attrs = match.group(1)
        name = re.search(r'\bname="([^"]*)"', attrs)
        rid = re.search(r'\br:id="([^"]+)"', attrs)
        path = targets.get(rid.group(1)) if rid else None
        if name is not None and path and path in files:
            sheets.append((decode_xml(name.group(1)), path))
    listed = {path for _, path in sheets}
    extra = sorted(
        (
            name
            for name in files
            if re.match(r"^xl/worksheets/sheet\d+\.xml$", name) and name not in listed
        ),
        key=_by_number,
    )
    for path in extra:
        sheets.append((path[path.rfind("/") + 1 : -4], path))
    if not sheets:
        return None

    parts: list[str] = []
    for name, path in sheets:
        lines: list[str] = []
        body = files[path].decode("utf-8", errors="replace")
        # 空行可能是自闭合的 <row r="5"/>，须单独认出，否则会吞掉下一行。
        for row in re.finditer(r"<row\b([^>]*?)(?:/>|>([\s\S]*?)</row>)", body):
            inner = row.group(2)
            if not inner:
                continue
            cells: list[str] = []
            for cell in re.finditer(r"<c\b([^>]*?)(?:/>|>([\s\S]*?)</c>)", inner):
                attrs = cell.group(1)
                cell_inner = cell.group(2) or ""
                ref = re.search(r'\br="([A-Z]+\d+)"', attrs)
                cell_type = re.search(r'\bt="([^"]+)"', attrs)
                value = re.search(r"<v>([^<]*)</v>", cell_inner)
                kind = cell_type.group(1) if cell_type else ""
                raw = value.group(1) if value else None
                if kind == "s":
                    text = shared[int(raw)] if raw is not None and raw.isdigit() else ""
                elif kind == "inlineStr":
                    text = runs_text(cell_inner)
                elif kind == "b":
                    text = "TRUE" if raw == "1" else "FALSE" if raw == "0" else ""
                else:
                    text = decode_xml(raw) if raw is not None else ""
                at = col_index(ref.group(1)) if ref else len(cells)
                while len(cells) <= at:
                    cells.append("")
                cells[at] = re.sub(r"[\t\r\n]+", " ", text)
            while cells and not cells[-1]:
                cells.pop()
            if not cells:
                continue
            row_no = re.search(r'\br="(\d+)"', row.group(1))
            lines.append(f"{row_no.group(1) if row_no else len(lines) + 1}\t" + "\t".join(cells))
        parts.append(f"## 工作表：{name}\n" + ("\n".join(lines) if lines else "（空）"))
    return "（每行开头是表格的行号，其后各列以制表符分隔）\n\n" + "\n\n".join(parts)


def office_text(data: bytes, ext: str) -> Optional[str]:
    """取 Office 文件的文字；不是这三种格式、不是 zip（旧版二进制 / 加密）或缺少正文部件时返回 None。"""
    suffix = ext.lower()
    if suffix not in OFFICE_EXT:
        return None
    if suffix == ".docx":
        want = lambda name: name == "word/document.xml"  # noqa: E731
    elif suffix == ".pptx":
        want = lambda name: bool(re.match(r"^ppt/slides/slide\d+\.xml$", name))  # noqa: E731
    else:
        want = lambda name: (  # noqa: E731
            name in ("xl/sharedStrings.xml", "xl/workbook.xml", "xl/_rels/workbook.xml.rels")
            or bool(re.match(r"^xl/worksheets/sheet\d+\.xml$", name))
        )
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            files = {
                info.filename: archive.read(info)
                for info in archive.infolist()
                if want(info.filename)
            }
    except (zipfile.BadZipFile, OSError, RuntimeError):
        return None
    try:
        if suffix == ".docx":
            return docx_text(files)
        if suffix == ".pptx":
            return pptx_text(files)
        return xlsx_text(files)
    except (KeyError, ValueError, IndexError):
        return None


__all__ = [
    "OFFICE_EXT",
    "col_index",
    "decode_xml",
    "docx_text",
    "office_text",
    "paragraph_text",
    "pptx_text",
    "runs_text",
    "tidy",
    "xlsx_text",
]
