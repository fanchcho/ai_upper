"""服务商的自定义请求头（对齐 Deva `shared/provider-headers.ts`）。

用途与上游一致：个别中转 / 企业网关按请求头识别客户端或租户（如要求 `originator`、
指定的 `user-agent`），官方端点也有可选头（`anthropic-beta`、`openai-organization`）。
用户填的头并在本应用默认头之后，同名即覆盖。

本模块只做纯数据整理，不认识 Qt、不读磁盘——界面草稿与手改过的 config.json 都走这里。
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

# 不允许经自定义请求头设置的名字（小写）：
#  · 鉴权头由「API 密钥」一栏负责，两处都能填会互相覆盖、出了问题难排查；
#  · 其余由请求正文与网络栈决定，改了只会让请求发不出去。
RESERVED_HEADERS = frozenset(
    {
        "authorization",
        "x-api-key",
        "content-type",
        "content-length",
        "host",
        "connection",
        "transfer-encoding",
    }
)

# 单个服务商最多保留的自定义请求头条数（防手改配置塞进成百上千条）。
MAX_CUSTOM_HEADERS = 32

# HTTP 头名的合法字符（RFC 9110 token）。
NAME_RE = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
# 头值只收可见 ASCII 与空格 / 制表符：其余字符会让整条请求发不出去。
VALUE_RE = re.compile(r"^[\t\x20-\x7e]*$")


def header_issue(name: str, value: str) -> Optional[str]:
    """一条请求头不能用的原因：`name` / `reserved` / `value`；可用返回 None。

    名、值均先去首尾空白；空名 / 空值不算问题，整理时直接略过（与上游 `headerIssue` 同）。
    """
    trimmed = name.strip()
    if trimmed and not NAME_RE.match(trimmed):
        return "name"
    if trimmed.lower() in RESERVED_HEADERS:
        return "reserved"
    if not VALUE_RE.match(value.strip()):
        return "value"
    return None


def sanitize_headers(raw: Any) -> Dict[str, str]:
    """把任意来源的请求头整理成可直接并进请求头表的字典。

    名字转小写（与本应用默认头同一写法，同名才能覆盖而不是并排发两条）、去首尾空白，
    略过空名 / 空值 / 不合法 / 被保留的条目，永不抛错。
    """
    out: Dict[str, str] = {}
    if not isinstance(raw, dict):
        return out
    for key, value in raw.items():
        if not isinstance(value, str):
            continue
        name = str(key).strip().lower()
        trimmed = value.strip()
        if not name or not trimmed or header_issue(name, trimmed):
            continue
        if name not in out and len(out) >= MAX_CUSTOM_HEADERS:
            break
        out[name] = trimmed
    return out


__all__ = [
    "MAX_CUSTOM_HEADERS",
    "NAME_RE",
    "RESERVED_HEADERS",
    "VALUE_RE",
    "header_issue",
    "sanitize_headers",
]
