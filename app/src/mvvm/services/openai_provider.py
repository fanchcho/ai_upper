"""OpenAI Chat Completions 风味适配器（兼容 DeepSeek / Moonshot / 智谱 / Qwen / Ollama 等）。

端点 `POST {baseURL}/chat/completions`（`stream: true`）。逐步对齐 Deva `providers/openai.ts`：

- 消息映射：一条 assistant 的工具结果会裂成多条 `{role:'tool'}` 消息；
  工具返回的图片只能挂到紧随其后的 user 消息（tool 消息只收文本）；
- `tool_calls` 增量按 `index` 拼接，`finish_reason` 到达后统一 flush；
- 输出上限字段：OpenAI 官方（含 Azure）认 `max_completion_tokens`，其余兼容服务商认 `max_tokens`；
- 带内错误块（HTTP 200 + `{"error":...}`）：没有 choices 就必须原样上报，
  否则本轮会以「自然结束 + 零正文」收场，用户只看到一句空回合提示。
"""
from __future__ import annotations

import json
from typing import Any, AsyncIterator, Optional
from urllib.parse import urlsplit

from mvvm.models.chat_models import DocumentPart, ImagePart, Message, TextPart, ToolResultPart, ToolUsePart
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
    tool_images_note,
)
from mvvm.services.sse import STREAM_IDLE_MS, StreamIdleError, iterate_sse
from mvvm.services.transport import CancelToken, CancelledError, HttpResponse, NetworkError, Transport


def _image_part(part: ImagePart) -> dict[str, Any]:
    return {"type": "image_url", "image_url": {"url": f"data:{part.mediaType};base64,{part.data}"}}


def map_messages(system: Optional[str], messages: Any) -> list[dict[str, Any]]:
    """归一化消息 → OpenAI 消息序列。"""
    out: list[dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})

    for message in normalize_messages(messages):
        content = message.content
        if isinstance(content, str):
            out.append({"role": message.role, "content": content})
            continue

        if message.role == "assistant":
            text = "".join(part.text for part in content if isinstance(part, TextPart))
            tool_uses = [part for part in content if isinstance(part, ToolUsePart)]
            out.append(
                {
                    "role": "assistant",
                    "content": text or None,
                    "tool_calls": [
                        {
                            "id": tool_use.id,
                            "type": "function",
                            "function": {
                                "name": tool_use.name,
                                "arguments": json.dumps(tool_use.input or {}, ensure_ascii=False),
                            },
                        }
                        for tool_use in tool_uses
                    ]
                    or None,
                }
            )
            continue

        # user 消息：文本/图片合并为一条 user；tool_result 各成一条 tool 消息。
        texts: list[str] = []
        images: list[dict[str, Any]] = []
        for part in content:
            if isinstance(part, TextPart):
                texts.append(part.text)
            elif isinstance(part, ImagePart):
                images.append(_image_part(part))
            elif isinstance(part, DocumentPart):
                # OpenAI Chat 无原生 PDF 通道：降级为文字说明，避免上下文断裂。
                texts.append(f"[附加文档：{part.name or '未命名'}（当前模型不支持直接读取其内容）]")
            elif isinstance(part, ToolResultPart):
                out.append({"role": "tool", "tool_call_id": part.toolUseId, "content": part.content})
                if part.images:
                    texts.append(tool_images_note(part.images))
                    images.extend(_image_part(image) for image in part.images)
        if images:
            merged: list[dict[str, Any]] = []
            if texts:
                merged.append({"type": "text", "text": "\n".join(texts)})
            merged.extend(images)
            out.append({"role": "user", "content": merged})
        elif texts:
            out.append({"role": "user", "content": "\n".join(texts)})
    return out


def thinking_fields(effort: Any) -> dict[str, Any]:
    """思考参数 → OpenAI Chat 请求字段（格式见 effort.ThinkFormat）。"""
    if effort is None:
        return {}
    downgraded = {"reasoning_effort": effort.effort} if effort.effort else {}
    if effort.format == "deepseek":
        return {"thinking": {"type": "enabled"}, **downgraded}
    if effort.format == "zai":
        return {"thinking": {"type": "enabled", "clear_thinking": False}, **downgraded}
    if effort.format == "qwen":
        return {"enable_thinking": True, **downgraded}
    return downgraded


