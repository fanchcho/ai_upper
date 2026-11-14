"""宿主桥接层：把原版渲染层的 `window.deva` 调用分发到 Python 服务。

为什么有这一层（选型记录，另见 docs/BUILD-PROGRESS.md）：
原版界面是 React + Lexical + xterm.js 的富交互页面，纯 Qt 控件无法做到逐像素一致。
用户明确允许「复用原版渲染层资产 + QtWebEngine 承载 + Python 桥接」，本模块就是那条桥。

调用约定（与 preload 的 `ipcRenderer.invoke(channel, ...args)` 一一对应）：
- JS 侧 `bridge.invoke(requestId, channel, argsJson)` 是**单向**的（QtWebChannel 的方法调用
  没有返回值通道），Python 处理完用 `runJavaScript` 回调 `window.__devaResolve(id, ok, payload)`；
- 频道名、参数顺序完全沿用 Deva 的 IPC 契约，便于和 158 条通道表逐条对照；
- 未实现的通道**显式报错**（JS 侧 reject，界面显示错误），绝不返回假成功。
"""
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Any, Callable

from utils.qt_compat import QtCore, Signal, Slot

QObject = QtCore.QObject

from mvvm.services.avatar_image import clear_avatar_image, read_avatar_image, write_avatar_image
from mvvm.services.persona_store import PersonaStore
from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.settings_service import SettingsService
from mvvm.services.skill_store import SkillStore

# 后台任务通知前缀，与 Deva `main/services/compaction.ts` 的 NOTIFY_MARKER 同值。
NOTIFY_MARKER = "⟦deva:notify⟧"


class BridgeError(RuntimeError):
    """通道处理失败时抛出的错误；JS 侧表现为 Promise reject。"""


class UnimplementedChannel(BridgeError):
    """通道尚未接入 Python 实现。显式暴露，不静默吞。"""


class Deferred:
    """标记一个通道「异步收尾」：处理函数拿 requestId，稍后自己调 `bridge.finish`。

    `provider:list-models` 是唯一需要的例子：探针最多等 15 秒，同步跑会把界面卡死。
    调用方式仍是同步入口（`bridge.invoke` 立即返回），只是结果由后台线程回送。
    """


