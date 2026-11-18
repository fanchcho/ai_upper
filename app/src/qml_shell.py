"""QML 壳的 Python 侧：真实会话 → 列表/正文、输入区发送、offscreen 启动与截图。

壳本身（三栏、配色、列表、输入框）全在 ``qml/Main.qml``；本模块只做 QML 做不到的事：

- **数据**：列表行来自 `ChatSessionStore.visible_sessions()`，正文来自该会话落盘的消息
  （`qml_shell_sessions.transcript_markdown` 拼成 Markdown，再交给 `markdown.body` 渲染）。
  壳里没有假数据，也不再内嵌一份 SESSIONS；
- **发送**：输入区走 `ChatHost.send`（源码树与打包产物共用的同一条回合宿主），流式增量
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

import base64
import json
import os
import queue
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from mvvm.services.attachments import AttachmentService
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.deliverables import open_item, reveal
from mvvm.services.persona_store import PersonaStore
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.settings_service import SettingsService
from mvvm.services.skill_store import SkillStore
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.webui.assembly import build_chat_host, trusted_workspace_from_env
from qml_shell_sessions import (
    attachment_rows,
    delivery_rows,
    session_rows,
    transcript_markdown,
)
from utils.app_home import app_home
from utils.paths import assets_root, module_file
from utils.qt_compat import QtCore, QtGui, QtQml, QtQuick

# 源码树里 QML 就在本模块旁边；打包后应用代码进了 egg/合并扩展，没有源码路径，
# QML 由 `package.py::_copy_supporting_trees` 放到 `<bundle>/assets/qml`——
# 与 `assets_root()` 同一口径（launcher 导出的 `AI_UPPER_HOME`）。
PACKAGED_QML = Path("qml") / "Main.qml"
SHOT_RELATIVE = Path("out") / "qml-shell" / "shot.png"
PLAIN_ENV = "AI_UPPER_QML_PLAIN"
SHOT_ENV = "AI_UPPER_QML_SHOT"
SEND_ENV = "AI_UPPER_QML_SEND"
PAGE_ENV = "AI_UPPER_QML_PAGE"
RENDER_TIMEOUT_S = 90.0

# 原版「文字大小」倍率（deva tokens.css `--chat-scale`）：标准 = 1，其余据 14px 基准。
CHAT_SCALES = {"sm": 13.0 / 14.0, "md": 1.0, "lg": 15.5 / 14.0, "xl": 17.0 / 14.0}
CHAT_SIZE_ORDER = ("sm", "md", "lg", "xl")
THEME_ORDER = ("system", "light", "dark")
# 界面文案：壳里只有设置页的行标签需要本地化（其余来自数据或图标）。
SETTINGS_LABELS = {
    "zh": {
        "language": "语言", "theme": "主题", "textSize": "文字大小",
        "themeSystem": "跟随系统", "themeLight": "浅色", "themeDark": "深色",
        "fontSm": "小", "fontMd": "标准", "fontLg": "大", "fontXl": "特大",
        "providers": "模型服务商", "noProviders": "还没有可用的服务商，点右上角 + 添加",
        "modelCount": "{count} 个模型", "extensions": "扩展", "builtIn": "内置",
    },
    "en": {
        "language": "Language", "theme": "Theme", "textSize": "Text size",
        "themeSystem": "System", "themeLight": "Light", "themeDark": "Dark",
        "fontSm": "Small", "fontMd": "Default", "fontLg": "Large", "fontXl": "Extra large",
        "providers": "Providers", "noProviders": "No providers yet — click + to add one",
        "modelCount": "{count} models", "extensions": "Extensions", "builtIn": "Built-in",
    },
}

# 页面名 → 让壳呈现该状态的标识；与 scripts/parity/qml_pages_all.sh 的清单一致。
PAGE_NAMES = (
    "chat", "empty", "first-run", "search-open", "search-results", "search-none",
    "settings-general", "settings-models", "settings-extensions", "settings-about",
    "model-picker", "ctx-menu", "delete-confirm", "hover-thread", "focus-composer",
    "long-mid", "long-bottom", "dark-chat",
)
# 正文列宽 = 窗口宽 - 侧栏 - 中列 - 左右外边距（1280-264-300-40）。
BODY_WIDTH = 676.0


def _plain_mode() -> bool:
    return os.environ.get(PLAIN_ENV, "").strip() == "1"


def _shot_path() -> Path:
    """headless 截图的落盘位置：`AI_UPPER_QML_SHOT` 优先，否则给一个可写的缺省值。

    缺省值不能从 `__file__` 数父目录：打包产物里的应用代码是合并扩展（built-in
    module），`__file__` 是 spec origin `"built-in"`——一个单段相对路径。CPython 3.8
    的 Windows `resolve()` 对不存在的相对路径原样返回（`Lib/pathlib.py:211`），于是
    `parents[2]` 在 `_PathParents.__getitem__` 里抛 IndexError，整个 qml_shell 在
    import 阶段就死了（CI run 44033731069 的 windows-py38 job 正是这样）。只有源码树
    里 `__file__` 才是真文件，那里才数父目录。
    """
    override = os.environ.get(SHOT_ENV, "").strip()
    if override:
        return Path(override)
    source_path = module_file(globals())
    if source_path is not None:
        return source_path.parents[2] / SHOT_RELATIVE
    return Path(tempfile.gettempdir()) / "ai_upper-qml-shell" / SHOT_RELATIVE.name


def qml_main() -> Path:
    """QML 入口：源码树 `<src>/qml/Main.qml`，否则 `<assets>/qml/Main.qml`。

    `__file__` 在打包产物里可能指向 egg 解包目录或不存在（合并扩展是 built-in
    module），所以用「文件在不在」判定，而不是靠路径形态猜。只认这两个位置：
    回落到别处会让缺 QML 的产物「碰巧」从开发树加载界面，冒烟测试也就失去意义。
    """
    source_path = module_file(globals())
    source = source_path.parent / "qml" / "Main.qml" if source_path is not None else None
    if source is not None and source.is_file():
        return source
    return assets_root() / PACKAGED_QML


def _send_text() -> str:
    return os.environ.get(SEND_ENV, "")


def _load_image(src: str) -> Any:
    """正文图片解码：`data:` URI（base64/百分号编码）与本地文件都解成 QImage。

    QTextDocument 自己不认 `data:` URI（`QTextDocument.addResource` 只吃 QUrl + 图片对象），
    所以图片由这里解码后交给渲染器注册成文档资源；解不出来返回 None，渲染器画 alt 占位，
    图片不会被静默吞掉（这条口径有测试锁住）。
    """
    text = (src or "").strip()
    if not text:
        return None
    image = QtGui.QImage()
    if text.startswith("data:"):
        head, _, payload = text.partition(",")
        try:
            if ";base64" in head:
                raw = base64.b64decode(payload, validate=False)
            else:
                from urllib.parse import unquote_to_bytes

                raw = unquote_to_bytes(payload)
        except (ValueError, TypeError, base64.binascii.Error):
            return None
        return image if image.loadFromData(raw) else None
    if text.startswith("file://"):
        text = text[len("file://"):]
    path = Path(text)
    if not path.is_absolute():
        path = app_home() / path
    if not path.is_file():
        return None
    return image if image.load(str(path)) else None


def _coerce_attachment_paths(attachments: Any) -> List[str]:
    """QML 传来的附件列表 → Python 字符串列表。

    QML 的 `var` 数组经 QVariantList 进来时，元素是 `QJSValue` 而不是 `str`
    （实测 `["<PySide6.QtQml.QJSValue object at 0x...>"]`）。只认 `isinstance(p, str)`
    会把用户亲手选中的文件全丢掉，消息于是「选了文件却没带上」。这里按 `toString()`
    取值并丢弃空串，其余类型一律忽略。
    """
    if not isinstance(attachments, (list, tuple)):
        return []
    paths: List[str] = []
    for item in attachments:
        if isinstance(item, str):
            text = item
        elif hasattr(item, "toString"):
            text = str(item.toString())
        else:
            continue
        if text:
            paths.append(text)
    return paths


def new_session_id() -> str:
    """新会话 id：渲染层用 `chat-<时间36><随机>` 的同一形状（复用 `base36`）。"""
    from mvvm.services.chat_session_store import base36

    return "qml-%s%s" % (base36(time.time() * 1000), uuid.uuid4().hex[:6])


class ShellBridge(QtCore.QObject):
    """QML 调过来的入口，以及回合事件回写 QML 属性的唯一出口。"""

    # 深浅主题：QML 侧 `Theme.dark` 绑这个属性（Main.qml 里一条 Binding）。
    # 为什么不写 Theme 单例的 property：`QQmlApplicationEngine.singletonInstance()`
    # 对 qmldir 里声明 `singleton` 的 QML 文件单例返回的是 QJSValue，`.setProperty()`
    # 落不到 QObject 上（实测 value 不变），主题切了个寂寞。走 context property 才可靠。
    darkModeChanged = QtCore.Signal()

    @QtCore.Property(bool, notify=darkModeChanged)
    def darkMode(self) -> bool:
        return self._dark

    def __init__(
        self,
        *,
        host: Any,
        store: ChatSessionStore,
        plain: bool,
        settings: Any = None,
        vault: Any = None,
        skills: Any = None,
    ) -> None:
        super().__init__()
        self._host = host
        self._store = store
        self._plain = plain
        self._settings = settings
        self._vault = vault
        self._skills = skills
        self._dark = False
        self._document: Any = None
        self._window: Any = None
        self._engine: Any = None
        self._events: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._persona_names: Dict[str, str] = {}
        self._active = ""
        self._pump: Any = None
        self._turn: Any = None  # qml_shell_sessions.TurnState | None
        self._turn_session = ""
        # 附件白名单只此一套服务；对话框由这里的 QFileDialog 提供。
        # **必须优先用宿主那一份**：`send()` 交给 `ChatHost.send` 读附件，宿主只认自己
        # `self.attachments` 的白名单。各 new 一份的话，回形针选中的文件在发送时会被判
        # 「已忽略未授权文件」——当初的分屏入口就是这个故障（旧用例
        # `test_bridge_and_host_share_one_attachment_service`，已随 web 入口删除；
        # 等价断言在 `app/tests/test_qml_chat_files.py` 里），这里沿用同一条规则。
        self._attachments = getattr(host, "attachments", None) or AttachmentService(
            store.home, WorkspaceGuard()
        )
        self._attachments.set_file_dialogs(pick_files=self._pick_files)
        self.rendered = 0
        self.deltas: List[str] = []
        self.stop = ""

        from markdown.body import BodyDocument

        self._body = BodyDocument(content_width=BODY_WIDTH)
        self._body.set_image_resolver(_load_image)
        # 首帧之前就把深浅算好：QML 的 Theme.dark 绑在 darkMode 上，晚一拍会闪白。
        self._dark = self._resolve_dark()
        self._sync_body_style()

    # ── 装配 ──────────────────────────────────────────────────────────────
    def bind_window(self, window: Any) -> None:
        self._window = window
        self._sync_theme_singleton()

    # ── 配置（设置页读写的真实来源：config.json）────────────────────────────
    def _config(self) -> Dict[str, Any]:
        return self._settings.get_config_sync() if self._settings is not None else {}

    def _write_config(self, patch: Dict[str, Any]) -> bool:
        if self._settings is None:
            return False
        try:
            self._settings.set_config(patch)
        except OSError as exc:  # 落盘失败必须显式暴露（原版 persist 吞异常，本工程不吞）
            print("QML CONFIG FAILED", f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            return False
        return True

    @QtCore.Slot(result=str)
    def language(self) -> str:
        """界面语言：原版存在 config.json 的 `locale`（zh-CN | en）。

        兼容旧键 `language`（zh | en）；两处都没有时按系统语言，和原版 detectLocale 一致。
        """
        config = self._config()
        locale = config.get("locale")
        if locale in ("zh-CN", "zh"):
            return "zh"
        if locale == "en":
            return "en"
        legacy = config.get("language")
        if legacy in ("zh", "en"):
            return str(legacy)
        return "en"

    @QtCore.Slot(result="QVariantMap")
    def labels(self) -> Dict[str, str]:
        """设置页文案（界面语言跟随 config.json 的 locale）。"""
        return dict(SETTINGS_LABELS[self.language()])

    @QtCore.Slot(result=str)
    def theme(self) -> str:
        value = self._config().get("theme")
        return value if value in THEME_ORDER else "system"

    @QtCore.Slot(result=int)
    def themeIndex(self) -> int:
        return THEME_ORDER.index(self.theme())

    @QtCore.Slot(result=int)
    def textSizeIndex(self) -> int:
        value = self._config().get("chatFontSize")
        return CHAT_SIZE_ORDER.index(value) if value in CHAT_SIZE_ORDER else 1

    @QtCore.Slot(str, result=bool)
    def setLanguage(self, value: str) -> bool:
        """写 `locale`（原版键名）。zh → zh-CN，en → en。"""
        target = "zh-CN" if value in ("zh", "zh-CN") else "en"
        if not self._write_config({"locale": target}):
            return False
        self._publish()
        return True

    @QtCore.Slot(str, result=bool)
    def setTheme(self, value: str) -> bool:
        if value not in THEME_ORDER:
            return False
        if not self._write_config({"theme": value}):
            return False
        self._apply_theme()
        return True

    @QtCore.Slot(int, result=bool)
    def setTextSize(self, index: int) -> bool:
        if not isinstance(index, int) or not 0 <= index < len(CHAT_SIZE_ORDER):
            return False
        if not self._write_config({"chatFontSize": CHAT_SIZE_ORDER[index]}):
            return False
        self._sync_body_style()
        self._render()
        return True

    # ── 主题与字号：QML 单例 Theme 与正文 QTextDocument 同步 ──────────────────
    def _resolve_dark(self) -> bool:
        """`system` 按应用配色方案解析（原版 prefers-color-scheme）。"""
        choice = self.theme()
        if choice == "dark":
            return True
        if choice == "light":
            return False
        hints = QtGui.QGuiApplication.styleHints() if QtGui.QGuiApplication.instance() else None
        scheme = getattr(hints, "colorScheme", None) if hints is not None else None
        return scheme == QtCore.Qt.ColorScheme.Dark

    def _theme_singleton(self) -> Any:
        engine = self._engine
        if engine is None:
            return None
        try:
            return engine.singletonInstance("", "Theme")
        except (RuntimeError, TypeError):
            return None

    def _sync_theme_singleton(self) -> None:
        """把解析后的深/浅推给 QML：更新 `darkMode` 并通知，Theme 单例由 QML 的 Binding 写。

        为什么不直接 `singletonInstance().setProperty("dark", ...)`：QML 文件单例在
        PySide6 里拿到的是 QJSValue，`setProperty` 不落到 QObject 上（实测值不变），
        主题切了个寂寞。走 context property + QML Binding 才可靠。
        """
        dark = self._resolve_dark()
        if dark == self._dark:
            return
        self._dark = dark
        self.darkModeChanged.emit()

    def _apply_theme(self) -> None:
        self._sync_theme_singleton()
        self._sync_body_style()
        self._render()
        self._publish()

    def _sync_body_style(self) -> None:
        """正文层与主题/字号同步：QTextDocument 的颜色与字体不能和壳各说各话。"""
        scale = CHAT_SCALES.get(self._config().get("chatFontSize"), 1.0)
        self._body.set_style(
            self._body.style.__class__(
                scale=scale,
                dark=self._resolve_dark(),
                sans=self._body.style.sans,
                mono=self._body.style.mono,
            )
        )

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

    @QtCore.Slot(result=str)
    def newSession(self) -> str:
        """加号按钮：建一条真实会话并切过去（原版 chat:create-session 同语义）。"""
        session_id = new_session_id()
        self._host.create_session({"sessionId": session_id})
        self._active = session_id
        self._turn = None
        self._turn_session = ""
        self._render()
        self._publish()
        return session_id

    # ── 设置页数据（真实来源：config.json / skills 目录 / secrets 库）────────────
    @QtCore.Slot(result=list)
    def modelRows(self) -> List[Dict[str, Any]]:
        """模型页：原版只列「在用」的服务商（已启用 / 已配密钥 / 自定义）。

        行的形状对齐原版 `provider-row`：名称、`N models`、启用点、缺密钥警告、详情箭头。
        """
        config = self._config()
        section = config.get("models") if isinstance(config.get("models"), dict) else {}
        providers = section.get("providers") if isinstance(section, dict) else None
        labels = SETTINGS_LABELS[self.language()]
        rows: List[Dict[str, Any]] = []
        for provider in providers if isinstance(providers, list) else []:
            if not isinstance(provider, dict):
                continue
            if (provider.get("purpose") or "llm") != "llm":
                continue
            provider_id = str(provider.get("id") or "")
            enabled = provider.get("enabled") is True
            has_key = bool(self._vault is not None and provider_id and self._vault.has_secret(provider_id))
            if not (enabled or has_key or provider.get("kind") == "custom"):
                continue
            models = provider.get("models")
            count = len(models) if isinstance(models, list) else 0
            rows.append(
                {
                    "id": provider_id,
                    "name": str(provider.get("name") or provider_id),
                    "accent": str(provider.get("accent") or "#8a8a94"),
                    "enabled": enabled,
                    "detail": labels["modelCount"].replace("{count}", str(count)),
                    "warn": enabled and not has_key,
                }
            )
        return rows

    @QtCore.Slot(result=list)
    def extensionRows(self) -> List[Dict[str, Any]]:
        """扩展页：真实技能列表（内置三条 + 磁盘技能），启用态来自 config.json。"""
        if self._skills is None:
            return []
        labels = SETTINGS_LABELS[self.language()]
        rows: List[Dict[str, Any]] = []
        for skill in self._skills.list_skills():
            rows.append(
                {
                    "id": str(skill.get("id") or ""),
                    "name": str(skill.get("name") or skill.get("id") or ""),
                    "description": str(skill.get("description") or ""),
                    "enabled": skill.get("enabled") is not False,
                    "builtin": skill.get("source") == "builtin",
                    "sourceLabel": labels["builtIn"] if skill.get("source") == "builtin" else "Skill",
                }
            )
        return rows

    @QtCore.Slot(str, result=bool)
    def setSkillEnabled(self, skill_id: str) -> bool:
        """扩展页开关：写 `skills.enabled[id]`（原版 set-enabled 语义）。"""
        if self._skills is None or not skill_id:
            return False
        try:
            current = self._config().get("skills")
            section = dict(current) if isinstance(current, dict) else {}
            enabled = section.get("enabled")
            enabled_map = dict(enabled) if isinstance(enabled, dict) else {}
            enabled_map[skill_id] = not bool(enabled_map.get(skill_id, True))
            section["enabled"] = enabled_map
            return self._write_config({"skills": section})
        except OSError as exc:  # noqa: BLE001 - 保持与 SkillStore 的异常口径一致
            print("QML CONFIG FAILED", f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            return False

    @QtCore.Slot(str, "QVariantList", result=bool)
    def sendWithAttachments(self, text: str, attachments: Any) -> bool:
        """输入区发送（带附件）：附件路径交给 `ChatHost.send`，与 `/send` 同一条链路。"""
        return self.send(text, attachments)

    @QtCore.Slot(str, result=bool)
    def send(self, text: str, attachments: Any = None) -> bool:
        """输入区发送：走真实回合宿主，事件稍后经 emit → tick 回到界面。

        没有选中会话时（空状态）先建一条真实会话再发——界面写着「发一条消息就会出现在
        这里」，按钮就不能点了没反应。

        `attachments` 是用户亲手选中的绝对路径列表（QML 回形针 → `pickAttachments` 的
        返回值，也已登记进 `AttachmentService` 白名单）；透传给宿主后由它读成内容块，
        与宿主侧的发送路径完全相同，不存在第二条附件链路。
        """
        body = (text or "").strip()
        paths = _coerce_attachment_paths(attachments)
        if not body and not paths:
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
            json.dumps(
                {"sessionId": self._active, "text": body, "attachments": paths},
                ensure_ascii=False,
            ),
            flush=True,
        )
        try:
            turn_id = self._host.send(
                {"sessionId": self._active, "text": body, "attachments": paths}
            )["turnId"]
        except Exception as exc:  # noqa: BLE001 - 发送失败要显式暴露，不能装作已发出
            self._turn = None
            print("QML SEND FAILED", f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            return False
        print("QML TURN", turn_id, flush=True)
        self._render()
        self._publish()
        return True

    # ── 附件与交付卡（宿主与服务共用同一套判定）────────────────────────────
    @QtCore.Slot(result="QVariantList")
    def pickAttachments(self) -> List[str]:
        """回形针：真弹 `QFileDialog`，选中的路径登记白名单后回给 QML 待发列表。

        与宿主侧的附件白名单走同一套 `AttachmentService.inspect`：类型 / 体积
        不合规的文件会被判 `supported=false`，这里只把能进的交给消息，其余打印原因
        （界面不静默吞掉用户的选择）。对话框取消返回空列表。
        """
        try:
            picked = self._attachments.pick_attachments()
        except Exception as exc:  # noqa: BLE001 - 没有对话框 / 被取消：显式打日志，不假成功
            print("QML PICK FAILED", f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            return []
        paths: List[str] = []
        for item in picked:
            if item.get("supported"):
                paths.append(str(item.get("path") or ""))
            else:
                print(
                    "QML PICK REJECTED",
                    json.dumps(item, ensure_ascii=False),
                    file=sys.stderr,
                    flush=True,
                )
        print("QML PICK", json.dumps(paths, ensure_ascii=False), flush=True)
        return paths

    @QtCore.Slot(result="QVariantList")
    def attachmentChips(self) -> List[Dict[str, Any]]:
        """当前会话的用户附件贴片（名称 / 类型 / 真实体积 / 图片 data URI）。"""
        return attachment_rows(self._session())

    @QtCore.Slot(result="QVariantList")
    def deliveryItems(self) -> List[Dict[str, Any]]:
        """当前会话的交付卡行（文件名 / 真实体积 / 目录 / 能否打开 / 是否已不存在）。"""
        return delivery_rows(self._session())

    @QtCore.Slot(str, str, result=bool)
    def openDeliverable(self, tool_use_id: str, path: str) -> bool:
        """交付卡「打开」：只认边车登记的路径（`deliverables.open_item` 同一条不变式）。"""
        return bool(open_item(self._session(), tool_use_id, self._delivered_index(tool_use_id, path))["ok"])

    @QtCore.Slot(str, str, result=bool)
    def revealDeliverable(self, tool_use_id: str, path: str) -> bool:
        """交付卡「在文件夹中显示」：同样只认边车路径。"""
        return bool(reveal(self._session(), tool_use_id, self._delivered_index(tool_use_id, path))["ok"])

    @QtCore.Slot(str, result=bool)
    def copyDeliverablePath(self, path: str) -> bool:
        """交付卡「复制路径」：只复制边车里登记过的路径，任意字符串一律拒绝。"""
        if not self._path_is_delivered(path):
            print("QML COPY REJECTED", json.dumps(path), file=sys.stderr, flush=True)
            return False
        clipboard = QtGui.QGuiApplication.clipboard()
        if clipboard is None:  # pragma: no cover - 无 GUI 平台插件时不存在
            return False
        clipboard.setText(path)
        return clipboard.text() == path

    def _session(self) -> Any:
        """当前会话对象（没有选中会话时为 None）。"""
        return self._store.load_session(self._active) if self._active else None

    def _delivered_index(self, tool_use_id: str, path: str) -> int:
        """边车里这条工具调用的第几个文件；不在边车里返回 -1（服务层据此拒绝）。"""
        from mvvm.services.deliverables import delivered_paths

        paths = delivered_paths(self._session(), tool_use_id)
        try:
            return paths.index(path)
        except ValueError:
            return -1

    def _path_is_delivered(self, path: str) -> bool:
        from mvvm.services.deliverables import delivered_paths

        session = self._session()
        if session is None or not isinstance(path, str) or not path:
            return False
        sidecar = getattr(session, "delivered", None)
        if not isinstance(sidecar, dict):
            return False
        return any(path in delivered_paths(session, key) for key in sidecar)

    def _dialog_parent(self) -> Any:
        """对话框父窗口：QML 的根对象是 `QQuickWindow`（不是 `QWidget`）。

        `QFileDialog` 的父参数只接受 `QWidget`；把 `QQuickWindow` 传进去会抛
        `TypeError: __init__ called with wrong argument types`，回形针就永远弹不出来。
        窗口是 widgets 时用它做模态父窗口，否则传 None（对话框照样模态于应用）。
        """
        from utils.qt_compat import QtWidgets

        return self._window if isinstance(self._window, QtWidgets.QWidget) else None

    def _pick_files(self) -> List[str]:
        """`QFileDialog.getOpenFileNames`：过滤条件沿用原版 `showOpenDialog` 那一份。"""
        from utils.qt_compat import QtWidgets

        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self._dialog_parent(),
            "选择附加文件",
            "",
            "支持的文件 (*.png *.jpg *.jpeg *.gif *.webp *.pdf *.docx *.xlsx *.pptx *.doc "
            "*.xls *.ppt *.txt *.md *.markdown *.json *.yaml *.yml *.toml *.csv *.log "
            "*.js *.jsx *.ts *.tsx *.vue *.svelte *.html *.css *.scss *.xml *.py *.go "
            "*.rs *.java *.kt *.c *.h *.cpp *.cs *.php *.sh *.sql);;"
            "图片 (*.png *.jpg *.jpeg *.gif *.webp);;"
            "PDF (*.pdf);;"
            "所有文件 (*)",
        )
        return [str(path) for path in paths]

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
        # 只渲染一遍：`attach` 会把自有文档的内容整篇搬进 QML 文档，
        # 不需要（也不应该）在那里再重渲染一次。
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

    @QtCore.Slot()
    def scrollBottom(self) -> None:
        """贴到底（首帧之后 contentHeight 才准，渲染时那次可能还是 0）。"""
        self._scroll_to_bottom()

    def rerender(self) -> None:
        """窗口尺寸稳定/画面首帧之后重排一次（代码块宽度取容器宽）。"""
        self._render()

    def _persona_name(self, persona_id: str) -> str:
        """会话行副标题显示的角色名（原版 `.cf-thread__owner`）。未知 id 回落默认角色。"""
        if not self._persona_names:
            try:
                for item in PersonaStore(app_home()).list_personas():
                    self._persona_names[str(item.get("id"))] = str(item.get("name") or "")
            except OSError:
                self._persona_names = {}
        return self._persona_names.get(persona_id or "", "") or "Deva"

    def _rows(self) -> List[Dict[str, Any]]:
        """列表行：会话行 + 角色 id/名（副标题）。角色名只影响显示，不参与排序。

        可见会话元信息只取一次：行投影与副标题取 personaId 用的是同一份，没必要列两遍索引。
        """
        metas = self._store.visible_sessions()
        rows = session_rows(self._store, lang=self.language(), metas=metas)
        owner = {str(getattr(m, "id", "")): str(getattr(m, "personaId", "") or "general")
                 for m in metas}
        for row in rows:
            persona = owner.get(row["id"], "general")
            row["persona"] = persona
            row["personaName"] = self._persona_name(persona)
        return rows

    def _publish(self) -> None:
        window = self._window
        if window is None:
            return
        rows = self._rows()
        active = self._active if any(row["id"] == self._active for row in rows) else ""
        window.setProperty("sessions", rows)
        window.setProperty("activeId", active)
        window.setProperty(
            "activeTitle",
            next((row["title"] for row in rows if row["id"] == active), ""),
        )
        window.setProperty(
            "activePersona",
            next((row.get("personaName", "") for row in rows if row["id"] == active), "Deva"),
        )
        busy = bool(active) and self._host.is_busy(active)
        window.setProperty("busy", busy)
        window.setProperty("status", "输出中…" if busy else "就绪")
        # 附件贴片与交付卡：每次重绘都按当前会话现算（落盘为唯一真相源）。
        session = self._session() if active else None
        window.setProperty("attachments", attachment_rows(session))
        window.setProperty("deliveries", delivery_rows(session))

    def initial(self) -> None:
        """首帧之前：没有选中会话就选第一条（空数据时保持空状态）。"""
        rows = self._rows()
        if rows:
            self._active = rows[0]["id"]
            self._render()
        self._publish()


def _select_page(window: Any) -> str:
    """按环境变量让壳呈现指定页面状态（逐页对比用；缺省 chat 即真实启动态）。"""
    page = os.environ.get(PAGE_ENV, "").strip() or "chat"
    if page not in PAGE_NAMES:
        print("QML PAGE UNKNOWN", f"{page!r}", file=sys.stderr, flush=True)
        page = "chat"
    window.setProperty("page", page)
    return page


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
    from main import HEADLESS_TIMEOUT_S  # 超时只在这里定义一次（main 是唯一入口）

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

    # 必须是真 `QApplication`（而不是 `QGuiApplication`）：附件选择要 `QFileDialog`，
    # 文件类型图标回落要 `QFileIconProvider`，复制路径要剪贴板——三者都只在 QApplication
    # 下可用；只建 QGuiApplication 时 `provider.icon(...)` 会段错误（见
    # mvvm/services/deliverables.py 的 `_icon_data_url`）。
    from utils.qt_compat import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
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
    bridge = ShellBridge(
        host=host,
        store=store,
        plain=plain,
        settings=settings,
        vault=vault,
        skills=SkillStore(home),
    )
    bridge_box["bridge"] = bridge

    engine = QtQml.QQmlApplicationEngine()
    bridge._engine = engine
    engine.rootContext().setContextProperty("shellBridge", bridge)
    engine.load(QtCore.QUrl.fromLocalFile(str(qml_main_path)))
    roots = engine.rootObjects()
    if not roots:
        print("QML FAILED", "reason=engine loaded no root object", file=sys.stderr, flush=True)
        return 1
    window = roots[0]
    bridge.bind_window(window)
    bridge.initial()
    _select_page(window)

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
    bridge.scrollBottom()
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
