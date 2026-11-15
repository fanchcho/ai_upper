"""为「聊天消息里的文件输出」证据跑准备一份真实数据目录（只写目标目录）。

灌进去的东西全部走现有服务层 / 落盘结构，不是界面常量：

1. 一条会话 `qml-files-demo`：
   - 用户消息带两件附件：一张真 PNG（内联 base64，与 web 入口落盘形态一致）与一个
     文本附件（`[附件文件]` 注入块，`AttachmentService` 的真实标记）；
   - 一次 `present_files` 工具调用 + 对应工具结果，`tool_use.id = tu-deliver-1`；
   - 边车 `delivered = {"tu-deliver-1": [chart.png, notes.md]}`，两个文件真的写到磁盘
     （chart.png 是 221 字节 PNG，notes.md 43 字节），所以卡片上的体积是 `os.stat` 的真实值。
2. 模型配置：`ANTHROPIC_BASE_URL` / `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` 都在时
   配一个 anthropic provider，供「带附件真发一轮」的证据跑用；否则只配一份占位配置
   （截图证据不需要网络）。

用法：.venv/bin/python out/chat-files/seed_chat_files.py <home 目录> [workspace 目录]
"""
from __future__ import annotations

import base64
import os
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "app" / "src"))

from mvvm.models.chat_models import (  # noqa: E402
    ImagePart,
    Message,
    TextPart,
    ToolResultPart,
    ToolUsePart,
    now_ms,
)
from mvvm.services.chat_session_store import ChatSessionStore  # noqa: E402
from mvvm.services.secrets_vault import SecretsVault  # noqa: E402
from mvvm.services.settings_service import SettingsService  # noqa: E402

SESSION_ID = "qml-files-demo"
TOOL_USE_ID = "tu-deliver-1"


def png_bytes(width: int = 24, height: int = 16) -> bytes:
    """一张合法 PNG（宽高可变），缩略图与 body 的 image_resolver 都认。"""

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    raw = bytearray()
    for y in range(height):
        raw.append(0)  # 过滤字节
        for x in range(width):
            raw.extend(((40 + x * 8) % 256, 120, (200 - y * 6) % 256))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def main() -> int:
    if len(sys.argv) < 2:
        print("用法：seed_chat_files.py <home> [workspace]", file=sys.stderr)
        return 2
    home = Path(sys.argv[1]).resolve()
    workspace = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else home / "ws"
    home.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)

    # 交付物：两个真实文件（体积就是卡片上要显示的数字）。
    chart = workspace / "chart.png"
    chart.write_bytes(png_bytes())
    notes = workspace / "notes.md"
    notes.write_bytes("# 季度总结\n\n- 收入增长 12%\n- 成本下降 3%\n".encode("utf-8"))
    attachment = workspace / "photo.png"
    attachment.write_bytes(png_bytes(32, 24))

    store = ChatSessionStore(home)
    store.ensure_session(SESSION_ID)
    session = store.load_session(SESSION_ID)
    session.messages = []

    image_b64 = base64.b64encode(attachment.read_bytes()).decode("ascii")
    session.messages.append(
        Message(
            role="user",
            content=[
                ImagePart(mediaType="image/png", data=image_b64, name="photo.png"),
                TextPart(
                    text="[附件文件] spec.txt\n```\n把图表和说明整理成一份季度总结。\n```"
                ),
                TextPart(text="把图表和说明整理成一份季度总结，用 present_files 交付给我。"),
            ],
        )
    )
    session.messages.append(
        Message(
            role="assistant",
            content=[
                TextPart(text="已经生成图表与说明，交付如下。"),
                ToolUsePart(
                    type="tool_use",
                    id=TOOL_USE_ID,
                    name="present_files",
                    input={"paths": [str(chart), str(notes)]},
                ),
            ],
        )
    )
    session.messages.append(
        Message(
            role="user",
            content=[
                ToolResultPart(
                    toolUseId=TOOL_USE_ID,
                    content="已交付 2 个文件，交付卡将在本轮回复结束后显示在回复末尾。",
                )
            ],
        )
    )
    session.delivered = {TOOL_USE_ID: [str(chart), str(notes)]}
    session.title = "季度总结交付"
    session.updatedAt = now_ms()
    store.save(SESSION_ID)

    base_url = os.environ.get("ANTHROPIC_BASE_URL", "").strip()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    model = os.environ.get("ANTHROPIC_MODEL", "").strip()
    settings = SettingsService(home)
    if base_url and api_key and model:
        vault = SecretsVault(home)
        vault.set_secret("p-demo", api_key)
        settings.set_config(
            {
                "models": {
                    "activeModelId": "p-demo:%s" % model,
                    "providers": [
                        {
                            "id": "p-demo",
                            "adapter": "anthropic",
                            "apiHost": base_url,
                            "enabled": True,
                            "models": [{"id": model, "enabled": True}],
                        }
                    ],
                }
            }
        )
        print("SEED provider=anthropic", base_url, model, flush=True)
    else:
        settings.set_config({"models": {"activeModelId": "", "providers": []}})
        print("SEED provider=none（未配置真实模型，截图证据不需要网络）", flush=True)

    print(
        "SEED",
        "home=%s" % home,
        "session=%s" % SESSION_ID,
        "tool_use=%s" % TOOL_USE_ID,
        "chart=%s(%d B)" % (chart, chart.stat().st_size),
        "notes=%s(%d B)" % (notes, notes.stat().st_size),
        "attachment=%s(%d B)" % (attachment, attachment.stat().st_size),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
