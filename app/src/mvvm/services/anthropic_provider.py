"""Anthropic Messages API 适配器：手写 SSE → 归一化 StreamEvent，不引 SDK。

端点：`POST {baseURL}/v1/messages`（`stream: true`）。逐段对齐 Deva `providers/anthropic.ts`：

- 消息映射：文本 / tool_use / image / document / tool_result 五种内容块；
- 提示缓存断点：system 末尾 + 最后一条消息的末块（`cache_control: ephemeral`）；
- 用量归一：Anthropic 的 `input_tokens` 只是「未命中缓存的余量」，
  三段（未命中 + 缓存写入 + 缓存命中）相加才是总提示 token；
- 残缺工具调用：参数 JSON 解析失败的扣到流尾，按 stop_reason 定性；
- 错误：HTTP 错误走 `http_error`，流内 `error` 事件走 `inband_error`。
"""
from __future__ import annotations
from locale_runtime import tr

from typing import Any, AsyncIterator, Optional

from mvvm.models.chat_models import (
    DocumentPart,
    ImagePart,
    Message,
    TextPart,
    ToolResultPart,
    ToolUsePart,
)
from mvvm.services.provider_gateway import (
    Done,
    GenerateRequest,
    NormalizedError,
    Provider,
    ProviderError,
    StreamError,
    StreamEvent,
    TextDelta,
    ThinkingDelta,
    ToolCall,
    Usage,
    http_error,
    inband_error,
    normalize_messages,
    parse_tool_args,
    settle_broken_calls,
)
from mvvm.services.sse import STREAM_IDLE_MS, StreamIdleError, iterate_sse
from mvvm.services.transport import CancelToken, CancelledError, HttpResponse, NetworkError, Transport

CACHE_CONTROL = {"type": "ephemeral"}
DEFAULT_MAX_TOKENS = 8192
ANTHROPIC_VERSION = "2023-06-01"


def _image_block(part: ImagePart) -> dict[str, Any]:
    return {"type": "image", "source": {"type": "base64", "media_type": part.mediaType, "data": part.data}}


def map_content(content: Any) -> list[dict[str, Any]]:
    """归一化内容 → Anthropic 内容块数组。"""
    if isinstance(content, str):
        return [{"type": "text", "text": content}] if content else []
    blocks: list[dict[str, Any]] = []
    for part in content:
        if isinstance(part, TextPart):
            blocks.append({"type": "text", "text": part.text})
        elif isinstance(part, ToolUsePart):
            blocks.append({"type": "tool_use", "id": part.id, "name": part.name, "input": part.input or {}})
        elif isinstance(part, ImagePart):
            blocks.append(_image_block(part))
        elif isinstance(part, DocumentPart):
            blocks.append(
                {
                    "type": "document",
                    "source": {"type": "base64", "media_type": part.mediaType, "data": part.data},
                }
            )
        elif isinstance(part, ToolResultPart):
            # 带图时 content 改为块数组（文字说明在前、图片随后），协议原生支持；
            # 不带图时照旧发字符串，请求体与改造前逐字节一致。
            if part.images:
                inner: list[dict[str, Any]] = []
                if part.content:
                    inner.append({"type": "text", "text": part.content})
                inner.extend(_image_block(image) for image in part.images)
                blocks.append(
                    {"type": "tool_result", "tool_use_id": part.toolUseId, "content": inner,
                     "is_error": bool(part.isError)}
                )
            else:
                blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": part.toolUseId,
                        "content": part.content,
                        "is_error": bool(part.isError),
                    }
                )
    return blocks


def map_messages(messages: Any) -> list[dict[str, Any]]:
    """相邻同角色消息合并为一条（块按原序拼接）。"""
    out: list[dict[str, Any]] = []
    for message in normalize_messages(messages):
        blocks = map_content(message.content)
        if out and out[-1]["role"] == message.role:
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": message.role, "content": blocks})
    return out


def mark_cache_tail(messages: list[dict[str, Any]]) -> None:
    """提示缓存断点②：给最后一条消息的最后一个内容块挂标记。"""
    if not messages:
        return
    blocks = messages[-1].get("content")
    if isinstance(blocks, list) and blocks:
        tail = blocks[-1]
        if isinstance(tail, dict):
            tail["cache_control"] = CACHE_CONTROL


