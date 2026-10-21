"""Real loopback WSS protocol fixtures and separately labelled queue unit checks."""

import asyncio
import base64
import json
import ssl
import subprocess
import threading
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from inkecho.config import Provider
from inkecho.providers import ProviderError
from inkecho.realtime import (
    CHUNK_BYTES,
    QUEUE_CHUNKS,
    QwenRealtimeSession,
    RealtimeConfig,
)

MODEL = "qwen3-asr-flash-realtime"
FINAL = "你好，Unicode café!"


@pytest.fixture(scope="module")
def certificate(tmp_path_factory):
    folder = tmp_path_factory.mktemp("realtime-tls")
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
            "subjectAltName=IP:127.0.0.1,DNS:localhost",
        ],
        check=True,
        capture_output=True,
    )
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.load_cert_chain(cert, key)
    trusted = ssl.create_default_context(cafile=str(cert))
    return server, trusted


async def exercise(certificate, operation, *, mode="normal", timeout=1):
    state = SimpleNamespace(events=[], headers=None, audio=[], connections=0, errors=[])

    async def handler(ws):
        state.connections += 1
        state.headers = ws.request.headers
        state.path = ws.request.path
        counter = 0

        async def send(kind, **values):
            nonlocal counter
            counter += 1
            await ws.send(
                json.dumps({"event_id": str(counter), "type": kind, **values})
            )

        await send("session.created", session={"id": "s1", "model": MODEL})
        try:
            async for message in ws:
                event = json.loads(message)
                state.events.append(event)
                kind = event["type"]
                if kind == "session.update":
                    if mode == "start_timeout":
                        continue
                    session = {"id": "s1", "model": MODEL, **event["session"]}
                    if mode == "wrong_session":
                        session["id"] = "other"
                    if mode == "wrong_format":
                        session["sample_rate"] = 48000
                    if mode == "wrong_model":
                        session["model"] = "other-model"
                    if mode == "wrong_encoding":
                        session["input_audio_format"] = "opus"
                    if mode == "omit_turn_detection":
                        del session["turn_detection"]
                    if mode == "vad_object":
                        session["turn_detection"] = {"type": "server_vad"}
                    await send("session.updated", session=session)
                    if mode == "early_finish":
                        await send("session.finished")
                elif kind == "input_audio_buffer.append":
                    state.audio.append(base64.b64decode(event["audio"]))
                    if mode == "remote_error":
                        await send("error", error={"message": "private-key audio text"})
                    if mode == "unsolicited_item":
                        await send(
                            "conversation.item.input_audio_transcription.completed",
                            item_id="other",
                            content_index=0,
                            transcript="do not return",
                        )
                    if mode == "placeholder" and len(state.audio) == 1:
                        await send(
                            "conversation.item.created",
                            item={"type": "message", "content": "never return this"},
                        )
                        await send(
                            "conversation.item.input_audio_transcription.text",
                            item_id="preview-without-commit",
                            content_index=False,
                            text="never return this preview",
                        )
                    if mode == "early_committed":
                        await send("input_audio_buffer.committed", item_id="i1")
                elif kind == "input_audio_buffer.commit":
                    if mode.startswith("ack_missing") or mode == "all_optional_missing":
                        await send("input_audio_buffer.committed")
                    elif mode.startswith("ack_null") or mode == "all_optional_null":
                        await send("input_audio_buffer.committed", item_id=None)
                    elif mode == "no_ack":
                        pass
                    else:
                        await send("input_audio_buffer.committed", item_id="i1")
                    if mode == "changed_ack":
                        await send("input_audio_buffer.committed", item_id="other")
                    await send(
                        "conversation.item.created",
                        item={"id": "i1", "role": "user", "type": "message"},
                    )
                elif kind == "session.finish":
                    if mode == "finish_timeout":
                        continue
                    if mode == "invalid_json":
                        await ws.send("audio secret is not json")
                        continue
                    if mode in {"empty", "ack_missing", "ack_null", "no_ack"}:
                        await send("session.finished")
                        continue
                    item = "other" if mode == "wrong_item" else "i1"
                    await send(
                        "conversation.item.input_audio_transcription.text",
                        item_id=item,
                        content_index=0,
                        text="wrong preview",
                        stash="draft",
                    )
                    final_kind = (
                        "conversation.item.input_audio_transcription.unknown"
                        if mode == "unknown_transcription"
                        else "conversation.item.input_audio_transcription.completed"
                    )
                    final = {
                        "item_id": item,
                        "content_index": False if mode == "bool_index" else 0,
                        "transcript": FINAL,
                    }
                    if mode in {"final_missing_id", "all_optional_missing"}:
                        del final["item_id"]
                    if mode in {"final_null_id", "all_optional_null"}:
                        final["item_id"] = None
                    if mode in {"final_missing_index", "all_optional_missing"}:
                        del final["content_index"]
                    if mode == "null_index":
                        final["content_index"] = None
                    await send(final_kind, **final)
                    if mode in {"duplicate", "changed_final"}:
                        await send(
                            "conversation.item.input_audio_transcription.completed",
                            item_id=item,
                            content_index=0,
                            transcript="changed" if mode == "changed_final" else FINAL,
                        )
                    if mode == "completed_no_finished":
                        continue
                    if mode in {"delayed_finished", "error_after_completed"}:
                        await state.release_finished.wait()
                    if mode == "error_after_completed":
                        await send("error", error={"message": "synthetic"})
                    else:
                        await send("session.finished")
        except ConnectionClosed:
            return  # Expected connection abort on intentionally invalid fixtures.
        except Exception as error:
            state.errors.append(type(error).__name__)

    async with serve(handler, "127.0.0.1", 0, ssl=certificate[0]) as server:
        port = server.sockets[0].getsockname()[1]
        session = QwenRealtimeSession(
            RealtimeConfig(f"wss://127.0.0.1:{port}/api-ws/v1/realtime", MODEL),
            "fixture-key",
            tls_context=certificate[1],
            timeout_seconds=timeout,
        )
        try:
            result = await operation(session, state)
        finally:
            await session.aclose()
    assert state.errors == []
    return result


