"""离线假传输：把适配器要吃的 SSE 字节精确喂进去，不需要真起 TLS 服务。

为什么这样测：SSE 分帧、增量拼接、错误归类、取消，都是这一层最容易出错、又最难在真实网络上
复现的地方。用假传输能精确控制**分块边界**（把一条事件切成两半）、状态码、响应头与中断时机，
测到的是真实的解析代码而不是替身逻辑。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Mapping, Optional, Sequence

from mvvm.services.transport import CancelToken, CancelledError, HttpResponse, NetworkError


def sse(event: Optional[str], data: Any) -> bytes:
    """构造一个 SSE 事件（data 为 dict/str 时自动 JSON 编码）。"""
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    prefix = f"event: {event}\n" if event else ""
    return f"{prefix}data: {payload}\n\n".encode("utf-8")


def openai_chunk(delta: dict[str, Any], finish: Optional[str] = None, **extra: Any) -> dict[str, Any]:
    choice: dict[str, Any] = {"index": 0, "delta": delta}
    if finish is not None:
        choice["finish_reason"] = finish
    return {"choices": [choice], **extra}


@dataclass
class ScriptedTransport:
    """按脚本回放响应。`chunks` 逐块产出，分块边界由调用方决定。"""

    status: int = 200
    headers: Mapping[str, str] = field(default_factory=dict)
    chunks: Sequence[bytes] = ()
    # 在第 N 块之后抛 NetworkError（模拟读中断）；None = 不中断。
    fail_after: Optional[int] = None
    # 请求阶段就失败（连接不上）。
    connect_error: Optional[str] = None
    # 请求阶段就被取消。
    cancel_on_send: Optional[CancelToken] = None

    calls: list[dict[str, Any]] = field(default_factory=list)

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        cancel: Optional[CancelToken] = None,
    ) -> HttpResponse:
        self.calls.append({"url": url, "headers": dict(headers), "body": body})
        if self.cancel_on_send is not None:
            self.cancel_on_send.cancel()
            raise CancelledError("请求已取消")
        if self.connect_error is not None:
            raise NetworkError(self.connect_error)
        return HttpResponse(status=self.status, headers=dict(self.headers), body=self._body())

    async def _body(self) -> AsyncIterator[bytes]:
        for index, chunk in enumerate(self.chunks):
            if self.fail_after is not None and index >= self.fail_after:
                raise NetworkError("连接被中断（模拟）")
            yield chunk

    @property
    def last_body(self) -> dict[str, Any]:
        """最后一次请求的 JSON 正文（断言消息映射用）。"""
        return json.loads(self.calls[-1]["body"].decode("utf-8"))
