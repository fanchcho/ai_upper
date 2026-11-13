"""OpenAI Chat Completions 适配器离线测试。

覆盖：文本/思考/拒绝增量、tool_calls 按 index 拼接、`finish_reason` 映射、
输出上限字段按服务地址切换、带内错误块、残缺工具调用、用量（含缓存命中）、取消。
"""
from __future__ import annotations

import asyncio

from mvvm.models.chat_models import DocumentPart, ImagePart, Message, TextPart, ToolResultPart, ToolUsePart
from mvvm.services.effort import EffortRequest
from mvvm.services.openai_provider import OpenAIProvider, map_messages, output_limit_field
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

from scripted_transport import ScriptedTransport, openai_chunk, sse


async def _collect(stream):
    return [event async for event in stream]


def run(transport, base_url="https://api.deepseek.com", **kwargs):
    request = GenerateRequest(
        model="deepseek-v4", messages=[Message(role="user", content="你好")], **kwargs
    )
    provider = OpenAIProvider(base_url, "sk-test", transport=transport)
    return asyncio.run(_collect(provider.stream(request)))


def test_text_and_thinking_deltas():
    transport = ScriptedTransport(
        chunks=[
            sse(None, openai_chunk({"reasoning_content": "想一想"})),
            sse(None, openai_chunk({"content": "你"})),
            sse(None, openai_chunk({"content": "好"}, finish="stop")),
            sse(None, "[DONE]"),
        ]
    )

    events = run(transport)
    assert [e.text for e in events if isinstance(e, ThinkingDelta)] == ["想一想"]
    assert [e.text for e in events if isinstance(e, TextDelta)] == ["你", "好"]
    assert events[-1] == Done("end_turn")


def test_refusal_delta_shown_as_text():
    transport = ScriptedTransport(
        chunks=[sse(None, openai_chunk({"refusal": "这个我不能做"}, finish="stop")), sse(None, "[DONE]")]
    )
    events = run(transport)
    assert [e.text for e in events if isinstance(e, TextDelta)] == ["这个我不能做"]


def test_tool_calls_accumulated_and_flushed_on_tool_use():
    transport = ScriptedTransport(
        chunks=[
            sse(None, openai_chunk({"tool_calls": [{"index": 0, "id": "call_1", "function": {"name": "read_file", "arguments": '{"pa'}}]})),
            sse(None, openai_chunk({"tool_calls": [{"index": 0, "function": {"arguments": 'th": "a.txt"}'}}]})),
            sse(None, openai_chunk({}, finish="tool_calls")),
            sse(None, "[DONE]"),
        ]
    )

    events = run(transport)
    calls = [e for e in events if isinstance(e, ToolCall)]
    assert len(calls) == 1
    assert calls[0].id == "call_1"
    assert calls[0].name == "read_file"
    assert calls[0].input == {"path": "a.txt"}
    assert events[-1] == Done("tool_use")


def test_length_truncated_call_reported_as_truncated():
    transport = ScriptedTransport(
        chunks=[
            sse(None, openai_chunk({"tool_calls": [{"index": 0, "id": "call_1", "function": {"name": "write_file", "arguments": '{"path": "a'}}]})),
            sse(None, openai_chunk({}, finish="length")),
            sse(None, "[DONE]"),
        ]
    )

    events = run(transport)
    assert not [e for e in events if isinstance(e, ToolCall)]
    truncated = [e for e in events if isinstance(e, ToolCallTruncated)]
    assert len(truncated) == 1
    assert truncated[0].cause == "max_tokens"
    assert events[-1] == Done("max_tokens")


def test_leftover_calls_without_finish_reason_treated_as_tool_use():
    transport = ScriptedTransport(
        chunks=[
            sse(None, openai_chunk({"tool_calls": [{"index": 0, "id": "call_9", "function": {"name": "glob", "arguments": '{"pattern": "*.py"}'}}]}))
        ]
    )
    events = run(transport)
    assert [e.name for e in events if isinstance(e, ToolCall)] == ["glob"]
    assert events[-1] == Done("tool_use")


def test_usage_with_openai_cached_tokens():
    transport = ScriptedTransport(
        chunks=[
            sse(
                None,
                {
                    "choices": [],
                    "usage": {
                        "prompt_tokens": 500,
                        "completion_tokens": 20,
                        "prompt_tokens_details": {"cached_tokens": 300},
                    },
                },
            ),
            sse(None, "[DONE]"),
        ]
    )
    usage = next(e for e in run(transport) if isinstance(e, Usage))
    # prompt_tokens 本就是含命中的总量，不能再加
    assert usage.input_tokens == 500
    assert usage.output_tokens == 20
    assert usage.cache_read == 300


def test_usage_falls_back_to_deepseek_hit_miss():
    transport = ScriptedTransport(
        chunks=[
            sse(None, {"choices": [], "usage": {"prompt_cache_hit_tokens": 200, "prompt_cache_miss_tokens": 50}}),
            sse(None, "[DONE]"),
        ]
    )
    usage = next(e for e in run(transport) if isinstance(e, Usage))
    assert usage.input_tokens == 250
    assert usage.cache_read == 200


def test_inband_error_block_reported():
    transport = ScriptedTransport(
        chunks=[
            sse(None, {"error": {"message": "quota exceeded", "code": "insufficient_quota"}}),
            sse(None, "[DONE]"),
        ]
    )
    events = run(transport)
    assert isinstance(events[0], StreamError)
    assert "quota" in events[0].error.message
    assert events[-1] == Done("error")


