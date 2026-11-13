"""OpenAI Responses API 适配器离线测试。

覆盖：`instructions` / 扁平工具声明 / `store:false`、input 拍平、函数调用按 item 累积、
`response.incomplete` 定性、`response.failed` 带内错误、拒绝与推理增量。
"""
from __future__ import annotations

import asyncio

from mvvm.models.chat_models import ImagePart, Message, TextPart, ToolResultPart, ToolUsePart
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
from mvvm.services.responses_provider import ResponsesProvider, map_input

from scripted_transport import ScriptedTransport, sse


async def _collect(stream):
    return [event async for event in stream]


def run(transport, **kwargs):
    request = GenerateRequest(model="gpt-5", messages=[Message(role="user", content="你好")], **kwargs)
    provider = ResponsesProvider("https://api.openai.com/v1", "sk-test", transport=transport)
    return asyncio.run(_collect(provider.stream(request)))


def function_call_events(call_id="call_1", name="read_file", args='{"path": "a.txt"}', done_args=None):
    return [
        sse(
            "response.output_item.added",
            {"type": "response.output_item.added", "item": {"id": "fc_1", "type": "function_call", "call_id": call_id, "name": name}},
        ),
        sse(
            "response.function_call_arguments.delta",
            {"type": "response.function_call_arguments.delta", "item_id": "fc_1", "delta": args[:5]},
        ),
        sse(
            "response.output_item.done",
            {
                "type": "response.output_item.done",
                "item": {
                    "id": "fc_1",
                    "type": "function_call",
                    "call_id": call_id,
                    "name": name,
                    "arguments": args if done_args is None else done_args,
                },
            },
        ),
    ]


def test_text_deltas_and_usage():
    transport = ScriptedTransport(
        chunks=[
            sse("response.output_text.delta", {"type": "response.output_text.delta", "delta": "你"}),
            sse("response.output_text.delta", {"type": "response.output_text.delta", "delta": "好"}),
            sse(
                "response.completed",
                {
                    "type": "response.completed",
                    "response": {
                        "usage": {
                            "input_tokens": 800,
                            "output_tokens": 12,
                            "input_tokens_details": {"cached_tokens": 600},
                        }
                    },
                },
            ),
        ]
    )

    events = run(transport)
    assert [e.text for e in events if isinstance(e, TextDelta)] == ["你", "好"]
    usage = next(e for e in events if isinstance(e, Usage))
    # input_tokens 已含缓存命中，不再相加
    assert usage.input_tokens == 800
    assert usage.cache_read == 600
    assert events[-1] == Done("end_turn")


def test_request_body_shape():
    transport = ScriptedTransport(chunks=[])
    run(
        transport,
        system="系统提示",
        tools=[{"name": "read_file", "description": "读", "inputSchema": {"type": "object"}}],
        max_tokens=4096,
        effort=EffortRequest(format="standard", effort="high"),
    )
    body = transport.last_body
    assert transport.calls[-1]["url"] == "https://api.openai.com/v1/responses"
    assert body["instructions"] == "系统提示"
    assert body["store"] is False
    assert body["stream"] is True
    assert body["max_output_tokens"] == 4096
    assert body["reasoning"] == {"effort": "high"}
    # Responses 的工具声明是扁平形状，不是 Chat 的 function 嵌套
    assert body["tools"][0]["type"] == "function"
    assert body["tools"][0]["name"] == "read_file"
    assert body["tools"][0]["strict"] is False
    assert "function" not in body["tools"][0]


def test_default_max_output_tokens():
    transport = ScriptedTransport(chunks=[])
    run(transport)
    assert transport.last_body["max_output_tokens"] == 8192


def test_function_call_becomes_tool_call():
    transport = ScriptedTransport(
        chunks=function_call_events()
        + [sse("response.completed", {"type": "response.completed", "response": {}})]
    )
    events = run(transport)
    calls = [e for e in events if isinstance(e, ToolCall)]
    assert len(calls) == 1
    assert calls[0].id == "call_1"
    assert calls[0].name == "read_file"
    assert calls[0].input == {"path": "a.txt"}
    assert events[-1] == Done("tool_use")


