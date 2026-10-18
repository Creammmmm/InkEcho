"""Local WSS task protocol, final sentence aggregation and bounded raw PCM."""

import asyncio
import json
import time
from dataclasses import replace

import pytest
from test_realtime import certificate as shared_certificate
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from inkecho.asr_streaming import create_streaming_session, streaming_config
from inkecho.config import Provider
from inkecho.dashscope_realtime import DashscopeRealtimeConfig, DashscopeRealtimeSession
from inkecho.providers import ProviderError

certificate = shared_certificate


async def exercise(ca, operation, mode="normal"):
    events, frames, stamps, requests = [], [], [], []

    async def handler(ws):
        requests.append(ws.request)
        task_id = None

        async def send(kind, **payload):
            await ws.send(
                json.dumps(
                    {
                        "header": {
                            "event": kind,
                            "task_id": "other" if mode == "wrong_task" else task_id,
                        },
                        "payload": payload,
                    }
                )
            )

        async def sentence(begin, end, text, final=True):
            await send(
                "result-generated",
                output={
                    "sentence": {
                        "begin_time": begin,
                        "end_time": end,
                        "text": text,
                        "sentence_end": final,
                    }
                },
            )

        try:
            async for raw in ws:
                if isinstance(raw, bytes):
                    frames.append(raw)
                    stamps.append(time.monotonic())
                    assert len(raw) <= 3200 and len(raw) % 2 == 0
                    if mode != "empty":
                        await sentence(0, None, "not final", False)
                    if mode == "early_finished":
                        await send("task-finished")
                    if mode == "remote_error":
                        await send("task-failed")
                    if mode == "close":
                        await ws.close()
                    continue
                event = json.loads(raw)
                events.append(event)
                action = event["header"]["action"]
                assert event["header"]["streaming"] == "duplex"
                if action == "run-task":
                    task_id = event["header"]["task_id"]
                    assert event["payload"]["task"] == "asr"
                    assert event["payload"]["model"] == "fun-asr-realtime"
                    assert event["payload"]["parameters"] == {
                        "format": "pcm",
                        "sample_rate": 16000,
                    }
                    if mode != "start_timeout":
                        await send("task-started")
                elif action == "finish-task":
                    assert event["header"]["task_id"] == task_id and event[
                        "payload"
                    ] == {"input": {}}
                    if mode == "finish_timeout":
                        continue
                    if mode == "empty":
                        # No nonfinal result was sent in this mode.
                        await send("task-finished")
                        continue
                    await sentence(100, 200, "世界")
                    if mode != "unfinished":
                        await sentence(0, 100, "你好")
                    if mode == "duplicate":
                        await sentence(0, 100, "你好")
                    if mode == "conflict":
                        await sentence(0, 100, "changed")
                    if mode == "overlap":
                        await sentence(90, 150, "overlap")
                    if mode == "heartbeat":
                        await send(
                            "result-generated", output={"sentence": {"heartbeat": True}}
                        )
                    await send("task-finished")
                else:
                    pytest.fail("task ASR must not send Qwen or Step commit events")
        except ConnectionClosed:
            pass

    async with serve(handler, "127.0.0.1", 0, ssl=ca[0]) as server:
        port = server.sockets[0].getsockname()[1]
        config = DashscopeRealtimeConfig(
            f"wss://127.0.0.1:{port}/inference/", "fun-asr-realtime"
        )
        session = DashscopeRealtimeSession(
            config, "synthetic-only", timeout_seconds=0.4, tls_context=ca[1]
        )
        try:
            await operation(session)
        finally:
            await session.aclose()
        assert all(t.done() for t in session._tasks)
        assert not session._sentences and not session._pending_sentences
    assert len(requests) == 1 and requests[0].path == "/inference/"
    assert requests[0].headers["Authorization"] == "Bearer synthetic-only"
    return events, frames, stamps


@pytest.mark.parametrize("mode", ["normal", "duplicate", "heartbeat"])
def test_out_of_order_finals_are_aggregated_once_after_task_finished(certificate, mode):
    async def operation(session):
        await session.start()
        await session.feed(b"\0\0" * 3200)
        result = await session.finish()
        assert result.text == "你好世界"
        assert not callable(session.set_completed_callback)

    events, frames, stamps = asyncio.run(exercise(certificate, operation, mode))
    assert b"".join(frames) == b"\0\0" * 3200
    assert len(frames) == 2 and stamps[1] - stamps[0] >= 0.075
    assert [e["header"]["action"] for e in events] == ["run-task", "finish-task"]


@pytest.mark.parametrize(
    "mode,code",
    [
        ("wrong_task", "response"),
        ("start_timeout", "timeout"),
        ("finish_timeout", "timeout"),
        ("early_finished", "response"),
        ("remote_error", "unavailable"),
        ("close", "network"),
        ("conflict", "response"),
        ("overlap", "response"),
        ("unfinished", "response"),
        ("empty", "empty"),
    ],
)
def test_protocol_failures_never_return_partial_or_reconnect(certificate, mode, code):
    async def operation(session):
        with pytest.raises(ProviderError) as caught:
            await session.start()
            await session.feed(b"\0\0" * 1600)
            if mode in {"early_finished", "remote_error", "close"}:
                await asyncio.sleep(0.05)
            await session.finish()
        assert caught.value.code == code

    asyncio.run(exercise(certificate, operation, mode))


@pytest.mark.parametrize("mode", ["cancel", "inactive", "deadline"])
def test_pending_task_cancels_and_expires_without_result(certificate, mode):
    async def operation(session):
        await session.start()
        await session.feed(b"\0\0" * 1600)
        task = asyncio.create_task(session.finish())
        while not session._finish_sent:
            await asyncio.sleep(0.001)
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
        assert session._closed

    asyncio.run(exercise(certificate, operation, "finish_timeout"))


def test_explicit_registry_config_and_no_8k_in_16k_adapter():
    item = Provider(
        "fun",
        "Fun",
        "transcription",
        "dashscope-ws",
        "https://dashscope.aliyuncs.com/api/v1",
        "fun-asr-realtime",
        parameters={"asr_protocol": "dashscope_task"},
    )
    config = streaming_config(item)
    assert config.url == "wss://dashscope.aliyuncs.com/api-ws/v1/inference/"
    session = create_streaming_session(item, config, "synthetic-only")
    assert isinstance(session, DashscopeRealtimeSession)
    asyncio.run(session.aclose())
    with pytest.raises(ProviderError):
        streaming_config(replace(item, model="fun-asr-flash-8k-realtime"))
    with pytest.raises(ProviderError):
        streaming_config(replace(item, parameters={}))
