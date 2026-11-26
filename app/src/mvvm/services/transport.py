"""HTTP 传输层抽象：真实实现走 httpx，测试用离线假传输喂字节。

为什么要这层：SSE 解析、重连、错误归类是这一阶段最需要测的东西，而它们**不该**要求真起一个
TLS 服务。适配器只依赖 `Transport.post(...)` 这个协议，测试注入 `ScriptedTransport` 就能精确
控制状态码、响应头、分块边界与中断时机——测的是真实解析代码，不是替身。

取消：用 `CancelToken`（对 Deva `AbortSignal` 的对应物）。读取时把它和每次读竞速，
所以「用户点停止」不必等满读超时。
"""
from __future__ import annotations
from locale_runtime import tr

import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator, Mapping, Optional, Protocol

from mvvm.services.http_client import CancelledError, build_client, describe_net_error


class CancelToken:
    """可取消标记。`cancel()` 幂等；读取方通过 `wait()` / `cancelled` 感知。"""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()

    async def wait_timeout(self, seconds: float) -> bool:
        """等到取消或超时；返回 True 表示已取消。"""
        if self.cancelled:
            return True
        try:
            await asyncio.wait_for(self._event.wait(), timeout=seconds)
            return True
        except asyncio.TimeoutError:
            return False


async def _empty_body() -> AsyncIterator[bytes]:  # pragma: no cover - 占位空流
    return
    yield b""


@dataclass
class HttpResponse:
    """一次已建立连接（2xx/4xx/5xx 都算已建立）的响应。"""

    status: int
    headers: Mapping[str, str] = field(default_factory=dict)
    body: AsyncIterator[bytes] = field(default_factory=_empty_body)  # type: ignore[assignment]
    _closer: Optional[object] = None

    async def text(self) -> str:
        """读完整个响应体（错误响应与非流式探测用）。"""
        chunks: list[bytes] = []
        try:
            async for chunk in self.body:
                chunks.append(chunk)
        except Exception:  # noqa: BLE001 - 读错误响应失败不该覆盖真正的状态码
            pass
        return b"".join(chunks).decode("utf-8", "replace")

    async def aclose(self) -> None:
        closer = getattr(self.body, "aclose", None)
        if closer is not None:
            try:
                await closer()
            except Exception:  # noqa: BLE001 - 关闭时的错误无意义
                pass


class Transport(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        cancel: Optional[CancelToken] = None,
    ) -> "asyncio.Future[HttpResponse] | object": ...


class HttpxTransport:
    """真实网络传输（httpx）。代理按 URL 逐请求判定。"""

    def __init__(self, proxy_url_resolver=None) -> None:
        # resolver(url) -> 代理地址或 None；缺省由调用方直接给固定代理
        self._resolver = proxy_url_resolver
        self._clients: dict[Optional[str], object] = {}

    def _client(self, proxy_url: Optional[str]):
        client = self._clients.get(proxy_url)
        if client is None:
            client = build_client(proxy_url)
            self._clients[proxy_url] = client
        return client

    async def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        cancel: Optional[CancelToken] = None,
    ) -> HttpResponse:
        proxy_url = self._resolver(url) if self._resolver else None
        client = self._client(proxy_url)
        request = client.build_request("POST", url, headers=dict(headers), content=body)
        try:
            response = await client.send(request, stream=True)
        except Exception as exc:  # noqa: BLE001 - 统一转成可读网络错误
            raise NetworkError(describe_net_error(exc)) from exc
        return HttpResponse(
            status=response.status_code,
            headers={k.lower(): v for k, v in response.headers.items()},
            body=_iter_httpx_body(response, cancel),
        )

    async def aclose(self) -> None:
        for client in self._clients.values():
            try:
                await client.aclose()  # type: ignore[attr-defined]
            except Exception:  # noqa: BLE001
                pass
        self._clients.clear()


class NetworkError(RuntimeError):
    """传输层网络失败（已翻译成用户可读文本）。"""


async def _iter_httpx_body(response, cancel: Optional[CancelToken]) -> AsyncIterator[bytes]:
    """逐块产出响应体；每次读都与取消标记竞速，并负责关闭底层响应。"""
    iterator = response.aiter_bytes()
    try:
        while True:
            if cancel is not None and cancel.cancelled:
                raise CancelledError(tr('legacy.f2187b0114d3'))
            if cancel is None:
                try:
                    yield await iterator.__anext__()
                except StopAsyncIteration:
                    return
                continue
            read = asyncio.ensure_future(iterator.__anext__())
            stop = asyncio.ensure_future(cancel.wait())
            done, pending = await asyncio.wait({read, stop}, return_when=asyncio.FIRST_COMPLETED)
            if stop in done:
                read.cancel()
                raise CancelledError(tr('legacy.f2187b0114d3'))
            stop.cancel()
            try:
                yield read.result()
            except StopAsyncIteration:
                return
    except CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - 读失败要变成可归类网络错误
        raise NetworkError(describe_net_error(exc)) from exc
    finally:
        await response.aclose()


__all__ = [
    "CancelToken",
    "CancelledError",
    "HttpResponse",
    "HttpxTransport",
    "NetworkError",
    "Transport",
]
