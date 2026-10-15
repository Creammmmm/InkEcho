"""Actual loopback WSS capability routing, never cloud or desktop input."""

import asyncio
import base64
import io
import json
import ssl
import subprocess
import time
import wave
from dataclasses import replace
from types import SimpleNamespace

import pytest
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from inkecho.config import Provider
from inkecho.providers import ProviderClient, ProviderError, validate_provider_protocol
from inkecho.realtime import CHUNK_BYTES, PROTOCOL, QwenRealtimeSession

MODEL = "qwen3-asr-flash-realtime"


def wav(pcm=b"\x01\x00" * 40017, *, rate=16000, channels=1, width=2):
    output = io.BytesIO()
    with wave.open(output, "wb") as recording:
        recording.setnchannels(channels)
        recording.setsampwidth(width)
        recording.setframerate(rate)
        recording.writeframes(pcm)
    return output.getvalue()


@pytest.fixture(scope="module")
def certificate(tmp_path_factory):
    folder = tmp_path_factory.mktemp("capability-wss")
    cert, key = folder / "cert.pem", folder / "key.pem"
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
            "subjectAltName=IP:127.0.0.1",
        ],
        check=True,
        capture_output=True,
    )
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(cert, key)
    return server, ssl.create_default_context(cafile=str(cert))


def provider(endpoint="wss://asr.example.invalid/realtime"):
    return Provider(
        "test",
        "Fixture",
        "transcription",
        "qwen",
        "https://custom.example.invalid/v1",
        MODEL,
        parameters={"asr_protocol": PROTOCOL, "realtime_url": endpoint},
    )


async def exercise(certificate, monkeypatch, operation, *, mode="normal"):
    state = SimpleNamespace(
        events=[], pcm=[], opened=0, closed=0, sessions=[], server_errors=[]
    )

    async def handler(socket):
        state.opened += 1
        state.authorization = socket.request.headers.get("Authorization")
        counter = 0

        async def send(kind, **values):
            nonlocal counter
            counter += 1
            await socket.send(
                json.dumps({"event_id": str(counter), "type": kind, **values})
            )

        try:
            await send("session.created", session={"id": "s1", "model": MODEL})
            async for message in socket:
                item = json.loads(message)
                kind = item["type"]
                state.events.append(kind)
                if kind == "session.update" and mode != "start_wait":
                    await send(
                        "session.updated",
                        session={"id": "s1", "model": MODEL, **item["session"]},
                    )
                elif kind == "input_audio_buffer.append":
                    state.pcm.append(base64.b64decode(item["audio"]))
                elif kind == "input_audio_buffer.commit":
                    await send("input_audio_buffer.committed", item_id="item1")
                elif kind == "session.finish" and mode != "finish_wait":
                    await send(
                        "conversation.item.input_audio_transcription.completed",
                        item_id="item1",
                        content_index=0,
                        transcript="固定测试结果",
                    )
                    await send("session.finished")
        except ConnectionClosed:
            pass  # Local cancellation intentionally closes in-flight fixtures.
        except Exception as error:
            state.server_errors.append(type(error).__name__)
        finally:
            state.closed += 1

    def create(*args, **options):
        session = QwenRealtimeSession(*args, **options, tls_context=certificate[1])
        state.sessions.append(session)
        return session

    monkeypatch.setattr("inkecho.provider_capability.QwenRealtimeSession", create)
    async with serve(handler, "127.0.0.1", 0, ssl=certificate[0]) as server:
        port = server.sockets[0].getsockname()[1]
        selected = provider(f"wss://127.0.0.1:{port}/api-ws/v1/realtime")
        result = await operation(selected, state)
    assert state.server_errors == []
    return result


