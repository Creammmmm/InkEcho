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
                json={"text": "你好", "choices": [{"message": {"content": "你好"}}]},
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
                {"text": "本地TLS", "choices": [{"message": {"content": "本地TLS"}}]}
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
    "adapter", ["multipart", "elevenlabs", "mimo-asr", "openrouter-asr"]
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
        else "chat/completions"
        if adapter == "mimo-asr"
        else "audio/transcriptions"
    )
    assert body