def thinking_param(effort: Any) -> Optional[dict[str, Any]]:
    """思考等级 → `thinking` 字段。"""
    if effort is None:
        return None
    if effort.format == "compat":
        return {"type": effort.thinking} if effort.thinking else None
    return {"type": "adaptive", "display": "summarized"}


def map_stop_reason(raw: Optional[str]) -> str:
    if raw == "tool_use":
        return "tool_use"
    if raw == "max_tokens":
        return "max_tokens"
    if raw == "refusal":
        return "refusal"
    if raw == "stop_sequence":
        return "stop"
    return "end_turn"


class AnthropicProvider(Provider):
    """Anthropic Messages API 适配器。"""

    name = "anthropic"

    def __init__(
        self,
        base_url: str,
        api_key: str,
        transport: Optional[Transport] = None,
        extra_headers: Optional[dict[str, str]] = None,
        idle_ms: int = STREAM_IDLE_MS,
        cancel: Optional[CancelToken] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.transport = transport
        self.extra_headers = dict(extra_headers or {})
        self.idle_ms = idle_ms
        self.cancel = cancel or CancelToken()

    # ── 请求 ──────────────────────────────────────────────────────────────
    def build_body(self, request: GenerateRequest) -> dict[str, Any]:
        messages = map_messages(request.messages)
        if request.cache:
            mark_cache_tail(messages)
        system: Any = request.system
        # 断点①：挂 cache_control 须把 system 从纯字符串改成 text 块数组。
        if request.cache and request.system:
            system = [{"type": "text", "text": request.system, "cache_control": CACHE_CONTROL}]
        body: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens or DEFAULT_MAX_TOKENS,
            "stream": True,
        }
        if system:
            body["system"] = system
        if request.tools:
            body["tools"] = [
                {"name": tool["name"], "description": tool.get("description", ""),
                 "input_schema": tool.get("inputSchema") or {"type": "object", "properties": {}}}
                for tool in request.tools
            ]
        if request.temperature is not None:
            body["temperature"] = request.temperature
        thinking = thinking_param(request.effort)
        if thinking:
            body["thinking"] = thinking
        if request.effort is not None and request.effort.effort:
            body["output_config"] = {"effort": request.effort.effort}
        return body

    def headers(self) -> dict[str, str]:
        headers = {
            "content-type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        }
        headers.update(self.extra_headers)
        return headers

    # ── 流 ────────────────────────────────────────────────────────────────
    async def stream(self, request: GenerateRequest) -> AsyncIterator[StreamEvent]:  # type: ignore[override]
        if self.transport is None:
            raise ProviderError(
                NormalizedError("invalid_request", tr('legacy.f3be68b5b69e'))
            )
        if self.cancel.cancelled:
            # 用户已点停止：别再把请求发出去（省一次计费），直接按中止收尾。
            yield Done("aborted")
            return
        url = f"{self.base_url}/v1/messages"
        try:
            response = await self.transport.post(
                url,
                headers=self.headers(),
                body=_encode(self.build_body(request)),
                cancel=self.cancel,
            )
        except CancelledError:
            yield Done("aborted")
            return
        except NetworkError as exc:
            yield StreamError(NormalizedError("network", str(exc), True))
            yield Done("error")
            return

        async for event in self._consume(response, bool(request.effort)):
            yield event

    async def _consume(self, response: HttpResponse, effort_sent: bool) -> AsyncIterator[StreamEvent]:
        if not (200 <= response.status < 300):
            text = await response.text()
            yield StreamError(
                http_error(response.status, text, response.headers.get("retry-after"), effort_sent)
            )
            yield Done("error")
            return

        tool_blocks: dict[int, dict[str, str]] = {}
        broken: list[tuple[str, str, str]] = []
        uncached_input = cache_write = cache_read = output_tokens = 0
        stop_reason = "end_turn"

        def take_usage(usage: Optional[dict[str, Any]]) -> None:
            nonlocal uncached_input, cache_write, cache_read, output_tokens
            if not isinstance(usage, dict):
                return
            if usage.get("input_tokens"):
                uncached_input = int(usage["input_tokens"])
            if usage.get("output_tokens"):
                output_tokens = int(usage["output_tokens"])
            if usage.get("cache_creation_input_tokens"):
                cache_write = int(usage["cache_creation_input_tokens"])
            if usage.get("cache_read_input_tokens"):
                cache_read = int(usage["cache_read_input_tokens"])

        try:
            async for sse in iterate_sse(response.body, self.idle_ms):
                if sse.data == "[DONE]":
                    break
                event = _loads(sse.data)
                if event is None:
                    continue
                kind = event.get("type")

                if kind == "message_start":
                    message = event.get("message")
                    if isinstance(message, dict):
                        take_usage(message.get("usage"))
                elif kind == "content_block_start":
                    index = int(event.get("index", 0))
                    block = event.get("content_block") or {}
                    if isinstance(block, dict) and block.get("type") == "tool_use":
                        tool_blocks[index] = {
                            "id": str(block.get("id") or ""),
                            "name": str(block.get("name") or ""),
                            "json": "",
                        }
                elif kind == "content_block_delta":
                    index = int(event.get("index", 0))
                    delta = event.get("delta") or {}
                    if not isinstance(delta, dict):
                        continue
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        yield TextDelta(str(delta["text"]))
                    elif delta.get("type") == "thinking_delta" and delta.get("thinking"):
                        yield ThinkingDelta(str(delta["thinking"]))
                    elif delta.get("type") == "input_json_delta":
                        pending_block = tool_blocks.get(index)
                        if pending_block is not None:
                            pending_block["json"] += str(delta.get("partial_json") or "")
                elif kind == "content_block_stop":
                    index = int(event.get("index", 0))
                    pending_block = tool_blocks.pop(index, None)
                    if pending_block is None:
                        continue
                    args = parse_tool_args(pending_block["json"])
                    if args is None:
                        # stop_reason 在块结束之后才到，届时再定性是不是被截断。
                        broken.append((pending_block["id"], pending_block["name"], pending_block["json"]))
                    else:
                        yield ToolCall(id=pending_block["id"], name=pending_block["name"], input=args)
                elif kind == "message_delta":
                    take_usage(event.get("usage"))
                    delta = event.get("delta") or {}
                    if isinstance(delta, dict) and delta.get("stop_reason"):
                        stop_reason = map_stop_reason(str(delta["stop_reason"]))
                elif kind == "error":
                    error = event.get("error") or {}
                    message = str(error.get("message") or tr('finish.ui.df9f1fb37552')) if isinstance(error, dict) else tr('finish.ui.df9f1fb37552')
                    code = str(error.get("type") or "") if isinstance(error, dict) else ""
                    yield StreamError(
                        inband_error(f"{message} {code}", NormalizedError("server", message, True))
                    )
                    yield Done("error")
                    return
        except CancelledError:
            yield Done("aborted")
            return
        except StreamIdleError as exc:
            yield StreamError(NormalizedError("network", str(exc), True))
            yield Done("error")
            return
        except NetworkError as exc:
            yield StreamError(NormalizedError("network", str(exc), True))
            yield Done("error")
            return
        finally:
            await response.aclose()

        # 截断时连块结束都没等到的工具块也算残缺；非截断的不完整收尾（异常断流）维持旧行为：不交出。
        if stop_reason == "max_tokens":
            for pending_block in tool_blocks.values():
                broken.append((pending_block["id"], pending_block["name"], pending_block["json"]))
        for truncated in settle_broken_calls(broken, stop_reason):
            yield truncated

        input_tokens = uncached_input + cache_write + cache_read
        if input_tokens or output_tokens:
            yield Usage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read=cache_read,
                cache_write=cache_write,
            )
        yield Done(stop_reason)


def _encode(payload: dict[str, Any]) -> bytes:
    import json

    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _loads(raw: str) -> Optional[dict[str, Any]]:
    import json

    try:
        parsed = json.loads(raw)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


__all__ = [
    "ANTHROPIC_VERSION",
    "AnthropicProvider",
    "CACHE_CONTROL",
    "map_content",
    "map_messages",
    "map_stop_reason",
    "mark_cache_tail",
    "thinking_param",
]
