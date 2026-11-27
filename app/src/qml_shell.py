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
from native_i18n import translate
from locale_runtime import tr

import asyncio
import base64
import json
import os
import queue
import sys
import threading
import tempfile
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List

from mvvm.services.attachments import AttachmentService
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.compaction import (
    CompactModel,
    context_window_for,
    estimate_tokens,
    trigger_tokens_for,
)
from mvvm.services.model_view import model_messages
from mvvm.services.deliverables import open_item, reveal
from mvvm.services.effort import (
    clamp_effort,
    is_toggle_effort,
    is_effort_level,
    supported_effort_levels,
)
from mvvm.services.model_resolve import resolve_default_model, resolve_ref
from mvvm.services.persona_store import PersonaStore
from mvvm.services.plugin_identity import shared_store
from mvvm.services.provider_registry import app_version
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services import settings_models
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

# 关于页「检查更新」：原版 UpdateSection.tsx -> window.deva.update.check() 走主进程 updater，
# 这里用同一个 GitHub releases 数据源做最小可验证实现；状态只回传界面，不自动下载安装。
UPDATE_RELEASES_API = "https://api.github.com/repos/sqfcyily/deva/releases/latest"
UPDATE_TIMEOUT_S = 15

# 原版「文字大小」倍率（deva tokens.css `--chat-scale`）：标准 = 1，其余据 14px 基准。
CHAT_SCALES = {"sm": 13.0 / 14.0, "md": 1.0, "lg": 15.5 / 14.0, "xl": 17.0 / 14.0}
CHAT_SIZE_ORDER = ("sm", "md", "lg", "xl")
THEME_ORDER = ("system", "light", "dark")
# 界面文案：壳里只有设置页的行标签需要本地化（其余来自数据或图标）。
SETTINGS_LABELS = {lang: {'language': translate(locale, 'settings.language'), 'theme': translate(locale, 'settings.theme'), 'textSize': translate(locale, 'settings.chatFontSize'), 'themeSystem': translate(locale, 'settings.themeSystem'), 'themeLight': translate(locale, 'settings.themeLight'), 'themeDark': translate(locale, 'settings.themeDark'), 'fontSm': translate(locale, 'settings.chatFontSm'), 'fontMd': translate(locale, 'settings.chatFontMd'), 'fontLg': translate(locale, 'settings.chatFontLg'), 'fontXl': translate(locale, 'settings.chatFontXl'), 'providers': translate(locale, 'models.providers'), 'noProviders': translate(locale, 'models.noProvidersYet'), 'modelCount': translate(locale, 'models.modelCount'), 'extensions': translate(locale, 'activity.extensions'), 'builtIn': translate(locale, 'extensions.builtin'), 'kindSkill': translate(locale, 'cf.kindSkill'), 'extEmpty': translate(locale, 'cf.extEmpty')} for lang, locale in (('zh', 'zh-CN'), ('en', 'en'))}

# 思考等级文案：逐字取自原版 `i18n/messages.ts` 的 `chat.effort.*`（zh 216-236 / en 1749-1772）。
# 名字与说明分开：菜单每档一行为「名字 + 说明」，贴片只写名字。
EFFORT_TEXT = {lang: {'title': translate(locale, 'chat.effort.title'), 'on': translate(locale, 'chat.effort.on'), 'onHint': translate(locale, 'chat.effort.onHint'), 'levels': {'default': translate(locale, 'chat.effort.levels.default'), 'low': translate(locale, 'chat.effort.levels.low'), 'medium': translate(locale, 'chat.effort.levels.medium'), 'high': translate(locale, 'chat.effort.levels.high'), 'xhigh': translate(locale, 'chat.effort.levels.xhigh'), 'max': translate(locale, 'chat.effort.levels.max')}, 'hints': {'default': translate(locale, 'chat.effort.hints.default'), 'low': translate(locale, 'chat.effort.hints.low'), 'medium': translate(locale, 'chat.effort.hints.medium'), 'high': translate(locale, 'chat.effort.hints.high'), 'xhigh': translate(locale, 'chat.effort.hints.xhigh'), 'max': translate(locale, 'chat.effort.hints.max')}} for lang, locale in (('zh', 'zh-CN'), ('en', 'en'))}
# 列表筛选与空态文案（原版 `cf.searchChats` / `cf.searchNoResults` / `chat.noSessions`）。
LIST_TEXT = {lang: {'searchChats': translate(locale, 'cf.searchChats'), 'noMatches': translate(locale, 'cf.searchNoResults'), 'noSessions': translate(locale, 'chat.noSessions')} for lang, locale in (('zh', 'zh-CN'), ('en', 'en'))}
# 无任何对话时的快速开启（原版 `i18n/messages.ts:1368-1369` 中文 / `:2883-2884` 英文）。
QUICK_TEXT = {lang: {'quickStartTitle': translate(locale, 'cf.quickStartTitle'), 'quickStartHint': translate(locale, 'cf.quickStartHint')} for lang, locale in (('zh', 'zh-CN'), ('en', 'en'))}
# 输入区贴片的兜底文案（没有可选模型时，原版显示 `chat.selectModel`）。
CHAT_TEXT = {lang: {'selectModel': translate(locale, 'chat.selectModel'), 'selectModelTitle': translate(locale, 'chat.selectModel'), 'context': translate(locale, 'chat.panel.context'), 'approx': translate(locale, 'chat.panel.approx'), 'usage': translate(locale, 'chat.panel.usage'), 'autoCompact': translate(locale, 'chat.panel.autoCompact')} for lang, locale in (('zh', 'zh-CN'), ('en', 'en'))}

