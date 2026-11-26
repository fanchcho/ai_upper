"""统一出站 HTTP：代理、超时、取消、网络错误解释。

对应 Deva `apps/desktop/src/main/http.ts`，但**只搬语义，不搬 Chromium 网络栈**：
Deva 走 Electron 的 `session.fetch` 以获得系统证书库与系统代理；Python 侧用 httpx，
证书认系统 CA（`certifi` + `ssl` 默认），企业网自签证书仍需 `SSL_CERT_FILE` 或用户自带 CA——
这一点如实写在这里，不假装等价。

代理口径与 Deva 一致：**默认直连，认 `HTTPS_PROXY` / `HTTP_PROXY` / `ALL_PROXY` / `NO_PROXY`
环境变量，不读系统代理**。Deva 另外有一条「直连失败改走系统代理重试」的兜底，那依赖 Chromium
得知系统代理；Python 拿不到，故本工程没有这一条，改为在错误信息里明说「设置了代理环境变量吗」。
"""
from __future__ import annotations

from locale_runtime import tr
import os
import ssl
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit

import httpx

# 与 Deva 一致：单条连接的建立超时，避免连不上时干等。
CONNECT_TIMEOUT_S = 15.0
# 读超时由 SSE 的空闲看门狗负责（STREAM_IDLE_MS）；这里给一个宽松的上限，防止 httpx 夺走控制权。
READ_TIMEOUT_S = 300.0


@dataclass(frozen=True)
class ProxyConfig:
    http: Optional[str] = None
    https: Optional[str] = None
    all: Optional[str] = None
    no_proxy: Optional[str] = None

    @classmethod
    def from_env(cls) -> "ProxyConfig":
        def get(*names: str) -> Optional[str]:
            for name in names:
                value = (os.environ.get(name) or "").strip()
                if value:
                    return value
            return None

        return cls(
            http=get("HTTP_PROXY", "http_proxy"),
            https=get("HTTPS_PROXY", "https_proxy"),
            all=get("ALL_PROXY", "all_proxy"),
            no_proxy=get("NO_PROXY", "no_proxy"),
        )

    def for_url(self, url: str) -> Optional[str]:
        """该地址该走哪个代理（与 Deva `proxyUri` 同口径）；None = 直连。"""
        host = (urlsplit(url).hostname or "").lower()
        if host and _matches_no_proxy(host, self.no_proxy):
            return None
        if urlsplit(url).scheme == "https":
            return self.https or self.all
        return self.http or self.all


def _matches_no_proxy(host: str, no_proxy: Optional[str]) -> bool:
    if not no_proxy:
        return False
    for raw in no_proxy.split(","):
        entry = raw.strip().lower().lstrip(".")
        if not entry:
            continue
        if entry == "*" or host == entry or host.endswith("." + entry):
            return True
    return False


_EXPLAIN: tuple[tuple[type[BaseException], str], ...] = (
    (httpx.ConnectError, 'finish.ui.6a00c431066f'),
    (httpx.ProxyError, 'finish.ui.02a423cd11bd'),
    (httpx.ConnectTimeout, 'finish.ui.7a97266a720d'),
    (httpx.ReadTimeout, 'finish.ui.e94846149523'),
    (httpx.WriteTimeout, 'finish.ui.0fa5b76d9d84'),
    (httpx.PoolTimeout, 'finish.ui.2d69275b940e'),
    (httpx.RemoteProtocolError, 'finish.ui.a6fd227e62e4'),
    (httpx.ReadError, 'finish.ui.a920e1ba4e83'),
    (httpx.WriteError, 'finish.ui.a920e1ba4e83'),
    (httpx.HTTPError, 'finish.ui.b915a774849b'),
)

_SSL_ERRORS: tuple[type[BaseException], ...] = (ssl.SSLError, httpx.ConnectError)


def describe_net_error(exc: BaseException) -> str:
    """把网络异常翻译成用户能看懂的说明（Deva `describeNetError` 的同类能力）。"""
    detail = str(exc).strip()
    if isinstance(exc, ssl.SSLError) or (
        isinstance(exc, httpx.ConnectError) and "CERTIFICATE" in detail.upper()
    ):
        base = tr('finish.ui.6b910528b203')
        return f"{base}（{detail[:160]}）" if detail else base
    for exc_type, text in _EXPLAIN:
        if isinstance(exc, exc_type):
            text = tr(text)
            return f"{text}（{detail[:160]}）" if detail else text
    return detail or exc.__class__.__name__


class CancelledError(RuntimeError):
    """请求被用户中止（与协议错误区分开，上层据此记 aborted 而不是 error）。"""


def build_client(proxy_url: Optional[str]) -> httpx.AsyncClient:
    """构造异步客户端。`proxy_url=None` 表示直连（显式覆盖环境变量代理）。"""
    timeout = httpx.Timeout(READ_TIMEOUT_S, connect=CONNECT_TIMEOUT_S)
    # trust_env=False 让代理与 CA 完全由我们决定：否则 httpx 会自己读环境变量，
    # 上层显式传「直连」时反而仍走代理。
    return httpx.AsyncClient(timeout=timeout, proxy=proxy_url, trust_env=False, follow_redirects=False)


__all__ = [
    "CancelledError",
    "CONNECT_TIMEOUT_S",
    "READ_TIMEOUT_S",
    "ProxyConfig",
    "build_client",
    "describe_net_error",
]
