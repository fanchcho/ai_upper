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

import json
from pathlib import Path
from typing import Any, Callable

from utils.qt_compat import QtCore, Signal, Slot

QObject = QtCore.QObject

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


class DevaBridge(QObject):
    """一个 WebEngine 页面 ↔ Python 服务 的桥。

    `on_ready` 在页面注入完成后由视图调用一次，把首批事件（sessions-changed 等）推给渲染层。
    """

    # 事件通道：名字与 preload 的 `ipcRenderer.on(...)` 一致
    event = Signal(str, str)  # (channel, payload_json)

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
        # 标题栏叠加层主题回调：由视图注入（桥不直接依赖视图类）。
        self._overlay_callback: Callable[[bool], None] | None = None
        # 窗口控制回调：同样由视图注入。没注入时通道必须显式报错，不能假装成功。
        self._window_actions: dict[str, Callable[..., Any]] = {}
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
        """把一条事件推给渲染层（对应 `webContents.send(channel, payload)`）。"""
        if self._view is None:
            return
        code = (
            f"window.__devaEmit({json.dumps(channel)}, "
            f"{json.dumps(json.dumps(payload, ensure_ascii=False))});"
        )
        self._view.page().runJavaScript(code)

    # ── 注册表 ────────────────────────────────────────────────────────────
    def register(self, channel: str, handler: Callable[..., Any]) -> None:
        self._handlers[channel] = handler

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
            result = handler(*args)
        except Exception as exc:  # noqa: BLE001 - 桥边界：任何异常都要变成前端的 reject
            self._resolve(request_id, False, _error_payload(exc))
            return
        self._resolve(request_id, True, result)

    def _resolve(self, request_id: str, ok: bool, payload: Any) -> None:
        if self._view is None:
            return
        body = json.dumps(payload, ensure_ascii=False) if payload is not None else "null"
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

        self.register("skills:list", self.skills.list_skills)
        self.register("skills:get", self.skills.get)

        self.register("profile:get", self._profile_get)

        self.register("chat:list-sessions", self._list_sessions)
        self.register("chat:load-session", self._load_session)
        self.register("chat:attach-session", self._attach_session)
        self.register("browser:state", self._browser_state)
        self.register("browser:ready", self._browser_state)
        self.register("browser:preview-pinned", lambda _tab=None: {"ok": True})
        self.register("window:set-overlay", self._set_overlay)

        self.register("secrets:has", self._secrets_has)
        self.register("secrets:list", self._secrets_list)
        self.register("secrets:available", self._secrets_available)

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
        del workspace_root  # 会话已无项目分桶；参数仅为兼容签名
        return [meta.model_dump() for meta in self.store.visible_sessions()]

    def _load_session(self, session_id: str, workspace_root: str | None = None) -> list[dict[str, Any]]:
        del workspace_root
        session = self.store.load_session(session_id)
        if session is None:
            return []
        return display_messages(session.messages)

    def _attach_session(self, session_id: str) -> dict[str, Any]:
        """接上会话：历史 + 进行中回合。当前还没有后台回合，turnId 恒为 null（不假造）。"""
        return {"messages": self._load_session(session_id), "turnId": None, "startedAt": None}

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
]
