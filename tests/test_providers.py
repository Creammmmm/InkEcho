"""Real local HTTPS requests with simulated providers, never vendor credentials."""

import asyncio
import base64
import io
import json
import ssl
import subprocess
import threading
import time
import wave
from collections import deque
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

import httpx
import pytest

from inkecho.config import Provider
from inkecho.providers import ProviderClient, ProviderError

REPLY = {"choices": [{"message": {"content": "你好，world!"}}]}


@pytest.fixture(scope="module")
def certificate(tmp_path_factory):
    path = tmp_path_factory.mktemp("provider-tls")
    cert, key = path / "certificate.pem", path / "private.pem"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=IP:127.0.0.1,DNS:localhost",
        ],
        check=True,
        capture_output=True,
    )
    return cert, key


@pytest.fixture
def server(certificate):
    state = SimpleNamespace(requests=[], responses=deque())

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            state.requests.append(
                {
                    "method": self.command,
                    "path": self.path,
                    "authorization": self.headers.get("Authorization"),
                    "sse": self.headers.get("X-DashScope-SSE"),
                    "body": json.loads(body) if body else None,
                }
            )
            response = state.responses.popleft() if state.responses else {}
            time.sleep(response.get("delay", 0))
            data = response.get("body", REPLY)
            encoded = data if isinstance(data, bytes) else json.dumps(data).encode()
            try:
                self.send_response(response.get("status", 200))
                self.send_header("Content-Length", str(len(encoded)))
                for name, value in response.get("headers", {}).items():
                    self.send_header(name, value)
                self.end_headers()
                self.wfile.write(encoded)
            except (BrokenPipeError, ConnectionResetError, ssl.SSLError):
                pass  # Expected when the client cancels a deliberately delayed reply.

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(*certificate)
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    worker = threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.02))
    worker.start()
    state.context = ssl.create_default_context(cafile=str(certificate[0]))
    state.provider = Provider(
        "test",
        "Local test",
        "transcription",
        "qwen",
        f"https://127.0.0.1:{httpd.server_port}/v1",
        "editable-test-model",
        "test-ref",
    )
    yield state
    httpd.shutdown()
    worker.join()
    httpd.server_close()


def wav():
    output = io.BytesIO()
    with wave.open(output, "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(16000)
        recording.writeframes(b"\x00\x00" * 160)
    return output.getvalue()


def run(server, operation, *, timeout=2):
    async def execute():
        async with httpx.AsyncClient(verify=server.context, trust_env=False) as http:
            return await operation(ProviderClient(http=http, timeout_seconds=timeout))

    return asyncio.run(execute())


def test_qwen_actual_https_body_and_auth(server):
    provider = replace(
        server.provider, parameters={"asr_options": {"enable_itn": False}}
    )
    result = run(server, lambda client: client.transcribe(provider, "test-key", wav()))
    request = server.requests[0]
    assert request["authorization"] == "Bearer test-key"
    assert request["path"] == "/v1/chat/completions"
    assert request["body"]["model"] == "editable-test-model"
    content = request["body"]["messages"][0]["content"][0]
    assert content["type"] == "input_audio"
    data = content["input_audio"]["data"]
    assert data.startswith("data:audio/wav;base64,")
    assert base64.b64decode(data.split(",")[1]) == wav()
    assert request["body"]["asr_options"] == {"enable_itn": False}
    assert request["body"]["stream"] is False
    assert result.text == "你好，world!" and result.seconds >= 0
    assert result.usage.total_tokens is None and result.text not in repr(result)


def test_polishing_protocol_and_exact_usage(server):
    provider = replace(server.provider, role="polishing", adapter="openai")
    server.responses.append(
        {
            "body": {
                **REPLY,
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 7,
                    "total_tokens": 19,
                },
            }
        }
    )
    result = run(
        server, lambda client: client.polish(provider, "test-key", "draft", "polish")
    )
    assert server.requests[0]["body"]["messages"] == [
        {"role": "system", "content": "polish"},
        {"role": "user", "content": "draft"},
    ]
    assert (
        result.usage.input_tokens,
        result.usage.output_tokens,
        result.usage.total_tokens,
    ) == (12, 7, 19)


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "authentication"),
        (403, "authentication"),
        (429, "rate_limit"),
        (400, "model"),
        (404, "model"),
        (500, "unavailable"),
        (503, "unavailable"),
    ],
)
def test_http_failures_sanitized_and_post_never_retried(server, status, code):
    server.responses.append(
        {"status": status, "body": {"error": "test-key private-text"}}
    )
    with pytest.raises(ProviderError) as caught:
        run(
            server, lambda client: client.transcribe(server.provider, "test-key", wav())
        )
    assert caught.value.code == code
    assert "test-key" not in str(caught.value) and "private-text" not in str(
        caught.value
    )
    assert len(server.requests) == 1