def test_real_wss_buffers_during_start_chunks_tail_and_final(certificate):
    async def scenario(session, state):
        pcm = b"\x01\x00" * (CHUNK_BYTES + 17)
        session.feed_nowait(pcm)
        await session.start()
        # A frame arrives before stop, proving upload is not deferred to finish.
        for _ in range(100):
            if state.audio:
                break
            await asyncio.sleep(0.002)
        assert state.audio and not session._finishing
        result = await session.finish()
        assert result.text == FINAL and FINAL not in repr(result)
        assert b"".join(state.audio) == pcm
        assert [len(chunk) for chunk in state.audio] == [3200, 3200, 34]
        assert state.headers["Authorization"] == "Bearer fixture-key"
        assert state.path.endswith("?model=" + MODEL)
        assert state.events[0]["session"] == {
            "input_audio_format": "pcm",
            "sample_rate": 16000,
            "input_audio_transcription": {},
            "turn_detection": None,
        }
        assert [event["type"] for event in state.events][-2:] == [
            "input_audio_buffer.commit",
            "session.finish",
        ]
        assert len({event["event_id"] for event in state.events}) == len(state.events)
        assert state.connections == 1
        assert all(task.done() for task in session._tasks)

    asyncio.run(exercise(certificate, scenario))


@pytest.mark.parametrize(
    "mode",
    [
        "duplicate",
        "normal",
        "omit_turn_detection",
        "placeholder",
        "ack_missing_with_final",
        "ack_null_with_final",
        "final_missing_id",
        "final_null_id",
        "final_missing_index",
        "all_optional_missing",
        "all_optional_null",
    ],
)
def test_real_wss_only_final_and_deduplicated(certificate, mode):
    async def scenario(session, _):
        await session.start()
        await session.feed(b"\x00\x00" * 1600)
        if mode == "placeholder":
            # Wait for the actual pre-commit notifications, not a synthetic unit call.
            for _ in range(100):
                if len(session._event_ids) >= 4:
                    break
                await asyncio.sleep(0.002)
            assert len(session._event_ids) >= 4
            assert session._item_id is None and session._transcript is None
            assert not session._done.done() and not session._commit_sent
        assert (await session.finish()).text == FINAL

    asyncio.run(exercise(certificate, scenario, mode=mode))


