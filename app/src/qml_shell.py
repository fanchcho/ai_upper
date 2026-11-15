"""QML 壳的 Python 侧：会话假数据、正文渲染桥、offscreen 启动与截图。

壳本身（三栏、配色、列表）全在 ``qml/Main.qml``；本模块只做 QML 做不到的两件事：

- 把 Markdown 渲染进 ``TextEdit`` 的 ``QQuickTextDocument``。渲染器是正文层唯一的
  实现（``markdown.document`` / ``markdown.body``），QML 侧不重复解析；
- headless 时等窗口真的画出第一帧再 ``grabWindow()`` 存 PNG，并按退出码报结果。

**降级路径**：实测 QML 的 ``TextEdit`` 渲染 ``border > 0`` 的 ``QTextFrame`` 会让进程
段错误（退出码 139，见 out/qml-body/SEGFAULT-EVIDENCE.md）。正文渲染器已避开这种
frame，但段错误无法在进程内捕获，所以这里保留 ``AI_UPPER_QML_PLAIN=1`` 开关：置 1
时正文退化为纯文本（``render_plain_text``，不解析 Markdown、不建表格），壳与列表照旧。
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

from utils.qt_compat import QtCore, QtGui, QtQml, QtQuick

QML_MAIN = Path(__file__).resolve().parent / "qml" / "Main.qml"
SHOT_PATH = Path(__file__).resolve().parents[2] / "out" / "qml-shell" / "shot.png"
PLAIN_ENV = "AI_UPPER_QML_PLAIN"
SHOT_ENV = "AI_UPPER_QML_SHOT"
RENDER_TIMEOUT_S = 90.0

# 三条假会话：标题/预览给列表，body 给正文。正文覆盖标题、列表、引用、行内代码、
# 代码块与表格——正是渲染器里最容易与 QML 排版冲突的几类块。
SESSIONS = [
    {
        "title": "QML 三栏壳落地",
        "preview": "从 WebEngine 切到 QML 的第一版壳",
        "body": """# QML 三栏壳

当前窗口由 `app/src/qml/Main.qml` 描述：左侧固定 264px 侧栏，中间会话列表，
右侧正文区。正文不是 QML 自己解析的，而是由 Python 侧的 Markdown 渲染器写入
`TextEdit` 的文档对象。

## 这一版做了什么

- 三栏 `RowLayout`，中列 `ListView` + delegate，右列 `TextEdit` 承载富文本；
- 主题 token 收敛到 `Theme.qml`，界面里不写死颜色；
- 正文走 `QQuickTextDocument`，与控件版共用同一份渲染代码。

## 还没做

1. 逐页 1:1 还原；
2. 真实的会话与流式回复；
3. 打包链的 QML 资源拷贝（本轮不碰）。

> 引用块用表格左列画竖线——`QTextFrame` 的 border 在 QML 里会段错误。

```python
def main() -> int:
    return run(headless=True)
```

| 项 | 状态 |
| --- | --- |
| 三栏壳 | 完成 |
| offscreen 截图 | 完成 |
""",
    },
    {
        "title": "正文渲染细节",
        "preview": "行高、字体栈与代码高亮",
        "body": """# 正文渲染细节

行高按字体实测行距换算成百分比，所以中文段落不会比浏览器更挤。

*行内代码* 用等宽字体与浅底色，`QTextCharFormat` 直接给。

1. 字体栈显式列出 CJK 家族；
2. 代码块用单列表格，不用 frame；
3. 分隔线是 1px 固定高度的空 frame（border 为 0）。
""",
    },
    {
        "title": "下一步计划",
        "preview": "从壳到逐页还原",
        "body": """# 下一步

壳能起来、能截图之后，再逐页对齐原版。