@pytest.mark.parametrize(
    "body,code",
    [
        (b"not json test-key", "response"),
        ([], "response"),
        ({}, "response"),
        ({"choices": [{"message": {"content": " \n"}}]}, "empty"),
        ({"choices": [{"message": {"content": []}}]}, "response"),
        ({"error": "private body"}, "response"),
    ],
)
def test_invalid_or_empty_result(server, body, code):
    server.responses.append({"body": body})
    with pytest.raises(ProviderError) as caught:
        run(
            server, lambda client: client.transcribe(server.provider, "test-key", wav())
        )
    assert caught.value.code == code


def test_missing_usage_is_not_fabricated(server):
    server.responses.append(
        {
            "body": {
                **REPLY,
                "usage": {
                    "prompt_tokens": True,
                    "completion_tokens": -1,
                    "total_tokens": "7",
                },
            }
        }
    )
    result = run(
        server, lambda client: client.transcribe(server.provider, "test-key", wav())
    )
    assert result.usage.input_tokens is None
    assert result.usage.output_tokens is None and result.usage.total_tokens is None


def test_model_discovery_is_not_capability_validation(server):
    server.responses.append({"body": {"data": [{"id": "a"}, {"id": "b"}, {"id": "a"}]}})
    connection = run(
        server, lambda client: client.check_connection(server.provider, "test-key")
    )
    assert connection.models == ("a", "b") and not connection.capability_verified
    assert server.requests[0]["method"] == "GET"
    assert server.requests[0]["path"] == "/v1/models"
    result = run(
        server,
        lambda client: client.test_capability(server.provider, "test-key", audio=wav()),
    )
    assert result.text and server.requests[-1]["method"] == "POST"


def test_only_discovery_retries_once(server):
    server.responses.extend([{"status": 503}, {"status": 503}, {}])
    with pytest.raises(ProviderError) as caught:
        run(server, lambda client: client.models(server.provider, "test-key"))
    assert caught.value.code == "unavailable" and len(server.requests) == 2


def test_timeout_is_bounded_and_sanitized(server):
    server.responses.append({"delay": 0.3})
    with pytest.raises(ProviderError) as caught:
        run(
            server,
            lambda client: client.transcribe(server.provider, "test-key", wav()),
            timeout=0.08,
        )
    assert caught.value.code == "timeout"


def test_cancellation_propagates_without_late_result(server):
    server.responses.append({"delay": 0.3})

    async def cancel(client):
        task = asyncio.create_task(
            client.transcribe(server.provider, "test-key", wav())
        )
        while not server.requests:
            await asyncio.sleep(0.005)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(server, cancel)
    assert len(server.requests) == 1


def test_redirect_does_not_forward_credentials(server):
    server.responses.append({"status": 302, "headers": {"Location": "/leak"}})
    with pytest.raises(ProviderError) as caught:
        run(
            server, lambda client: client.transcribe(server.provider, "test-key", wav())
        )
    assert caught.value.code == "response" and len(server.requests) == 1


def test_response_size_bound(server):
    server.responses.append({"body": b"x" * 2_000_001})
    with pytest.raises(ProviderError) as caught:
        run(
            server, lambda client: client.transcribe(server.provider, "test-key", wav())
        )
    assert caught.value.code == "response"


def test_untrusted_tls_is_rejected(server):
    with pytest.raises(ProviderError) as caught:
        asyncio.run(ProviderClient().transcribe(server.provider, "test-key", wav()))
    assert caught.value.code == "network" and not server.requests


