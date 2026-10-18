"""Native families over actual local TLS; only final visible text is emitted."""

import asyncio
import json
import math
from dataclasses import replace

import pytest
from test_polish_stream import certificate as shared_certificate
from test_polish_stream import run
from test_polish_stream import server as shared_server

from inkecho.config import ConfigError
from inkecho.polish_protocols import NativeStream, request
from inkecho.provider_catalog import PRESETS
from inkecho.providers import ProviderError

certificate = shared_certificate
server = shared_server


def events(family):
    if family == "responses":
        values = [
            {
                "type": "response.created",
                "response": {"id": "r1", "status": "in_progress"},
            },
            {
                "type": "response.output_text.delta",
                "item_id": "i1",
                "output_index": 0,
                "content_index": 0,
                "delta": "你好",
            },
            {
                "type": "response.output_text.done",
                "item_id": "i1",
                "output_index": 0,
                "content_index": 0,
                "text": "你好",
            },
            {
                "type": "response.completed",
                "response": {**response(), "output": [response()["output"][1]]},
            },
        ]
        values[1:1] = [
            {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {
                    "id": "i1",
                    "type": "message",
                    "role": "assistant",
                    "status": "in_progress",
                    "content": [],
                },
            },
            {
                "type": "response.content_part.added",
                "output_index": 0,
                "content_index": 0,
                "item_id": "i1",
                "part": {"type": "output_text", "text": ""},
            },
        ]
        values[-1:-1] = [
            {
                "type": "response.content_part.done",
                "output_index": 0,
                "content_index": 0,
                "item_id": "i1",
                "part": {"type": "output_text", "text": "你好"},
            },
            {
                "type": "response.output_item.done",
                "output_index": 0,
                "item": response()["output"][1],
            },
        ]
        return [{**value, "sequence_number": n} for n, value in enumerate(values)]
    if family == "messages":
        return [
            {
                "type": "message_start",
                "message": {
                    "type": "message",
                    "id": "m1",
                    "role": "assistant",
                    "content": [],
                    "usage": {"input_tokens": 7, "output_tokens": 0},
                },
            },
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "thinking", "thinking": "private"},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "thinking_delta", "thinking": "never output"},
            },
            {"type": "content_block_stop", "index": 0},
            {
                "type": "content_block_start",
                "index": 1,
                "content_block": {"type": "text", "text": ""},
            },
            {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "text_delta", "text": "你好"},
            },
            {"type": "content_block_stop", "index": 1},
            {
                "type": "message_delta",
                "delta": {"stop_reason": "end_turn"},
                "usage": {"output_tokens": 2},
            },
            {"type": "message_stop"},
        ]
    return [
        {
            "candidates": [
                {
                    "index": 0,
                    "content": {
                        "role": "model",
                        "parts": [
                            {"text": "private", "thought": True},
                            {"text": "你好"},
                        ],
                    },
                }
            ]
        },
        {
            "candidates": [{"index": 0, "finishReason": "STOP"}],
            "usageMetadata": {
                "promptTokenCount": 7,
                "candidatesTokenCount": 2,
                "totalTokenCount": 9,
            },
        },
    ]


def response():
    return {
        "id": "r1",
        "status": "completed",
        "output": [
            {"type": "reasoning", "summary": [{"text": "never output"}]},
            {
                "type": "message",
                "id": "i1",
                "role": "assistant",
                "status": "completed",
                "content": [{"type": "output_text", "text": "你好"}],
            },
        ],
        "usage": {"input_tokens": 7, "output_tokens": 2, "total_tokens": 9},
    }


def nonstream(family):
    if family == "responses":
        return response()
    if family == "messages":
        return {
            "type": "message",
            "role": "assistant",
            "stop_reason": "end_turn",
            "content": [
                {"type": "thinking", "thinking": "private"},
                {"type": "text", "text": "你好"},
            ],
            "usage": {"input_tokens": 7, "output_tokens": 2},
        }
    return {
        "candidates": [
            {
                "index": 0,
                "finishReason": "STOP",
                "content": {
                    "role": "model",
                    "parts": [{"thought": True, "text": "private"}, {"text": "你好"}],
                },
            }
        ]
    }


def encode(value):
    return b"data: " + json.dumps(value, ensure_ascii=False).encode() + b"\n\n"


