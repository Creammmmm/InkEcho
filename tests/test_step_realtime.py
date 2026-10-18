"""Actual local TLS StepFun ASR events; no live cloud or hardware microphone."""

import asyncio
import base64
import json
import time
from dataclasses import replace

import pytest
from test_realtime import certificate as shared_certificate
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from inkecho.config import Provider
from inkecho.providers import ProviderError
from inkecho.realtime import CHUNK_BYTES, QUEUE_CHUNKS
from inkecho.step_realtime import PCM_FORMAT, StepRealtimeConfig, StepRealtimeSession

certificate = shared_certificate


async def exercise(ca, operation, mode="normal"):
    events = []
    connections = []

    async def handler(ws):
        connections.append(ws.request)
        counter = 0

        async def send(kind, **values):
            nonlocal counter
            counter += 1
            meta = {} if mode == "optional_metadata" else {"meta": {"session_id": "s1"}}
            await ws.send(
                json.dumps({"event_id": str(counter), "type": kind, **meta, **values})
            )

        try:
            await send("session.created", session={})
            async for raw in ws:
                event = json.loads(raw)
                events.append(event)
                kind = event["type"]
                if kind == "session.update":
                    assert event["session"]["audio"]["input"]["format"] == PCM_FORMAT
                    assert event["session"]["audio"]["input"]["turn_detection"] == {}
                    if mode == "start_timeout":
                        continue
                    config = event["session"]
                    if mode == "vad":
                        config["audio"]["input"]["turn_detection"] = {
                            "type": "server_vad"
                        }
                    await send("session.updated", session=config)
                elif kind == "input_audio_buffer.append":
                    assert base64.b64decode(event["audio"]) == b"\0\0" * 1600
                    await send(
                        "conversation.item.input_audio_transcription.delta",
                        text="unconfirmed",
                        stash="never output",
                        item_id="i1",
                    )
                    if mode == "early_completed":
                        await send(
                            "conversation.item.input_audio_transcription.completed",
                            item_id="i1",
                            content_index=0,
                            transcript="not authorized",
                        )
                elif kind == "input_audio_buffer.commit":
                    if mode == "finish_timeout":
                        continue
                    if mode != "missing_ack":
                        await send("input_audio_buffer.committed", item_id="i1")
                    await send(
                        "conversation.item.input_audio_transcription.completed",
                        item_id="other" if mode == "wrong_item" else "i1",
                        content_index=False if mode == "bool_index" else 0,
                        transcript="" if mode == "empty" else "最终转写",
                    )
                else:
                    pytest.fail("Step ASR must never send Qwen session.finish")
        except ConnectionClosed:
            pass

    async with serve(handler, "127.0.0.1", 0, ssl=ca[0]) as server:
        port = server.sockets[0].getsockname()[1]
        config = StepRealtimeConfig(
            f"wss://127.0.0.1:{port}/v1/realtime/asr/stream", "stepaudio-2.5-asr-stream"
        )
        session = StepRealtimeSession(
            config,
            "synthetic-only",
            timeout_seconds=0.1 if "timeout" in mode else 1,
            tls_context=ca[1],
        )
        try:
            await operation(session)
        finally:
            await session.aclose()
        assert all(t.done() for t in session._tasks)
    assert len(connections) == 1
    assert connections[0].path == "/v1/realtime/asr/stream"
    assert connections[0].headers["Authorization"] == "Bearer synthetic-only"
    return events


@pytest.mark.parametrize("mode", ["normal", "optional_metadata"])
def test_actual_wss_manual_commit_returns_only_matched_final(certificate, mode):
    async def operation(session):
        await session.start()
        await session.feed(b"\0\0" * 1600)
        result = await session.finish()
        assert result.text == "最终转写"
        assert not callable(session.set_completed_callback)

    events = asyncio.run(exercise(certificate, operation, mode))
    assert [x["type"] for x in events].count("input_audio_buffer.commit") == 1
    assert "session.finish" not in [x["type"] for x in events]


@pytest.mark.parametrize(
    "mode,code",
    [
        ("start_timeout", "timeout"),
        ("finish_timeout", "timeout"),
        ("vad", "response"),
        ("missing_ack", "response"),
        ("wrong_item", "response"),
        ("bool_index", "response"),
        ("early_completed", "response"),
        ("empty", "empty"),
    ],
)
def test_failures_do_not_promote_partial_or_reconnect(certificate, mode, code):
    async def operation(session):
        with pytest.raises(ProviderError) as caught:
            await session.start()
            await session.feed(b"\0\0" * 1600)
            if mode == "early_completed":
                await asyncio.sleep(0.05)
            await session.finish()
        assert caught.value.code == code

    asyncio.run(exercise(certificate, operation, mode))


def test_cancel_before_finish_sends_no_commit(certificate):
    async def operation(session):
        await session.start()
        session.feed_nowait(b"\0\0" * 1600)
        await session.aclose()

    events = asyncio.run(exercise(certificate, operation))
    assert not any(x["type"] == "input_audio_buffer.commit" for x in events)


def test_queue_is_bounded_and_config_rejects_wrong_sample_rate_or_language():
    config = StepRealtimeConfig(
        "wss://example.invalid/v1/realtime/asr/stream", "stepaudio-2.5-asr-stream"
    )
    session = StepRealtimeSession(config, "synthetic-only")

    async def scenario():
        for _ in range(QUEUE_CHUNKS):
            session.feed_nowait(b"\0" * CHUNK_BYTES)
        with pytest.raises(ProviderError) as caught:
            session.feed_nowait(b"\0" * CHUNK_BYTES)
        assert caught.value.code == "unavailable"
        await session.aclose()

    asyncio.run(scenario())
    for changes in [
        {"sample_rate": True},
        {"sample_rate": 48000},
        {"language": None},
        {"endpoint": "wss://user:key@example.invalid/asr"},
        {"endpoint": "wss://example.invalid/asr?key=secret"},
    ]:
        with pytest.raises(ProviderError):
            replace(config, **changes)


def test_config_requires_explicit_step_asr_protocol():
    provider = Provider(
        "step",
        "Step",
        "transcription",
        "stepfun-realtime",
        "https://api.stepfun.com/v1",
        "stepaudio-2.5-asr-stream",
        parameters={"asr_protocol": "stepfun_realtime"},
    )
    assert (
        StepRealtimeConfig.from_provider(provider).url
        == "wss://api.stepfun.com/v1/realtime/asr/stream"
    )
    with pytest.raises(ProviderError):
        StepRealtimeConfig.from_provider(replace(provider, parameters={}))


@pytest.mark.parametrize("mode", ["cancel", "inactive", "deadline"])
def test_waiting_for_commit_result_respects_cancel_epoch_and_absolute_deadline(
    certificate, mode
):
    async def operation(session):
        await session.start()
        await session.feed(b"\0\0" * 1600)
        task = asyncio.create_task(session.finish())
        # Observe our own client state only; the server intentionally never completes.
        for _ in range(100):
            if session._commit_sent:
                break
            await asyncio.sleep(0.001)
        assert session._commit_sent
        if mode == "cancel":
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        elif mode == "inactive":
            session.active = lambda: False
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            session.deadline = time.monotonic() + 0.01
            with pytest.raises(ProviderError) as caught:
                await task
            assert caught.value.code == "timeout"
        assert session._closed and session._queue.empty()
        assert all(t.done() for t in session._tasks)

    events = asyncio.run(exercise(certificate, operation, "finish_timeout"))
    assert [x["type"] for x in events].count("input_audio_buffer.commit") == 1
    assert not any(x["type"] == "session.finish" for x in events)
