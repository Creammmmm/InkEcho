"""Verify wire formats, bounded errors and no paid-request replay."""

import asyncio
import base64
import io
import json
import ssl
import threading
import wave
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from test_providers import certificate  # noqa: F401 - reuse the local test CA fixture

from inkecho.config import Provider
from inkecho.providers import ProviderClient, ProviderError


def audio():
    data = io.BytesIO()
    with wave.open(data, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"\0\0" * 1600)
    return data.getvalue()


def provider(adapter):
    return Provider(
        "fixture",
        "Fixture",
        "transcription",
        adapter,
        "https://localhost/v1",
        {
            "multipart": "whisper-1",
            "elevenlabs": "scribe_v2",
            "mimo-asr": "mimo-v2.5-asr",
            "openrouter-asr": "openai/whisper-1",
            "stepfun-http": "stepaudio-2.5-asr",
            "zhipu-asr": "glm-asr-2512",
            "minimax-asr": "asr-1.0",
            "zenmux-asr": "qwen/qwen3-asr-flash",
            "orca-audio": "google/gemini-2.5-pro",
        }[adapter],
    )


@pytest.mark.parametrize(
    "adapter", ["multipart", "elevenlabs", "mimo-asr", "openrouter-asr"]
)
def test_explicit_http_wire_format_and_single_post(adapter):
    async def scenario():
        requests = []

        async def handle(request):
            requests.append(request)
            data = await request.aread()
            if adapter == "mimo-asr":
                body = json.loads(data)
                assert request.url.path == "/v1/chat/completions"
                assert body["stream"] is False and body["asr_options"] == {}
                encoded = body["messages"][0]["content"][0]["input_audio"]["data"]
                assert base64.b64decode(encoded.split(",")[1]) == audio()
            elif adapter == "openrouter-asr":
                body = json.loads(data)
                assert request.url.path == "/v1/audio/transcriptions"
                assert body["input_audio"]["format"] == "wav"
                assert base64.b64decode(body["input_audio"]["data"]) == audio()
            else:
                assert request.headers["content-type"].startswith(
                    "multipart/form-data;"
                )
                assert audio() in data
                assert (
                    b'name="model_id"' if adapter == "elevenlabs" else b'name="model"'
                ) in data
                assert request.url.path == (
                    "/v1/speech-to-text"
                    if adapter == "elevenlabs"
                    else "/v1/audio/transcriptions"
                )
            if adapter == "elevenlabs":
                assert (
                    request.headers["xi-api-key"] == "synthetic-only"
                    and "authorization" not in request.headers
                )
            else:
                assert request.headers["authorization"] == "Bearer synthetic-only"
            return httpx.Response(
                200,
                json={
                    "text": "你好",
                    "choices": [
                        {"finish_reason": "stop", "message": {"content": "你好"}}
                    ],
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            async with ProviderClient(http=http) as client:
                result = await client.transcribe(
                    provider(adapter), "synthetic-only", audio()
                )
                assert result.text == "你好" and len(requests) == 1

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "status,code", [(429, "rate_limit"), (503, "unavailable"), (401, "authentication")]
)
def test_billable_error_is_not_retried(status, code):
    async def scenario():
        calls = []

        def handle(request):
            calls.append(request)
            return httpx.Response(status, json={})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            with pytest.raises(ProviderError) as caught:
                await ProviderClient(http=http).transcribe(
                    provider("multipart"), "synthetic-only", audio()
                )
            assert caught.value.code == code and len(calls) == 1

    asyncio.run(scenario())


def test_known_text_model_or_invalid_audio_is_rejected_before_network():
    async def scenario():
        def handle(_):
            pytest.fail("must not reach network")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            client = ProviderClient(http=http)
            item = replace(provider("multipart"), model="deepseek-chat")
            with pytest.raises(ProviderError) as caught:
                await client.transcribe(item, "synthetic-only", audio())
            assert caught.value.code == "protocol"
            with pytest.raises(ProviderError) as caught:
                await client.transcribe(
                    provider("elevenlabs"), "synthetic-only", b"not-wav"
                )
            assert caught.value.code == "audio"

    asyncio.run(scenario())


def test_timeout_and_cancel_stop_without_retry_or_closing_borrowed_http():
    async def scenario():
        entered = asyncio.Event()
        calls = []

        async def handle(request):
            calls.append(request)
            entered.set()
            await asyncio.Event().wait()

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            client = ProviderClient(http=http, timeout_seconds=0.05)
            with pytest.raises(ProviderError) as caught:
                await client.transcribe(
                    provider("multipart"), "synthetic-only", audio()
                )
            assert caught.value.code == "timeout" and len(calls) == 1
            entered.clear()
            task = asyncio.create_task(
                client.transcribe(provider("multipart"), "synthetic-only", audio())
            )
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert len(calls) == 2 and not http.is_closed

    asyncio.run(scenario())


@pytest.fixture
def tls_asr(request):
    local_ca = request.getfixturevalue("certificate")
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            seen.append((self.path, dict(self.headers), body))
            response = json.dumps(
                {
                    "text": "本地TLS",
                    "choices": [
                        {"finish_reason": "stop", "message": {"content": "本地TLS"}}
                    ],
                }
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(*local_ca)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield (
            f"https://127.0.0.1:{server.server_port}/v1",
            ssl.create_default_context(cafile=str(local_ca[0])),
            seen,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


@pytest.mark.parametrize(
    "adapter",
    [
        "multipart",
        "elevenlabs",
        "mimo-asr",
        "openrouter-asr",
        "stepfun-http",
        "zhipu-asr",
        "minimax-asr",
        "zenmux-asr",
        "orca-audio",
    ],
)
def test_actual_local_tls_upload_and_final_parse(tls_asr, adapter):
    endpoint, verify, seen = tls_asr

    async def scenario():
        async with httpx.AsyncClient(verify=verify, trust_env=False) as http:
            async with ProviderClient(http=http) as client:
                result = await client.transcribe(
                    replace(provider(adapter), base_url=endpoint),
                    "synthetic-only",
                    audio(),
                )
                assert result.text == "本地TLS"

    asyncio.run(scenario())
    assert len(seen) == 1
    path, headers, body = seen[0]
    assert headers.get("Authorization") == (
        None if adapter == "elevenlabs" else "Bearer synthetic-only"
    )
    assert headers.get("xi-api-key") == (
        "synthetic-only" if adapter == "elevenlabs" else None
    )
    assert path.endswith(
        "speech-to-text"
        if adapter == "elevenlabs"
        else "speech_to_text"
        if adapter == "minimax-asr"
        else "chat/completions"
        if adapter in {"mimo-asr", "orca-audio"}
        else "audio/transcriptions"
    )
    assert body
    if adapter in {"zenmux-asr", "openrouter-asr"}:
        payload = json.loads(body)
        assert payload["model"] == provider(adapter).model
        assert payload["input_audio"]["format"] == "wav"
        assert base64.b64decode(payload["input_audio"]["data"]) == audio()
        assert payload["response_format"] == "json"
    elif adapter in {"mimo-asr", "orca-audio"}:
        payload = json.loads(body)
        assert (
            payload["model"] == provider(adapter).model and payload["stream"] is False
        )
        content = payload["messages"][0]["content"]
        assert payload["messages"][0]["role"] == "user"
        if adapter == "orca-audio":
            assert "asr_options" not in payload
            assert len(content) == 2 and content[0]["type"] == "text"
            assert "transcript" in content[0]["text"]
            assert content[1]["type"] == "input_audio"
            assert content[1]["input_audio"]["format"] == "wav"
            assert base64.b64decode(content[1]["input_audio"]["data"]) == audio()
        else:
            assert len(content) == 1 and content[0]["type"] == "input_audio"
            assert (
                base64.b64decode(content[0]["input_audio"]["data"].split(",")[1])
                == audio()
            )
    else:
        from email.parser import BytesParser
        from email.policy import default

        message = BytesParser(policy=default).parsebytes(
            b"Content-Type: " + headers["Content-Type"].encode() + b"\r\n\r\n" + body
        )
        fields = {
            part.get_param("name", header="content-disposition"): part.get_payload(
                decode=True
            )
            for part in message.iter_parts()
        }
        assert fields["file"] == audio()
        assert (
            fields["model_id" if adapter == "elevenlabs" else "model"].decode()
            == provider(adapter).model
        )
        if adapter in {"zhipu-asr", "minimax-asr"}:
            assert fields["stream"] == b"false"
        if adapter != "elevenlabs" and adapter != "zhipu-asr":
            assert fields["response_format"] == b"json"


@pytest.mark.parametrize("adapter", ["mimo-asr", "orca-audio"])
@pytest.mark.parametrize(
    "choice",
    [
        None,
        [],
        {"finish_reason": "length", "message": {"content": "partial"}},
        {"finish_reason": "content_filter", "message": {"content": "partial"}},
        {"message": {"content": "missing finish"}},
        {"finish_reason": "stop", "message": None},
        {"finish_reason": "stop", "message": []},
        {"finish_reason": "stop", "message": {"content": "tool", "tool_calls": [{}]}},
    ],
)
def test_audio_chat_requires_complete_stop_and_well_formed_message(adapter, choice):
    async def scenario():
        def handle(_):
            return httpx.Response(200, json={"choices": [choice]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            with pytest.raises(ProviderError) as caught:
                await ProviderClient(http=http).transcribe(
                    provider(adapter), "synthetic-only", audio()
                )
            assert caught.value.code == "response"

    asyncio.run(scenario())


def test_zhipu_duration_limit_prevents_request():
    data = io.BytesIO()
    with wave.open(data, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"\0\0" * (16000 * 30 + 1))

    async def scenario():
        def handle(_):
            pytest.fail("overlong Zhipu audio must not upload")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as http:
            with pytest.raises(ProviderError) as caught:
                await ProviderClient(http=http).transcribe(
                    provider("zhipu-asr"), "synthetic-only", data.getvalue()
                )
            assert caught.value.code == "audio"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "adapter,parameters",
    [
        ("zhipu-asr", {"hotwords": ["词一", "词二"]}),
        ("stepfun-http", {"hotwords": '["词一","词二"]'}),
        ("minimax-asr", {"language": "zh-CN"}),
    ],
)
def test_actual_local_tls_vendor_form_controls(tls_asr, adapter, parameters):
    from email.parser import BytesParser
    from email.policy import default

    endpoint, verify, seen = tls_asr

    async def scenario():
        async with httpx.AsyncClient(verify=verify, trust_env=False) as http:
            await ProviderClient(http=http).transcribe(
                replace(provider(adapter), base_url=endpoint, parameters=parameters),
                "synthetic-only",
                audio(),
            )

    asyncio.run(scenario())
    _, headers, body = seen[0]
    message = BytesParser(policy=default).parsebytes(
        b"Content-Type: " + headers["Content-Type"].encode() + b"\r\n\r\n" + body
    )
    fields = [
        (
            part.get_param("name", header="content-disposition"),
            part.get_payload(decode=True),
        )
        for part in message.iter_parts()
    ]
    if adapter == "zhipu-asr":
        assert [v.decode() for k, v in fields if k == "hotwords[]"] == ["词一", "词二"]
        assert not any(k == "response_format" for k, _ in fields)
    elif adapter == "stepfun-http":
        assert json.loads(next(v for k, v in fields if k == "hotwords")) == [
            "词一",
            "词二",
        ]
    else:
        assert headers["language"] == "zh-CN" and not any(
            k == "language" for k, _ in fields
        )
    if adapter in {"zhipu-asr", "minimax-asr"}:
        assert next(v for k, v in fields if k == "stream") == b"false"


def test_zenmux_json_boolean_option_is_not_stringified(tls_asr):
    endpoint, verify, seen = tls_asr

    async def scenario():
        async with httpx.AsyncClient(verify=verify, trust_env=False) as http:
            await ProviderClient(http=http).transcribe(
                replace(
                    provider("zenmux-asr"),
                    base_url=endpoint,
                    parameters={"enable_itn": True},
                ),
                "synthetic-only",
                audio(),
            )

    asyncio.run(scenario())
    assert json.loads(seen[0][2])["enable_itn"] is True