@pytest.mark.parametrize("family", ["responses", "messages", "gemini"])
@pytest.mark.parametrize("stream", [False, True])
def test_native_request_and_finality_over_actual_tls(server, family, stream):
    provider = replace(
        server.provider,
        adapter=family,
        model="models/gemini-test" if family == "gemini" else "test-model",
    )
    server.replies.append(
        {
            "type": "text/event-stream" if stream else "application/json",
            "steps": [(0, b"".join(map(encode, events(family))))]
            if stream
            else [(0, json.dumps(nonstream(family)).encode())],
        }
    )
    sent = []

    async def operation(client):
        async def emit(text):
            await asyncio.sleep(0)
            sent.append(text)

        if stream:
            result = await client.polish_stream(
                provider, "synthetic-key", "whole input", "custom instructions", emit
            )
        else:
            result = await client.polish(
                provider, "synthetic-key", "whole input", "custom instructions"
            )
        assert result.text == "你好"

    run(server, operation)
    item = server.requests[0]
    assert len(server.requests) == 1 and sent == (["你好"] if stream else [])
    body = item["body"]
    headers = {key.lower(): value for key, value in server.headers[0].items()}
    if family == "responses":
        assert item["path"] == "/v1/responses"
        assert body["store"] is False and body["instructions"] == "custom instructions"
        assert body["input"] == [
            {"role": "user", "content": [{"type": "input_text", "text": "whole input"}]}
        ]
        assert headers["authorization"] == "Bearer synthetic-key"
    elif family == "messages":
        assert (
            item["path"] == "/v1/messages" and body["system"] == "custom instructions"
        )
        assert body["messages"] == [{"role": "user", "content": "whole input"}]
        assert body["max_tokens"] == 2048
        assert (
            headers["x-api-key"] == "synthetic-key"
            and headers["anthropic-version"] == "2023-06-01"
        )
        assert "authorization" not in headers
    else:
        assert item["path"] == "/v1/models/gemini-test:" + (
            "streamGenerateContent?alt=sse" if stream else "generateContent"
        )
        assert (
            headers["x-goog-api-key"] == "synthetic-key"
            and "authorization" not in headers
        )
        assert body["systemInstruction"] == {"parts": [{"text": "custom instructions"}]}
        assert body["contents"] == [
            {"role": "user", "parts": [{"text": "whole input"}]}
        ]


@pytest.mark.parametrize("family", ["responses", "messages", "gemini"])
@pytest.mark.parametrize("failure", ["eof", "error", "truncated"])
def test_native_partial_failure_never_replays(server, family, failure):
    values = events(family)
    if failure == "eof":
        values = values[:-1]
    elif failure == "error":
        values = values[:-1] + [{"error": {"message": "synthetic"}}]
    elif family == "responses":
        values[-1]["response"]["status"] = "incomplete"
    elif family == "messages":
        values[-2]["delta"]["stop_reason"] = "max_tokens"
    else:
        values[-1]["candidates"][0]["finishReason"] = "MAX_TOKENS"
    server.replies.append({"steps": [(0, b"".join(map(encode, values)))]})
    provider = replace(server.provider, adapter=family)
    sent = []

    async def operation(client):
        async def emit(text):
            sent.append(text)

        with pytest.raises(ProviderError):
            await client.polish_stream(
                provider, "synthetic-key", "input", "prompt", emit
            )

    run(server, operation)
    assert sent == ["你好"] and len(server.requests) == 1


@pytest.mark.parametrize(
    "model",
    [
        "../escape",
        "models/../escape",
        "model?key=bad",
        "models/models/gemini",
        "x#fragment",
        "https://host/x",
    ],
)
def test_gemini_model_cannot_escape_selected_origin(server, model):
    with pytest.raises(ProviderError) as caught:
        request(
            replace(server.provider, adapter="gemini", model=model),
            "key",
            "input",
            "prompt",
        )
    assert caught.value.code == "configuration"


