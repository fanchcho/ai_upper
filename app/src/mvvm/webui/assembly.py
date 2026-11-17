"""回合层对象图装配：把回合宿主、模型网关与工具运行时接成一张图。

为什么单独成模块：QML 壳（`qml_shell.py`，源码树与打包产物共用的那条入口）与测试夹具
（`app/tests/`）都要这一套装配。写两份就会漂移——改了一处忘了另一处，表现为「测试里能
发消息、真实入口里不能」这种最难查的差异。

装配口径（`qml_shell.py` 的打包入口即按此装配）：
- 每轮按会话定格的 `modelRef` 现解析模型、现取密钥、现造适配器（设置页改动下一轮生效）；
- 工具的根目录取会话的 `focusRoot`；文件类工具仍过 `WorkspaceGuard`（本工程的安全底线）；
- 会话的思考档位 → 本轮思考参数，同样按会话现查。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

from mvvm.services.chat_session_store import ChatSessionStore
from mvvm.services.provider_setup import ModelGateway
from mvvm.services.secrets_vault import SecretsVault
from mvvm.services.settings_service import SettingsService
from mvvm.services.tool_runtime import ToolRuntime
from mvvm.services.workspace_guard import WorkspaceGuard
from mvvm.view_models.chat_vm import ChatViewModel
from mvvm.webui.host import ChatHost


def build_chat_host(
    *,
    settings: SettingsService,
    vault: SecretsVault,
    store: ChatSessionStore,
    guard: WorkspaceGuard,
    home: Path,
    emit: Callable[[dict[str, Any]], None],
    emit_sessions_changed: Callable[[], None],
    transport: Any = None,
) -> tuple[ChatHost, ModelGateway]:
    """造一个接了真实网关的回合宿主；返回（宿主，网关）。

    `transport` 只在测试里给（脚本化响应）；生产路径留空 = 真实 httpx 传输。
    """
    gateway = ModelGateway(settings, vault, transport)

    def session_model(session_id: str) -> Optional[str]:
        """会话里定格的模型引用；会话不存在时 None（回落全局默认）。"""
        session = store.load_session(session_id) if session_id else None
        return session.model if session is not None else None

    def session_root(session_id: str) -> Optional[Path]:
        session = store.load_session(session_id) if session_id else None
        focus = session.focusRoot if session is not None else None
        return Path(focus) if focus else None

    def tool_factory(session_id: str) -> ToolRuntime:
        return ToolRuntime(guard, session_root(session_id), home=home, session_id=session_id)

    def vm_factory(session_id: str) -> ChatViewModel:
        return ChatViewModel(
            store,
            None,
            tool_factory(session_id),
            session_id=session_id,
            turn_factory=lambda cancel, model_ref, sid=session_id: gateway.turn_provider(
                cancel, model_ref, sid
            ),
            provider_factory=gateway.provider_factory(session_id),
            compact_model_provider=lambda sid=session_id: gateway.compact_model(session_model(sid)),
            models_section_provider=settings.models_section,
            compaction_config_provider=gateway.compaction_settings,
            effort_provider=lambda level, sid=session_id: gateway.effort_parameter(
                level, session_model(sid)
            ),
        )

    host = ChatHost(
        store=store,
        guard=guard,
        home=home,
        emit=emit,
        emit_sessions_changed=emit_sessions_changed,
        tool_factory=tool_factory,
        vm_factory=vm_factory,
    )
    return host, gateway


def trusted_workspace_from_env() -> Optional[str]:
    """`DEVA_APP_WORKSPACE`：启动时登记为受信根的工作区目录（与桌面入口同口径）。"""
    import os

    value = os.environ.get("DEVA_APP_WORKSPACE", "").strip()
    return value or None


__all__ = ["build_chat_host", "trusted_workspace_from_env"]
