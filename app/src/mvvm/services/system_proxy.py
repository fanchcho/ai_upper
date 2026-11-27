"""Resolve native system/PAC routes without executing PAC inside the UI process.

libproxy owns desktop configuration, PAC download/evaluation and WPAD. Qt supplies
WinHTTP/CFNetwork on Windows/macOS and the platform fallback on Linux.
"""
from __future__ import annotations

import atexit
import ctypes
import ctypes.util
import logging
import sys
import threading

_lock = threading.Lock()
_library = None
_factory = None
_checked = False


def system_proxy(url: str) -> str | None:
    global _checked, _library, _factory
    if sys.platform.startswith('linux'):
        with _lock:
            if not _checked:
                _checked = True
                name = ctypes.util.find_library('proxy') or 'libproxy.so.1'
                if name:
                    try:
                        lib = ctypes.CDLL(name)
                        lib.px_proxy_factory_new.restype = ctypes.c_void_p
                        lib.px_proxy_factory_free.argtypes = [ctypes.c_void_p]
                        lib.px_proxy_factory_get_proxies.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
                        lib.px_proxy_factory_get_proxies.restype = ctypes.POINTER(ctypes.c_char_p)
                        lib.px_proxy_factory_free_proxies.argtypes = [ctypes.POINTER(ctypes.c_char_p)]
                        factory = lib.px_proxy_factory_new()
                        if factory:
                            _library, _factory = lib, factory
                            atexit.register(lib.px_proxy_factory_free, factory)
                    except (OSError, AttributeError) as exc:
                        logging.getLogger(__name__).warning('System PAC resolver unavailable: %s', exc)
                else:
                    logging.getLogger(__name__).warning('System PAC resolver unavailable: libproxy not found; using Qt platform resolver')
            if _library:
                proxies = _library.px_proxy_factory_get_proxies(_factory, url.encode())
                if not proxies:
                    return None
                try:
                    index = 0
                    while proxies[index]:
                        value = proxies[index].decode()
                        if value.startswith(('http://', 'https://', 'socks5://')):
                            return value
                        index += 1
                    return None
                finally:
                    _library.px_proxy_factory_free_proxies(proxies)
    from utils.qt_compat import QtCore, QtNetwork
    QUrl = QtCore.QUrl
    QNetworkProxy = QtNetwork.QNetworkProxy
    QNetworkProxyFactory = QtNetwork.QNetworkProxyFactory
    QNetworkProxyQuery = QtNetwork.QNetworkProxyQuery
    for proxy in QNetworkProxyFactory.systemProxyForQuery(QNetworkProxyQuery(QUrl(url))):
        scheme = {QNetworkProxy.HttpProxy: 'http', QNetworkProxy.HttpCachingProxy: 'http',
                  QNetworkProxy.Socks5Proxy: 'socks5'}.get(proxy.type())
        if scheme and proxy.hostName():
            host = proxy.hostName()
            if ':' in host:
                host = '[' + host + ']'
            return f'{scheme}://{host}:{proxy.port()}'
    return None
