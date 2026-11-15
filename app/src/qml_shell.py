"""QML 壳的 Python 侧：真实会话 → 列表/正文、输入区发送、offscreen 启动与截图。

壳本身（三栏、配色、列表、输入框）全在 ``qml/Main.qml``；本模块只做 QML 做不到的事：

- **数据**：列表行来自 `ChatSessionStore.visible_sessions()`，正文来自该会话落盘的消息
  （`qml_shell_sessions.transcript_markdown` 拼成 Markdown，再交给 `markdown.body` 渲染）。
  壳里没有假数据，也不再内嵌一份 SESSIONS；
- **发送**：输入区走 `ChatHost.send`（与 WebEngine 渲染层同一条回合宿主），流式增量
  从宿主推回的事件里取，实时重渲染正文；用户消息与回复都由 ViewModel 落盘；
- **截图**：headless 时等窗口真的画出第一帧再 ``grabWindow()`` 存 PNG，并按退出码报结果。

线程：回合在后台线程跑，宿主 ``emit`` 从那个线程回调。这里只把事件放进队列，GUI 线程
的 ``tick()`` 取出来改界面（QML 属性只能在 GUI 线程写）。

**降级路径**：实测 QML 的 ``TextEdit`` 渲染 ``border > 0`` 的 ``QTextFrame`` 会让进程
段错误（退出码 139，见 out/qml-body/SEGFAULT-EVIDENCE.md）。正文渲染器已避开这种
frame，但段错误无法在进程内捕获，所以这里保留 ``AI_UPPER_QML_PLAIN=1`` 开关：置 1
时正文退化为纯文本（``render_plain_text``，不建表格），壳与列表照旧。
"""
from __future__ import annotations

import json
import os
import queue
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.persona_store import PersonaStore
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.settings_service import SettingsService
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.webui.assembly import build_chat_host, trusted_workspace_from_env
from qml_shell_sessions import session_rows, transcript_markdown
from utils.app_home import app_home
from utils.paths import assets_root
from utils.qt_compat import QtCore, QtGui, QtQml, QtQuick

# 源码树里 QML 就在本模块旁边；打包后应用代码进了 egg/合并扩展，没有源码路径，
# QML 由 `package.py::_copy_supporting_trees` 放到 `<bundle>/assets/qml`——
# 与 `assets_root()` 同一口径（launcher 导出的 `AI_UPPER_HOME`）。
PACKAGED_QML = Path("qml") / "Main.qml"
SHOT_PATH = Path(__file__).resolve().parents[2] / "out" / "qml-shell" / "shot.png"
PLAIN_ENV = "AI_UPPER_QML_PLAIN"
SHOT_ENV = "AI_UPPER_QML_SHOT"
SEND_ENV = "AI_UPPER_QML_SEND"
RENDER_TIMEOUT_S = 90.0
# 正文列宽 = 窗口宽 - 侧栏 - 中列 - 左右外边距（1280-264-300-40）。
BODY_WIDTH = 676.0


def _plain_mode() -> bool:
    return os.environ.get(PLAIN_ENV, "").strip() == "1"


def _shot_path() -> Path:
    override = os.environ.get(SHOT_ENV, "").strip()
    return Path(override) if override else SHOT_PATH


def qml_main() -> Path:
    """QML 入口：源码树 `<src>/qml/Main.qml`，否则 `<assets>/qml/Main.qml`。

    `__file__` 在打包产物里可能指向 egg 解包目录或不存在（合并扩展是 built-in
    module），所以用「文件在不在」判定，而不是靠路径形态猜。只认这两个位置：
    回落到别处会让缺 QML 的产物「碰巧」从开发树加载界面，冒烟测试也就失去意义。
    """
    source = Path(__file__).resolve().parent / "qml" / "Main.qml"
    if source.is_file():
        return source
    return assets_root() / PACKAGED_QML


def _send_text() -> str:
    return os.environ.get(SEND_ENV, "")


def new_session_id() -> str:
    """新会话 id：渲染层用 `chat-<时间36><随机>` 的同一形状（复用 `base36`）。"""
    from mvvm.services.chat_session_store import base36

    return "qml-%s%s" % (base36(time.time() * 1000), uuid.uuid4().hex[:6])


