"""生成对话页截图用的固定会话数据（只写目标目录，供两边共用同一个 DEVA_HOME 数据）。

为什么要固定数据：对话页的像素对比前提是两边渲染同一份历史。Deva 的会话文件格式是
`<DEVA_HOME>/data/chats/<id>.json` + `_index.json`，本脚本按该格式写一条含用户消息、
助手文本、工具调用与结果的会话，原版与端口读同一份。

用法: .venv/bin/python scripts/parity/make_chat_fixture.py <输出目录>
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SESSION_ID = "parity-chat"
TITLE = "对比用会话：一条完整回合"

# 固定时间戳：两边渲染出的相对时间（刚刚 / 几分钟前）必须一致，否则截图不可比。
CREATED_AT = int(datetime(2026, 11, 14, 9, 30, tzinfo=timezone.utc).timestamp() * 1000)
UPDATED_AT = CREATED_AT + 60_000

MESSAGES = [
    {"role": "user", "content": "帮我看看这个目录里有什么，然后说明一下 README 的用途。"},
    {
        "role": "assistant",
        "content": [
            {"type": "text", "text": "我先列一下目录内容。"},
            {
                "type": "tool_use",
                "id": "toolu_parity_1",
                "name": "list_dir",
                "input": {"path": "/srv/workspace/demo"},
            },
        ],
    },
    {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "toolUseId": "toolu_parity_1",
                "content": "README.md\nsrc\npackage.json",
                "isError": False,
            }
        ],
    },
    {
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": "目录里有 `README.md`、`src` 和 `package.json`。README 用来记录项目用途与运行方式。",
            }
        ],
    },
]
SESSION = {
    "id": SESSION_ID,
    "title": TITLE,
    "createdAt": CREATED_AT,
    "updatedAt": UPDATED_AT,
    "messages": MESSAGES,
    "personaId": "general",
}

INDEX = [
    {
        "id": SESSION_ID,
        "title": TITLE,
        "createdAt": CREATED_AT,
        "updatedAt": UPDATED_AT,
        "personaId": "general",
    }
]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{SESSION_ID}.json").write_text(
        json.dumps(SESSION, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "_index.json").write_text(
        json.dumps(INDEX, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"fixture written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