- 会话列表接真实数据；
- 正文支持流式增量；
- 主题切换复用 `BodyDocument.set_theme`。
""",
    },
]


def _plain_mode() -> bool:
    return os.environ.get(PLAIN_ENV, "").strip() == "1"


def _shot_path() -> Path:
    override = os.environ.get(SHOT_ENV, "").strip()
    return Path(override) if override else SHOT_PATH


class ShellBridge(QtCore.QObject):
    """QML 调过来的两个入口：初始挂载与切换会话。"""

    def __init__(self, body: Any, plain: bool) -> None:
        super().__init__()
        self._body = body
        self._plain = plain
        self._document: Any = None
        self.rendered = 0

    @QtCore.Slot(QtQuick.QQuickTextDocument, result=bool)
    def attach(self, quick_document: Any) -> bool:
        self._document = quick_document
        self._render(quick_document, SESSIONS[0]["body"])
        return True

    @QtCore.Slot(QtQuick.QQuickTextDocument, str, result=bool)
    def render(self, quick_document: Any, text: str) -> bool:
        self._document = quick_document
        self._render(quick_document, text)
        return True

    def rerender(self, text: str) -> None:
        """窗口宽度稳定后重排一次（代码块宽度取容器宽）。"""
        if self._document is not None:
            self._render(self._document, text)

    def _render(self, quick_document: Any, text: str) -> None:
        if self._plain:
            self._body.set_plain_text(text)
        else:
            self._body.set_markdown(text)
        self._body.attach(quick_document)
        self.rendered += 1


def _body_document() -> Any:
    from markdown.body import BodyDocument

    # 正文列宽 = 窗口宽 - 侧栏 - 中列 - 左右外边距（1280-264-300-40）。
    return BodyDocument(content_width=676.0)


def _pump(app: Any, predicate: Any, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def run(headless: bool) -> int:
    """启动 QML 壳；headless 时截图并按结果返回 0/1。"""
    from main import HEADLESS_TIMEOUT_S  # 与 WebEngine 路径共用同一超时

    if not QML_MAIN.is_file():
        print("QML FAILED", f"missing={QML_MAIN}", file=sys.stderr, flush=True)
        return 1

    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
    plain = _plain_mode()
    bridge = ShellBridge(_body_document(), plain)

    engine = QtQml.QQmlApplicationEngine()
    engine.rootContext().setContextProperty("bodyBridge", bridge)
    engine.load(QtCore.QUrl.fromLocalFile(str(QML_MAIN)))
    roots = engine.rootObjects()
    if not roots:
        print("QML FAILED", "reason=engine loaded no root object", file=sys.stderr, flush=True)
        return 1
    window = roots[0]

    window.setProperty("sessions", SESSIONS)
    window.setProperty("activeIndex", 0)
    window.setProperty("activeTitle", SESSIONS[0]["title"])
    window.setProperty("activeBody", "" if plain else SESSIONS[0]["body"])
    if plain:
        field = window.findChild(QtCore.QObject, "bodyView")
        if field is not None:
            field.setProperty("plainBody", SESSIONS[0]["body"])

    window.show()

    if not headless:
        from utils.qt_compat import exec_loop

        return exec_loop(app)

    frames = {"count": 0}
    window.frameSwapped.connect(lambda: frames.__setitem__("count", frames["count"] + 1))
    painted = _pump(
        app,
        lambda: frames["count"] > 0 or (window.isExposed() and bridge.rendered > 0),
        HEADLESS_TIMEOUT_S,
    )
    # 再泵几轮，让首帧之后的文档重排（表格/代码块宽度）落到画面上。
    _pump(app, lambda: False, 0.3)
    bridge.rerender(SESSIONS[0]["body"])
    _pump(app, lambda: False, 0.3)

    if not painted or bridge.rendered == 0:
        print(
            "QML FAILED",
            f"platform={app.platformName()}",
            f"exposed={window.isExposed()}",
            f"frames={frames['count']}",
            f"rendered={bridge.rendered}",
            file=sys.stderr,
            flush=True,
        )
        window.close()
        return 1

    image = window.grabWindow()
    if image.isNull():
        print("QML FAILED", "reason=grabWindow returned a null image", file=sys.stderr, flush=True)
        window.close()
        return 1

    out = _shot_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(out)):
        print("QML FAILED", f"reason=could not save {out}", file=sys.stderr, flush=True)
        window.close()
        return 1

    print(
        "QML OK",
        f"platform={app.platformName()}",
        f"title={window.property('title')!r}",
        f"sessions={len(SESSIONS)}",
        f"plain={plain}",
        f"png={out}",
        f"size={image.width()}x{image.height()}",
        flush=True,
    )
    window.close()
    return 0
