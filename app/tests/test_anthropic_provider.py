"""Anthropic 适配器的离线测试：SSE 解析、工具调用拼接、错误归一、取消、用量统计。

全部走 `ScriptedTransport`，不发起任何网络请求。
"""
from __future__ import annotations

import asyncio

from mvvm.models.chat_models import ImagePart, Message, TextPart, ToolResultPart, ToolUsePart
from mvvm.services.anthropic_provider import AnthropicProvider
from mvvm.services.effort import EffortRequest
from mvvm.services.provider_gateway import (
    Done,
    GenerateRequest,
    StreamError,
    TextDelta,
    ThinkingDelta,
    ToolCall,
    ToolCallTruncated,
    Usage,
)
from mvvm.services.transport import CancelToken

from scripted_transport import ScriptedTransport, sse


async def _collect(stream):
    return [event async for event in stream]


def run(transport, **kwargs):
    request = GenerateRequest(
        model="claude-sonnet-5-5", messages=[Message(role="user", content="你好")], **kwargs
    )
    provider = AnthropicProvider("https://api.example.com", "sk-test", transport=transport)
    return asyncio.run(_collect(provider.stream(request)))


def text_stream(*chunks):
    events = [
        sse(
            "message_start",
            {
                "type": "message_start",
                "message": {
                    "usage": {
                        "input_tokens": 100,
                        "cache_read_input_tokens": 40,
                        "cache_creation_input_tokens": 10,
                    }
                },
            },
        ),
        sse(
            "content_block_start",
            {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
        ),
    ]
    for piece in chunks:
        events.append(
            sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "text_delta", "text": piece},
                },
            )
        )
    events.append(
        sse(
            "message_delta",
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": 7},
            },
        )
    )
    events.append(sse("message_stop", {"type": "message_stop"}))
    return ScriptedTransport(chunks=events)


def test_text_stream_usage_and_cache():
    events = run(text_stream("你", "好", "！"))

    assert [e.text for e in events if isinstance(e, TextDelta)] == ["你", "好", "！"]
    usage = next(e for e in events if isinstance(e, Usage))
    # Anthropic 的 input_tokens 只是未命中缓存的余量：100 + 10 写入 + 40 命中 = 150
    assert usage.input_tokens == 150
    assert usage.output_tokens == 7
    assert usage.cache_read == 40
    assert usage.cache_write == 10
    assert events[-1] == Done("end_turn")


def test_request_body_headers_and_cache_breakpoints():
    transport = text_stream("好")
    run(transport, system="你是助手", cache=True, max_tokens=2048)

    call = transport.calls[-1]
    assert call["url"] == "https://api.example.com/v1/messages"
    assert call["headers"]["x-api-key"] == "sk-test"
    assert call["headers"]["anthropic-version"] == "2023-06-01"
    body = transport.last_body
    assert body["stream"] is True
    assert body["max_tokens"] == 2048
    # 断点①：system 从字符串改成带 cache_control 的 text 块
    assert body["system"] == [
        {"type": "text", "text": "你是助手", "cache_control": {"type": "ephemeral"}}
    ]
    # 断点②：最后一条消息的末块
    assert body["messages"][-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}


def test_thinking_and_output_config_sent():
    transport = text_stream("好")
    effort = EffortRequest(format="standard", effort="high")
    run(transport, effort=effort)

    body = transport.last_body
    assert body["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert body["output_config"] == {"effort": "high"}


def test_sse_split_across_chunk_boundary():
    """同一条事件被切成两半也必须正确拼回来（真实网络就是这样分块的）。"""
    whole = sse(
        "content_block_delta",
        {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "跨块"}},
    )
    head = sse("message_start", {"type": "message_start", "message": {"usage": {"input_tokens": 5}}})
    tail = sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn"}})
    transport = ScriptedTransport(chunks=[head, whole[:17], whole[17:], tail])

    events = run(transport)
    assert [e.text for e in events if isinstance(e, TextDelta)] == ["跨块"]
    assert events[-1] == Done("end_turn")


def test_tool_call_accumulated_by_index():
    transport = ScriptedTransport(
        chunks=[
            sse(
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 1,
                    "content_block": {"type": "tool_use", "id": "toolu_1", "name": "read_file"},
                },
            ),
            sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 1,
                    "delta": {"type": "input_json_delta", "partial_json": '{"path":'},
                },
            ),
            sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 1,
                    "delta": {"type": "input_json_delta", "partial_json": ' "a.txt"}'},
                },
            ),
            sse("content_block_stop", {"type": "content_block_stop", "index": 1}),
            sse(
                "message_delta",
                {"type": "message_delta", "delta": {"stop_reason": "tool_use"}},
            ),
        ]
    )

    events = run(transport)
    calls = [e for e in events if isinstance(e, ToolCall)]
    assert len(calls) == 1
    assert calls[0].id == "toolu_1"
    assert calls[0].name == "read_file"
    assert calls[0].input == {"path": "a.txt"}
    assert events[-1] == Done("tool_use")