@pytest.mark.parametrize(
    "kind",
    ["unregistered", "reasoning", "function_call", "refusal", "wrong_id", "wrong_part"],
)
def test_responses_binds_output_before_delivery(kind):
    state = NativeStream("responses")
    state.receive(json.dumps(events("responses")[0]))
    values = events("responses")
    if kind == "unregistered":
        with pytest.raises(ProviderError):
            state.receive(
                json.dumps(
                    {
                        "type": "response.output_text.delta",
                        "sequence_number": 1,
                        "item_id": "never_registered",
                        "output_index": 0,
                        "content_index": 0,
                        "delta": "must not deliver",
                    }
                )
            )
    elif kind in {"function_call", "refusal"}:
        event = values[1]
        event["item"]["type"] = kind
        with pytest.raises(ProviderError):
            state.receive(json.dumps(event))
    elif kind == "reasoning":
        event = values[1]
        event["item"]["type"] = "reasoning"
        state.receive(json.dumps(event))
        with pytest.raises(ProviderError):
            state.receive(json.dumps(values[2]))
    else:
        state.receive(json.dumps(values[1]))
        state.receive(json.dumps(values[2]))
        event = values[3]
        event["item_id" if kind == "wrong_id" else "content_index"] = (
            "wrong" if kind == "wrong_id" else 1
        )
        with pytest.raises(ProviderError):
            state.receive(json.dumps(event))
    assert not state.parts


