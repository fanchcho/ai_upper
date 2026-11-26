"""OpenAI Responses API 适配器（`POST {baseURL}/responses`，`stream: true`）。

与 Chat Completions 并列的第二套 OpenAI 协议，面向 OpenAI 官方新接口。逐步对齐
Deva `providers/openai-responses.ts`：

- system → 顶层 `instructions`（无状态，每轮都发）；
- 消息拍平成 `input` 数组：assistant 文本 → `{role:'assistant', content:[output_text]}`，
  tool_use → 独立 `function_call` 项；user 文本/图片/PDF → 一条 user 消息，
  tool_result → 独立 `function_call_output` 项；
- 工具声明用 Responses 的**扁平**形状（非 Chat 的 function 嵌套），`strict: false`；
- `call_id` 是串联 function_call ↔ function_call_output 的键；
- `store: false`：不在服务端留存，也不使用 `previous_response_id`。
"""
from __future__ import annotations
from locale_runtime import tr

import json
from typing import Any, AsyncIterator, Optional

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

DEFAULT_MAX_OUTPUT = 8192


def _image_url(part: ImagePart) -> str:
    return f"data:{part.mediaType};base64,{part.data}"


def map_input(messages: Any) -> list[dict[str, Any]]:
    """归一化消息 → Responses `input` 序列（工具调用/结果各自成独立顶层项）。"""
    out: list[dict[str, Any]] = []
    for message in normalize_messages(messages):
        content = message.content
        if isinstance(content, str):
            if content:
                out.append({"role": message.role, "content": [{"type": "input_text", "text": content}]})
            continue

        if message.role == "assistant":
            text = "".join(part.text for part in content if isinstance(part, TextPart))
            if text:
                out.append({"role": "assistant", "content": [{"type": "output_text", "text": text}]})
            for part in content:
                if isinstance(part, ToolUsePart):
                    out.append(
                        {
                            "type": "function_call",
                            "call_id": part.id,
                            "name": part.name,
                            "arguments": json.dumps(part.input or {}, ensure_ascii=False),
                        }
                    )
            continue

        # user 消息：先落工具结果（独立项），再把文本/图片/PDF 并成一条 user 消息。
        parts: list[dict[str, Any]] = []
        for part in content:
            if isinstance(part, ToolResultPart):
                out.append(
                    {"type": "function_call_output", "call_id": part.toolUseId, "output": part.content}
                )
                # output 按字符串发（块数组并非所有网关都认）；工具返回的图片挪进随后的 user 消息。
                if part.images:
                    parts.append({"type": "input_text", "text": tool_images_note(part.images)})
                    parts.extend(
                        {"type": "input_image", "image_url": _image_url(image)} for image in part.images
                    )
            elif isinstance(part, TextPart):
                parts.append({"type": "input_text", "text": part.text})
            elif isinstance(part, ImagePart):
                parts.append({"type": "input_image", "image_url": _image_url(part)})
            elif isinstance(part, DocumentPart):
                parts.append(
                    {
                        "type": "input_file",
                        "filename": part.name or "document.pdf",
                        "file_data": f"data:{part.mediaType};base64,{part.data}",
                    }
                )
        if parts:
            out.append({"role": "user", "content": parts})
    return out