@pytest.mark.parametrize(
    ("mode", "code"),
    [
        ("wrong_item", "response"),
        ("changed_final", "response"),
        ("invalid_json", "response"),
        ("empty", "empty"),
        ("remote_error", "unavailable"),
        ("unsolicited_item", "response"),
        ("finish_timeout", "timeout"),
        ("changed_ack", "response"),
        ("bool_index", "response"),
        ("unknown_transcription", "response"),
        ("ack_missing", "empty"),
        ("ack_null", "empty"),
        ("no_ack", "response"),
        ("null_index", "response"),
    ],
)
def test_real_wss_failures_never_return_partial(certificate, mode, code):
    async def scenario(session, state):
        await session.start()
        session.feed_nowait(b"\x01\x00" * 160)
        with pytest.raises(ProviderError) as error:
            await session.finish()
        assert error.value.code == code
        assert "private" not in str(error.value) and "audio secret" not in repr(
            error.value
        )
        assert state.connections == 1  # No automatic retry/reconnect of billable audio.
        assert all(task.done() for task in session._tasks)

    asyncio.run(exercise(certificate, scenario, mode=mode, timeout=0.1))


@pytest.mark.parametrize(
    "mode",
    [
        "wrong_session",
        "wrong_format",
        "wrong_model",
        "wrong_encoding",
        "vad_object",
        "start_timeout",
    ],
)
def test_real_wss_start_failure_cleans_prebuffer(certificate, mode):
    async def scenario(session, _):
        session.feed_nowait(b"\x00\x00" * 1600)
        with pytest.raises(ProviderError):
            await session.start()
        assert session._queue.empty() and not session._tail and not session._key
        assert all(task.done() for task in session._tasks)

    asyncio.run(exercise(certificate, scenario, mode=mode, timeout=0.1))


def test_real_wss_unsolicited_finish_rejected(certificate):
    async def scenario(session, _):
        try:
            await session.start()
            await asyncio.sleep(0.03)
            await session.finish()
        except ProviderError as error:
            assert error.code == "response"
        else:
            pytest.fail("unsolicited session.finished was accepted")

    asyncio.run(exercise(certificate, scenario, mode="early_finish"))


@pytest.mark.parametrize("mode", ["unsolicited_item", "early_committed"])
def test_real_wss_result_or_ack_before_manual_commit_is_rejected(certificate, mode):
    async def scenario(session, state):
        await session.start()
        await session.feed(bytes(CHUNK_BYTES))
        with pytest.raises(ProviderError) as caught:
            await session.wait_failure()
        assert caught.value.code == "response"
        assert session._item_id is None and session._transcript is None
        assert not session._commit_sent
        assert not any(e["type"] == "input_audio_buffer.commit" for e in state.events)

    asyncio.run(exercise(certificate, scenario, mode=mode))


@pytest.mark.parametrize("item_id", ["", 42, "x" * 201])
def test_commit_ack_requires_a_bounded_nonempty_string(item_id):
    async def scenario():
        session = QwenRealtimeSession(
            RealtimeConfig("wss://test.invalid/ws", MODEL), "fixture-key"
        )
        session._ready = asyncio.get_running_loop().create_future()
        session._ready.set_result(None)
        session._commit_sent = True
        with pytest.raises(ProviderError) as caught:
            await session._event(
                {"type": "input_audio_buffer.committed", "item_id": item_id}
            )
        assert caught.value.code == "response" and session._item_id is None
        await session.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("payload", [{}, {"item_id": None}])
def test_optional_ack_identity_can_bind_at_final_and_is_never_erased(payload):
    async def scenario():
        session = QwenRealtimeSession(
            RealtimeConfig("wss://test.invalid/ws", MODEL), "fixture-key"
        )
        session._ready = asyncio.get_running_loop().create_future()
        session._ready.set_result(None)
        session._commit_sent = True
        await session._event({"type": "input_audio_buffer.committed", **payload})
        assert session._commit_acknowledged and session._item_id is None
        # Recognition can finish after commit but before session.finish is sent.
        await session._event(
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "item_id": "i1",
                "content_index": 0,
                "transcript": FINAL,
            }
        )
        await session._event({"type": "input_audio_buffer.committed", **payload})
        assert session._item_id == "i1"
        assert session._transcript == FINAL and not session._finish_sent
        with pytest.raises(ProviderError):
            await session._event(
                {"type": "input_audio_buffer.committed", "item_id": "other"}
            )
        await session.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("item_id", ["", False, 42, [], "x" * 201, "other"])
