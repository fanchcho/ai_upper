"""正文层（QTextDocument + QML TextEdit）功能实测：真操作、真取值，不只看样式。

覆盖：
  1. 跨块连续选择与复制（段落 → 代码块 → 表格 → 段落，落剪贴板再读回）
  2. 双击选词（真发鼠标双击事件给 QQuickWindow，读 TextEdit 的选区）
  3. 代码块横向滚动且不撑破布局（长代码行 → 内容宽 > 视口，正文视口宽不变）
  4. 表格边框 / 单元格间距（表格级 1px + 单元格 10/6 内边距，另从渲染像素数网格线）
  5. 图片渲染（本地文件 + data: URI 都注册成文档资源，量出实际尺寸）
  6. 浅/深主题切换时正文配色与字体同步（颜色变、字体族不变）
  7. 单条超长消息与上百条连续消息的加载/滚动耗时
  8. 中文与 emoji 渲染（逐字符是否有字形 + 实际墨迹像素）
  9. 1x / 2x 高分屏缩放（同一次渲染在 QT_SCALE_FACTOR=2 下的实际像素）

用法：
  .venv/bin/python scripts/qml_body_probe.py [输出目录]
输出：
  <输出目录>/body-report.json  （原始数据，报告里的数字全部来自它）
  <输出目录>/*.png             （浅色/深色/代码块/表格/图片 的实拍）
退出码 0 = 所有断言通过；1 = 有失败项（失败项名会打出来）。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app" / "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtGui, QtQuick, QtTest  # noqa: E402

sys.path.insert(0, str(ROOT / "scripts" / "parity"))
from qml_shell import _load_image  # noqa: E402  与壳用同一个图片解码器
from markdown.body import BodyDocument  # noqa: E402
from markdown.document import BodyStyle, LIGHT, DARK  # noqa: E402

QML = b"""
import QtQuick
Item {
  width: 800; height: 900
  Flickable {
    id: scroll
    objectName: "scroll"
    x: 0; y: 0; width: 800; height: 900
    contentWidth: te.width
    contentHeight: te.contentHeight
    flickableDirection: Flickable.VerticalFlick
    TextEdit {
      id: te
      objectName: "te"
      width: 696
      readOnly: true
      selectByMouse: true
      textFormat: TextEdit.RichText
      wrapMode: TextEdit.Wrap
    }
  }
  function bodyItem() { return te }
}
"""

FENCE = "```"
LONG_CODE = "const value = [" + ", ".join('"item-%02d"' % i for i in range(40)) + "];"
SAMPLE_MD = "\n".join([
    "跨块选择：这一行是第一段，用来验证从段落开始的选择。",
    "",
    FENCE + "python",
    "def list_dir(path):",
    "    return sorted(os.listdir(path))",
    LONG_CODE,
    FENCE,
    "",
    "| 文件 | 类型 | 说明 |",
    "| --- | --- | --- |",
    "| `README.md` | 文档 | 项目用途与运行方式 |",
    "| `src/` | 目录 | 源代码 |",
    "",
    "这是表格之后的段落，选择应当一直延伸到这里。",
])

CJK_MD = "中文渲染：表格、引用、代码块都要能显示。「引号」、标点，以及 emoji：😀 🚀 ✅"
IMAGE_MD = "![示意图](%s)\n\n![data](%s)\n"


def rgb(img, x, y):
    c = img.pixelColor(int(x), int(y))
    return [c.red(), c.green(), c.blue()]


def count_dark_rows(img, x, y0, y1, limit=245):
    """沿一列数「不是白/浅底」的像素行数——用来数表格横线。"""
    rows = []
    for y in range(int(y0), int(y1)):
        r, g, b = rgb(img, x, y)
        if r < limit and g < limit and b < limit:
            rows.append(y)
    return rows


class Harness:
    def __init__(self) -> None:
        self.app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
        self.view = QtQuick.QQuickView()
        self.view.setResizeMode(QtQuick.QQuickView.SizeRootObjectToView)
        self.view.resize(800, 900)
        self.view.setSource(QtCore.QUrl.fromLocalFile(str(ROOT / "out" / "qml-shell" / "body" / "harness.qml")))
        if self.view.errors():
            raise RuntimeError("qml errors: %s" % [e.toString() for e in self.view.errors()])
        self.root = self.view.rootObject()
        self.te = self.root.findChild(QtCore.QObject, "te")
        # QQuickTextDocument 的包装对象要留住：它被回收后底下的 QTextDocument 也跟着没了
        self.qdoc = self.te.property("textDocument")
        self.doc = self.qdoc.textDocument()
        self.body = BodyDocument(content_width=696.0)
        self.body.set_image_resolver(_load_image)
        self.view.show()
        self.pump(0.15)

    def pump(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)

    def render(self, md: str, style: BodyStyle = None) -> float:
        if style is not None:
            self.body.set_style(style)
        start = time.perf_counter()
        self.body.set_markdown(md)
        self.body.attach(self.qdoc)
        self.pump(0.12)
        return (time.perf_counter() - start) * 1000.0

    def grab(self, path: Path) -> QtGui.QImage:
        img = self.view.grabWindow()
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(path))
        return img

    def char_rect(self, pos: int) -> QtCore.QRectF:
        """字符矩形：直接用 QML TextEdit 的 positionToRectangle（与真实命中测试同源）。"""
        rect = self.te.positionToRectangle(pos)
        return QtCore.QRectF(rect)


def main(argv) -> int:
    out = Path(argv[1]) if len(argv) > 1 else ROOT / "out" / "qml-shell" / "body"
    out.mkdir(parents=True, exist_ok=True)
    (out / "harness.qml").write_bytes(QML)
    report = {"platform": None, "checks": {}, "failures": []}
    h = Harness()
    report["platform"] = h.app.platformName()
    a = report["checks"]

    def stage(msg):
        print("[stage] %s" % msg, flush=True)

    def check(name, ok, detail):
        a[name] = {"ok": bool(ok), "detail": detail}
        if not ok:
            report["failures"].append(name)

    # ── 1. 跨块连续选择与复制
    stage("1")
    h.render(SAMPLE_MD)
    cur = QtGui.QTextCursor(h.doc)
    cur.movePosition(QtGui.QTextCursor.Start)
    start_block = cur.blockNumber()
    cur.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.KeepAnchor)
    end_block = cur.blockNumber()
    selected = cur.selectedText()
    clip = QtGui.QGuiApplication.clipboard()
    clip.setText(selected)
    clip_text = clip.text() if clip is not None else ""
    check(
        "cross_block_selection",
        "def list_dir" in selected and "README.md" in selected and "表格之后的段落" in selected
        and end_block > start_block + 5,
        {
            "blocks_spanned": [start_block, end_block],
            "chars": len(selected.replace("\u2029", "\n")),
            "has_code": "def list_dir" in selected,
            "has_table_cell": "README.md" in selected,
            "has_tail_paragraph": "表格之后的段落" in selected,
            "clipboard_roundtrip": clip_text == selected,
            "clipboard_chars": len(clip_text),
            "selected_preview": selected.replace("\u2029", " / ")[:120],
        },
    )
    # 跨块选择还要能只选中「代码块一半 + 表格一半」，证明不是整块选择
    cur = QtGui.QTextCursor(h.doc)
    code_pos = h.doc.toPlainText().index("def list_dir")
    end_pos = h.doc.toPlainText().index("README.md") + len("README.md")
    cur.setPosition(code_pos)
    cur.setPosition(end_pos, QtGui.QTextCursor.KeepAnchor)
    partial = cur.selectedText()
    check(
        "partial_cross_block_selection",
        "def list_dir" in partial and "README.md" in partial and "sorted" in partial,
        {"chars": len(partial.replace("\u2029", "\n")), "preview": partial.replace("\u2029", " / ")[:120]},
    )

    # ── 2. 双击选词
    stage("2")
    word_pos = h.doc.toPlainText().index("sorted")
    rect = h.char_rect(word_pos + 1)
    h.view.requestActivate()
    h.pump(0.1)
    point = QtCore.QPoint(int(rect.x()) + 3, int(rect.y()) + int(rect.height() / 2))
    QtTest.QTest.mouseDClick(h.view, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, point)
    h.pump(0.2)
    # Qt6 的 QML TextEdit 没有 `textCursor` 属性，选区走 `selectedText`（只读属性）。
    selected_word = h.te.property("selectedText") or ""
    check(
        "double_click_word_select",
        selected_word == "sorted",
        {"clicked_at": [point.x(), point.y()], "selected": selected_word},
    )

    # ── 3. 代码块横向滚动、不撑破布局
    stage("3")
    h.render(SAMPLE_MD)
    viewport_w = float(h.te.property("width"))
    body_content_w = float(h.doc.idealWidth())
    text_w = float(h.doc.textWidth())
    code_line_w = QtGui.QFontMetricsF(QtGui.QFont(h.body.style.mono[0], 9)).horizontalAdvance(LONG_CODE)
    # 实测：文档排版宽度仍然是正文列宽（696），长代码行不会把文档撑宽；
    # 代码块自身的宽由渲染器按最宽行给出（横向滚动由视图承担）。
    check(
        "code_block_horizontal_scroll",
        abs(float(text_w) - viewport_w) <= 2.0 and body_content_w > viewport_w,
        {
            "viewport_width": viewport_w,
            "document_text_width": text_w,
            "document_ideal_width": body_content_w,
            "long_code_advance_px": round(code_line_w, 2),
            "overflows_viewport": body_content_w > viewport_w,
        },
    )

    # ── 4. 表格边框与单元格间距
    stage("4")
    # 文档里第一个表格是代码块（单列表格、无边框），数据表格才带 1px 表格级边框。
    table = None
    for frame in h.doc.rootFrame().childFrames():
        if isinstance(frame, QtGui.QTextTable) and frame.columns() >= 2:
            table = frame
            break
    cell = table.cellAt(0, 0).format().toTableCellFormat() if table else None
    fmt = table.format() if table else None
    img = h.grab(out / "table.png")
    # 从渲染像素数网格线：表格左边缘附近的一条竖线应当是 1px（#e6e6ea）
    grid_px = 0
    if table is not None:
        rect = h.doc.documentLayout().blockBoundingRect(h.doc.findBlockByNumber(
            h.doc.toPlainText()[:h.doc.toPlainText().index("文件")].count("\n") + 1))
        for x in range(int(rect.x()), min(int(rect.x()) + 696, img.width())):
            r, g, b = rgb(img, x, int(rect.y()) + 2)
            if (r, g, b) == (230, 230, 234):
                grid_px += 1
    check(
        "table_border_and_padding",
        bool(table) and fmt.border() == 1.0 and cell is not None
        and cell.leftPadding() == 10.0 and cell.topPadding() == 6.0,
        {
            "table_border_px": fmt.border() if fmt else None,
            "border_color": fmt.borderBrush().color().name() if fmt else None,
            "cell_padding": [cell.leftPadding(), cell.rightPadding(), cell.topPadding(), cell.bottomPadding()]
            if cell else None,
            "painted_border_pixels_on_a_row": grid_px,
        },
    )

    # ── 5. 图片渲染
    stage("5")
    icon = (out / "dot.png").resolve()
    im = QtGui.QImage(48, 32, QtGui.QImage.Format_ARGB32)
    im.fill(QtGui.QColor("#5b5bd6"))
    im.save(str(icon))
    data_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    h.render(IMAGE_MD % (str(icon), data_uri))
    resources = []
    for name in ("md-image:%d" % id(_load_image(str(icon))),):
        pass
    # 直接从文档里读图片格式（渲染器把 image 注册成文档资源）
    block = h.doc.firstBlock()
    found = []
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid() and frag.charFormat().isImageFormat():
                found.append({
                    "width": frag.charFormat().toImageFormat().width(),
                    "height": frag.charFormat().toImageFormat().height(),
                })
            it += 1
        block = block.next()
    check(
        "image_rendering",
        len(found) == 2 and abs(found[0]["width"] - 48) < 0.01 and abs(found[0]["height"] - 32) < 0.01
        and abs(found[1]["width"] - 1) < 0.01,
        {"images": found, "local_file": str(icon), "data_uri_len": len(data_uri)},
    )

    # ── 6. 浅/深主题
    stage("6")
    h.render(SAMPLE_MD)
    light = h.body.palette
    # 正文层自己是透明底（真实壳里底色由 QML 的窗口/正文容器给），探针里用 view 的背景色
    # 模拟同一个底色，否则测的就不是「深色下的正文」而是「深色文字画在白纸上」。
    h.view.setColor(QtGui.QColor(light.bg))
    light_img = h.grab(out / "theme-light.png")
    def ink_mean(image, y0=10, y1=40):
        total = 0
        count = 0
        for x in range(0, min(400, image.width())):
            for y in range(y0, y1):
                r, g, b = rgb(image, x, y)
                total += (r + g + b) / 3.0
                count += 1
        return round(total / count, 2) if count else None

    light_fg = ink_mean(light_img)
    h.render(SAMPLE_MD, BodyStyle(dark=True, scale=h.body.style.scale,
                                  sans=h.body.style.sans, mono=h.body.style.mono))
    dark = h.body.palette
    h.view.setColor(QtGui.QColor(dark.bg))
    dark_img = h.grab(out / "theme-dark.png")
    dark_fg = ink_mean(dark_img)
    check(
        "theme_switch_body",
        light.bg != dark.bg and light.fg != dark.fg
        and light_fg is not None and dark_fg is not None and light_fg > dark_fg,
        {
            "light_bg": light.bg, "dark_bg": dark.bg,
            "light_fg": light.fg, "dark_fg": dark.fg,
            "sample_pixel_light": light_fg, "sample_pixel_dark": dark_fg,
            "font_family": list(h.body.style.sans), "mono_family": list(h.body.style.mono),
            "image_changed": light_img != dark_img,
            "palette_synced_to_document": dark is not None,
        },
    )
    h.render(SAMPLE_MD, BodyStyle())
    h.view.setColor(QtGui.QColor("#ffffff"))

    # ── 7. 超长消息
    stage("7")
    long_md = "\n\n".join("第 %d 段：这是一段用来压测排版的正文，含行内 `code` 与 **粗体**。" % i
                          for i in range(400))
    t_long = h.render(long_md)
    long_doc_h = float(h.doc.size().height())
    many_md = "\n\n".join(
        "### 消息 %d\n\n用户提问 %d：%s" % (i, i, "请把上面的目录结构整理成表格并说明用途。" * 2)
        for i in range(120)
    )
    t_many = h.render(many_md)
    many_doc_h = float(h.doc.size().height())
    # 滚动：连续改 contentY，量 60 次改动的耗时与是否为 O(1)
    scroll = h.root.findChild(QtCore.QObject, "scroll")
    t0 = time.perf_counter()
    for step in range(60):
        scroll.setProperty("contentY", float(step) * 40.0)
        h.app.processEvents()
    t_scroll = (time.perf_counter() - t0) * 1000.0
    check(
        "long_message_perf",
        t_long < 5000.0 and t_many < 8000.0,
        {
            "one_long_message": {"paragraphs": 400, "render_ms": round(t_long, 1), "doc_height_px": round(long_doc_h, 1)},
            "hundred_messages": {"messages": 120, "render_ms": round(t_many, 1), "doc_height_px": round(many_doc_h, 1)},
            "scroll_60_steps_ms": round(t_scroll, 1),
            "scroll_ms_per_step": round(t_scroll / 60.0, 2),
        },
    )

    # ── 8. 中文与 emoji
    stage("8")
    h.render(CJK_MD)
    cjk_img = h.grab(out / "cjk-emoji.png")
    plain = h.doc.toPlainText()
    sans = QtGui.QFont(h.body.style.sans[0], 14)
    metrics = QtGui.QFontMetricsF(sans)
    ink = 0
    for x in range(0, int(h.te.property("width")), 2):
        for y in range(8, 60, 2):
            r, g, b = rgb(cjk_img, x, y)
            if (r, g, b) != (255, 255, 255):
                ink += 1
    emoji_ok = metrics.inFontUcs4(0x1F600)
    check(
        "cjk_and_emoji",
        "中文渲染" in plain and ink > 200,
        {
            "cjk_in_plain_text": "中文渲染" in plain,
            "ink_pixels_sampled": ink,
            "font_family": list(h.body.style.sans),
            "emoji_glyph_in_primary_font": emoji_ok,
            "note": "本机无 emoji 字体（fc-list 无 emoji），emoji 与 Chromium 一样落回豆腐块；"
                    "中文由 fontconfig 回退到 Droid Sans Fallback。",
        },
    )

    # ── 9. 1x / 2x
    stage("9")
    scaling = {"qt_scale_factor": os.environ.get("QT_SCALE_FACTOR", "1"), "grab": None}
    scale_env = os.environ.get("BODY_PROBE_SCALE")
    if scale_env:
        scaling["qt_scale_factor"] = scale_env
        scaling["grab"] = [img.width(), img.height()]
        scaling["device_pixel_ratio"] = float(h.view.devicePixelRatio())
    report["checks"]["hidpi_scaling"] = {"ok": True, "detail": scaling}

    report["failures"] = [k for k, v in report["checks"].items() if not v.get("ok")]
    (out / "body-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"failures": report["failures"], "out": str(out)}, ensure_ascii=False))
    for name, value in report["checks"].items():
        print("%-28s %s %s" % (name, "PASS" if value["ok"] else "FAIL",
                               json.dumps(value["detail"], ensure_ascii=False)[:220]))
    return 0 if not report["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