class ResponsesProvider(Provider):
    """OpenAI Responses API 适配器。"""

    name = "responses"

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
        body: dict[str, Any] = {
            "model": request.model,
            "input": map_input(request.messages),
            # 输出上限：未指定时给 8192（与 Anthropic 一致，降低长回复被截断概率）。
            "max_output_tokens": request.max_tokens or DEFAULT_MAX_OUTPUT,
            # 无状态使用：不留存于服务端（隐私一致）。
            "store": False,
            "stream": True,
        }
        if request.system:
            body["instructions"] = request.system
        if request.tools:
            body["tools"] = [
                {
                    "type": "function",
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema") or {"type": "object", "properties": {}},
                    # 严格模式要求全 required + additionalProperties:false，本应用 schema 未必满足。
                    "strict": False,
                }
                for tool in request.tools
            ]
        if request.temperature is not None:
            body["temperature"] = request.temperature
        # 思考等级（值已按模型能力表映射）。不请求 summary：未认证组织请求推理摘要会被 400。
        if request.effort is not None:
            body["reasoning"] = {"effort": request.effort.effort} if request.effort.effort else {}
        return body

    def headers(self) -> dict[str, str]:
        headers = {"content-type": "application/json", "authorization": f"Bearer {self.api_key}"}
        headers.update(self.extra_headers)
        return headers

    async def stream(self, request: GenerateRequest) -> AsyncIterator[StreamEvent]:  # type: ignore[override]
        if self.transport is None:
            raise ProviderError(
                NormalizedError("invalid_request", tr('legacy.c9abf9e85d10'))
            )
        if self.cancel.cancelled:
            yield Done("aborted")
            return
        url = f"{self.base_url}/responses"
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

        # output item id -> 累积中的函数调用
        calls: dict[str, dict[str, str]] = {}
        broken: list[tuple[str, str, str]] = []
        stop_reason = "end_turn"
        saw_tool = False
        input_tokens = output_tokens = cache_read = 0

        def take_usage(event: dict[str, Any]) -> None:
            nonlocal input_tokens, output_tokens, cache_read
            payload = event.get("response")
            usage = payload.get("usage") if isinstance(payload, dict) else None
            if not isinstance(usage, dict):
                return
            if usage.get("input_tokens"):
                input_tokens = int(usage["input_tokens"])
            if usage.get("output_tokens"):
                output_tokens = int(usage["output_tokens"])
            # Responses 的 input_tokens 已是含缓存命中的总量，cached_tokens 只是其中命中的那部分。
            details = usage.get("input_tokens_details") or {}
            hit = details.get("cached_tokens") if isinstance(details, dict) else None
            if hit:
                cache_read = int(hit)

        try:
            async for sse in iterate_sse(response.body, self.idle_ms):
                if sse.data == "[DONE]":
                    break
                event = _loads(sse.data)
                if event is None:
                    continue
                kind = event.get("type")

                if kind == "response.output_text.delta":
                    delta = event.get("delta")
                    if isinstance(delta, str) and delta:
                        yield TextDelta(delta)
                elif kind in ("response.reasoning_summary_text.delta", "response.reasoning_text.delta"):
                    # 推理摘要（仅在服务端产出时到达）——作为思考展示，不持久化。
                    delta = event.get("delta")
                    if isinstance(delta, str) and delta:
                        yield ThinkingDelta(delta)
                elif kind == "response.refusal.delta":
                    delta = event.get("delta")
                    if isinstance(delta, str) and delta:
                        yield TextDelta(delta)
                elif kind == "response.output_item.added":
                    item = event.get("item") or {}
                    if isinstance(item, dict) and item.get("type") == "function_call" and item.get("id"):
                        calls[str(item["id"])] = {
                            "call_id": str(item.get("call_id") or ""),
                            "name": str(item.get("name") or ""),
                            "args": "",
                        }
                elif kind == "response.function_call_arguments.delta":
                    call = calls.get(str(event.get("item_id") or ""))
                    if call is not None and isinstance(event.get("delta"), str):
                        call["args"] += str(event["delta"])
                elif kind == "response.output_item.done":
                    item = event.get("item") or {}
                    if isinstance(item, dict) and item.get("type") == "function_call":
                        item_id = str(item.get("id") or "")
                        acc = calls.get(item_id)
                        call_id = str(item.get("call_id") or (acc or {}).get("call_id") or "")
                        name = str(item.get("name") or (acc or {}).get("name") or "")
                        # done 事件里的 arguments 为权威全量；缺失时回落流式累积。
                        raw_args = item.get("arguments") if isinstance(item.get("arguments"), str) else (acc or {}).get("args", "")
                        if item_id:
                            calls.pop(item_id, None)
                        args = parse_tool_args(str(raw_args))
                        if args is None:
                            # 解析不了先扣下：截断原因（response.incomplete）在其后才到。
                            broken.append((call_id, name, str(raw_args)))
                        else:
                            saw_tool = True
                            yield ToolCall(id=call_id, name=name, input=args)
                elif kind == "response.completed":
                    take_usage(event)
                elif kind == "response.incomplete":
                    take_usage(event)
                    payload = event.get("response") or {}
                    details = payload.get("incomplete_details") if isinstance(payload, dict) else None
                    reason = details.get("reason") if isinstance(details, dict) else None
                    if reason == "max_output_tokens":
                        stop_reason = "max_tokens"
                    elif reason == "content_filter":
                        stop_reason = "refusal"
                elif kind == "response.failed":
                    take_usage(event)
                    payload = event.get("response") or {}
                    error = payload.get("error") if isinstance(payload, dict) else None
                    message = str(
                        (error or {}).get("message") or "生成失败" if isinstance(error, dict) else ""
                    ) or "生成失败"
                    code = str((error or {}).get("code") or "") if isinstance(error, dict) else ""
                    yield StreamError(
                        inband_error(f"{message} {code}", NormalizedError("server", message, False))
                    )
                    yield Done("error")
                    return
                elif kind == "error":
                    raw_message = event.get("message")
                    if not isinstance(raw_message, str):
                        error = event.get("error") or {}
                        raw_message = (error.get("message") if isinstance(error, dict) else None) or "流式错误"
                    message = str(raw_message)
                    yield StreamError(
                        inband_error(message, NormalizedError("server", message, False))
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

        # 残缺的调用：截断时连 output_item.done 都没等到的也算上。
        if stop_reason == "max_tokens":
            for call in calls.values():
                broken.append((call["call_id"], call["name"], call["args"]))
        elif broken:
            saw_tool = True
        for truncated in settle_broken_calls(broken, stop_reason):
            yield truncated

        # 有工具调用即按 tool_use 收尾——但不覆盖 max_tokens（截断须如实上报）。
        if saw_tool and stop_reason != "max_tokens":
            stop_reason = "tool_use"

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


__all__ = ["ResponsesProvider", "map_input"]