def test_zero_turn_is_not_silently_empty():
    """HTTP 200 但一个事件都没有：必须留下 Done，由上层报「空回合」，不能假装有内容。"""
    events = run(ScriptedTransport(chunks=[]))
    assert events == [Done("end_turn")]


def test_network_error_mid_stream():
    transport = ScriptedTransport(
        chunks=[
            sse(None, openai_chunk({"content": "半"})),
            sse(None, openai_chunk({"content": "句"})),
        ],
        fail_after=1,
    )
    events = run(transport)
    assert [e.text for e in events if isinstance(e, TextDelta)] == ["半"]
    assert isinstance(events[-1], Done)
    assert any(isinstance(e, StreamError) and e.error.kind == "network" for e in events)


def test_http_400_context_length():
    transport = ScriptedTransport(
        status=400,
        chunks=[b'{"error":{"message":"This model\'s maximum context length is 8192 tokens"}}'],
    )
    events = run(transport)
    assert events[0].error.kind == "context_length"
    assert events[0].error.limit == 8192


def test_output_limit_field_per_host():
    assert output_limit_field("https://api.openai.com/v1") == "max_completion_tokens"
    assert output_limit_field("https://foo.openai.azure.com/") == "max_completion_tokens"
    assert output_limit_field("https://api.deepseek.com") == "max_tokens"
    assert output_limit_field("not a url") == "max_tokens"


def test_body_uses_max_completion_tokens_and_stream_options():
    transport = ScriptedTransport(chunks=[sse(None, "[DONE]")])
    run(transport, base_url="https://api.openai.com/v1", max_tokens=1234)
    body = transport.last_body
    assert body["max_completion_tokens"] == 1234
    assert "max_tokens" not in body
    assert body["stream_options"] == {"include_usage": True}
    assert body["stream"] is True


def test_thinking_fields_per_format():
    for level_format, expected in (
        ("deepseek", {"thinking": {"type": "enabled"}}),
        ("zai", {"thinking": {"type": "enabled", "clear_thinking": False}}),
        ("qwen", {"enable_thinking": True}),
    ):
        transport = ScriptedTransport(chunks=[sse(None, "[DONE]")])
        run(transport, effort=EffortRequest(format=level_format, effort="high"))
        body = transport.last_body
        for key, value in expected.items():
            assert body[key] == value
        assert body["reasoning_effort"] == "high"


def test_reasoning_field_added_to_assistant_history():
    transport = ScriptedTransport(chunks=[sse(None, "[DONE]")])
    request = GenerateRequest(
        model="deepseek-v4",
        messages=[
            Message(role="user", content="问"),
            Message(role="assistant", content="答"),
            Message(role="user", content="再问"),
        ],
        effort=EffortRequest(format="deepseek", effort="high", reasoning_field=True),
    )
    provider = OpenAIProvider("https://api.deepseek.com", "k", transport=transport)
    asyncio.run(_collect(provider.stream(request)))
    assistant = [m for m in transport.last_body["messages"] if m["role"] == "assistant"]
    assert assistant and assistant[0]["reasoning_content"] == ""


def test_message_mapping_splits_tool_results_and_moves_images():
    messages = [
        Message(role="user", content="读文件"),
        Message(
            role="assistant",
            content=[
                TextPart(text="我看一下"),
                ToolUsePart(id="t1", name="read_file", input={"path": "a.txt"}),
            ],
        ),
        Message(
            role="user",
            content=[
                ToolResultPart(
                    toolUseId="t1",
                    content="图片如下",
                    images=[ImagePart(mediaType="image/png", data="AAAA", name="shot.png")],
                )
            ],
        ),
    ]
    mapped = map_messages("系统提示", messages)

    assert mapped[0] == {"role": "system", "content": "系统提示"}
    assert mapped[1] == {"role": "user", "content": "读文件"}
    assistant = mapped[2]
    assert assistant["content"] == "我看一下"
    assert assistant["tool_calls"][0]["function"]["arguments"] == '{"path": "a.txt"}'
    tool_message = mapped[3]
    assert tool_message == {"role": "tool", "tool_call_id": "t1", "content": "图片如下"}
    # 图片只能挂到紧随其后的 user 消息
    follow = mapped[4]
    assert follow["role"] == "user"
    assert follow["content"][0]["type"] == "text"
    assert "shot.png" in follow["content"][0]["text"]
    assert follow["content"][1]["image_url"]["url"] == "data:image/png;base64,AAAA"


def test_document_downgraded_to_text_note():
    mapped = map_messages(
        None,
        [Message(role="user", content=[DocumentPart(mediaType="application/pdf", data="AAA", name="规范.pdf")])],
    )
    assert mapped[0]["role"] == "user"
    assert "规范.pdf" in mapped[0]["content"]


def test_cancel_before_request_sends_nothing():
    from mvvm.services.transport import CancelToken

    cancel = CancelToken()
    cancel.cancel()
    transport = ScriptedTransport(chunks=[])
    provider = OpenAIProvider("https://x.test", "k", transport=transport, cancel=cancel)
    events = asyncio.run(_collect(provider.stream(GenerateRequest(model="m", messages=[]))))
    assert transport.calls == []
    assert events == [Done("aborted")]