@pytest.mark.parametrize("family", ["responses", "messages", "gemini"])
def test_native_discovery_headers_and_protocol_models(server, family):
    value = {"data": [{"id": "text-model"}]}
    if family == "gemini":
        value = {
            "models": [
                {
                    "name": "models/text-model",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {
                    "name": "models/embedding-only",
                    "supportedGenerationMethods": ["embedContent"],
                },
            ]
        }
    server.replies.append(
        {"type": "application/json", "steps": [(0, json.dumps(value).encode())]}
    )

    async def operation(client):
        result = await client.models(
            replace(server.provider, adapter=family), "synthetic-key"
        )
        assert result == (
            ["models/text-model"] if family == "gemini" else ["text-model"]
        )

    run(server, operation)
    assert server.requests[0]["path"] == "/v1/models"
    headers = {key.lower(): value for key, value in server.headers[0].items()}
    if family == "messages":
        assert (
            headers["x-api-key"] == "synthetic-key" and "authorization" not in headers
        )
    if family == "gemini":
        assert (
            headers["x-goog-api-key"] == "synthetic-key"
            and "authorization" not in headers
        )


@pytest.mark.parametrize("value", [[], {}, None, True, 7])
@pytest.mark.parametrize("family", ["responses", "messages"])
def test_native_bad_event_type_is_sanitized(family, value):
    state = NativeStream(family)
    with pytest.raises(ProviderError) as caught:
        state.receive(json.dumps({"type": value}))
    assert caught.value.code == "response" and not state.parts


@pytest.mark.parametrize(
    "mode", ["index_gap", "overlap", "after_end", "usage_type", "multiple_delta"]
)
def test_messages_block_order_and_cumulative_usage_over_tls(server, mode):
    values = events("messages")
    expected = "response"
    if mode == "index_gap":
        values[1]["index"] = 1
    elif mode == "overlap":
        del values[3]
    elif mode == "after_end":
        values.insert(
            -1,
            {
                "type": "content_block_start",
                "index": 2,
                "content_block": {"type": "text", "text": "late"},
            },
        )
    elif mode == "usage_type":
        values[0]["message"]["usage"] = "bad"
    else:
        values.insert(
            -2,
            {
                "type": "message_delta",
                "delta": {"stop_reason": None},
                "usage": {"output_tokens": 1},
            },
        )
        expected = None
    server.replies.append({"steps": [(0, b"".join(map(encode, values)))]})

    async def operation(client):
        async def emit(_text):
            return None

        if expected:
            with pytest.raises(ProviderError) as caught:
                await client.polish_stream(
                    replace(server.provider, adapter="messages"),
                    "key",
                    "input",
                    "prompt",
                    emit,
                )
            assert caught.value.code == expected
        else:
            result = await client.polish_stream(
                replace(server.provider, adapter="messages"),
                "key",
                "input",
                "prompt",
                emit,
            )
            assert result.text == "你好" and result.usage.output_tokens == 2

    run(server, operation)


@pytest.mark.parametrize("family", ["responses", "messages", "gemini"])
def test_native_callback_cancel_keeps_prefix_without_retry(server, family):
    server.replies.append({"steps": [(0, b"".join(map(encode, events(family))))]})
    sent = []

    async def operation(client):
        async def emit(text):
            sent.append(text)
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await client.polish_stream(
                replace(server.provider, adapter=family), "key", "input", "prompt", emit
            )

    run(server, operation)
    assert sent == ["你好"] and len(server.requests) == 1


@pytest.mark.parametrize("family", ["responses", "messages", "gemini"])
@pytest.mark.parametrize("value", [True, "1", None, float("nan"), float("inf")])
def test_native_numeric_controls_reject_bad_types_before_network(server, family, value):
    if isinstance(value, float) and not math.isfinite(value):
        with pytest.raises(ConfigError):
            replace(server.provider, adapter=family, parameters={"temperature": value})
        return
    provider = replace(
        server.provider, adapter=family, parameters={"temperature": value}
    )
    with pytest.raises(ProviderError) as caught:
        request(provider, "key", "input", "prompt")
    assert caught.value.code == "configuration" and not server.requests


@pytest.mark.parametrize("family", ["responses", "messages", "gemini"])
def test_native_first_text_precedes_final_response_and_timeout_keeps_prefix(
    server, family
):
    values = events(family)
    split = next(
        index + 1
        for index, value in enumerate(values)
        if (
            value.get("type") in {"response.output_text.delta", "content_block_delta"}
            and (
                value.get("delta", {}).get("type") == "text_delta"
                if isinstance(value.get("delta"), dict)
                else True
            )
        )
        or family == "gemini"
    )
    server.replies.append(
        {
            "steps": [
                (0, b"".join(map(encode, values[:split]))),
                (0.2, b"".join(map(encode, values[split:]))),
            ]
        }
    )
    seen = []

    async def operation(client):
        async def emit(text):
            seen.append((text, server.completed))
            await asyncio.sleep(0.01)

        with pytest.raises(ProviderError) as caught:
            await client.polish_stream(
                replace(server.provider, adapter=family), "key", "input", "prompt", emit
            )
        assert caught.value.code == "timeout"

    run(server, operation, timeout=0.1)
    assert seen == [("你好", False)] and len(server.requests) == 1


@pytest.mark.parametrize("family", ["responses", "messages", "gemini"])
def test_native_nonstream_text_limit(server, family):
    value = nonstream(family)
    huge = "x" * 200001
    if family == "responses":
        value["output"][1]["content"][0]["text"] = huge
    elif family == "messages":
        value["content"][1]["text"] = huge
    else:
        value["candidates"][0]["content"]["parts"][1]["text"] = huge
    server.replies.append(
        {"type": "application/json", "steps": [(0, json.dumps(value).encode())]}
    )

    async def operation(client):
        with pytest.raises(ProviderError) as caught:
            await client.polish(
                replace(server.provider, adapter=family), "key", "input", "prompt"
            )
        assert caught.value.code == "response"

    run(server, operation)
    assert len(server.requests) == 1


@pytest.mark.parametrize(
    "field,value", [("type", []), ("type", {}), ("usage", "bad"), ("usage", [1])]
)
def test_messages_bad_start_fields_are_sanitized(field, value):
    state = NativeStream("messages")
    item = events("messages")[0]
    item["message"][field] = value
    with pytest.raises(ProviderError) as caught:
        state.receive(json.dumps(item))
    assert caught.value.code == "response"


@pytest.mark.parametrize("kind", [[], {}, None, 7])
def test_messages_bad_block_type_is_sanitized(kind):
    state = NativeStream("messages")
    state.receive(json.dumps(events("messages")[0]))
    with pytest.raises(ProviderError) as caught:
        state.receive(
            json.dumps(
                {
                    "type": "content_block_start",
                    "index": 0,
                    "content_block": {"type": kind},
                }
            )
        )
    assert caught.value.code == "response"


@pytest.mark.parametrize("methods", [None, "generateContent", {}, [None]])
def test_gemini_discovery_invalid_capability_type_is_sanitized(server, methods):
    server.replies.append(
        {
            "type": "application/json",
            "steps": [
                (
                    0,
                    json.dumps(
                        {
                            "models": [
                                {
                                    "name": "models/x",
                                    "supportedGenerationMethods": methods,
                                }
                            ]
                        }
                    ).encode(),
                )
            ],
        }
    )

    async def operation(client):
        with pytest.raises(ProviderError) as caught:
            await client.models(replace(server.provider, adapter="gemini"), "key")
        assert caught.value.code == "response"

    run(server, operation)


@pytest.mark.parametrize("family", ["messages", "gemini"])
def test_native_model_pagination_does_not_expose_keys(server, family):
    if family == "messages":
        pages = [
            {"data": [{"id": "first"}], "has_more": True, "last_id": "cursor"},
            {"data": [{"id": "second"}], "has_more": False},
        ]
    else:
        pages = [
            {
                "models": [
                    {
                        "name": "models/first",
                        "supportedGenerationMethods": ["generateContent"],
                    }
                ],
                "nextPageToken": "cursor",
            },
            {
                "models": [
                    {
                        "name": "models/second",
                        "supportedGenerationMethods": ["generateContent"],
                    }
                ]
            },
        ]
    for value in pages:
        server.replies.append(
            {"type": "application/json", "steps": [(0, json.dumps(value).encode())]}
        )

    async def operation(client):
        result = await client.models(
            replace(server.provider, adapter=family), "synthetic-key"
        )
        assert len(result) == 2

    run(server, operation)
    assert len(server.requests) == 2
    assert server.requests[1]["path"] == "/v1/models?" + (
        "after_id=cursor" if family == "messages" else "pageToken=cursor"
    )
    assert all("synthetic-key" not in item["path"] for item in server.requests)


@pytest.mark.parametrize(
    "preset",
    [item for item in PRESETS if item.role == "polishing" and item.adapter == "openai"],
    ids=lambda item: item.id,
)
def test_chat_vendor_presets_use_explicit_chat_wire(server, preset):
    from test_polish_stream import DONE, STOP, event

    server.replies.append({"steps": [(0, event("你好") + STOP + DONE)]})
    provider = replace(server.provider, adapter=preset.adapter, name=preset.label)

    async def operation(client):
        async def emit(_text):
            return None

        result = await client.polish_stream(
            provider, "synthetic-key", "input", "custom prompt", emit
        )
        assert result.text == "你好"

    run(server, operation)
    item = server.requests[0]
    assert item["path"] == "/v1/chat/completions"
    assert item["body"]["messages"] == [
        {"role": "system", "content": "custom prompt"},
        {"role": "user", "content": "input"},
    ]
    assert item["authorization"] == "Bearer synthetic-key"


def test_responses_interleaved_output_items_fail_before_second_delivery(server):
    values = events("responses")[:4]
    values.append(
        {
            "type": "response.output_item.added",
            "sequence_number": 4,
            "output_index": 1,
            "item": {
                "id": "i2",
                "type": "message",
                "role": "assistant",
                "status": "in_progress",
                "content": [],
            },
        }
    )
    values.append(
        {
            "type": "response.output_text.delta",
            "sequence_number": 5,
            "output_index": 1,
            "content_index": 0,
            "item_id": "i2",
            "delta": "must not deliver",
        }
    )
    server.replies.append({"steps": [(0, b"".join(map(encode, values)))]})
    sent = []

    async def operation(client):
        async def emit(text):
            sent.append(text)

        with pytest.raises(ProviderError) as caught:
            await client.polish_stream(
                replace(server.provider, adapter="responses"),
                "key",
                "input",
                "prompt",
                emit,
            )
        assert caught.value.code == "response"

    run(server, operation)
    assert sent == ["你好"]


@pytest.mark.parametrize("token", [None, "", [], 7])
def test_messages_missing_required_pagination_token_is_not_success(server, token):
    value = {"data": [{"id": "first"}], "has_more": True, "last_id": token}
    server.replies.append(
        {"type": "application/json", "steps": [(0, json.dumps(value).encode())]}
    )

    async def operation(client):
        with pytest.raises(ProviderError) as caught:
            await client.models(replace(server.provider, adapter="messages"), "key")
        assert caught.value.code == "response"

    run(server, operation)
    assert len(server.requests) == 1


@pytest.mark.parametrize("mode", ["unregistered", "wrong_item", "part_gap"])
def test_responses_bad_binding_over_tls_never_calls_delivery(server, mode):
    values = events("responses")[:4]
    if mode == "unregistered":
        values = [values[0], {**values[3], "sequence_number": 1}]
    elif mode == "wrong_item":
        values[-1]["item_id"] = "not-registered"
    else:
        values[2]["content_index"] = 1
    server.replies.append({"steps": [(0, b"".join(map(encode, values)))]})
    sent = []

    async def operation(client):
        async def emit(text):
            sent.append(text)

        with pytest.raises(ProviderError) as caught:
            await client.polish_stream(
                replace(server.provider, adapter="responses"),
                "key",
                "input",
                "prompt",
                emit,
            )
        assert caught.value.code == "response"

    run(server, operation)
    assert sent == []