@pytest.mark.parametrize(
    "change,code",
    [
        ({"model": ""}, "configuration"),
        ({"parameters": {"stream": True}}, "configuration"),
        ({"adapter": "unsupported"}, "configuration"),
    ],
)
def test_invalid_provider_configuration_never_calls_network(server, change, code):
    with pytest.raises(ProviderError) as caught:
        run(
            server,
            lambda client: client.transcribe(
                replace(server.provider, **change), "test-key", wav()
            ),
        )
    assert caught.value.code == code and not server.requests


@pytest.mark.parametrize("data", [b"", b"not wav", b"x" * 7_499_971])
def test_invalid_audio_never_calls_network(server, data):
    with pytest.raises(ProviderError) as caught:
        run(server, lambda client: client.transcribe(server.provider, "test-key", data))
    assert caught.value.code == "audio" and not server.requests


def test_truncated_wav_never_calls_network(server):
    with pytest.raises(ProviderError) as caught:
        run(
            server,
            lambda client: client.transcribe(server.provider, "test-key", wav()[:-2]),
        )
    assert caught.value.code == "audio" and not server.requests


@pytest.mark.parametrize("key", ["", " ", "bad\nheader"])
def test_missing_or_invalid_key_never_calls_network(server, key):
    with pytest.raises(ProviderError) as caught:
        run(server, lambda client: client.transcribe(server.provider, key, wav()))
    assert caught.value.code == "credentials" and not server.requests


@pytest.mark.parametrize(
    "model",
    [
        "qwen3-asr-flash-realtime",
        "qwen3-asr-flash-realtime-2026-02-10",
        "qwen-audio-3.1-asr-flash-streaming",
        "qwen3-asr-flash-filetrans",
        "qwen3-asr-flash-filetrans-2025-11-17",
        " QWEN3-ASR-FLASH-REALTIME ",
        "fun-asr-flash-8k-realtime-2026-01-28",
    ],
)
def test_incompatible_protocol_never_encodes_or_uploads_audio(
    server, model, monkeypatch
):
    provider = replace(server.provider, model=model)

    def unexpected_encode(_audio):
        raise AssertionError("An incompatible model must not encode audio")

    monkeypatch.setattr(base64, "b64encode", unexpected_encode)
    with pytest.raises(ProviderError) as caught:
        run(server, lambda client: client.transcribe(provider, "test-key", wav()))
    assert caught.value.code == "protocol"
    assert server.requests == []
    assert model not in str(caught.value) and "test-key" not in str(caught.value)


def test_capability_protocol_is_checked_before_audio_is_required(server):
    provider = replace(server.provider, model="qwen3-asr-flash-realtime")
    with pytest.raises(ProviderError) as caught:
        run(server, lambda client: client.test_capability(provider, "test-key"))
    assert caught.value.code == "protocol"
    assert server.requests == []


@pytest.mark.parametrize("model", ["qwen3-asr-flash", "future-vendor-audio-model-v7"])
def test_protocol_guard_keeps_http_model_ids_editable(server, model):
    provider = replace(server.provider, model=model)
    result = run(server, lambda client: client.transcribe(provider, "test-key", wav()))
    assert result.text == "你好，world!"
    assert server.requests[0]["body"]["model"] == model


def test_discovery_still_lists_incompatible_protocol_models(server):
    provider = replace(server.provider, model="qwen3-asr-flash-realtime")
    server.responses.append({"body": {"data": [{"id": "qwen3-asr-flash-realtime"}]}})
    connection = run(
        server, lambda client: client.check_connection(provider, "test-key")
    )
    assert connection.models == ("qwen3-asr-flash-realtime",)
    assert not connection.capability_verified