@pytest.mark.parametrize("suffix", ["completed", "failed"])
def test_final_supplied_id_must_be_valid_and_consistent(item_id, suffix):
    async def scenario():
        session = QwenRealtimeSession(
            RealtimeConfig("wss://test.invalid/ws", MODEL), "fixture-key"
        )
        session._ready = asyncio.get_running_loop().create_future()
        session._ready.set_result(None)
        session._commit_sent = True
        await session._event({"type": "input_audio_buffer.committed", "item_id": "i1"})
        with pytest.raises(ProviderError) as caught:
            await session._event(
                {
                    "type": "conversation.item.input_audio_transcription." + suffix,
                    "item_id": item_id,
                    "transcript": FINAL,
                }
            )
        assert caught.value.code == "response" and session._transcript is None
        await session.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("index", [None, False, True, 1, -1, "0", []])
@pytest.mark.parametrize("suffix", ["completed", "failed"])
def test_final_optional_index_is_strict_when_supplied(index, suffix):
    async def scenario():
        session = QwenRealtimeSession(
            RealtimeConfig("wss://test.invalid/ws", MODEL), "fixture-key"
        )
        session._ready = asyncio.get_running_loop().create_future()
        session._ready.set_result(None)
        session._commit_sent = True
        await session._event({"type": "input_audio_buffer.committed"})
        with pytest.raises(ProviderError) as caught:
            await session._event(
                {
                    "type": "conversation.item.input_audio_transcription." + suffix,
                    "content_index": index,
                    "transcript": FINAL,
                }
            )
        assert caught.value.code == "response" and session._transcript is None
        await session.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("item", [None, [], "message", {}, {"type": "other"}])
def test_created_notification_still_requires_a_message_object(item):
    async def scenario():
        session = QwenRealtimeSession(
            RealtimeConfig("wss://test.invalid/ws", MODEL), "fixture-key"
        )
        session._ready = asyncio.get_running_loop().create_future()
        session._ready.set_result(None)
        with pytest.raises(ProviderError) as caught:
            await session._event({"type": "conversation.item.created", "item": item})
        assert caught.value.code == "response" and session._item_id is None
        await session.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("action", ["cancel", "stale", "deadline"])
@pytest.mark.parametrize("mode", ["normal", "omit_turn_detection", "placeholder"])
def test_real_wss_cancel_and_expiry_stop_remaining_audio(certificate, action, mode):
    async def scenario(session, state):
        await session.start()
        session.feed_nowait(b"\x00\x00" * (1600 if mode == "placeholder" else 160))
        if mode == "placeholder":
            for _ in range(100):
                if len(session._event_ids) >= 4:
                    break
                await asyncio.sleep(0.002)
            assert len(session._event_ids) >= 4
        if action == "cancel":
            await session.aclose()
        elif action == "stale":
            session.active = lambda: False
            await asyncio.sleep(0.07)
        else:
            session.deadline = time.monotonic() - 1
            await asyncio.sleep(0.07)
        before = len(state.events)
        with pytest.raises((ProviderError, asyncio.CancelledError)):
            await session.finish()
        await session.aclose()
        await asyncio.sleep(0.02)
        assert len(state.events) == before
        assert len(state.audio) == (1 if mode == "placeholder" else 0)
        assert not any(e["type"] == "input_audio_buffer.commit" for e in state.events)

    asyncio.run(exercise(certificate, scenario, mode=mode))


@pytest.mark.parametrize("turn", [{}, {"type": "server_vad"}, False, "null", []])
def test_nonnull_turn_detection_is_rejected_after_manual_update(turn):
    async def scenario():
        session = QwenRealtimeSession(
            RealtimeConfig("wss://test.invalid/ws", MODEL), "fixture-key"
        )
        session._session_id = "s1"
        session._manual_update_sent = True
        session._ready = asyncio.get_running_loop().create_future()
        with pytest.raises(ProviderError) as caught:
            await session._event(
                {
                    "type": "session.updated",
                    "event_id": "update",
                    "session": {
                        "id": "s1",
                        "model": MODEL,
                        "input_audio_format": "pcm",
                        "sample_rate": 16000,
                        "turn_detection": turn,
                    },
                }
            )
        assert caught.value.code == "response" and not session._ready.done()
        await session.aclose()

    asyncio.run(scenario())


def test_omitted_turn_detection_requires_our_manual_update_sent_first():
    async def scenario():
        session = QwenRealtimeSession(
            RealtimeConfig("wss://test.invalid/ws", MODEL), "fixture-key"
        )
        session._session_id = "s1"
        session._ready = asyncio.get_running_loop().create_future()
        with pytest.raises(ProviderError) as caught:
            await session._event(
                {
                    "type": "session.updated",
                    "event_id": "update",
                    "session": {
                        "id": "s1",
                        "model": MODEL,
                        "input_audio_format": "pcm",
                        "sample_rate": 16000,
                    },
                }
            )
        assert caught.value.code == "response" and not session._ready.done()
        await session.aclose()

    asyncio.run(scenario())