def test_truncated_tool_call_reported_not_executed():
    """参数被截断：必须报 ToolCallTruncated，绝不能当成 {} 去执行。"""
    transport = ScriptedTransport(
        chunks=[
            sse(
                "content_block_start",
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": "tool_use", "id": "toolu_2", "name": "write_file"},
                },
            ),
            sse(
                "content_block_delta",
                {
                    "type": "content_block_delta",
                    "index": 0,
                    "delta": {"type": "input_json_delta", "partial_json": '{"path": "a.txt", "content": "x'},
                },
            ),
            sse("content_block_stop", {"type": "content_block_stop", "index": 0}),
            sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": "max_tokens"}}),
        ]
    )

    events = run(transport)
    assert not [e for e in events if isinstance(e, ToolCall)]
    truncated = [e for e in events if isinstance(e, ToolCallTruncated)]
    assert len(truncated) == 1
    assert truncated[0].cause == "max_tokens"
    assert truncated[0].name == "write_file"
    assert events[-1] == Done("max_tokens")


def test_http_error_mapped_with_retry_after():
    transport = ScriptedTransport(
        status=429, headers={"retry-after": "3"}, chunks=[b'{"error":{"message":"slow down"}}']
    )

    events = run(transport)
    error = events[0]
    assert isinstance(error, StreamError)
    assert error.error.kind == "rate_limit"
    assert error.error.retryable is True
    assert error.error.retry_after_ms == 3000
    assert events[-1] == Done("error")


def test_context_overflow_error_carries_limit():
    body = b'{"error":{"message":"prompt is too long: 3000 tokens > 2000 maximum"}}'
    transport = ScriptedTransport(status=400, chunks=[body])

    events = run(transport)
    error = events[0].error
    assert error.kind == "context_length"
    assert error.limit == 2000


def test_inband_error_event_surfaces():
    transport = ScriptedTransport(
        chunks=[
            sse("error", {"type": "error", "error": {"type": "overloaded_error", "message": "过载"}}),
        ]
    )

    events = run(transport)
    assert isinstance(events[0], StreamError)
    assert "过载" in events[0].error.message
    assert events[-1] == Done("error")


def test_network_failure_yields_retryable_error():
    transport = ScriptedTransport(
        chunks=[
            sse("message_start", {"type": "message_start"}),
            sse("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "半"}}),
        ],
        fail_after=1,
    )

    events = run(transport)
    assert isinstance(events[0], StreamError)
    assert events[0].error.kind == "network"
    assert events[0].error.retryable is True
    assert events[-1] == Done("error")


def test_cancel_token_aborts_stream():
    cancel = CancelToken()
    transport = ScriptedTransport(chunks=[sse("message_start", {"type": "message_start"})])
    provider = AnthropicProvider(
        "https://api.example.com", "sk-test", transport=transport, cancel=cancel
    )
    cancel.cancel()

    events = asyncio.run(_collect(provider.stream(GenerateRequest(model="m", messages=[]))))
    assert events == [Done("aborted")]  # 取消发生在请求前：不发请求，直接以中止收尾
    assert transport.calls == []

    cancel2 = CancelToken()
    transport2 = ScriptedTransport(cancel_on_send=cancel2)
    provider2 = AnthropicProvider(
        "https://api.example.com", "sk-test", transport=transport2, cancel=cancel2
    )
    events2 = asyncio.run(_collect(provider2.stream(GenerateRequest(model="m", messages=[]))))
    assert events2 == [Done("aborted")]


def test_message_mapping_merges_roles_and_keeps_blocks():
    transport = text_stream("好")
    messages = [
        Message(role="user", content="读一下"),
        Message(role="assistant", content=[ToolUsePart(id="t1", name="read_file", input={"path": "a.txt"})]),
        Message(role="user", content=[ToolResultPart(toolUseId="t1", content="内容")]),
        Message(role="user", content=[TextPart(text="继续")]),
    ]
    provider = AnthropicProvider("https://api.example.com", "k", transport=transport)
    body = provider.build_body(GenerateRequest(model="m", messages=messages))

    roles = [m["role"] for m in body["messages"]]
    assert roles == ["user", "assistant", "user"]  # 连续两条 user 合并
    last_blocks = body["messages"][-1]["content"]
    assert [b["type"] for b in last_blocks] == ["tool_result", "text"]
    assert last_blocks[0]["tool_use_id"] == "t1"


def test_tool_result_with_images_becomes_block_array():
    transport = text_stream("好")
    provider = AnthropicProvider("https://api.example.com", "k", transport=transport)
    messages = [
        Message(
            role="user",
            content=[
                ToolResultPart(
                    toolUseId="t1",
                    content="图片如下",
                    images=[ImagePart(mediaType="image/png", data="AAAA")],
                )
            ],
        )
    ]
    body = provider.build_body(GenerateRequest(model="m", messages=messages))
    result_block = body["messages"][0]["content"][0]
    assert result_block["type"] == "tool_result"
    assert [b["type"] for b in result_block["content"]] == ["text", "image"]
    assert result_block["content"][1]["source"]["media_type"] == "image/png"


def test_unknown_stop_reason_falls_back_to_end_turn():
    transport = ScriptedTransport(
        chunks=[sse("message_delta", {"type": "message_delta", "delta": {"stop_reason": "wat"}})]
    )
    assert run(transport)[-1] == Done("end_turn")