@pytest.mark.parametrize(
    "model",
    [
        "qwen-audio-3.0-asr-flash",
        "qwen-audio-3.1-asr-flash",
        "fun-asr-flash-2026-06-15",
    ],
)
def test_dashscope_sync_audio_uses_correct_endpoint_payload_and_headers(server, model):
    provider = replace(
        server.provider,
        model=model,
        base_url=server.provider.base_url.removesuffix("/v1")
        + "/proxy/compatible-mode/v1",
        parameters={"language_hints": ["zh"]},
    )
    server.responses.append({"body": {"output": {"text": "语音识别成功。"}}})
    result = run(server, lambda client: client.transcribe(provider, "test-key", wav()))
    request = server.requests[0]
    assert (
        request["path"]
        == "/proxy/api/v1/services/aigc/multimodal-generation/generation"
    )
    assert request["authorization"] == "Bearer test-key"
    assert request["sse"] == "disable"
    body = request["body"]
    assert body["model"] == model
    assert "messages" not in body and "stream" not in body
    assert body["parameters"] == {
        "format": "wav",
        "sample_rate": "16000",
        "language_hints": ["zh"],
    }
    content = body["input"]["messages"][0]["content"][0]
    assert content["type"] == "input_audio"
    assert base64.b64decode(content["input_audio"]["data"].split(",")[1]) == wav()
    assert result.text == "语音识别成功。"
    assert result.usage.total_tokens is None
    assert provider.base_url.endswith("/proxy/compatible-mode/v1")


@pytest.mark.parametrize(
    "output",
    [
        {"output": {"sentence": {"text": "嵌套结果"}}},
        {"sentence": {"text": "嵌套结果"}},
        {"text": "", "output": {"sentence": {"text": "嵌套结果"}}},
    ],
)
def test_dashscope_nested_sentence_and_usage_are_parsed(server, output):
    provider = replace(
        server.provider,
        model="qwen-audio-3.0-asr-flash",
        base_url=server.provider.base_url.removesuffix("/v1") + "/api/v1",
    )
    server.responses.append(
        {
            "body": {
                "output": output,
                "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5},
            }
        }
    )
    result = run(server, lambda client: client.transcribe(provider, "test-key", wav()))
    assert result.text == "嵌套结果"
    assert result.usage.input_tokens == 2 and result.usage.output_tokens == 3
    assert result.usage.total_tokens == 5


@pytest.mark.parametrize(
    "body,code",
    [
        ({}, "response"),
        ({"output": []}, "response"),
        ({"output": {"text": 42}}, "response"),
        ({"output": {"text": "  "}}, "empty"),
    ],
)
def test_dashscope_empty_and_malformed_outputs_are_rejected(server, body, code):
    provider = replace(
        server.provider,
        model="qwen-audio-3.0-asr-flash",
        base_url=server.provider.base_url.removesuffix("/v1") + "/api/v1",
    )
    server.responses.append({"body": body})
    with pytest.raises(ProviderError) as caught:
        run(server, lambda client: client.transcribe(provider, "test-key", wav()))
    assert caught.value.code == code


@pytest.mark.parametrize(
    "base_url",
    [
        "https://example.invalid/v1",
        "https://example.invalid/unknown",
    ],
)
def test_dashscope_does_not_guess_or_escape_configured_api_path(server, base_url):
    provider = replace(
        server.provider, model="qwen-audio-3.0-asr-flash", base_url=base_url
    )
    with pytest.raises(ProviderError) as caught:
        run(server, lambda client: client.transcribe(provider, "test-key", wav()))
    assert caught.value.code == "configuration"
    assert server.requests == []


def test_dashscope_same_origin_and_port_are_preserved():
    from inkecho.providers import dashscope_base_url

    assert dashscope_base_url(
        "https://tenant.example:9443/customer/compatible-mode/v1/"
    ) == ("https://tenant.example:9443/customer/api/v1")


@pytest.mark.parametrize(
    "base_url",
    [
        "https://example.invalid/compatible-mode/v1?redirect=other",
        "https://user:password@example.invalid/compatible-mode/v1",
    ],
)
def test_dashscope_url_conversion_defensively_rejects_unsafe_inputs(base_url):
    from inkecho.providers import dashscope_base_url

    with pytest.raises(ProviderError) as caught:
        dashscope_base_url(base_url)
    assert caught.value.code == "configuration"


def test_zero_sample_rate_audio_is_rejected_before_duration_or_network(server):
    audio = bytearray(wav())
    audio[24:28] = b"\x00" * 4
    with pytest.raises(ProviderError) as caught:
        run(
            server,
            lambda client: client.transcribe(server.provider, "test-key", bytes(audio)),
        )
    assert caught.value.code == "audio"
    assert server.requests == []