def test_queue_unit_bounded_overflow_is_terminal():
    async def scenario():
        session = QwenRealtimeSession(
            RealtimeConfig("wss://test.invalid/ws", MODEL), "k"
        )
        for _ in range(QUEUE_CHUNKS):
            session.feed_nowait(b"\x00" * CHUNK_BYTES)
        assert session._queue.qsize() == QUEUE_CHUNKS
        with pytest.raises(ProviderError) as error:
            session.feed_nowait(b"\x00" * CHUNK_BYTES)
        assert error.value.code == "unavailable" and session._queue.empty()
        with pytest.raises(ProviderError):
            await session.start()
        await session.aclose()

    asyncio.run(scenario())


def test_queue_unit_async_backpressure_times_out_without_drop():
    async def scenario():
        session = QwenRealtimeSession(
            RealtimeConfig("wss://test.invalid/ws", MODEL), "k", timeout_seconds=0.05
        )
        for _ in range(QUEUE_CHUNKS):
            session.feed_nowait(b"\x00" * CHUNK_BYTES)
        with pytest.raises(ProviderError) as error:
            await session.feed(b"\x01\x00" * 1600)
        assert error.value.code == "timeout" and session._queue.empty()
        await session.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("pcm", [b"x", "not bytes"])
def test_invalid_audio_is_terminal(pcm):
    async def scenario():
        session = QwenRealtimeSession(
            RealtimeConfig("wss://test.invalid/ws", MODEL), "k"
        )
        with pytest.raises(ProviderError) as error:
            session.feed_nowait(pcm)
        assert error.value.code == "audio"
        await session.aclose()

    asyncio.run(scenario())


def provider(**changes):
    return replace(
        Provider(
            "qwen",
            "Qwen",
            "transcription",
            "qwen",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            MODEL,
            "fixture",
            parameters={"asr_protocol": "qwen_realtime"},
        ),
        **changes,
    )


def test_protocol_explicit_gateway_and_official_endpoints():
    official = RealtimeConfig.from_provider(provider())
    assert (
        official.url == f"wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model={MODEL}"
    )
    workspace = provider(base_url="https://abc123.cn-beijing.maas.aliyuncs.com/v1")
    assert (
        "abc123.cn-beijing.maas.aliyuncs.com/api-ws"
        in RealtimeConfig.from_provider(workspace).url
    )
    custom = provider(
        base_url="https://gateway.invalid/v1",
        parameters={
            "asr_protocol": "qwen_realtime",
            "realtime_url": "wss://gateway.invalid/prefix/ws",
        },
    )
    assert RealtimeConfig.from_provider(custom).url.endswith("prefix/ws?model=" + MODEL)


@pytest.mark.parametrize(
    "changes",
    [
        {"parameters": {}},
        {"base_url": "https://gateway.invalid/v1"},
        {
            "parameters": {
                "asr_protocol": "qwen_realtime",
                "realtime_url": "ws://gateway.invalid/ws",
            }
        },
        {
            "parameters": {
                "asr_protocol": "qwen_realtime",
                "realtime_url": "wss://secret@gateway.invalid/ws",
            }
        },
        {
            "parameters": {
                "asr_protocol": "qwen_realtime",
                "realtime_url": "wss://gateway.invalid/ws?api_key=secret",
            }
        },
    ],
)
def test_unsupported_protocol_or_insecure_endpoint_rejected(changes):
    with pytest.raises(ProviderError) as error:
        RealtimeConfig.from_provider(provider(**changes))
    assert error.value.code == "configuration" and "secret" not in str(error.value)


@pytest.mark.parametrize("rate", [8000, 24000, 48000])
def test_rate_not_silently_changed(rate):
    with pytest.raises(ProviderError):
        RealtimeConfig.from_provider(provider(), sample_rate=rate)


def test_unknown_provider_parameter_not_silently_ignored():
    with pytest.raises(ProviderError):
        RealtimeConfig.from_provider(
            provider(parameters={"asr_protocol": "qwen_realtime", "temperature": 0.1})
        )