# 页面名 → 让壳呈现该状态的标识；18 页对比清单见 scripts/parity/qml_pages_all.sh，
# 末尾两项是本轮详情/高级设置截图用的单页状态，不加入 18 页全量清单。
PAGE_NAMES = (
    "chat", "empty", "first-run", "search-open", "search-results", "search-none",
    "settings-general", "settings-models", "settings-models-provider",
    "settings-models-advanced", "settings-extensions", "settings-about",
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


def _open_external(url: str) -> bool:
    """用系统默认浏览器打开已经验证过 scheme 的链接（测试可替换此函数）。"""
    return bool(QtGui.QDesktopServices.openUrl(QtCore.QUrl(url)))


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


def _version_tuple(value: str) -> tuple:
    """比较版本号：只取数字段，忽略预发布后缀（与 updater.ts 的 semver newer 判定同量级）。"""
    parts = []
    for chunk in value.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def new_session_id() -> str:
    """新会话 id：渲染层用 `chat-<时间36><随机>` 的同一形状（复用 `base36`）。"""
    from mvvm.services.chat_session_store import base36

    return "qml-%s%s" % (base36(time.time() * 1000), uuid.uuid4().hex[:6])


class ShellBridge(QtCore.QObject):
    """QML 调过来的入口，以及回合事件回写 QML 属性的唯一出口。"""

    # 关于页检查更新：worker 线程算完发一次状态，QML 的 Connections 接收。
    updateStateChanged = QtCore.Signal("QVariantMap")
    interactionsChanged = QtCore.Signal('QVariantList')

    # 深浅主题：QML 侧 `Theme.dark` 绑这个属性（Main.qml 里一条 Binding）。
    # 为什么不写 Theme 单例的 property：`QQmlApplicationEngine.singletonInstance()`
    # 对 qmldir 里声明 `singleton` 的 QML 文件单例返回的是 QJSValue，`.setProperty()`
    # 落不到 QObject 上（实测 value 不变），主题切了个寂寞。走 context property 才可靠。
    extensionsChanged = QtCore.Signal()
    localeChanged = QtCore.Signal()
    darkModeChanged = QtCore.Signal()
    themeChoiceChanged = QtCore.Signal()
    _preparedReady = QtCore.Signal()

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
        self._mount_session = ""
        # Persisted, user-selected roots retain trust across application restarts.
        for meta in store.list_sessions():
            root = getattr(meta, "focusRoot", None)
            if root and Path(root).is_dir() and str(Path(root).resolve()) == root:
                self._host.guard.trust_root(root)
        self._last_interactions = []
        self._pump: Any = None
        self._turn: Any = None  # qml_shell_sessions.TurnState | None
        self._turn_session = ""
        # 当前在跑回合的 turnId：原版 Composer 的停止键走 `chat:abort(turnId)`；
        # 这里保存 send() 的返回值，停止时按 id 取消，未跑回合时为空串。
        self._turn_id = ""
        # 未读会话 id：原版 Rail.tsx:1124-1156 在头像右上角打红点；当前会话打开即清除。
        self._unread: set[str] = set()
        self._attention: set[str] = set()
        # 回复完成/错误通知：由 run() 注入 TrayController.notify；无托盘时为 None。
        self._notifier: Any = None
        # 回合中输入的插话：原版 chat:insert；后端没有步内注入，如实排到本轮结束后的下一轮。
        self._pending_inserts: List[str] = []
        # 检查更新的状态机：idle / checking / latest / available / error。
        self._update_state: Dict[str, Any] = {"phase": "idle"}
        self._update_thread: Any = None
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
        self._preparedReady.connect(self._finish_prepared_render, QtCore.Qt.QueuedConnection)
        self._render_epoch = 0
        self._render_jobs = []
        self._render_executor = None
        from markdown.cache import DisplayCache
        self._display_cache = DisplayCache()
        self._display_key = None
        self.rendered = 0
        self.deltas: List[str] = []
        self.stop = ""

        from markdown.body import BodyDocument

        self._body = BodyDocument(content_width=BODY_WIDTH)
        self._body.set_image_resolver(_load_image)
        # 首帧之前就把深浅算好：QML 的 Theme.dark 绑在 darkMode 上，晚一拍会闪白。
        self._dark = self._resolve_dark()
        hints = QtGui.QGuiApplication.styleHints()
        hints.colorSchemeChanged.connect(self._system_theme_changed)
        self._sync_body_style()

    # ── 装配 ──────────────────────────────────────────────────────────────
    def bind_window(self, window: Any) -> None:
        self._window = window
        self._sync_theme_singleton()

    @QtCore.Slot(str, str, result=str)
    def pluginSettings(self, operation: str, payload: str) -> str:
        from mvvm.services.plugin_settings import PluginSettings
        import json
        service = PluginSettings(self._settings, self._vault)
        try:
            data = json.loads(payload or "{}")
            if operation == "saveModel":
                service.save_custom(data.get("baseUrl", ""), data.get("model", ""), data.get("key"))
            elif operation == "saveServer":
                service.save_server(data["id"], data["config"], data.get("key"))
            elif operation == "deleteServer":
                service.delete_server(data["id"])
            elif operation == "saveIdentity":
                service.save_identity(data["id"], data["text"])
                self._persona_names = {}
                self._publish()
            elif operation == "saveApproval":
                service.write(approvalEnabled=data.get('enabled') is True)
            elif operation not in ("read", "identities"):
                raise ValueError(tr('legacy.e33129d04c41'))
            return json.dumps({"ok": True, "model": service.custom(), "servers": service.servers(), "approvalEnabled": service.data().get('approvalEnabled') is True,
                               "identities": service.identities() if operation in ("identities", "saveIdentity") else []})
        except (ValueError, OSError, KeyError) as exc:
            from native_i18n import translate_error
            return json.dumps({"ok": False, "error": translate_error(self.locale, str(exc))})

    @QtCore.Slot(result='QVariantList')
    def pendingInteractions(self):
        controller = getattr(self._host, 'interactions', None)
        return controller.pending(self._active) if controller else []

    @QtCore.Slot(str, str, str, result=bool)
    def answerInteraction(self, request_id, outcome, answer):
        controller = getattr(self._host, 'interactions', None)
        return bool(controller and controller.answer(self._active, request_id, outcome, answer))

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
        return "zh" if QtCore.QLocale.system().name().lower().startswith("zh") else "en"

    @QtCore.Property(str, notify=localeChanged)
    def locale(self):
        return "zh-CN" if self.language() == "zh" else "en"

    @QtCore.Slot(str, result=str)
    def translate(self, key):
        from native_i18n import translate
        return translate(self.locale, key)

    @QtCore.Slot(result="QVariantMap")
    def labels(self) -> Dict[str, str]:
        """设置页文案（界面语言跟随 config.json 的 locale）。"""
        return dict(SETTINGS_LABELS[self.language()])

    @QtCore.Slot(result=str)
    def appVersion(self) -> str:
        """About 页版本号：只从 provider_registry.app_version() 取，QML 不写版本字面量。"""
        return app_version()

    @QtCore.Slot(result="QVariantMap")
    def updateState(self) -> Dict[str, Any]:
        """当前检查更新状态（About 页重新挂载时接回已有状态）。"""
        return dict(self._update_state)

    @QtCore.Slot()
    def checkForUpdates(self) -> None:
        """原版 UpdateSection 的 `check()`：只触发检查，不自动下载安装。"""
        if self._update_state.get("phase") == "checking":
            return
        self._set_update_state({"phase": "checking"})
        thread = threading.Thread(target=self._check_updates_worker, daemon=True)
        self._update_thread = thread
        thread.start()

    def _set_update_state(self, state: Dict[str, Any]) -> None:
        self._update_state = dict(state)
        self.updateStateChanged.emit(dict(state))

    def _check_updates_worker(self) -> None:
        state: Dict[str, Any]
        try:
            request = urllib.request.Request(
                UPDATE_RELEASES_API,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": f"deva/{app_version()}",
                },
            )
            with urllib.request.urlopen(request, timeout=UPDATE_TIMEOUT_S) as response:
                payload = json.loads(response.read().decode("utf-8"))
            tag = str(payload.get("tag_name") or "").strip().lstrip("vV")
            if not tag:
                raise ValueError(tr('legacy.3682234e64de'))
            if _version_tuple(tag) > _version_tuple(app_version()):
                state = {
                    "phase": "available",
                    "version": tag,
                    "url": str(payload.get("html_url") or ""),
                }
            else:
                state = {"phase": "latest", "version": app_version()}
        except Exception as exc:  # 网络 / 解析失败都如实回到界面
            state = {"phase": "error", "message": f"{type(exc).__name__}: {exc}"}
        try:
            self._set_update_state(state)
        except RuntimeError:
            # 窗口已销毁时对象可能已断开，忽略这一次收尾。
            pass

    @QtCore.Slot(result=str)
    def theme(self) -> str:
        value = self._config().get("theme")
        return value if value in THEME_ORDER else "system"

    @QtCore.Property(str, notify=themeChoiceChanged)
    def themeChoice(self) -> str:
        return self.theme()

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
        if value not in ("zh", "zh-CN", "en"):
            return False
        target = "zh-CN" if value in ("zh", "zh-CN") else "en"
        if not self._write_config({"locale": target}):
            return False
        self.localeChanged.emit()
        self._publish()
        self._render()
        return True

    @QtCore.Slot(str, result=bool)
    def setTheme(self, value: str) -> bool:
        if value not in THEME_ORDER:
            return False
        if not self._write_config({"theme": value}):
            return False
        self.themeChoiceChanged.emit()
        self._apply_theme()
        return True

    @QtCore.Slot(result=bool)
    def sidebarCollapsed(self) -> bool:
        """会话列表是否收起（原版 `loadLayout().sidebarCollapsed` 落盘在 layout 里）。"""
        return bool(self._config().get("sidebarCollapsed", False))

    @QtCore.Slot(bool, result=bool)
    def setSidebarCollapsed(self, collapsed: bool) -> bool:
        """Ctrl/Cmd+B 的持久化：写 config.json 的 sidebarCollapsed。"""
        return self._write_config({"sidebarCollapsed": bool(collapsed)})

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
        return (scheme() if callable(scheme) else scheme) == QtCore.Qt.ColorScheme.Dark

    @QtCore.Slot()
    def _system_theme_changed(self) -> None:
        if self.theme() == "system":
            self._apply_theme()

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
        self._unread.discard(self._active)
        self._turn = None
        self._turn_session = ""
        self._publish()
        self._prepare_render()
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

    @QtCore.Slot(str, result=bool)
    def deleteSession(self, session_id: str) -> bool:
        """删除一条真实会话；删当前会话时按 Deva `openFirstSession` 选后备。

        Deva `deleteSession` 先 reload 列表，再 `openFirstSession(list)`：
        在剩下的非归档/非成员会话里取 `updatedAt` 最大的一条；一条都没有就回到空态。
        """
        key = str(session_id or "")
        if not key or not self._store.session_path(key).exists():
            return False
        self._host.delete_session(key)
        if self._active == key:
            rows = self._rows()
            self._active = str(rows[0]["id"]) if rows else ""
            self._turn = None
            self._turn_session = ""
            self._render()
        self._publish()
        return True

    @QtCore.Slot(str, str, result=bool)
    def renameSession(self, session_id: str, title: str) -> bool:
        """重命名会话：走 `ChatHost.rename_session`（与 Web 入口同一条服务链路）。

        `ChatHost` 负责原版的空白折叠、长度上限与「空标题恢复自动标题」规则；
        壳只负责刷新列表。未建档会话返回 false。
        """
        key = str(session_id or "")
        if not key:
            return False
        result = self._host.rename_session({"sessionId": key, "title": str(title or "")})
        if not result:
            return False
        self._publish()
        return True

    @QtCore.Slot(str, result=bool)
    def archiveSession(self, session_id: str) -> bool:
        """归档会话：走 `ChatHost.set_archived`，并复刻 Deva 的当前会话回退。

        `ChatHost` 会拒绝进行中的会话（`{"ok": false}`），壳不做第二套忙碌判定。
        当前会话被归档后，列表按 `visible_sessions()` 取最近一条作为新的当前会话。
        """
        key = str(session_id or "")
        if not key:
            return False
        result = self._host.set_archived({"sessionId": key, "archived": True})
        if not result or not result.get("ok"):
            return False
        if self._active == key:
            rows = self._rows()
            self._active = str(rows[0]["id"]) if rows else ""
            self._turn = None
            self._turn_session = ""
            self._render()
        self._publish()
        return True

    @QtCore.Slot(str, result=bool)
    def unarchiveSession(self, session_id: str) -> bool:
        """把会话移回对话列表：与归档共用 `ChatHost.set_archived`。"""
        key = str(session_id or "")
        if not key:
            return False
        result = self._host.set_archived({"sessionId": key, "archived": False})
        if not result or not result.get("ok"):
            return False
        self._publish()
        return True

    @QtCore.Slot("QVariantList", bool, result=int)
    def archiveSessions(self, session_ids: list, archived: bool) -> int:
        """批量操作只发布最终状态，避免逐条回退、渲染即将归档的正文。"""
        failed = 0
        changed = False
        active_archived = False
        for session_id in session_ids:
            key = str(session_id or "")
            result = self._host.set_archived({"sessionId": key, "archived": archived})
            if not result or not result.get("ok"):
                failed += 1
                continue
            changed = True
            active_archived = active_archived or (archived and key == self._active)
        if active_archived:
            rows = self._rows()
            self._active = str(rows[0]["id"]) if rows else ""
            self._turn = None
            self._turn_session = ""
            self._render()
        if changed:
            self._publish()
        return failed

    # ── 快速开启（无任何对话时的中列）────────────────────────────────────────
    @QtCore.Slot(result=list)
    def quickStartPersonas(self) -> List[Dict[str, Any]]:
        """无对话空态的角色卡片，形状对齐原版 `QuickStart`（`Rail.tsx:1296-1326`）。

        原版直接遍历 `personas`（`useExtensions()`，即 `personas:list` 的同一份排好序的
        花名册）：`<Avatar persona={p} size={48} />` + `p.name` + `p.desc`。这里同样现读
        `PersonaStore.list_personas()`，不另存一份投影——角色改名/改描述/新加文件后
        下次重绘就是新的，空态不会停在开机那一刻的旧列表。
        """
        try:
            records = shared_store().list_personas()
        except OSError:
            return []
        return [
            {
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or item.get("id") or ""),
                "desc": str(item.get("description") or ""),
                # 自定义头像（data URI）优先；空串时 QML 走预生成的 `avatars/<id>.svg`。
                "avatarImage": str(item.get("avatarImage") or ""),
            }
            for item in records
            if item.get("id")
        ]

    @QtCore.Slot(result="QVariantList")
    def personaRecords(self) -> List[Dict[str, Any]]:
        """角色管理列表：与 quickStart 同一份 PersonaStore 记录，但带完整字段。"""
        return shared_store().list_personas()

    @QtCore.Slot(str, result="QVariantMap")
    def personaDetail(self, persona_id: str) -> Dict[str, Any]:
        return shared_store().get(str(persona_id or "")) or {}

    @QtCore.Slot(str, result=bool)
    def personaSave(self, payload: str) -> bool:
        """新建/编辑角色：写 frontmatter + prompt（原版 personas:upsert）。"""
        try:
            data = json.loads(payload or "{}")
            shared_store().upsert(data)
            self._publish()
            return True
        except (OSError, ValueError, TypeError, KeyError):
            return False

    @QtCore.Slot(str, result=bool)
    def personaDelete(self, persona_id: str) -> bool:
        result = shared_store().remove(str(persona_id or ""))
        self._publish()
        return bool(result.get("ok", True))

    @QtCore.Slot(str, bool, result=bool)
    def personaSetEnabled(self, persona_id: str, enabled: bool) -> bool:
        result = shared_store().set_enabled(str(persona_id or ""), bool(enabled))
        self._publish()
        return bool(result.get("ok", True))

    @QtCore.Slot("QVariantList", result=bool)
    def personaReorder(self, ids: Any) -> bool:
        result = shared_store().reorder([str(value) for value in (ids or [])])
        self._publish()
        return bool(result.get("ok", True))

    @QtCore.Slot(str, result=str)
    def personaPickAvatar(self, persona_id: str) -> str:
        """选择图片并写入角色头像；返回 data URI（失败空串）。"""
        from utils.qt_compat import QtWidgets
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self._dialog_parent(), self.translate("native.pickFiles"), "",
            self.translate("native.images") + " (*.png *.jpg *.jpeg *.gif *.webp)")
        if not paths:
            return ""
        try:
            data = Path(paths[0]).read_bytes()
            mime = "image/png" if paths[0].lower().endswith(".png") else "image/jpeg"
            uri = "data:%s;base64,%s" % (mime, base64.b64encode(data).decode("ascii"))
            shared_store().set_avatar_image(str(persona_id or ""), uri)
            self._publish()
            return uri
        except OSError:
            return ""

    @QtCore.Slot(str, result=bool)
    def personaClearAvatar(self, persona_id: str) -> bool:
        try:
            shared_store().clear_avatar_image(str(persona_id or ""))
            self._publish()
            return True
        except OSError:
            return False

    @QtCore.Slot(str, result=str)
    def startQuickStart(self, persona_id: str) -> str:
        """点头像开新对话：等价原版 `startWith`（`ChatFirstShell.tsx:408-411`）。

        `newSession(personaId, undefined, personas.find(p => p.id === personaId)?.model)`：
        建一条绑定该角色（以及角色自带模型，若有）的会话并落盘，随即切过去。角色 id 非法
        或不存在时什么都不做、返回空串——原版这时 `newSession` 拿到的是一个查不到的角色，
        宁可停在原地也不建一条绑定未知角色的空对话。
        """
        record = shared_store().get(str(persona_id or ""))
        if record is None:
            return ""
        session_id = new_session_id()
        self._host.create_session(
            {
                "sessionId": session_id,
                "personaId": record["id"],
                "modelRef": str(record.get("model") or "") or None,
            }
        )
        self._active = session_id
        self._turn = None
        self._turn_session = ""
        self._render()
        self._publish()
        return session_id

    # ── 设置页数据（真实来源：config.json / skills 目录 / secrets 库）────────────
    def _has_key(self, provider_id: str) -> bool:
        """该服务商是否已存密钥（只读布尔；明文不出服务层）。"""
        if self._vault is None or not provider_id:
            return False
        try:
            return bool(self._vault.has_secret(provider_id))
        except OSError:  # 钥匙串/密文读失败按「没有」处理，不让设置页整页崩
            return False

    @QtCore.Slot(result=list)
    def modelRows(self) -> List[Dict[str, Any]]:
        """模型页列表：原版只列「在用」的服务商（已启用 / 已配密钥 / 自定义）。

        行形状对齐原版 `provider-row`：名称、`N models`、启用点、缺密钥警告、详情箭头。
        过滤与判定都在 `settings_models`（同一份规则被列表/详情/写回共用）。
        """
        return settings_models.provider_rows(self._models_section(), self._has_key, self.language())

    @QtCore.Slot(result="QVariantMap")
    def modelsPaneLabels(self) -> Dict[str, Any]:
        """模型页文案（标题 / 空态 / 添加按钮 / 详情页标签），界面语言跟随 config.json。"""
        return settings_models.models_text(self.language())

    @QtCore.Slot(str, result="QVariantMap")
    def providerDetail(self, provider_id: str) -> Dict[str, Any]:
        """服务商详情页投影；id 不存在返回空字典（界面据此退回列表，不画半页）。"""
        detail = settings_models.provider_detail(
            self._models_section(), provider_id, self.language(), self._has_key
        )
        return detail or {}

    @QtCore.Slot(str, str, str, result=bool)
    def setProviderField(self, provider_id: str, field: str, value: str) -> bool:
        """改服务商的一个文本/布尔字段（名称、地址、启用位）。

        只收这三类：密钥走钥匙串、协议/模型清单有各自入口——把任意字段名直接写进配置
        会让界面一个拼写错误就改坏别的东西。
        """
        if field not in ("name", "apiHost", "enabled"):
            return False
        if field == "enabled":
            patch: Dict[str, Any] = {"enabled": value == "1"}
        elif field == "name":
            name = value.strip()
            if not name:
                return False
            patch = {"name": name}
        else:
            patch = {"apiHost": value.strip().rstrip("/")}
        return self._commit_models(settings_models.update_provider(self._models_section(), provider_id, patch))

    @QtCore.Slot(str, result=bool)
    def deleteProvider(self, provider_id: str) -> bool:
        """删除服务商：配置里的条目与钥匙串里的密钥一起删（原版 `removeProvider`）。"""
        updated = settings_models.remove_provider(self._models_section(), provider_id)
        if updated is None:
            return False
        if not self._commit_models(updated):
            return False
        if self._vault is not None:
            try:
                self._vault.delete_secret(provider_id)
            except OSError as exc:  # 配置已删，密钥删失败要留下痕迹
                print("QML SECRET FAILED", f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return True

    @QtCore.Slot(result=str)
    def addProvider(self) -> str:
        """新建自定义对话服务商并返回其 id（原版 `addCustomProvider`）；失败返回空串。"""
        section = self._models_section()
        existing = {str(p.get("id")) for p in settings_models.provider_entries(section)}
        base = "custom"
        index = 1
        while f"{base}-{index}" in existing:
            index += 1
        provider_id = f"{base}-{index}"
        name = settings_models.models_text(self.language())["newProviderName"]
        provider = settings_models.new_provider(section, provider_id, name)
        return provider_id if self._commit_models(settings_models.add_provider(section, provider)) else ""

    @QtCore.Slot(str, str, bool, result=bool)
    def setModelEnabled(self, provider_id: str, model_id: str, enabled: bool) -> bool:
        """模型行开关：写 `models[].enabled`（原版 `toggleModel`）。"""
        return self._commit_models(
            settings_models.set_model_enabled(self._models_section(), provider_id, model_id, enabled)
        )

    @QtCore.Slot(str, str, result=bool)
    def addModel(self, provider_id: str, model_id: str) -> bool:
        return self._commit_models(settings_models.add_model(self._models_section(), provider_id, model_id))

    @QtCore.Slot(str, str, result=bool)
    def removeModel(self, provider_id: str, model_id: str) -> bool:
        return self._commit_models(settings_models.remove_model(self._models_section(), provider_id, model_id))

    @QtCore.Slot(str, "QVariantList", result=bool)
    def setProviderHeaders(self, provider_id: str, rows: Any) -> bool:
        """自定义请求头：把界面上的行整理成表写进 `models.providers[].headers`。

        行来自 QML（`[{name, value}, ...]`）；整理规则（保留名 / 非法字符 / 32 条上限）
        在 `provider_headers.sanitize_headers`，与发出请求时同一份，界面写的就等于会发的。
        """
        raw: Dict[str, Any] = {}
        for row in rows if isinstance(rows, list) else []:
            if isinstance(row, dict):
                raw[str(row.get("name") or "")] = row.get("value")
        return self._commit_models(settings_models.set_headers(self._models_section(), provider_id, raw))

    def _commit_models(self, models: Any) -> bool:
        """新的 `models` 段落盘并让界面重读；None = 目标不存在/未改动成功。

        `config:set` 只做顶层浅合并，所以整段 `models` 回写（`_write_models` 同一条路径），
        漏写兄弟字段就会被清掉。
        """
        if models is None:
            return False
        if not self._write_models(models):
            return False
        self._publish()
        return True

    # ── 输入区贴片：模型菜单 / 思考等级（原版 ModelPanel.tsx + EffortPicker.tsx）──────
    def _models_section(self) -> Dict[str, Any]:
        section = self._config().get("models")
        return section if isinstance(section, dict) else {}

    def _active_ref(self) -> Any:
        """本对话生效的模型引用。

        原版 `ModelPanel.tsx:49`：本对话已选 → 否则回落「最近使用」（`models.activeModelId`），
        与主进程 `resolveModelRef` 的兜底同一口径；两者都解析不出才留空。
        """
        section = self._models_section()
        session = self._session() if self._active else None
        stored = getattr(session, "model", None) if session is not None else None
        return resolve_ref(stored, section) or resolve_default_model(section)

    def _active_effort(self) -> str:
        """本对话生效档位：会话定格值 > 全局最近使用 > 默认（`ModelGateway.effort_level` 同口径）。"""
        session = self._session() if self._active else None
        stored = getattr(session, "effort", None) if session is not None else None
        if isinstance(stored, str) and stored:
            return stored
        value = self._models_section().get("activeEffort")
        return value if isinstance(value, str) and value else "default"

    @QtCore.Slot(result=list)
    def modelMenuGroups(self) -> List[Dict[str, Any]]:
        """模型菜单：已启用服务商 × 已启用模型，按服务商分组（原版 `ModelPanel.tsx:38`）。

        只列对话模型（`purpose == 'llm'`）：决策模型不生成文本，绝不可被选为对话模型。
        没有模型的组不出现；组内顺序沿用配置顺序（原版同样不过滤顺序）。
        """
        providers = self._models_section().get("providers")
        groups: List[Dict[str, Any]] = []
        for provider in providers if isinstance(providers, list) else []:
            if not isinstance(provider, dict):
                continue
            if provider.get("enabled") is not True:
                continue
            if (provider.get("purpose") or "llm") != "llm":
                continue
            models = provider.get("models")
            items = [
                {
                    "id": str(model.get("id") or ""),
                    "name": str(model.get("name") or model.get("id") or ""),
                }
                for model in (models if isinstance(models, list) else [])
                if isinstance(model, dict) and model.get("enabled") is True and model.get("id")
            ]
            if not items:
                continue
            groups.append(
                {
                    "id": str(provider.get("id") or ""),
                    "name": str(provider.get("name") or provider.get("id") or ""),
                    "models": items,
                }
            )
        return groups

    @QtCore.Slot(result="QVariantMap")
    def effortMenu(self) -> Dict[str, Any]:
        """思考等级菜单：档位收敛到当前模型真正支持的那几档（原版 `EffortPicker.tsx`）。

        `levels` 空 = 该模型不支持思考等级（原版此时整个贴片不出现）；`toggle` = 只能开、
        不能调档，唯一一档显示为「开启」。名字与说明逐字取自原版 i18n。
        """
        text = EFFORT_TEXT[self.language()]
        active = self._active_ref()
        adapter = active.adapter if active is not None else ""
        model_id = active.model if active is not None else ""
        levels = supported_effort_levels(adapter, model_id) if adapter else []
        toggle = is_toggle_effort(adapter, model_id) if levels else False
        options: List[Dict[str, Any]] = []
        for level in (["default"] + levels) if levels else []:
            name = text["on"] if toggle and level != "default" else text["levels"].get(level, level)
            hint = text["onHint"] if toggle and level != "default" else text["hints"].get(level, "")
            options.append({"level": level, "name": name, "hint": hint})
        current = clamp_effort(adapter, model_id, self._active_effort()) if levels else "default"
        return {
            "title": text["title"],
            "toggle": toggle,
            "current": current,
            # 「默认」只放灯泡：贴片文案为空串（原版 `current !== 'default'` 才写名字）。
            "label": "" if current == "default" else text["on"] if toggle else text["levels"].get(current, current),
            "options": options,
        }

    @QtCore.Slot(result="QVariantMap")
    def chatLabels(self) -> Dict[str, Any]:
        """输入区/列表的本地化文案（模型贴片兜底名、搜索占位、两种空态、快速开启）。"""
        return {**CHAT_TEXT[self.language()], **LIST_TEXT[self.language()], **QUICK_TEXT[self.language()]}

    @QtCore.Slot(result="QVariantMap")
    def contextUsage(self) -> Dict[str, Any]:
        """本对话的上下文占用（原版 `chat:context-usage`，只读，不参与任何判定）。

        读数口径与压缩判定同一套：回合结束后的 `session.lastInputTokens` 优先；没有时按
        `estimate_tokens(model_messages(...))` 估算并标 `estimated`。窗口与压缩线直接调
        `compaction.context_window_for` / `trigger_tokens_for`，用户改窗口、引擎从报错学到的
        真实窗口都会反映到这里，壳里不另存一份真相。

        `used` 为 None = 没有读数（新对话 / 没有可用模型），QML 据此不画圆环。
        """
        section = self._models_section()
        ref = self._active_ref()
        session = self._session() if self._active else None
        if ref is None:
            return {"used": None, "estimated": False, "window": 0, "trigger": None}
        model = CompactModel(
            adapter=ref.adapter,
            provider_id=ref.provider_id,
            base_url=ref.base_url,
            model=ref.model,
        )
        window = context_window_for(model, section)
        trigger = trigger_tokens_for(model, section)
        messages = list(getattr(session, "messages", None) or []) if session is not None else []
        if not messages:
            return {"used": None, "estimated": False, "window": window, "trigger": trigger}
        last = getattr(session, "lastInputTokens", None)
        if isinstance(last, int) and last > 0:
            return {"used": last, "estimated": False, "window": window, "trigger": trigger}
        return {
            "used": estimate_tokens(model_messages(messages)),
            "estimated": True,
            "window": window,
            "trigger": trigger,
        }

    @QtCore.Slot(str, str, result=bool)
    def setActiveModel(self, provider_id: str, model_id: str) -> bool:
        """点选模型：本对话定格 + 记为「最近使用」，两处都落盘（原版 `ModelPanel.tsx:95`）。

        失败显式返回 False（模型不存在 / 配置写失败），界面据此提示，不做假成功。
        """
        section = self._models_section()
        if resolve_ref(f"{provider_id}:{model_id}", section) is None:
            return False
        models = dict(section)
        models["activeModelId"] = f"{provider_id}:{model_id}"
        if not self._write_models(models):
            return False
        if self._active and not self._store.set_model(self._active, f"{provider_id}:{model_id}"):
            # 会话尚未建档（惰性会话）不是错误：原版同样返回 `{ok:false}` 且不建档，
            # 由首发时的覆盖层落库。这里同样只记「最近使用」，不报失败。
            pass
        self._publish()
        return True

    @QtCore.Slot(str, result=bool)
    def setActiveEffort(self, level: str) -> bool:
        """点选档位：本对话定格 + 记为「最近使用」（原版 `ModelPanel.tsx:105`）。"""
        if not is_effort_level(level):
            return False
        models = dict(self._models_section())
        models["activeEffort"] = level
        if not self._write_models(models):
            return False
        if self._active:
            self._store.set_effort(self._active, None if level == "default" else level)
        self._publish()
        return True

    def _write_models(self, models: Dict[str, Any]) -> bool:
        """`models` 段整块写回（`config:set` 只做顶层浅合并，漏写兄弟字段即被清掉）。"""
        cleaned = {key: value for key, value in models.items() if value is not None}
        return self._write_config({"models": cleaned})

    @QtCore.Slot(str, bool, result=str)
    def personaAvatar(self, key, pop):
        from mvvm.services.humation import Humation
        if not hasattr(self, '_humation'): self._humation = Humation()
        record = shared_store().get(key) or {}
        return self._humation.image(key, record.get('avatar', ''), pop)

    @QtCore.Slot(str, result=str)
    def personaVeil(self, key):
        # Use the same generated shape, including non-circular avatar specs.
        import re
        from urllib.parse import unquote, quote
        svg = unquote(self.personaAvatar(key, False).split(',', 1)[1])
        viewbox = re.search(r'viewBox="([^"]+)"', svg).group(1)
        shape = re.search(r'<clipPath id="c"><path d="([^"]+)"', svg).group(1)
        return 'data:image/svg+xml,' + quote(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="' + viewbox +
            '"><path d="' + shape + '" fill="black" fill-opacity="0.55"/></svg>')

    @QtCore.Slot(str, float, bool, result=str)
    def extensionInstructions(self, source, width, dark):
        # Settings skill preview: app.css:5344-5356, smaller than chat Markdown.
        document = QtGui.QTextDocument()
        font = QtGui.QFont("DejaVu Sans"); font.setPointSizeF(12.5 * 72 / 96)
        document.setDefaultFont(font)
        document.setMarkdown(source)
        document.setTextWidth(width)
        block = document.begin()
        previous_heading = False
        while block.isValid():
            cursor = QtGui.QTextCursor(block)
            fmt = block.blockFormat()
            level = fmt.headingLevel()
            # Qt HTML line metrics add 2px after the heading; compensate here,
            # without moving the QML text container (see extensions-calibration audit).
            fmt.setTopMargin(0 if block == document.begin() else (6 if previous_heading else 12))
            fmt.setBottomMargin(0)
            fmt.setLineHeight(21.125 if level else 20.625, QtGui.QTextBlockFormat.FixedHeight.value)
            fmt.setHeadingLevel(0)
            cursor.setBlockFormat(fmt)
            if level:
                cursor.select(QtGui.QTextCursor.BlockUnderCursor)
                chars = cursor.charFormat()
                chars.clearProperty(QtGui.QTextFormat.FontSizeAdjustment)
                chars.setFontPointSize({1:16.25, 2:14.375, 3:13.125}.get(level,12.5) * 72 / 96)
                cursor.setCharFormat(chars)
            previous_heading = bool(level)
            block = block.next()
        return document.toHtml()

    def _extension_runtime(self):
        if not hasattr(self, '_ext_runtime'):
            from mvvm.services.extension_runtime import ExtensionRuntime
            from mvvm.services.extension_settings import ExtensionSettings
            self._ext_runtime = ExtensionRuntime(ExtensionSettings(self._settings, self._vault), self.extensionsChanged.emit)
            QtGui.QGuiApplication.instance().aboutToQuit.connect(self._ext_runtime.close)
            if self._window is not None: self._window.destroyed.connect(self._ext_runtime.close)
            self._ext_fingerprint = None
            self._ext_timer = QtCore.QTimer(self)
            self._ext_timer.setInterval(500)
            self._ext_timer.timeout.connect(self._check_extensions)
            self._ext_timer.start()
        return self._ext_runtime

    def _check_extensions(self):
        home = self._settings.home
        paths = [home / 'config.json', home / 'mcp.json', home / 'skills']
        if (home / 'skills').exists(): paths += list((home / 'skills').glob('*/SKILL.md'))
        try:
            fingerprint = [(str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths if p.exists()]
            if fingerprint != self._ext_fingerprint:
                self._ext_fingerprint = fingerprint
                self._ext_runtime.reconcile()
                self.extensionsChanged.emit()
        except (OSError, ValueError): self.extensionsChanged.emit()

    @QtCore.Slot(str, str, str, str, result=str)
    def extensionAction(self, action, kind, key, payload):
        from mvvm.services.extension_settings import ExtensionSettings
        service = ExtensionSettings(self._settings, self._vault)
        try:
            data = json.loads(payload or '{}')
            if action == 'errors':
                self._extension_runtime()
                return json.dumps({'ok': True, 'errors': service.errors()})
            if action == 'retry': self._extension_runtime().retry(key)
            if action == 'update': service.update(kind, key, data)
            elif action == 'remove':
                service.remove(kind, key)
                return json.dumps({'ok': True})
            elif action == 'secret':
                service.secret(key, data['field'], data['value'])
                self._extension_runtime().retry(key)
            elif action not in ('detail', 'retry'): raise ValueError('Unknown extension operation')
            item = service.detail(kind, key)
            if kind == 'mcp': item.update(self._extension_runtime().view(key))
            return json.dumps({'ok': True, 'item': item})
        except (OSError, ValueError, KeyError, TypeError) as exc:
            return json.dumps({'ok': False, 'error': str(exc)})

    @QtCore.Slot(result=list)
    def extensionRows(self) -> List[Dict[str, Any]]:
        """扩展页：技能与 MCP 注册列表，启用态来自各自的配置来源。

        行形状对齐原版 `SettingsPane.tsx:195-260`：徽标恒为扩展类型（技能 = `cf.kindSkill`），
        `note` 只在 source == "builtin" 时给 `cf.builtin`，内置行 `locked`（开关禁用、不可点开详情）。
        """
        if self._skills is None:
            return []
        labels = SETTINGS_LABELS[self.language()]
        rows: List[Dict[str, Any]] = []
        for skill in self._skills.list_skills():
            builtin = skill.get("source") == "builtin"
            rows.append(
                {
                    "kind": "skill",
                    "id": str(skill.get("id") or ""),
                    "name": str(skill.get("name") or skill.get("id") or ""),
                    "enabled": skill.get("enabled") is not False,
                    "builtin": builtin,
                    "roles": skill.get("roles"),
                    "badge": labels["kindSkill"],
                    "note": labels["builtIn"] if builtin else "",
                }
            )
        if self._settings is not None and self._vault is not None:
            from mvvm.services.extension_settings import ExtensionSettings
            from functools import cmp_to_key
            service = ExtensionSettings(self._settings, self._vault)
            try:
                registry = service.registry()
                config = service.read('config.json')
            except (OSError, ValueError):
                registry, config = {}, {}
            collator = QtCore.QCollator(QtCore.QLocale('en_US'))
            ordered = sorted(registry.items(), key=cmp_to_key(
                lambda a, b: collator.compare(str(a[1].get('name') or a[0]), str(b[1].get('name') or b[0]))))
            for key, record in ordered:
                server = dict(record, id=key, enabled=config.get('mcp', {}).get('enabled', {}).get(key) is True)
                rows.append({
                    "id": server["id"], "kind": "mcp",
                    "name": server.get("name") or server["id"],
                    "enabled": server.get("enabled") is True, "builtin": False,
                    "roles": config.get("mcp", {}).get("roles", {}).get(key),
                    "warning": self._extension_runtime().view(key)["status"] in ('error','needs_config','needs_secret'),
                    "badge": translate(self.locale, "cf.kindMcp"),
                    "note": translate(self.locale, "extensions.status." + self._extension_runtime().view(key)["status"])
                        if server.get("enabled") is True else "",
                })
        personas = {p['id']: p for p in shared_store().list_personas()}
        for row in rows:
            row['roleAvatars'] = {key: personas.get(key, {}).get('avatarImage','') for key in row.get('roles') or []}
        return rows

    @QtCore.Slot(str, str, result=bool)
    def toggleExtension(self, kind: str, extension_id: str) -> bool:
        if kind != "mcp":
            return self.setSkillEnabled(extension_id)
        from mvvm.services.plugin_settings import PluginSettings
        service = PluginSettings(self._settings, self._vault)
        row = next((r for r in service.servers(include_registered=True) if r['id'] == extension_id), None)
        if row is None:
            return False
        try:
            return service.set_server_enabled(extension_id, not row.get('enabled', False))
        except OSError:
            return False

    @QtCore.Slot(str, result=bool)
    def setSkillEnabled(self, skill_id: str) -> bool:
        """扩展页开关：写 `skills.enabled[id]`（原版 SkillsService.setEnabled 同一条语义链）。

        落盘走 `SkillStore.set_enabled`：内置技能恒启用（`RESERVED_IDS` → no-op）、非法 id
        不落盘，这两条规则由服务层单点定义并被 `app/tests/test_settings_write.py` 锁住；
        壳里不另写一份 config 合并逻辑。

        返回「落盘后可读到的启用态」而不是「有没有调过」：调用方拿它刷新行数据，
        写失败时返回值不会翻面，界面就不会假装切换成功。
        """
        if self._skills is None or not skill_id:
            return False
        # 开关是「取反」语义，服务层只收绝对值：先用当前启用位算目标值。
        current = next(
            (row["enabled"] for row in self.extensionRows() if row["id"] == skill_id and row["kind"] == "skill"), None
        )
        if current is None:
            return False
        try:
            self._skills.set_enabled(skill_id, not current)
        except OSError as exc:  # noqa: BLE001 - 与 _write_config 的异常口径一致
            print("QML CONFIG FAILED", f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            return False
        # SkillStore 直接写盘，绕过了 SettingsService 的内存副本；不失效缓存的话，
        # 后续任何一次设置页写入都会用旧副本覆盖掉刚写下的 `skills.enabled`。
        if self._settings is not None:
            self._settings.reload()
        return next(
            (row["enabled"] for row in self.extensionRows() if row["id"] == skill_id and row["kind"] == "skill"), False
        )

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
            self._turn_id = ""
            print("QML SEND FAILED", f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            return False
        self._turn_id = str(turn_id)
        print("QML TURN", turn_id, flush=True)
        self._render()
        self._publish()
        return True

    @QtCore.Slot(result=bool)
    def stopGeneration(self) -> bool:
        """停止当前回合：原版 `Composer.tsx:973-991` 的停止键 → `chat:abort(turnId)`。

        没有 store 的 turnId 时（例如从已有会话接续的回合），退回 `ChatHost.attach()`
        取正在跑的 turnId；两者都没有就明确返回 False，不假称已停止。
        """
        turn_id = self._turn_id
        if not turn_id and self._active:
            try:
                turn_id = str(self._host.attach(self._active).get("turnId") or "")
            except Exception:  # noqa: BLE001 - 查询失败按「没有可停回合」处理
                turn_id = ""
        if not turn_id:
            print("QML STOP IGNORED", json.dumps({"sessionId": self._active}), file=sys.stderr, flush=True)
            return False
        ok = bool(self._host.abort(turn_id).get("ok", False))
        print("QML STOP", json.dumps({"turnId": turn_id, "ok": ok}), flush=True)
        return ok

    # ── 附件与交付卡（宿主与服务共用同一套判定）────────────────────────────
    @QtCore.Slot(result=str)
    def beginWorkspace(self) -> str:
        if self._mount_session:
            return self.translate('native.message32')
        if not self._active or self._session() is None:
            return self.translate('native.message33')
        self._mount_session = self._active
        return ""

    @QtCore.Slot()
    def cancelWorkspace(self) -> None:
        self._mount_session = ""

    @QtCore.Slot(QtCore.QUrl, result=str)
    def acceptWorkspace(self, url: Any) -> str:
        # Only a pending user picker may grant a new root; never trust a raw
        # focusRoot supplied by a message/tool. Bind to the opening session.
        session_id = self._mount_session
        self._mount_session = ""
        if not session_id:
            return self.translate('native.message34')
        if session_id != self._active:
            return self.translate('native.message35')
        try:
            if not url.isLocalFile() or url.host():
                return self.translate('native.message36')
            root = Path(url.toLocalFile()).resolve(strict=True)
            if not root.is_dir():
                return self.translate('native.message37')
            if not os.access(root, os.R_OK | os.X_OK):
                return self.translate('native.message38')
            if not self._store.set_focus(session_id, str(root)):
                return self.translate('native.message39')
            self._host.guard.trust_root(root)
        except (OSError, RuntimeError, ValueError) as exc:
            return self.translate('native.message40') + str(exc)
        self._publish()
        return ""

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

    @QtCore.Slot("QVariantList", result="QVariantList")
    def acceptDroppedFiles(self, urls: Any) -> List[Dict[str, Any]]:
        """窗口拖放：QML 传 file:// URL 列表，按原版 `fs:dropped-entries` 的判定登记。

        支持文件与文件夹；不支持的类型按 inspect 的 `supported=False` 原样返回，
        QML 只把 supported 的路径加入待发列表，不静默吞掉原因。
        """
        paths: List[str] = []
        for value in urls or []:
            # QML 的 drop.urls 元素到 PySide 是 QUrl；也兼容调用方直接传字符串路径。
            if isinstance(value, QtCore.QUrl):
                local = value.toLocalFile()
            else:
                text = str(value or "")
                if not text:
                    continue
                local = QtCore.QUrl(text).toLocalFile() if text.startswith("file:") else text
            if local:
                paths.append(local)
        rows = self._attachments.inspect_paths(paths)
        print("QML DROP", json.dumps([row.get("path") for row in rows], ensure_ascii=False), flush=True)
        return rows

    @QtCore.Slot(result="QVariantList")
    def attachClipboardImage(self) -> List[Dict[str, Any]]:
        """剪贴板里的图片 → 临时 PNG → 与选择框同一条 inspect 白名单链路。

        原版 `Composer.tsx:508` 走 `fs:paste-attachment`；QML 没有该 IPC，
        这里用 QClipboard 取图落盘后复用 AttachmentService。
        """
        clipboard = QtGui.QGuiApplication.clipboard()
        if clipboard is None:
            return []
        image = clipboard.image()
        if image is None or image.isNull():
            return []
        directory = Path(tempfile.mkdtemp(prefix="ai-upper-paste-"))
        target = directory / "pasted.png"
        if not image.save(str(target), "PNG"):
            return []
        rows = self._attachments.inspect_paths([str(target)])
        print("QML PASTE IMAGE", json.dumps(str(target), ensure_ascii=False), flush=True)
        return rows

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

    def set_notifier(self, notifier: Any) -> None:
        self._notifier = notifier

    @QtCore.Slot(result=bool)
    def closeToTray(self) -> bool:
        """关窗是否驻留托盘：原版 index.ts:164-172（win32 默认开，其它平台仅显式 true）。"""
        pref = self._config().get("closeToTray")
        import sys as _sys
        if _sys.platform == "win32":
            return pref is not False
        return pref is True

    @QtCore.Slot(result="QVariantList")
    def mentionCandidates(self):
        session = self._session()
        members = (getattr(session, 'members', None) or []) if session else []
        rows = []
        seen = set()
        for member in members:
            name = str(member.get('name') or '')
            if name and name not in seen:
                rows.append({'name':name, 'desc': '成员', 'kind':'mention'})
                seen.add(name)
        for persona in self.quickStartPersonas():
            name = str(persona.get('name') or '')
            if name and name not in seen:
                rows.append({'name':name, 'desc':persona.get('desc',''), 'kind':'mention'})
                seen.add(name)
        return rows

    @QtCore.Slot(result="QVariantList")
    def slashCommands(self) -> List[Dict[str, Any]]:
        """输入框 `/` 指令联想（原版 Composer.tsx:382-420 的内建指令子集）。

        `/compact` 已接 `ChatHost.compact`；`/rewind` 没有后端，不在候选里假装可用。
        """
        rows = [{'name':'compact', 'desc':self.translate('cf.slash.compact'), 'kind':'command'},
                {'name':'rewind', 'desc':self.translate('cf.slash.rewind'), 'kind':'command'}]
        seen = {'compact', 'rewind'}
        persona = getattr(self._session(), 'personaId', None) or 'general'
        for skill in self._skills.list_skills() if self._skills else []:
            name = skill['name']
            roles = skill.get('roles')
            if not skill.get('enabled') or (roles is not None and persona not in roles) or name.lower() in seen:
                continue
            seen.add(name.lower())
            rows.append({'name':name, 'desc':skill['description'], 'kind':'skill'})
        return rows

    @QtCore.Slot(str, int, str, result='QVariantMap')
    @QtCore.Slot(str, int, str, 'QVariantList', result='QVariantMap')
    def rewind(self, action, turn, mode, force=None):
        try:
            result = self._host.rewind(self._active, action, turn, mode, force or [])
            self._publish()
            return result
        except Exception as exc:
            return {'error':str(exc)}

    @QtCore.Slot(str, result=bool)
    def runSlashCommand(self, name: str) -> bool:
        """执行选中的 `/` 指令：compact 起真实压缩回合；未知指令返回 False。"""
        if name != "compact" or not self._active or self._host.is_busy(self._active):
            return False
        try:
            turn_id = self._host.compact({"sessionId": self._active})["turnId"]
        except Exception as exc:  # noqa: BLE001 - 压缩失败显式暴露
            print("QML SLASH FAILED", f"{type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            return False
        print("QML SLASH", json.dumps({"name": name, "turnId": turn_id}, ensure_ascii=False), flush=True)
        return True

    @QtCore.Slot(str, result=bool)
    def insertMessage(self, text: str) -> bool:
        """输入框在回合中按「发送」：先进入待插入队列；回合结束后按原文发给同一会话。"""
        value = str(text or "").strip()
        if not value or not self._active:
            return False
        if not self._host.is_busy(self._active):
            return self.send(value)
        self._pending_inserts.append(value)
        print("QML INSERT QUEUED", json.dumps({"sessionId": self._active, "text": value}, ensure_ascii=False), flush=True)
        self._publish()
        return True

    @QtCore.Slot(result="QVariantList")
    def pendingInserts(self) -> List[str]:
        return list(self._pending_inserts)

    @QtCore.Slot(str, result="QVariantMap")
    def providerModels(self, provider_id: str) -> Dict[str, Any]:
        """设置页「拉取模型」：真实调用 ModelGateway.list_models（provider:list-models 同语义）。"""
        if self._settings is None:
            return {"ok": False, "models": [], "message": "settings unavailable"}
        vault = self._vault or SecretsVault(self._store.home)
        try:
            from mvvm.services.provider_setup import ModelGateway
            result = asyncio.run(ModelGateway(self._settings, vault).list_models(str(provider_id or "")))
            return {"ok": bool(result.ok), "models": list(result.models), "message": result.message or ""}
        except Exception as exc:  # noqa: BLE001 - 网络/配置错误要在界面显示
            return {"ok": False, "models": [], "message": f"{type(exc).__name__}: {exc}"}

    @QtCore.Slot(result="QVariantMap")
    def backgroundCapsule(self) -> Dict[str, Any]:
        """后台任务胶囊数据：会话边车 `background`（原版 BackgroundCapsule）。"""
        session = self._session()
        return dict(getattr(session, "background", None) or {}) if session is not None else {}

    @QtCore.Slot(result="QVariantMap")
    def todoCapsule(self) -> Dict[str, Any]:
        """当前会话的 Todo 清单（原版 Composer.tsx:864 TodoCapsule）。"""
        if not self._active:
            return {}
        state = self._host.todos(self._active).get("active")
        if not state:
            return {}
        items = state.get("items") or []
        return {
            "id": state.get("id") or "",
            "title": state.get("title") or "",
            "items": items,
            "done": sum(1 for item in items if item.get("status") == "completed"),
            "total": len(items),
        }

    @QtCore.Slot(str, result=bool)
    def openExternal(self, url: str) -> bool:
        """正文里的链接点击：原版渲染层 `<a>` 由 Chromium 直接打开，QML 侧显式转系统浏览器。

        只放行 http/https/mailto；`javascript:`、`file:` 等一律拒绝并返回 False。
        """
        value = str(url or "").strip()
        if not value:
            return False
        if QtCore.QUrl(value).scheme().lower() not in ("http", "https", "mailto"):
            print("QML OPEN EXTERNAL REJECTED", json.dumps({"url": value}, ensure_ascii=False), file=sys.stderr, flush=True)
            return False
        ok = _open_external(value)
        print("QML OPEN EXTERNAL", json.dumps({"url": value, "ok": ok}, ensure_ascii=False), flush=True)
        return ok

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
            self.translate("native.pickFiles"),
            "",
            self.translate("native.supportedFiles") + " (*.png *.jpg *.jpeg *.gif *.webp *.pdf *.docx *.xlsx *.pptx *.doc "
            "*.xls *.ppt *.txt *.md *.markdown *.json *.yaml *.yml *.toml *.csv *.log "
            "*.js *.jsx *.ts *.tsx *.vue *.svelte *.html *.css *.scss *.xml *.py *.go "
            "*.rs *.java *.kt *.c *.h *.cpp *.cs *.php *.sh *.sql);;"
            + self.translate("native.images") + " (*.png *.jpg *.jpeg *.gif *.webp);;"
            "PDF (*.pdf);;"
            + self.translate("native.allFiles") + " (*)",
        )
        return [str(path) for path in paths]

    @QtCore.Slot(result=QtCore.QObject)
    def botsService(self):
        if not hasattr(self, '_remote_bots'):
            from mvvm.services.remote_bots import RemoteBots
            self._remote_bots = RemoteBots(self)
        return self._remote_bots

    @QtCore.Slot(result=QtCore.QObject)
    def tasksService(self):
        if not hasattr(self, '_scheduled_tasks'):
            from mvvm.services.scheduled_tasks import ScheduledTasks
            self._scheduled_tasks = ScheduledTasks(self)
        return self._scheduled_tasks

    # ── 事件回写（GUI 线程）───────────────────────────────────────────────
    def tick(self) -> bool:
        """GUI 线程周期调用：drain 回合线程的界面写入，再把事件落到正文上。"""
        self._finish_prepared_render()
        self._host.drain()
        pending = self.pendingInteractions()
        if pending != self._last_interactions:
            self._last_interactions = pending
            self.interactionsChanged.emit(pending)
        controller = getattr(self._host, 'interactions', None)
        attention = {meta.id for meta in self._store.visible_sessions() if controller and controller.pending(meta.id)}
        changed = attention != self._attention
        for sid in attention - self._attention:
            self._notify_turn(sid, "等待处理", error=True)
        self._attention = attention
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

    def _notify_turn(self, session_id: str, message: str, *, error: bool) -> None:
        """窗口不在前台时弹回复通知（原版 reply-notify.ts:64-80）。"""
        if self._notifier is None or self._window is None:
            return
        active = QtGui.QGuiApplication.focusWindow() is self._window
        if active:
            return
        title = next((row["title"] for row in self._rows() if row["id"] == session_id), "Deva")
        body = ("回复因错误中断：" + message) if error else "回复已完成"
        self._last_notify_session = session_id
        self._notifier(title, body)

    def _handle(self, payload: Dict[str, Any]) -> bool:
        if hasattr(self, "_remote_bots"):
            self._remote_bots.turn_event(payload)
        if hasattr(self, "_scheduled_tasks"):
            self._scheduled_tasks.turn_event(payload)
        session_id = str(payload.get("sessionId") or "")
        event = payload.get("event")
        if not isinstance(event, dict):
            return False
        kind = event.get("type")
        # 回合在别的会话结束时给它记未读（当前正在看的会话不打红点）。
        if kind in ("done", "error") and session_id and session_id != self._active:
            self._unread.add(session_id)
        if session_id != self._turn_session:
            if kind in ("done", "error"):
                self._notify_turn(session_id, str(event.get("message") or ""), error=kind=="error")
            return kind in ("done", "error")
        if kind == "text_delta" and self._turn is not None:
            text = str(event.get("text") or "")
            self.deltas.append(text)
            print("QML STREAM", json.dumps({"text": text}, ensure_ascii=False), flush=True)
            return self._turn.apply(event)
        if kind == "error":
            self._turn_id = ""
            self._notify_turn(session_id, str(event.get("message") or ""), error=True)
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
            self._notify_turn(session_id, "", error=False)
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
            self._turn_id = ""
            queued = list(self._pending_inserts)
            self._pending_inserts.clear()
            if queued and self._active:
                self.send("\n\n".join(queued))
            return True
        return False

    def turn_finished(self) -> bool:
        return self._turn is None and (not self._turn_session)

    # ── 渲染与属性 ────────────────────────────────────────────────────────
    def _markdown_base(self) -> str:
        session = self._store.load_session(self._active) if self._active else None
        return transcript_markdown(session.messages, lang=self.language(), include_activity=True) if session is not None else ""

    def _markdown(self) -> str:
        base = self._markdown_base()
        if self._turn is not None:
            # 回合中的「基础正文」在发送时已经取过；落盘会追加本轮消息，不能再拼一遍。
            return self._turn.markdown(lang=self.language())
        return base

    def _prepare_render(self) -> None:
        if self._document is None:
            return
        from concurrent.futures import ThreadPoolExecutor
        from markdown.prepare import prepare_document
        if self._render_executor is None:
            self._render_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="body-render")
            QtCore.QCoreApplication.instance().aboutToQuit.connect(self._close_render_worker)
            if self._engine is not None:
                self._engine.destroyed.connect(self._close_render_worker)
        self._render_epoch += 1
        for _, _, job in self._render_jobs:
            job.cancel()
        source = self._markdown()
        self._display_key = None
        if isinstance(self._document, QtQuick.QQuickTextDocument):
            key = self._display_cache.key(self._active, source, self._plain,
                                          self._body.style,
                                          (self._body.content_width, self._document.parent().width(),
                                           self._window.devicePixelRatio() if self._window else 1.0))
            cached = self._display_cache.get(key)
            if cached is not None:
                self._display_cache.activate(cached, self._document)
                self._body = cached.body
                self.rendered += 1
                self._scroll_to_bottom()
                return
            self._display_key = key
        job = self._render_executor.submit(
            prepare_document, source, self._plain, self._body.style,
            self._body.content_width, _load_image)
        self._render_jobs.append((self._render_epoch, source, job))
        job.add_done_callback(lambda _: self._preparedReady.emit())

    def _close_render_worker(self, *args) -> None:
        self._render_epoch += 1
        if self._render_executor is not None:
            self._render_executor.shutdown(wait=True, cancel_futures=True)
            self._render_executor = None
        self._render_jobs.clear()

    def _finish_prepared_render(self) -> None:
        pending = []
        for epoch, source, job in self._render_jobs:
            if not job.done():
                pending.append((epoch, source, job))
                continue
            if job.cancelled():
                continue
            try:
                fragment, images = job.result()
            except Exception as exc:
                if epoch == self._render_epoch:
                    print("QML PREPARE FAILED", str(exc), file=sys.stderr)
                    self._render()
                continue
            if epoch != self._render_epoch:
                continue
            if self._display_key is not None:
                from markdown.cache import Display
                old = self._body
                self._body = type(old)(style=old.style, content_width=old.content_width)
                self._body.set_image_resolver(_load_image)
                target = QtGui.QTextDocument()
                previous = self._document.textDocument()
                target.setDefaultFont(previous.defaultFont())
                target.setDefaultTextOption(previous.defaultTextOption())
                self._display_cache.activate(Display(self._body, target), self._document)
            if self._display_key is None:
                document = self._body.document
                document.clear()
                document.setDocumentMargin(0)
                QtGui.QTextCursor(document).insertFragment(fragment)
                kind = QtGui.QTextDocument.ResourceType.ImageResource.value
                for url, image in images:
                    document.addResource(kind, url, image)
            self._body._source = source
            self._body._plain = self._plain
            self._body._rendered_width = self._body.content_width
            if self._display_key is None:
                self._body.attach(self._document)
            else:
                self._body.attach(self._document, fragment=fragment, images=images)
            if self._display_key is not None and not images and "![" not in source:
                # External image files can change without changing Markdown.
                self._display_cache.put(self._display_key, self._display_cache.current)
            self.rendered += 1
            self._scroll_to_bottom()
        self._render_jobs = pending

    def _render(self) -> None:
        self._display_cache.invalidate_current()
        self._render_epoch += 1
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
                for item in shared_store().list_personas():
                    self._persona_names[str(item.get("id"))] = str(item.get("name") or "")
            except OSError:
                self._persona_names = {}
        return self._persona_names.get(persona_id or "", "") or "Deva"

    def _rows(self) -> List[Dict[str, Any]]:
        """列表行：会话行 + 角色 id/名（副标题）+ 挂载目录名（搜索用）。

        可见会话元信息只取一次：行投影与副标题取 personaId 用的是同一份，没必要列两遍索引。
        `focusName` 是 `focusRoot` 的 basename：原版搜索按「标题 + 角色名 + 挂载目录名」过滤
        （`Rail.tsx:444-452`），目录名在栏里显示的就是 basename。
        """
        metas = self._store.visible_sessions()
        rows = session_rows(self._store, lang=self.language(), metas=metas)
        owner = {str(getattr(m, "id", "")): str(getattr(m, "personaId", "") or "general")
                 for m in metas}
        focus = {str(getattr(m, "id", "")): str(getattr(m, "focusRoot", "") or "")
                 for m in metas}
        for row in rows:
            persona = owner.get(row["id"], "general")
            row["persona"] = persona
            row["personaName"] = self._persona_name(persona)
            root = focus.get(row["id"], "")
            row["focusRoot"] = root
            row["focusName"] = os.path.basename(root.rstrip("/\\")) if root else ""
            row["unread"] = row["id"] in self._unread
            row["attention"] = row["id"] in self._attention
        return rows

    def _publish(self) -> None:
        window = self._window
        if window is None:
            return
        rows = self._rows()
        active = self._active if any(row["id"] == self._active for row in rows) else ""
        window.setProperty("sessions", rows)
        # 已归档会话单独一份投影：归档视图（原版 `Archived chats`）用同一套
        # `session_rows` 形状，来源仍是 `ChatSessionStore.list_sessions()`，不另造数据。
        archived_metas = [
            meta
            for meta in self._store.list_sessions()
            if meta.archived and not meta.parentId and self._store.session_path(meta.id).exists()
        ]
        window.setProperty(
            "archivedSessions",
            session_rows(self._store, lang=self.language(), metas=archived_metas),
        )
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
        window.setProperty("sideCollapsed", self.sidebarCollapsed())
        window.setProperty("status", self.translate("native.streaming") if busy else self.translate("native.ready"))
        # 附件贴片与交付卡：每次重绘都按当前会话现算（落盘为唯一真相源）。
        session = self._session() if active else None
        window.setProperty("focusRoot", str(session.focusRoot or "") if session else "")
        window.setProperty("attachments", attachment_rows(session))
        window.setProperty("deliveries", delivery_rows(session))
        # 输入区两个贴片：文案与勾选都按「本对话生效 → 最近使用」现算，不缓存成另一份真相。
        labels = self.chatLabels()
        ref = self._active_ref()
        effort = self.effortMenu()
        window.setProperty("modelLabel", ref.model if ref is not None else labels["selectModel"])
        window.setProperty("activeModelRef", ref.ref if ref is not None else "")
        window.setProperty("modelGroups", self.modelMenuGroups())
        window.setProperty("effortMenu", effort)
        window.setProperty("effortLabel", effort["label"])
        window.setProperty("activeEffort", effort["current"])
        window.setProperty("chatText", labels)
        window.setProperty("pendingInserts", self.pendingInserts())
        window.setProperty("todoCapsule", self.todoCapsule())
        window.setProperty("backgroundCapsule", self.backgroundCapsule())
        # 快速开启的角色卡片：空态直接绑这个属性，重绘即刷新（与列表同一拍）。
        window.setProperty("quickStartPersonas", self.quickStartPersonas())
        # 上下文圆环：读数缺失（新对话 / 无模型）时 used=None，QML 据此整个不画。
        window.setProperty("contextUsage", self.contextUsage())

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

    from utils.qt_compat import QtWidgets
    from mvvm.services.single_instance import SingleInstance
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    instance = SingleInstance(app_home(), app)
    if not instance.acquire():
        return 0
    app.aboutToQuit.connect(instance.close)
    home = app_home()
    settings = SettingsService(home)
    vault = SecretsVault(home)
    store = ChatSessionStore(home)
    personas = shared_store()
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
    app.aboutToQuit.connect(host.shutdown)

    engine = QtQml.QQmlApplicationEngine()
    bridge._engine = engine
    engine.rootContext().setContextProperty("shellBridge", bridge)
    engine.load(QtCore.QUrl.fromLocalFile(str(qml_main_path)))
    roots = engine.rootObjects()
    if not roots:
        print("QML FAILED", "reason=engine loaded no root object", file=sys.stderr, flush=True)
        return 1
    window = roots[0]
    instance.attach(window)
    from mvvm.services.tray import TrayController
    tray = TrayController(app, window)
    window.setProperty("trayAvailable", tray.install())
    bridge.set_notifier(tray.notify)
    if tray.icon is not None:
        tray.icon.messageClicked.connect(lambda: (tray.show(), bridge.openSession(getattr(bridge, "_last_notify_session", ""))))
    bridge.bind_window(window)
    bridge.tasksService()
    bridge.botsService()
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