class ShellBridge(QtCore.QObject):
    """QML 调过来的入口，以及回合事件回写 QML 属性的唯一出口。"""

    def __init__(self, *, host: Any, store: ChatSessionStore, plain: bool) -> None:
        super().__init__()
        self._host = host
        self._store = store
        self._plain = plain
        self._document: Any = None
        self._window: Any = None
        self._events: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._active = ""
        self._pump: Any = None
        self._turn: Any = None  # qml_shell_sessions.TurnState | None
        self._turn_session = ""
        self.rendered = 0
        self.deltas: List[str] = []
        self.stop = ""

        from markdown.body import BodyDocument

        self._body = BodyDocument(content_width=BODY_WIDTH)

    # ── 装配 ──────────────────────────────────────────────────────────────
    def bind_window(self, window: Any) -> None:
        self._window = window

    def emit(self, payload: Dict[str, Any]) -> None:
        """宿主回调（可能来自回合线程）：只入队，GUI 线程的 tick 再动界面。"""
        self._events.put(payload)

    # ── QML → Python ──────────────────────────────────────────────────────
    @QtCore.Slot(QtQuick.QQuickTextDocument, result=bool)
    def attach(self, quick_document: Any) -> bool:
        self._document = quick_document
        self._render()
        return True

    @QtCore.Slot(str, result=bool)
    def openSession(self, session_id: str) -> bool:
        """切换会话：正文按该会话落盘的消息重渲染。"""
        self._active = str(session_id or "")
        self._turn = None
        self._turn_session = ""
        self._render()
        self._publish()
        return True

    @QtCore.Slot(str, result=bool)
    def send(self, text: str) -> bool:
        """输入区发送：走真实回合宿主，事件稍后经 emit → tick 回到界面。

        没有选中会话时（空状态）先建一条真实会话再发——界面写着「发一条消息就会出现在
        这里」，按钮就不能点了没反应。
        """
        body = (text or "").strip()
        if not body:
            return False
        if not self._active:
            self._active = new_session_id()
            self._host.create_session({"sessionId": self._active})
        if self._host.is_busy(self._active):
            return False
        base = self._markdown_base()
        from qml_shell_sessions import TurnState

        self._turn = TurnState(base, body)
        self._turn_session = self._active
        self.stop = ""
        self.deltas = []
        print(
            "QML SEND",
            json.dumps({"sessionId": self._active, "text": body}, ensure_ascii=False),
            flush=True,
        )
        try:
            turn_id = self._host.send({"sessionId": self._active, "text": body})["turnId"]
        except Exception as exc:  # noqa: BLE001 - 发送失败要显式暴露，不能装作已发出
            self._turn = None
            print("QML SEND FAILED", f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            return False
        print("QML TURN", turn_id, flush=True)
        self._render()
        self._publish()
        return True

    # ── 事件回写（GUI 线程）───────────────────────────────────────────────
    def tick(self) -> bool:
        """GUI 线程周期调用：drain 回合线程的界面写入，再把事件落到正文上。"""
        self._host.drain()
        changed = False
        while True:
            try:
                payload = self._events.get_nowait()
            except queue.Empty:
                break
            changed = self._handle(payload) or changed
        if changed:
            self._render()
            self._publish()
        return changed

    def _handle(self, payload: Dict[str, Any]) -> bool:
        session_id = str(payload.get("sessionId") or "")
        event = payload.get("event")
        if session_id != self._turn_session or not isinstance(event, dict):
            return False
        kind = event.get("type")
        if kind == "text_delta" and self._turn is not None:
            text = str(event.get("text") or "")
            self.deltas.append(text)
            print("QML STREAM", json.dumps({"text": text}, ensure_ascii=False), flush=True)
            return self._turn.apply(event)
        if kind == "error":
            print(
                "QML TURN ERROR",
                json.dumps(event, ensure_ascii=False),
                file=sys.stderr,
                flush=True,
            )
            if self._turn is not None:
                self._turn.apply(event)
            return True
        if kind == "done":
            self.stop = str(event.get("stopReason") or "")
            print(
                "QML TURN DONE",
                json.dumps(
                    {"stopReason": self.stop, "deltas": len(self.deltas)},
                    ensure_ascii=False,
                ),
                flush=True,
            )
            # 以落盘为准：VM 在 done 之前已把用户消息与回复写进会话文件。
            self._turn = None
            self._turn_session = ""
            return True
        return False

    def turn_finished(self) -> bool:
        return self._turn is None and (not self._turn_session)

    # ── 渲染与属性 ────────────────────────────────────────────────────────
    def _markdown_base(self) -> str:
        session = self._store.load_session(self._active) if self._active else None
        return transcript_markdown(session.messages) if session is not None else ""

    def _markdown(self) -> str:
        base = self._markdown_base()
        if self._turn is not None:
            # 回合中的「基础正文」在发送时已经取过；落盘会追加本轮消息，不能再拼一遍。
            return self._turn.markdown()
        return base

    def _render(self) -> None:
        if self._document is None:
            return
        if self._plain:
            self._body.set_plain_text(self._markdown())
        else:
            self._body.set_markdown(self._markdown())
        self._body.attach(self._document)
        self.rendered += 1
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        """正文重绘后贴到底部：流式增量与切换会话时，新内容不该藏在滚动区外。"""
        window = self._window
        if window is None:
            return
        scroller = window.findChild(QtCore.QObject, "bodyScroll")
        if scroller is None:
            return
        try:
            content = float(scroller.property("contentHeight") or 0.0)
            viewport = float(scroller.property("height") or 0.0)
            scroller.setProperty("contentY", max(0.0, content - viewport))
        except (TypeError, ValueError):
            return

    def rerender(self) -> None:
        """窗口尺寸稳定/画面首帧之后重排一次（代码块宽度取容器宽）。"""
        self._render()

    def _publish(self) -> None:
        window = self._window
        if window is None:
            return
        rows = session_rows(self._store)
        active = self._active if any(row["id"] == self._active for row in rows) else ""
        window.setProperty("sessions", rows)
        window.setProperty("activeId", active)
        window.setProperty(
            "activeTitle",
            next((row["title"] for row in rows if row["id"] == active), ""),
        )
        busy = bool(active) and self._host.is_busy(active)
        window.setProperty("busy", busy)
        window.setProperty("status", "输出中…" if busy else "就绪")

    def initial(self) -> None:
        """首帧之前：没有选中会话就选第一条（空数据时保持空状态）。"""
        rows = session_rows(self._store)
        if rows:
            self._active = rows[0]["id"]
            self._render()
        self._publish()


def _pump(app: Any, predicate: Any, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def _start_ticker(bridge: ShellBridge) -> Any:
    """交互模式下靠定时器推进：没有它，后台线程的事件永远到不了界面。"""
    timer = QtCore.QTimer()
    timer.setInterval(30)
    timer.timeout.connect(bridge.tick)
    timer.start()
    return timer


def run(headless: bool) -> int:
    """启动 QML 壳；headless 时截图并按结果返回 0/1。"""
    from main import HEADLESS_TIMEOUT_S  # 与 WebEngine 路径共用同一超时

    qml_main_path = qml_main()
    if not qml_main_path.is_file():
        print("QML FAILED", f"missing={qml_main_path}", file=sys.stderr, flush=True)
        return 1

    home = app_home()
    settings = SettingsService(home)
    vault = SecretsVault(home)
    store = ChatSessionStore(home)
    personas = PersonaStore(home)
    personas.ensure_seeded()
    guard = WorkspaceGuard()
    workspace = trusted_workspace_from_env()
    if workspace:
        guard.trust_root(workspace)

    app = QtGui.QGuiApplication.instance() or QtGui.QGuiApplication([])
    bridge_box: Dict[str, ShellBridge] = {}

    def emit(payload: Dict[str, Any]) -> None:
        bridge_box["bridge"].emit(payload)

    host, _gateway = build_chat_host(
        settings=settings,
        vault=vault,
        store=store,
        guard=guard,
        home=home,
        emit=emit,
        emit_sessions_changed=lambda: None,
    )

    plain = _plain_mode()
    bridge = ShellBridge(host=host, store=store, plain=plain)
    bridge_box["bridge"] = bridge

    engine = QtQml.QQmlApplicationEngine()
    engine.rootContext().setContextProperty("shellBridge", bridge)
    engine.load(QtCore.QUrl.fromLocalFile(str(qml_main_path)))
    roots = engine.rootObjects()
    if not roots:
        print("QML FAILED", "reason=engine loaded no root object", file=sys.stderr, flush=True)
        return 1
    window = roots[0]
    bridge.bind_window(window)
    bridge.initial()

    window.show()
    ticker = _start_ticker(bridge)

    if not headless:
        from utils.qt_compat import exec_loop

        try:
            return exec_loop(app)
        finally:
            ticker.stop()

    frames = {"count": 0}
    window.frameSwapped.connect(lambda: frames.__setitem__("count", frames["count"] + 1))
    painted = _pump(
        app,
        lambda: frames["count"] > 0 or (window.isExposed() and bridge.rendered > 0),
        HEADLESS_TIMEOUT_S,
    )
    _pump(app, lambda: False, 0.3)
    bridge.rerender()
    _pump(app, lambda: False, 0.2)

    send_text = _send_text()
    if send_text:
        if not bridge.send(send_text):
            print("QML FAILED", "reason=send rejected", file=sys.stderr, flush=True)
            window.close()
            return 1
        finished = _pump(app, bridge.turn_finished, HEADLESS_TIMEOUT_S)
        if not finished:
            print(
                "QML FAILED",
                f"reason=turn did not finish in {HEADLESS_TIMEOUT_S:.0f}s",
                f"stop={bridge.stop!r}",
                file=sys.stderr,
                flush=True,
            )
            window.close()
            return 1
        if bridge.stop != "end_turn":
            print(
                "QML FAILED",
                f"reason=turn ended with stop={bridge.stop!r}",
                file=sys.stderr,
                flush=True,
            )
            window.close()
            return 1
        # 落盘后的正文重排（新段落进来，代码块宽度要跟着容器算）。
        _pump(app, lambda: False, 0.2)
        bridge.rerender()
        _pump(app, lambda: False, 0.3)

    if not painted or bridge.rendered == 0:
        print(
            "QML FAILED",
            f"platform={app.platformName()}",
            f"exposed={window.isExposed()}",
            f"frames={frames['count']}",
            f"rendered={bridge.rendered}",
            f"home={home}",
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

    rows = session_rows(store)
    print(
        "QML OK",
        f"platform={app.platformName()}",
        f"title={window.property('title')!r}",
        f"sessions={len(rows)}",
        f"active={bridge._active!r}",
        f"plain={plain}",
        f"turn_stop={bridge.stop!r}",
        f"deltas={len(bridge.deltas)}",
        f"home={home}",
        f"png={out}",
        f"size={image.width()}x{image.height()}",
        flush=True,
    )
    ticker.stop()
    window.close()
    return 0
