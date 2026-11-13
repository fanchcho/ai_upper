"""SSE 分帧 + 空闲看门狗。

逐行对齐 Deva `providers/sse.ts`：

- 事件以空行分隔（`\\n\\n`），`\\r\\n` 先统一成 `\\n`，否则分帧漏判；
- `event:` 行给事件名，`data:` 行可多行（按 `\\n` 拼接），`:` 开头的注释行（心跳）忽略；
- 没有 data 行的块不产出事件；
- 连续 `idle_ms` 收不到任何字节（含心跳）就判连接僵死，抛 `StreamIdleError`。

与 Deva 的差异：Deva 从 Web Stream 的 reader 读，这里从**任意异步字节流**读
（适配器传 httpx 的 `aiter_bytes()`），因此可以离线喂假数据做测试，不需要真起服务。
"""
from __future__ import annotations

import asyncio
import codecs
from dataclasses import dataclass
from typing import AsyncIterator, Union

STREAM_IDLE_MS = 60_000


class StreamIdleError(RuntimeError):
    """空闲超时专用的错误：对上层是一个可重试的网络错误。"""

    def __init__(self, ms: int) -> None:
        seconds = round(ms / 1000)
        super().__init__(f"连接空闲超过 {seconds}s，判定为中断")
        self.name = "StreamIdleError"


@dataclass(frozen=True)
class SSEEvent:
    event: str | None
    data: str


async def iterate_sse(
    source: AsyncIterator[Union[bytes, str]], idle_ms: int = 0
) -> AsyncIterator[SSEEvent]:
    """把字节流切成 SSE 事件。`idle_ms=0` 表示不设空闲看门狗。"""
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    buffer = ""
    iterator = source.__aiter__()
    while True:
        try:
            chunk = await _read_with_idle(iterator, idle_ms)
        except StopAsyncIteration:
            break
        text = decoder.decode(chunk) if isinstance(chunk, bytes) else chunk
        buffer += text.replace("\r\n", "\n")

        while True:
            sep = buffer.find("\n\n")
            if sep == -1:
                break
            block = buffer[:sep]
            buffer = buffer[sep + 2:]
            event_name: str | None = None
            data_lines: list[str] = []
            for line in block.split("\n"):
                if line.startswith("event:"):
                    event_name = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    value = line[len("data:"):]
                    data_lines.append(value[1:] if value.startswith(" ") else value)
                # 以 ':' 开头的注释行（心跳）直接忽略
            if data_lines:
                yield SSEEvent(event=event_name, data="\n".join(data_lines))


async def _read_with_idle(iterator: AsyncIterator[Union[bytes, str]], idle_ms: int):
    """读下一块；超时抛 StreamIdleError。没有空闲限制时直接读。"""
    if idle_ms <= 0:
        return await iterator.__anext__()
    try:
        return await asyncio.wait_for(iterator.__anext__(), timeout=idle_ms / 1000)
    except asyncio.TimeoutError as exc:
        raise StreamIdleError(idle_ms) from exc


__all__ = ["SSEEvent", "STREAM_IDLE_MS", "StreamIdleError", "iterate_sse"]