def test_real_wss_capability_sends_pcm_frames_and_returns_final(
    certificate, monkeypatch
):
    async def operation(selected, state):
        validate_provider_protocol(selected)
        async with ProviderClient(timeout_seconds=2) as client:
            result = await client.test_capability(selected, "fixture-key", audio=wav())
            assert client.http is None  # No HTTP audio upload was made.
        assert result.text == "固定测试结果"
        assert b"".join(state.pcm) == b"\x01\x00" * 40017
        assert all(0 < len(chunk) <= CHUNK_BYTES for chunk in state.pcm)
        assert state.events[-2:] == ["input_audio_buffer.commit", "session.finish"]
        assert state.authorization == "Bearer fixture-key" and state.opened == 1
        assert all(session._closed and session._key == "" for session in state.sessions)

    asyncio.run(exercise(certificate, monkeypatch, operation))


@pytest.mark.parametrize("mode", ["start_wait", "finish_wait"])
def test_real_wss_capability_cancellation_closes_without_replay(
    certificate, monkeypatch, mode
):
    async def operation(selected, state):
        async with ProviderClient(timeout_seconds=2) as client:
            task = asyncio.create_task(
                client.test_capability(selected, "fixture-key", audio=wav())
            )
            expected = "session.update" if mode == "start_wait" else "session.finish"
            deadline = time.monotonic() + 2
            while expected not in state.events:
                assert time.monotonic() < deadline
                await asyncio.sleep(0.005)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await asyncio.sleep(0.03)
            assert state.opened == 1 and state.closed == 1
            assert all(session._closed for session in state.sessions)
            if mode == "start_wait":
                assert "input_audio_buffer.commit" not in state.events

    asyncio.run(exercise(certificate, monkeypatch, operation, mode=mode))


def test_real_wss_capability_whole_operation_timeout(certificate, monkeypatch):
    async def operation(selected, state):
        async with ProviderClient(timeout_seconds=0.1) as client:
            with pytest.raises(ProviderError) as caught:
                await client.test_capability(selected, "fixture-key", audio=wav())
            assert caught.value.code == "timeout" and state.opened == 1
            assert all(session._closed for session in state.sessions)

    asyncio.run(exercise(certificate, monkeypatch, operation, mode="finish_wait"))


@pytest.mark.parametrize(
    "audio",
    [
        None,
        "not bytes",
        [],
        b"",
        b"not wav",
        wav(b""),
        wav(b"\x01\x00\x01"),
        wav()[:20] + b"\x06\x00" + wav()[22:],
        wav(rate=48000),
        wav(channels=2),
        wav(width=1),
        wav()[:-2],
    ],
)
def test_invalid_realtime_test_audio_rejected_before_connection(monkeypatch, audio):
    def forbidden(*_args, **_options):
        raise AssertionError("must validate WAV before opening network")

    monkeypatch.setattr("inkecho.provider_capability.QwenRealtimeSession", forbidden)

    async def execute():
        async with ProviderClient() as client:
            with pytest.raises(ProviderError) as caught:
                await client.test_capability(provider(), "fixture-key", audio=audio)
            assert caught.value.code == "audio"

    asyncio.run(execute())


def test_http_transcribe_still_refuses_explicit_realtime_without_encoding_or_network():
    async def execute():
        async with ProviderClient() as client:
            with pytest.raises(ProviderError) as caught:
                await client.transcribe(provider(), "fixture-key", b"invalid WAV")
            assert caught.value.code == "protocol" and client.http is None

    asyncio.run(execute())


def test_closed_client_cannot_start_realtime_capability(monkeypatch):
    def forbidden(*_args, **_options):
        raise AssertionError("closed lifecycle must not open a WebSocket")

    monkeypatch.setattr("inkecho.provider_capability.QwenRealtimeSession", forbidden)

    async def execute():
        client = ProviderClient()
        await client.aclose()
        with pytest.raises(ProviderError) as caught:
            await client.test_capability(provider(), "fixture-key", audio=wav())
        assert caught.value.code == "configuration"

    asyncio.run(execute())


@pytest.mark.parametrize(
    "model",
    [
        "qwen3-asr-flash",
        "qwen3-asr-flash-filetrans",
        "fun-asr-flash",
        "qwen-audio-3.1-asr-flash-streaming",
    ],
)
def test_known_other_model_protocol_is_rejected_in_realtime_mode(model):
    with pytest.raises(ProviderError) as caught:
        validate_provider_protocol(replace(provider(), model=model))
    assert caught.value.code == "protocol"