def output_limit_field(base_url: str) -> str:
    """输出上限的字段名（见 Deva `outputLimitField`）。"""
    try:
        host = (urlsplit(base_url).hostname or "").lower()
    except ValueError:
        return "max_tokens"
    return "max_completion_tokens" if host == "api.openai.com" or host.endswith(".openai.azure.com") else "max_tokens"


def map_finish_reason(raw: Optional[str]) -> str:
    if raw == "tool_calls" or raw == "function_call":
        return "tool_use"
    if raw == "content_filter" or raw == "sensitive":
        return "refusal"
    if raw == "length":
        return "max_tokens"
    return "end_turn"


class OpenAIProvider(Provider):
    """OpenAI Chat Completions 适配器。"""

    name = "openai"

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

    def build_body(self, request: GenerateRequest) -> dict[str, Any]:
        messages = map_messages(request.system, request.messages)
        # DeepSeek 思考模式要求每条回放的助手消息都带 reasoning_content（缺即 400）。
        # 本应用不留思维链，补空串即可（Deva 同样如此兜底）。
        if request.effort is not None and request.effort.reasoning_field:
            for message in messages:
                if message["role"] == "assistant":
                    message.setdefault("reasoning_content", "")
        body: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            output_limit_field(self.base_url): request.max_tokens,
            **thinking_fields(request.effort),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if request.tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("inputSchema") or {"type": "object", "properties": {}},
                    },
                }
                for tool in request.tools
            ]
        if request.temperature is not None:
            body["temperature"] = request.temperature
        return body

    def headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json", "authorization": f"Bearer {self.api_key}"}
        headers.update(self.extra_headers)
        return headers

    async def stream(self, request: GenerateRequest) -> AsyncIterator[StreamEvent]:  # type: ignore[override]
        if self.transport is None:
            raise ProviderError(
                NormalizedError("invalid_request", "OpenAIProvider 未配置传输层：请传入 transport")
            )
        if self.cancel.cancelled:
            yield Done("aborted")
            return
        url = f"{self.base_url}/chat/completions"
        try:
            response = await self.transport.post(
                url, headers=self.headers(), body=_encode(self.build_body(request)), cancel=self.cancel
            )
        except CancelledError:
            yield Done("aborted")
            return
        except NetworkError as exc:
            yield StreamError(NormalizedError("network", str(exc), True))
            yield Done("error")
            return

        async for event in self._consume(response, request.effort is not None):
            yield event

    async def _consume(self, response: HttpResponse, effort_sent: bool) -> AsyncIterator[StreamEvent]:
        if not (200 <= response.status < 300):
            text = await response.text()
            yield StreamError(
                http_error(response.status, text, response.headers.get("retry-after"), effort_sent)
            )
            yield Done("error")
            return

        calls: dict[int, dict[str, str]] = {}
        stop_reason = "end_turn"
        input_tokens = output_tokens = cache_read = 0

        def flush_calls() -> list[StreamEvent]:
            events: list[StreamEvent] = []
            broken: list[tuple[str, str, str]] = []
            for index in sorted(calls):
                call = calls[index]
                args = parse_tool_args(call["args"])
                if args is None:
                    broken.append((call["id"], call["name"], call["args"]))
                else:
                    events.append(ToolCall(id=call["id"], name=call["name"], input=args))
            calls.clear()
            events.extend(settle_broken_calls(broken, stop_reason))
            return events

        try:
            async for sse in iterate_sse(response.body, self.idle_ms):
                if sse.data == "[DONE]":
                    break
                chunk = _loads(sse.data)
                if chunk is None:
                    continue

                # 带内错误块：HTTP 200 + `data: {"error":{...}}`（配额耗尽、内容拦截、上游 5xx）。
                inband = chunk.get("error")
                if isinstance(inband, dict) and not isinstance(chunk.get("choices"), list):
                    message = str(
                        inband.get("message") or inband.get("code") or inband.get("type")
                        or "服务端返回了未说明的错误"
                    )
                    yield StreamError(
                        inband_error(
                            f"{message} {inband.get('code') or ''}",
                            NormalizedError("server", message, False),
                        )
                    )
                    yield Done("error")
                    return

                usage = chunk.get("usage")
                if isinstance(usage, dict):
                    if usage.get("prompt_tokens"):
                        input_tokens = int(usage["prompt_tokens"])
                    if usage.get("completion_tokens"):
                        output_tokens = int(usage["completion_tokens"])
                    # 两家都是服务端自动前缀缓存：只有命中量、没有写入量；
                    # prompt_tokens 本就是含命中的总量，不必再加。
                    details = usage.get("prompt_tokens_details") or {}
                    hit = details.get("cached_tokens") if isinstance(details, dict) else None
                    hit = hit or usage.get("prompt_cache_hit_tokens")
                    if hit:
                        cache_read = int(hit)
                    # 个别网关只透传 DeepSeek 的命中/未命中两段而不给 prompt_tokens。
                    if not usage.get("prompt_tokens") and (
                        usage.get("prompt_cache_hit_tokens") or usage.get("prompt_cache_miss_tokens")
                    ):
                        input_tokens = int(usage.get("prompt_cache_hit_tokens") or 0) + int(
                            usage.get("prompt_cache_miss_tokens") or 0
                        )

                choices = chunk.get("choices")
                choice = choices[0] if isinstance(choices, list) and choices else None
                if not isinstance(choice, dict):
                    continue

                delta = choice.get("delta") or {}
                if isinstance(delta, dict):
                    if delta.get("content"):
                        yield TextDelta(str(delta["content"]))
                    # DeepSeek-R1 等把思维链放在 reasoning_content。
                    if delta.get("reasoning_content"):
                        yield ThinkingDelta(str(delta["reasoning_content"]))
                    # 拒绝走 refusal 字段而非 content：不接这一路整轮就「什么都没返回」。
                    if delta.get("refusal"):
                        yield TextDelta(str(delta["refusal"]))
                    for partial in delta.get("tool_calls") or []:
                        if not isinstance(partial, dict):
                            continue
                        index = int(partial.get("index", 0))
                        current = calls.get(index) or {"id": "", "name": "", "args": ""}
                        if partial.get("id"):
                            current["id"] = str(partial["id"])
                        function = partial.get("function") or {}
                        if isinstance(function, dict):
                            if function.get("name"):
                                current["name"] = str(function["name"])
                            if function.get("arguments"):
                                current["args"] += str(function["arguments"])
                        calls[index] = current

                finish_reason = choice.get("finish_reason")
                if finish_reason:
                    # 智谱：network_error = 推理异常，本步输出不完整——按可重试错误上报。
                    if finish_reason == "network_error":
                        yield StreamError(
                            NormalizedError("server", "服务端推理异常（finish_reason: network_error）", True)
                        )
                        yield Done("error")
                        return
                    stop_reason = map_finish_reason(str(finish_reason))
                    if stop_reason == "tool_use":
                        for event in flush_calls():
                            yield event
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

        # 残留未 flush 的工具调用：finish_reason=length / 内容拦截（截在参数中途），
        # 或个别实现不带 finish_reason（兜底按工具调用收尾）。
        if calls:
            if stop_reason == "end_turn":
                stop_reason = "tool_use"
            for event in flush_calls():
                yield event

        if input_tokens or output_tokens:
            yield Usage(input_tokens=input_tokens, output_tokens=output_tokens, cache_read=cache_read)
        yield Done(stop_reason)


def _encode(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _loads(raw: str) -> Optional[dict[str, Any]]:
    try:
        parsed = json.loads(raw)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


__all__ = [
    "OpenAIProvider",
    "map_finish_reason",
    "map_messages",
    "output_limit_field",
    "thinking_fields",
]