def test_function_call_arguments_done_event_is_authoritative():
    transport = ScriptedTransport(
        chunks=function_call_events(args='{"path": "a.txt"}', done_args='{"path": "b.txt"}')
    )
    calls = [e for e in run(transport) if isinstance(e, ToolCall)]
    assert calls[0].input == {"path": "b.txt"}


def test_incomplete_max_output_tokens_marks_truncation():
    transport = ScriptedTransport(
        chunks=function_call_events(args='{"path": "a', done_args='{"path": "a')
        + [
            sse(
                "response.incomplete",
                {
                    "type": "response.incomplete",
                    "response": {"incomplete_details": {"reason": "max_output_tokens"}},
                },
            )
        ]
    )
    events = run(transport)
    assert not [e for e in events if isinstance(e, ToolCall)]
    truncated = [e for e in events if isinstance(e, ToolCallTruncated)]
    assert truncated and truncated[0].cause == "max_tokens"
    assert events[-1] == Done("max_tokens")


def test_content_filter_maps_to_refusal():
    transport = ScriptedTransport(
        chunks=[
            sse(
                "response.incomplete",
                {
                    "type": "response.incomplete",
                    "response": {"incomplete_details": {"reason": "content_filter"}},
                },
            )
        ]
    )
    assert run(transport)[-1] == Done("refusal")


def test_response_failed_surfaces_error():
    transport = ScriptedTransport(
        chunks=[
            sse(
                "response.failed",
                {
                    "type": "response.failed",
                    "response": {"error": {"message": "upstream boom", "code": "server_error"}},
                },
            )
        ]
    )
    events = run(transport)
    assert isinstance(events[0], StreamError)
    assert "boom" in events[0].error.message
    assert events[-1] == Done("error")


def test_stream_error_event_surfaces():
    transport = ScriptedTransport(
        chunks=[sse("error", {"type": "error", "message": "context_length_exceeded"})]
    )
    events = run(transport)
    assert events[0].error.kind == "context_length"
    assert events[-1] == Done("error")


def test_refusal_and_reasoning_deltas():
    transport = ScriptedTransport(
        chunks=[
            sse("response.reasoning_text.delta", {"type": "response.reasoning_text.delta", "delta": "思考"}),
            sse("response.refusal.delta", {"type": "response.refusal.delta", "delta": "拒绝理由"}),
        ]
    )
    events = run(transport)
    assert [e.text for e in events if isinstance(e, ThinkingDelta)] == ["思考"]
    assert [e.text for e in events if isinstance(e, TextDelta)] == ["拒绝理由"]


def test_map_input_flattens_blocks():
    messages = [
        Message(role="user", content="问题"),
        Message(
            role="assistant",
            content=[TextPart(text="调用工具"), ToolUsePart(id="c1", name="glob", input={"pattern": "*.py"})],
        ),
        Message(
            role="user",
            content=[
                ToolResultPart(
                    toolUseId="c1",
                    content="结果",
                    images=[ImagePart(mediaType="image/png", data="AAAA", name="图表.png")],
                )
            ],
        ),
    ]
    mapped = map_input(messages)

    assert mapped[0]["content"][0] == {"type": "input_text", "text": "问题"}
    assert mapped[1]["content"][0] == {"type": "output_text", "text": "调用工具"}
    assert mapped[2]["type"] == "function_call"
    assert mapped[2]["call_id"] == "c1"
    assert mapped[2]["arguments"] == '{"pattern": "*.py"}'
    assert mapped[3] == {"type": "function_call_output", "call_id": "c1", "output": "结果"}
    # 工具结果里的图片挪到随后的 user 消息
    assert mapped[4]["role"] == "user"
    assert "图表.png" in mapped[4]["content"][0]["text"]
    assert mapped[4]["content"][1]["type"] == "input_image"


def test_cancel_before_request_sends_nothing():
    from mvvm.services.transport import CancelToken

    cancel = CancelToken()
    cancel.cancel()
    transport = ScriptedTransport(chunks=[])
    provider = ResponsesProvider("https://x.test", "k", transport=transport, cancel=cancel)
    events = asyncio.run(_collect(provider.stream(GenerateRequest(model="m", messages=[]))))
    assert transport.calls == []
    assert events == [Done("aborted")]