@pytest.mark.parametrize("endpoint", [None, 123, b"wss://secret.invalid/ws"])
def test_invalid_endpoint_type_is_sanitized(endpoint):
    with pytest.raises(ProviderError) as error:
        RealtimeConfig(endpoint, MODEL)
    assert error.value.code == "configuration"


def test_real_wss_rejects_untrusted_certificate(certificate):
    async def scenario(session, state):
        session._tls_context = ssl.create_default_context()
        with pytest.raises(ProviderError) as error:
            await session.start()
        assert error.value.code == "network"
        assert state.connections == 0
        assert all(task.done() for task in session._tasks)

    asyncio.run(exercise(certificate, scenario))


def test_tls_verification_cannot_be_disabled():
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    with pytest.raises(ProviderError):
        QwenRealtimeSession(
            RealtimeConfig("wss://test.invalid/ws", MODEL), "k", tls_context=context
        )


@pytest.mark.parametrize("cancel", [False, True])
def test_cold_tls_preparation_keeps_onset_and_cannot_open_after_cancel(
    monkeypatch, cancel
):
    """A blocked trust-store load must leave the event loop and capture usable."""
    from inkecho import realtime

    entered, release, completed = (
        threading.Event(),
        threading.Event(),
        threading.Event(),
    )
    original = ssl.create_default_context
    calls, opened = [], []

    def trust():
        calls.append(threading.get_ident())
        entered.set()
        assert release.wait(3)
        try:
            return original()
        finally:
            completed.set()

    monkeypatch.setattr(realtime.ssl, "create_default_context", trust)

    async def scenario():
        owner = threading.get_ident()
        session = QwenRealtimeSession(
            RealtimeConfig("wss://test.invalid/ws", MODEL), "synthetic-key"
        )
        assert not calls  # Construction no longer loads the trust store.
        onset = b"\x11\x00" * (CHUNK_BYTES // 2)
        session.feed_nowait(onset)

        async def open_without_network():
            opened.append(True)
            assert session._tls_context.check_hostname
            assert session._tls_context.verify_mode == ssl.CERT_REQUIRED
            assert session._queue.get_nowait() == onset
            session._ready.set_result(None)

        async def no_audio_sender():
            pass

        async def no_receiver():
            pass

        monkeypatch.setattr(session, "_open", open_without_network)
        monkeypatch.setattr(session, "_send_audio", no_audio_sender)
        monkeypatch.setattr(session, "_receive", no_receiver)
        task = asyncio.create_task(session.start())
        try:
            async with asyncio.timeout(2):
                while not entered.is_set():
                    await asyncio.sleep(0)
            assert len(calls) == 1 and calls[0] != owner
            assert not opened
            assert session._queue.qsize() == 1
            if cancel:
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert session._closed
                assert session._queue.empty() and not session._tail
            release.set()
            if not cancel:
                await task
                assert opened == [True]
            else:
                async with asyncio.timeout(2):
                    while not completed.is_set():
                        await asyncio.sleep(0)
                await asyncio.sleep(0)
                assert not opened
        finally:
            release.set()
            await session.aclose()

    asyncio.run(scenario())


def test_real_wss_redirect_never_forwards_credentials(certificate):
    async def scenario():
        hits = []

        async def target(ws):
            hits.append(ws.request.headers.get("Authorization"))

        async with serve(target, "127.0.0.1", 0, ssl=certificate[0]) as second:
            target_port = second.sockets[0].getsockname()[1]

            def redirect(connection, request):
                response = connection.respond(302, "fixture redirect")
                response.headers["Location"] = f"wss://127.0.0.1:{target_port}/ws"
                return response

            async with serve(
                target, "127.0.0.1", 0, ssl=certificate[0], process_request=redirect
            ) as first:
                source_port = first.sockets[0].getsockname()[1]
                session = QwenRealtimeSession(
                    RealtimeConfig(f"wss://127.0.0.1:{source_port}/ws", MODEL),
                    "fixture-key",
                    tls_context=certificate[1],
                    timeout_seconds=0.2,
                )
                with pytest.raises(ProviderError) as error:
                    await session.start()
                assert error.value.code == "network"
                assert hits == []
                await session.aclose()

    asyncio.run(scenario())


def test_real_wss_expiry_at_connect_completion_closes_owned_socket(certificate):
    async def scenario(session, state):
        original_open = session._open

        async def open_then_expire():
            await original_open()
            session.active = lambda: False

        session._open = open_then_expire
        with pytest.raises(asyncio.CancelledError):
            await session.start()
        assert session._socket is not None
        assert session._socket.transport.is_closing()
        assert state.events == []
        assert all(task.done() for task in session._tasks)

    asyncio.run(exercise(certificate, scenario))


def test_real_wss_empty_recording_never_commits(certificate):
    async def scenario(session, state):
        await session.start()
        with pytest.raises(ProviderError) as error:
            await session.finish()
        assert error.value.code == "audio"
        assert not any(e["type"] == "input_audio_buffer.commit" for e in state.events)

    asyncio.run(exercise(certificate, scenario))


def test_real_wss_cancel_while_waiting_for_final(certificate):
    async def scenario(session, state):
        await session.start()
        session.feed_nowait(b"\x00\x00" * 160)
        pending = asyncio.create_task(session.finish())
        for _ in range(100):
            if any(e["type"] == "session.finish" for e in state.events):
                break
            await asyncio.sleep(0.002)
        session.active = lambda: False
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert session._transcript is None
        assert all(task.done() for task in session._tasks)

    asyncio.run(exercise(certificate, scenario, mode="finish_timeout"))


def test_real_wss_failure_monitor_reports_disconnect_before_stop(certificate):
    async def scenario(session, state):
        await session.start()
        monitor = asyncio.create_task(session.wait_failure())
        session.feed_nowait(b"\x01\x00" * 1600)
        with pytest.raises(ProviderError) as error:
            await asyncio.wait_for(monitor, 1)
        assert error.value.code == "unavailable"
        assert not any(
            event["type"] in {"input_audio_buffer.commit", "session.finish"}
            for event in state.events
        )

    asyncio.run(exercise(certificate, scenario, mode="remote_error"))


def test_cancelled_monitor_does_not_cancel_shared_transport_failure_state(certificate):
    async def scenario(session, _state):
        await session.start()
        monitor = asyncio.create_task(session.wait_failure())
        await asyncio.sleep(0)
        monitor.cancel()
        with pytest.raises(asyncio.CancelledError):
            await monitor
        session.feed_nowait(b"\x01\x00" * 160)
        assert (await session.finish()).text == FINAL
        with pytest.raises(asyncio.CancelledError):
            await session.wait_failure()

    asyncio.run(exercise(certificate, scenario))


@pytest.mark.parametrize("mode", ["delayed_finished", "error_after_completed"])
def test_completed_observer_precedes_closure_but_does_not_replace_it(certificate, mode):
    async def operation(session, state):
        state.release_finished = asyncio.Event()
        observed = asyncio.Event()
        values = []

        def completed(result):
            values.append(result.text)
            observed.set()

        session.set_completed_callback(completed)
        await session.start()
        session.feed_nowait(b"\1\0" * 2000)
        task = asyncio.create_task(session.finish())
        await asyncio.wait_for(observed.wait(), 1)
        assert values == [FINAL] and not task.done()
        state.release_finished.set()
        if mode == "error_after_completed":
            with pytest.raises(ProviderError, match="unavailable"):
                await task
        else:
            assert (await task).text == FINAL

    asyncio.run(exercise(certificate, operation, mode=mode))


@pytest.mark.parametrize(
    "mode", ["duplicate", "changed_final", "bool_index", "wrong_item"]
)
def test_completed_observer_is_once_and_only_validated(certificate, mode):
    async def operation(session, state):
        values = []
        session.set_completed_callback(lambda result: values.append(result.text))
        await session.start()
        session.feed_nowait(b"\1\0" * 2000)
        if mode == "duplicate":
            assert (await session.finish()).text == FINAL
        else:
            with pytest.raises(ProviderError, match="response"):
                await session.finish()
        assert values == ([FINAL] if mode in {"duplicate", "changed_final"} else [])

    asyncio.run(exercise(certificate, operation, mode=mode))


def test_completed_callback_does_not_turn_missing_finished_into_success(certificate):
    async def operation(session, state):
        values = []
        session.set_completed_callback(lambda result: values.append(result.text))
        await session.start()
        session.feed_nowait(b"\1\0" * 2000)
        with pytest.raises(ProviderError) as caught:
            await session.finish()
        assert caught.value.code == "timeout"
        assert values == [FINAL]
        assert session._closed

    asyncio.run(
        exercise(certificate, operation, mode="completed_no_finished", timeout=0.1)
    )
