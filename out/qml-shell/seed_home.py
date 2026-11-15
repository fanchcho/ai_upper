"""为 QML 壳准备一份真实数据目录（只写目标目录，不碰默认 home）。

用途：QML 壳的会话列表与正文读的是 `ChatSessionStore` 落盘的会话，所以证据跑之前要先
用**现有服务层**（`append_message` / `save` / `SettingsService.set_config`）灌一批真实
会话——不是假数据常量，重开壳时读的就是这些文件。

三条会话：
1. 含代码块与表格的正文（截图要展示的富文本）；
2. 含引用、列表与行内代码；
3. 一条短会话。

模型配置与密钥同样写进这份目录：`ANTHROPIC_BASE_URL` / `ANTHROPIC_API_KEY` /
`ANTHROPIC_MODEL` 存在时配一个 anthropic provider（本机代理），否则不配——壳照常能开，
发送会以「尚未配置模型」收场，不是假成功。

用法：.venv/bin/python out/qml-shell/seed_home.py <home 目录> [--empty]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app" / "src"))

from mvvm.models.chat_models import Message, now_ms  # noqa: E402
from mvvm.services.chat_session_store import ChatSessionStore  # noqa: E402
from mvvm.services.secrets_vault import SecretsVault  # noqa: E402
from mvvm.services.settings_service import SettingsService  # noqa: E402

BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "").strip()
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
MODEL = os.environ.get("ANTHROPIC_MODEL", "").strip()

RICH_ASSISTANT = """已把 QML 壳从写死的假数据接到真实会话：列表行取自
`ChatSessionStore.visible_sessions()`，正文按落盘消息重渲染。

```python
def rows(store):
    return [m.id for m in store.visible_sessions()]
```

| 项 | 状态 |
| --- | --- |
| 会话列表接真实数据 | 完成 |
| 流式回复 | 完成 |
| 空状态 | 完成 |

下一步是把输入区接上真实回合宿主，再把增量实时刷进正文。"""

SECOND_USER = "正文渲染器为什么不用 QTextFrame 画引用竖线？"
SECOND_ASSISTANT = """因为 QML 的 `TextEdit` 渲染 `border > 0` 的 `QTextFrame` 会段错误（退出码 139）。

引用块改用表格左列背景画竖线：

> 引用用表格，不用 frame。

1. `QTextFrame` 只用来画 1px 分隔线，border 恒为 0；
2. 代码块是单列表格，宽度按容器宽重新计算。"""

THIRD_USER = "先把壳跑起来，逐页还原之后再说。"
THIRD_ASSISTANT = "好的，壳已经是可启动、可截图的最小版本。"


def seed(home: Path) -> None:
    store = ChatSessionStore(home)
    now = now_ms()

    def add(session_id: str, title: str, pairs: list, updated_at: int) -> None:
        store.ensure_session(session_id)
        session = store.load_session(session_id)
        session.createdAt = updated_at - 600_000
        for role, text in pairs:
            session.messages.append(Message(role=role, content=text))
        session.title = title
        session.updatedAt = updated_at
        store.save(session_id)

    add(
        "qml-real-1",
        "QML 壳接真实数据",
        [("user", "把 QML 壳的假数据换成真实会话，并把发送链接上。"), ("assistant", RICH_ASSISTANT)],
        now,
    )
    add(
        "qml-real-2",
        "正文渲染细节",
        [("user", SECOND_USER), ("assistant", SECOND_ASSISTANT)],
        now - 3_600_000,
    )
    add(
        "qml-real-3",
        "下一步计划",
        [("user", THIRD_USER), ("assistant", THIRD_ASSISTANT)],
        now - 26 * 3_600_000,
    )


def configure(home: Path) -> str:
    """模型配置：环境里有真 provider 就写进去，返回描述（写进报告）。"""
    settings = SettingsService(home)
    if not (BASE_URL and API_KEY and MODEL):
        return "no-provider-env"
    settings.set_config(
        {
            "models": {
                "activeModelId": "local:%s" % MODEL,
                "providers": [
                    {
                        "id": "local",
                        "adapter": "anthropic",
                        "apiHost": BASE_URL,
                        "enabled": True,
                        "models": [
                            {"id": MODEL, "enabled": True, "contextWindow": 128000}
                        ],
                    }
                ],
                "activeEffort": "default",
            },
            "theme": "light",
        }
    )
    vault = SecretsVault(home, backend="file")
    vault.set_secret("local", API_KEY)
    return "anthropic@%s model=%s" % (BASE_URL.split("/")[2], MODEL)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    home = Path(argv[1]).resolve()
    home.mkdir(parents=True, exist_ok=True)
    if "--empty" not in argv[1:]:
        seed(home)
    print("home:", home)
    print("provider:", configure(home))
    print("sessions:", [m.id for m in ChatSessionStore(home).visible_sessions()])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