class DevaBridge(QObject):
    """一个 WebEngine 页面 ↔ Python 服务 的桥。

    `on_ready` 在页面注入完成后由视图调用一次，把首批事件（sessions-changed 等）推给渲染层。
    """

    # 事件通道：名字与 preload 的 `ipcRenderer.on(...)` 一致
    event = Signal(str, str)  # (channel, payload_json)
    # 后台线程回送调用结果：runJavaScript 必须在 GUI 线程调，跨线程时先经这个信号。
    _deferred_result = Signal(str, bool, str)  # (request_id, ok, payload_json)
    # 后台线程推事件（回合线程 emit `chat:event`）同样要回 GUI 线程。
    _emit_requested = Signal(str, str)  # (channel, payload_json)

    def __init__(
        self,
        *,
        settings: SettingsService,
        personas: PersonaStore,
        store: ChatSessionStore,
        home: Path,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.personas = personas
        self.store = store
        self.home = Path(home)
        self.skills = SkillStore(self.home)
        self._view: Any = None
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._deferred: set[str] = set()
        # 标题栏叠加层主题回调：由视图注入（桥不直接依赖视图类）。
        self._overlay_callback: Callable[[bool], None] | None = None
        # 窗口控制回调：同样由视图注入。没注入时通道必须显式报错，不能假装成功。
        self._window_actions: dict[str, Callable[..., Any]] = {}
        # 回合宿主（`ChatHost`）：读取类通道也要用它（attach-session 的进行中回合、
        # list-sessions 的受信根恢复）。没有它时相关通道不注册，调用显式报未接入。
        self.chat_host: Any = None
        self.model_gateway: Any = None
        self._deferred_result.connect(
            self._resolve_deferred, QtCore.Qt.ConnectionType.QueuedConnection
        )
        self._emit_requested.connect(
            self._write_emit, QtCore.Qt.ConnectionType.QueuedConnection
        )
        self._register_defaults()

    def set_overlay_callback(self, callback: Callable[[bool], None]) -> None:
        self._overlay_callback = callback

    def set_window_actions(self, **actions: Callable[..., Any]) -> None:
        """注入真实窗口能力（minimize / toggle_maximize / close / is_fullscreen）。

        渲染层的 `window:minimize` 等通道原来被注册成空 lambda：界面点下去没反应，
        但 Promise 是 resolve 的——这正是「静默假成功」。现在改为必须有真实实现。
        """
        self._window_actions = {name: fn for name, fn in actions.items() if fn is not None}

    # ── 视图接线 ──────────────────────────────────────────────────────────
    def attach_view(self, view: Any) -> None:
        """记录 WebEngineView：Python 处理后要把结果送回页面。"""
        self._view = view

    def emit_event(self, channel: str, payload: Any) -> None:
        """把一条事件推给渲染层（对应 `webContents.send(channel, payload)`）。

        回合在后台线程跑，事件也从那里推；`runJavaScript` 只能在 GUI 线程调，所以这里统一
        走信号回到 GUI 线程再写页面（同线程时 QueuedConnection 也只是稍后派发，视觉无差）。
        """
        if self._view is None:
            return
        self._emit_requested.emit(
            str(channel), json.dumps(payload, ensure_ascii=False)
        )

    def _write_emit(self, channel: str, payload_json: str) -> None:
        if self._view is None:
            return
        # payload 以 JSON 字面量直接嵌进调用：渲染层的回调拿到的是对象（与原版
        # `webContents.send` 的结构化克隆一致），不是一段需要自己 JSON.parse 的字符串。
        code = (
            f"window.__devaEmit({json.dumps(channel)}, {payload_json});"
        )
        self._view.page().runJavaScript(code)

    # ── 注册表 ────────────────────────────────────────────────────────────
    def register(self, channel: str, handler: Callable[..., Any]) -> None:
        self._handlers[channel] = handler

    def register_deferred(self, channel: str, handler: Callable[..., Any]) -> None:
        """注册异步通道：handler(request_id, *args) 自己调 `finish` 回送结果。"""
        self._handlers[channel] = handler
        self._deferred.add(channel)

    def finish(self, request_id: str, ok: bool, payload: Any) -> None:
        """异步通道的收尾入口；可在任意线程调用（跨线程时经信号回到 GUI 线程）。"""
        body = json.dumps(payload, ensure_ascii=False) if payload is not None else "null"
        self._deferred_result.emit(str(request_id), bool(ok), body)

    def _resolve_deferred(self, request_id: str, ok: bool, payload_json: str) -> None:
        self._write_resolve(request_id, ok, payload_json)

    def handles(self, channel: str) -> bool:
        return channel in self._handlers

    def channels(self) -> list[str]:
        return sorted(self._handlers)

    # ── 调用入口（QtWebChannel 唯一暴露的方法）─────────────────────────────
    @Slot(str, str, str)
    def invoke(self, request_id: str, channel: str, args_json: str) -> None:
        """处理一次前端调用；结果通过 `window.__devaResolve` 回送。"""
        try:
            args = json.loads(args_json) if args_json else []
            if not isinstance(args, list):
                raise BridgeError("调用参数必须是数组")
            handler = self._handlers.get(channel)
            if handler is None:
                raise UnimplementedChannel(f"通道未接入：{channel}")
            if channel in self._deferred:
                # 结果由处理函数稍后 `finish` 回送；这里不 resolve。
                handler(request_id, *args)
                return
            result = handler(*args)
        except Exception as exc:  # noqa: BLE001 - 桥边界：任何异常都要变成前端的 reject
            self._resolve(request_id, False, _error_payload(exc))
            return
        self._resolve(request_id, True, result)

    def _resolve(self, request_id: str, ok: bool, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False) if payload is not None else "null"
        self._write_resolve(request_id, ok, body)

    def _write_resolve(self, request_id: str, ok: bool, body: str) -> None:
        if self._view is None:
            return
        code = (
            f"window.__devaResolve({json.dumps(request_id)}, "
            f"{'true' if ok else 'false'}, {body});"
        )
        self._view.page().runJavaScript(code)

    # ── 首批通道（首启页 / 会话列表 / 设置页所需）──────────────────────────
    def _register_defaults(self) -> None:
        self.register("config:get", lambda: self.settings.get_config_sync())
        self.register("config:set", self._config_set)

        self.register("personas:list", lambda: self.personas.list_personas())
        self.register("personas:get", self.personas.get)
        self.register("personas:upsert", self.personas.upsert)
        self.register("personas:remove", self.personas.remove)
        self.register("personas:set-enabled", self.personas.set_enabled)
        self.register("personas:reorder", self.personas.reorder)
        self.register("personas:set-avatar-image", self.personas.set_avatar_image)
        self.register("personas:clear-avatar-image", self.personas.clear_avatar_image)

        self.register("skills:list", self.skills.list_skills)
        self.register("skills:get", self.skills.get)
        self.register("skills:remove", self.skills.remove)
        self.register("skills:set-enabled", self.skills.set_enabled)
        self.register("skills:set-roles", self.skills.set_roles)

        self.register("profile:get", self._profile_get)
        self.register("profile:set-avatar", self._profile_set_avatar)
        self.register("profile:set-avatar-image", self._profile_set_avatar_image)

        self.register("chat:list-sessions", self._list_sessions)
        self.register("chat:load-session", self._load_session)
        self.register("chat:attach-session", self._attach_session)
        # 写路径：全部转到 `ChatHost`（宿主没接线时这些通道不注册，调用显式报未接入）。
        for channel, method in (
            ("chat:send", "send"),
            ("chat:abort", "abort"),
            ("chat:compact", "compact"),
            ("chat:create-session", "create_session"),
            ("chat:set-model", "set_model"),
            ("chat:set-effort", "set_effort"),
            ("chat:set-focus", "set_focus"),
            ("chat:rename-session", "rename_session"),
            ("chat:set-archived", "set_archived"),
            ("chat:delete-session", "delete_session"),
            ("chat:reset", "reset"),
            ("chat:delete-turns", "delete_turns"),
            ("chat:todos", "todos"),
            ("chat:todo-cancel", "cancel_todos"),
        ):
            self.register(channel, self._host_method(method))
        self.register("browser:state", self._browser_state)
        self.register("browser:ready", self._browser_state)
        self.register("browser:preview-pinned", lambda _tab=None: {"ok": True})
        self.register("window:set-overlay", self._set_overlay)

        self.register("secrets:has", self._secrets_has)
        self.register("secrets:list", self._secrets_list)
        self.register("secrets:available", self._secrets_available)
        self.register("secrets:set", self._secrets_set)
        self.register("secrets:delete", self._secrets_delete)

        # 模型清单探针：最长等 15 秒，必须异步回送，否则同步跑会把渲染层主线程卡死。
        self.register_deferred("provider:list-models", self._list_models)

        # 窗口控制：原版是 `mainWindow?.minimize()` 一类直调。这里必须由视图注入真实实现，
        # 没注入就显式报错——此前的空 lambda 会让界面「点了没反应但 Promise 成功」。
        self.register("window:minimize", self._window_action("minimize"))
        self.register("window:toggle-maximize", self._window_action("toggle_maximize"))
        self.register("window:close", self._window_action("close"))
        self.register("window:is-fullscreen", self._window_action("is_fullscreen"))
        self.register("app:get-platform", lambda: "linux")

        self.register("clipboard:read-text", self._clipboard_read)
        self.register("clipboard:write-text", self._clipboard_write)

        self.register("update:get-state", self._update_state)
        self.register("remote:get-state", self._remote_state)

    # ── 各通道实现 ────────────────────────────────────────────────────────
    def _host_method(self, method: str) -> Callable[..., Any]:
        """宿主方法包装：宿主未接线时抛「未接入」，绝不返回假成功。"""

        def run(*args: Any) -> Any:
            host = self.chat_host
            if host is None:
                raise UnimplementedChannel(f"回合宿主未接线：{method}")
            return getattr(host, method)(*args)

        return run

    def _attach_session(self, session_id: str) -> dict[str, Any]:
        """接上会话：历史 + 进行中回合（同一时刻取出，不会漏掉随后的 done）。"""
        host = self.chat_host
        if host is None:
            return {"messages": self._load_session(session_id), "turnId": None, "startedAt": None}
        return host.attach(session_id)

    def _profile_set_avatar(self, spec: Any) -> dict[str, bool]:
        """写头像 spec；超过 4096 字节存空串（即视为清除，回落默认头像）。"""
        value = spec if isinstance(spec, str) else ""
        section = self.settings.get("profile")
        section = dict(section) if isinstance(section, dict) else {}
        section["avatar"] = "" if len(value) > 4096 else value
        return self.settings.set_config({"profile": section})

    def _profile_set_avatar_image(self, data_uri: Any) -> str:
        """空串 = 清除图片；否则落盘并回读 data URI（校验/写入失败为空串）。"""
        directory = self.home / "profile"
        uri = data_uri if isinstance(data_uri, str) else ""
        if not uri:
            clear_avatar_image(directory, "avatar")
            return ""
        return write_avatar_image(directory, "avatar", uri)

    def _secrets_set(self, provider_id: Any, key: Any) -> dict[str, bool]:
        vault = getattr(self, "vault", None)
        if vault is None:
            return {"ok": False, "available": False}
        return vault.set_secret(str(provider_id or ""), str(key or ""))

    def _secrets_delete(self, provider_id: Any) -> dict[str, bool]:
        vault = getattr(self, "vault", None)
        if vault is None:
            raise UnimplementedChannel("密钥库未接线：secrets:delete")
        result = vault.delete_secret(str(provider_id or ""))
        return {"ok": True} if result.get("ok") else result

    def _list_models(self, request_id: str, cfg: Any) -> None:
        """`provider:list-models`：后台线程跑探针，结果经信号回到 GUI 线程回送。

        入参是渲染层的 `{adapter, providerId, baseURL}`；密钥由网关从密钥库现取。
        """
        gateway = self.model_gateway
        if gateway is None:
            self.finish(request_id, False, {"unimplemented": True, "message": "模型网关未接线"})
            return
        payload = cfg if isinstance(cfg, dict) else {}

        def work() -> None:
            try:
                result = asyncio.run(
                    gateway.list_models(
                        str(payload.get("providerId") or ""),
                        payload.get("adapter") or None,
                        payload.get("baseURL") or None,
                    )
                )
                self.finish(request_id, True, list_models_payload(result))
            except Exception as exc:  # noqa: BLE001 - 桥边界：异常回给渲染层而不是吞掉
                self.finish(request_id, False, _error_payload(exc))

        threading.Thread(target=work, name="list-models", daemon=True).start()

    def _window_action(self, name: str) -> Callable[..., Any]:
        """把窗口能力包成通道处理函数；视图没有注入时必须抛错。"""

        def run(*args: Any) -> Any:
            del args
            action = self._window_actions.get(name)
            if action is None:
                raise UnimplementedChannel(f"窗口能力未接线：{name}")
            return action()

        return run

    def _config_set(self, patch: Any) -> dict[str, bool]:
        if not isinstance(patch, dict):
            raise BridgeError("config:set 需要一个对象")
        return self.settings.set_config(patch)

    def _profile_get(self) -> dict[str, str]:
        section = self.settings.get("profile")
        avatar = section.get("avatar") if isinstance(section, dict) else None
        return {
            "avatar": avatar if isinstance(avatar, str) and avatar else DEFAULT_USER_AVATAR,
            "avatarImage": "",
        }

    def _list_sessions(self, workspace_root: str | None = None) -> list[dict[str, Any]]:
        """`chat:list-sessions`：全部会话（含归档与成员会话——渲染层自己过滤）。

        原版还会把每个非空 `focusRoot` 登记为受信根：否则重启后 `git:status` / `fs:*`
        首行 `assertInside` 抛「拒绝访问」，界面表现为 git 丢失。宿主存在时用它的守卫。
        """
        del workspace_root  # 会话已无项目分桶；参数仅为兼容签名
        # 惰性会话（只进内存索引、尚未 save）不列：原版里它们只活在渲染层，
        # 主进程索引根本没有它们——列出来会凭空多一条空对话。
        metas = [m for m in self.store.list_sessions() if self.store.session_path(m.id).exists()]
        guard = getattr(self.chat_host, "guard", None)
        if guard is not None:
            for meta in metas:
                if meta.focusRoot:
                    guard.trust_root(meta.focusRoot)
        return [meta.model_dump() for meta in metas]

    def _load_session(self, session_id: str, workspace_root: str | None = None) -> list[dict[str, Any]]:
        del workspace_root
        session = self.store.load_session(session_id)
        if session is None:
            return []
        return display_messages(session.messages)

    def _browser_state(self) -> dict[str, Any]:
        """内置浏览器未接入：返回 Deva `BrowserUiState` 的空态。

        字段必须齐全（含 `handoff`）：渲染层在主界面渲染时直接读
        `browserState?.handoff[id]`，少一个键就会整棵树抛错、页面白屏——空态也要照契约给全。
        """
        return {
            "open": False,
            "pinned": False,
            "active": None,
            "tabs": [],
            "current": {},
            "operating": {},
            "handoff": {},
        }

    def _set_overlay(self, symbol_color: str | None = None) -> None:
        """主题切换时同步标题栏叠加层底色（原版 `window:set-overlay` 的 Linux 分支）。

        Linux 上 Electron 的叠加区是实色、图标色由底色自动对比得出，故这里只跟主题换底色；
        深色判定用原版的 symbolColor 取值（`#e4e4e7` = 深色主题）。
        """
        dark = symbol_color == "#e4e4e7"
        if self._overlay_callback is not None:
            self._overlay_callback(dark)

    def _clipboard_read(self) -> str:
        """原版是 Electron `clipboard.readText()`；这里走 Qt 剪贴板（没有剪贴板时返回空串）。"""
        from utils.qt_compat import QtGui

        app_clipboard = QtGui.QGuiApplication.clipboard()
        return app_clipboard.text() if app_clipboard is not None else ""

    def _clipboard_write(self, text: Any = "") -> dict[str, bool]:
        """原版把非字符串参数统一按空串处理（`typeof text === 'string' ? text : ''`）。"""
        from utils.qt_compat import QtGui

        value = text if isinstance(text, str) else ""
        app_clipboard = QtGui.QGuiApplication.clipboard()
        if app_clipboard is not None:
            app_clipboard.setText(value)
        return {"ok": True}

    def _secrets_has(self, provider_id: str) -> bool:
        return bool(getattr(self, "vault", None) and self.vault.has_secret(provider_id))

    def _secrets_list(self) -> list[str]:
        return list(self.vault.list_keys()) if getattr(self, "vault", None) else []

    def _secrets_available(self) -> bool:
        return bool(getattr(self, "vault", None) and self.vault.available())

    def _update_state(self) -> dict[str, Any]:
        return {"status": "idle"}

    def _remote_state(self) -> dict[str, Any]:
        return {"bots": [], "enabled": False}


# Deva `services/profile.ts` 的默认用户头像（同一份 Humation spec，界面首帧必须一致）
DEFAULT_USER_AVATAR = (
    '{"selections":{"head":"hm1-p-000004","body":"hm1-p-000028","bottom":"hm1-p-000037",'
    '"item":"hm1-p-000062","glasses":"hm1-p-000058"},"colors":{"stroke":"000000",'
    '"hair":"B0B0B0","skin":"FFE0BD","clothes":"2D2D2D","bottom":"000000"},"background":"0D8CE9"}'
)


def _error_payload(exc: Exception) -> dict[str, Any]:
    return {
        "name": type(exc).__name__,
        "message": str(exc),
        "unimplemented": isinstance(exc, UnimplementedChannel),
    }


def list_models_payload(result: Any) -> dict[str, Any]:
    """`ListModelsResult`（frozen dataclass）→ 渲染层契约形状 `{ok, models?, kind?, message?}`。

    `ListModelsResult` **不是** pydantic 模型，没有 `model_dump()`；之前桥里直接调它，
    每次「拉取模型」都以 AttributeError 收场（界面永远显示拉取失败）。这里显式按契约
    只放这四个键，`models` 用数组（原版是 `string[]`）。
    """
    payload: dict[str, Any] = {"ok": bool(getattr(result, "ok", False))}
    models = list(getattr(result, "models", ()) or ())
    if models:
        payload["models"] = models
    kind = getattr(result, "kind", None)
    if kind:
        payload["kind"] = kind
    message = getattr(result, "message", None)
    if message:
        payload["message"] = message
    return payload


def display_messages(messages: list[Any]) -> list[dict[str, Any]]:
    """存储消息 → Deva 的 `DisplayMessage[]`（渲染层重建历史用）。

    规则照抄原版 `main/services/chat.ts` 的 `toDisplayMessages`，界面才与重开原版会话一致：
    - 同一轮内、只被 tool_result（user 角色）隔开的连续 assistant 段**并入上一条展示气泡**——
      有工具调用时一轮在持久化历史里是多条 assistant，逐条成气泡会重开后每段各显一个头像；
    - tool_result 不单独成气泡，而是按 toolUseId **回填**上一条 assistant 里那张工具卡的 status；
    - 真实用户消息把合并链断开（lastAssistant = None），其后的 assistant 另起新气泡。

    形状严格照 preload 的 `DisplayMessage` / `DisplayBlock`。
    """
    out: list[dict[str, Any]] = []
    last_assistant: dict[str, Any] | None = None

    for message in messages:
        content = getattr(message, "content", None)
        role = getattr(message, "role", "")

        if role == "assistant":
            parts = [{"type": "text", "text": content}] if isinstance(content, str) else list(content or [])
            blocks: list[dict[str, Any]] = []
            for part in parts:
                kind = getattr(part, "type", "")
                if kind == "text":
                    text = str(getattr(part, "text", ""))
                    if text:
                        blocks.append({"kind": "text", "text": text})
                elif kind == "tool_use":
                    blocks.append(
                        {
                            "kind": "tool",
                            "id": str(getattr(part, "id", "")),
                            "name": str(getattr(part, "name", "")),
                            "args": getattr(part, "input", {}) or {},
                            "status": "ok",
                        }
                    )
            if last_assistant is not None:
                last_assistant["blocks"].extend(blocks)
            else:
                last_assistant = {"role": "assistant", "blocks": blocks}
                out.append(last_assistant)
            continue

        # ── user ──────────────────────────────────────────────────────────
        if isinstance(content, str):
            if content.startswith(NOTIFY_MARKER):
                out.append(
                    {
                        "role": "user",
                        "text": _notify_headline(content[len(NOTIFY_MARKER) :]),
                        "attachments": [],
                        "notify": True,
                    }
                )
            else:
                out.append({"role": "user", "text": content, "attachments": []})
            last_assistant = None
            continue

        parts = list(content or [])
        if any(getattr(p, "type", "") == "tool_result" for p in parts):
            # 工具结果回灌：回填工具卡状态，不生成气泡、也不断开合并链。
            if last_assistant is not None:
                cards = {
                    b.get("id"): b
                    for b in last_assistant["blocks"]
                    if b.get("kind") == "tool" and b.get("id")
                }
                for part in parts:
                    if getattr(part, "type", "") != "tool_result":
                        continue
                    card = cards.get(str(getattr(part, "toolUseId", "")))
                    if card is None:
                        continue
                    card["status"] = "error" if getattr(part, "isError", False) else "ok"
            continue

        # 真实用户消息：最后一个 text 块是提问正文（其余为附件注入块，暂不重建）。
        text_parts = [str(getattr(p, "text", "")) for p in parts if getattr(p, "type", "") == "text"]
        out.append({"role": "user", "text": text_parts[-1] if text_parts else "", "attachments": []})
        last_assistant = None
    return out


def _notify_headline(body: str) -> str:
    """后台任务通知：原版取标记后的首行作标题（`noticeHeadline`）。"""
    line = body.lstrip("\n").split("\n", 1)[0]
    return line.strip()


__all__ = [
    "BridgeError",
    "DEFAULT_USER_AVATAR",
    "DevaBridge",
    "UnimplementedChannel",
    "display_messages",
    "list_models_payload",
]
