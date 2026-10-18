"""Controlled completion/closure races; no real microphone or cloud requests."""

import asyncio
from dataclasses import replace

import pytest
import test_application_realtime as realtime
from test_application_realtime import Connection
from test_application_streaming import Inputs

from inkecho.core import State
from inkecho.providers import ProviderError, Result, Usage

TEXT = "实时识别。"


@pytest.fixture
def realtime_sessions(tmp_path):
    return realtime.sessions.__wrapped__(tmp_path)


class EarlyConnection(Connection):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.protocol = asyncio.Event()
        self.callback = None
        self.error = False
        self.final_text = TEXT

    def set_completed_callback(self, callback):
        self.callback = callback

    async def finish(self):
        self.finished += 1
        try:
            self.callback(Result(TEXT, Usage(), 0))
            await self.protocol.wait()
            if self.error:
                raise ProviderError("response")
            return Result(self.final_text, Usage(), 0)
        finally:
            await self.aclose()


async def until(predicate):
    async with asyncio.timeout(1):
        while not predicate():
            await asyncio.sleep(0)


def configure(create, client):
    session, connections = create(factory=EarlyConnection)
    session.store.save_settings(
        replace(session.store.load_settings(), polishing_enabled=True)
    )
    session.client, session.inputs = client, Inputs()
    outcomes = []
    session.finished.connect(outcomes.append)
    return session, connections, outcomes


async def begin(session, connections):
    await session.toggle()
    await connections[0].started.wait()
    session.recorder.pcm_ready.emit(b"\1\0" * 2000)
    session.stop_recording()
    return connections[0]


def test_early_whole_prompt_output_waits_for_asr_success_and_follows_focus(
    realtime_sessions,
):
    async def run():
        release = asyncio.Event()
        received = []

        class Client:
            async def polish_stream(self, provider, key, text, prompt, on_delta):
                received.append((text, prompt))
                await on_delta("甲")
                await release.wait()
                await on_delta("乙")
                return Result("甲乙", Usage(), 0)

        session, connections, outcomes = configure(realtime_sessions, Client())
        expected_prompt = session.store.load_prompt(
            session.store.load_settings().prompt
        ).body
        connection = await begin(session, connections)
        await until(lambda: session.inputs.written == "甲")
        assert not outcomes and connection.finished == 1
        session.inputs.focus = "second"
        release.set()
        await until(lambda: session.inputs.written == "甲乙")
        assert not outcomes and session.controller.state == State.INJECTING
        connection.protocol.set()
        await until(lambda: bool(outcomes))
        assert outcomes[0]["outcome"] == "succeeded"
        assert received == [(TEXT, expected_prompt)]
        assert session.inputs.destinations == ["first", "second"]
        assert connection.closed

    asyncio.run(run())


@pytest.mark.parametrize("attempt", [False, True])
@pytest.mark.parametrize("conflict", [False, True])
def test_asr_closure_error_never_succeeds_or_replays(
    realtime_sessions, attempt, conflict
):
    async def run():
        started = asyncio.Event()

        class Client:
            async def polish_stream(self, provider, key, text, prompt, on_delta):
                if attempt:
                    await on_delta("甲")
                started.set()
                await asyncio.Event().wait()

        session, connections, outcomes = configure(realtime_sessions, Client())
        connection = await begin(session, connections)
        await started.wait()
        if attempt:
            await until(lambda: session.inputs.written == "甲")
        connection.error = not conflict
        connection.final_text = "conflicting" if conflict else TEXT
        connection.protocol.set()
        await until(lambda: bool(outcomes))
        assert outcomes[0]["outcome"] == "failed"
        assert session.inputs.written == ("甲" if attempt else "")
        assert connection.closed and connection.finished == 1

    asyncio.run(run())


@pytest.mark.parametrize("attempt", [False, True])
def test_polish_failure_fallback_waits_for_asr_and_is_forbidden_after_attempt(
    realtime_sessions, attempt
):
    async def run():
        trigger = asyncio.Event()
        started = asyncio.Event()

        class Client:
            async def polish_stream(self, provider, key, text, prompt, on_delta):
                if attempt:
                    await on_delta("甲")
                started.set()
                await trigger.wait()
                raise ProviderError("network")

        session, connections, outcomes = configure(realtime_sessions, Client())
        connection = await begin(session, connections)
        await started.wait()
        if attempt:
            await until(lambda: session.inputs.written == "甲")
        trigger.set()
        if attempt:
            await until(lambda: bool(outcomes))
            assert outcomes[0]["outcome"] == "failed"
            assert session.inputs.written == "甲"
        else:
            for _ in range(20):
                await asyncio.sleep(0)
            assert not outcomes and not session.inputs.written
            connection.protocol.set()
            await until(lambda: bool(outcomes))
            assert outcomes[0]["outcome"] == "succeeded"
            assert session.inputs.written == TEXT
        assert connection.closed

    asyncio.run(run())


@pytest.mark.parametrize("action", ["cancel", "expire", "replace"])
def test_early_pipeline_late_callback_cannot_output_after_task_end(
    realtime_sessions, action
):
    async def run():
        started = asyncio.Event()

        class Client:
            async def polish_stream(self, provider, key, text, prompt, on_delta):
                await on_delta("甲")
                started.set()
                await asyncio.Event().wait()

        session, connections, outcomes = configure(realtime_sessions, Client())
        connection = await begin(session, connections)
        await started.wait()
        await until(lambda: session.inputs.written == "甲")
        if action == "expire":
            session.controller.task.deadline = 0
            session.controller.tick()
        else:
            session.cancel()
        await until(lambda: connection.closed)
        if action == "replace":
            session.last_toggle = 0
            await session.toggle()
            await connections[1].started.wait()
        connection.callback(Result("late", Usage(), 0))
        connection.protocol.set()
        for _ in range(20):
            await asyncio.sleep(0)
        assert session.inputs.written == "甲"
        assert len(outcomes) == 1 and outcomes[0]["outcome"] != "succeeded"
        session.cancel()
        await session.close()

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["missing_key", "prestream"])
@pytest.mark.parametrize("asr_error", [False, True])
def test_prestream_error_never_falls_back_before_valid_asr_finish(
    realtime_sessions, failure, asr_error
):
    async def run():
        started = asyncio.Event()

        class Client:
            async def polish_stream(self, *args):
                pytest.fail("prestream failure must precede provider call")

        session, connections, outcomes = configure(realtime_sessions, Client())
        if failure == "missing_key":
            # Credentials are selected by reference; remove the loaded role at
            # the completed callback boundary to exercise the actual key check.
            class MissingKeyConnection(EarlyConnection):
                async def finish(self):
                    session.keys.pop("polishing", None)
                    started.set()
                    return await super().finish()

            session.realtime_factory = lambda *a, **kw: (
                connections.append(MissingKeyConnection(*a, **kw)) or connections[-1]
            )
        else:

            async def fail_before_stream(*args, **kwargs):
                started.set()
                raise ProviderError("network")

            session._stream_polish = fail_before_stream
        connection = await begin(session, connections)
        await started.wait()
        for _ in range(20):
            await asyncio.sleep(0)
        assert not outcomes and not session.inputs.written
        assert not connection.closed
        connection.error = asr_error
        connection.protocol.set()
        await until(lambda: bool(outcomes))
        assert outcomes[0]["outcome"] == ("failed" if asr_error else "succeeded")
        assert session.inputs.written == ("" if asr_error else TEXT)
        assert connection.finished == 1 and connection.closed
        await session.close()

    asyncio.run(run())


@pytest.fixture(scope="module")
def pipeline_tls(tmp_path_factory):
    import test_realtime

    return test_realtime.certificate.__wrapped__(tmp_path_factory)


@pytest.mark.parametrize("closure_first", [False, True])
def test_actual_local_wss_https_sse_overlap_keeps_final_success_barrier(
    realtime_sessions, pipeline_tls, closure_first
):
    import json
    import time

    import httpx
    from test_polish_stream import DONE, STOP, event
    from websockets.asyncio.server import serve

    from inkecho.providers import ProviderClient
    from inkecho.realtime import QwenRealtimeSession

    async def run():
        asr_release, asr_finished, sse_release = (asyncio.Event() for _ in range(3))
        times, errors, bodies = {}, [], []
        began = time.monotonic()

        async def websocket(ws):
            counter = 0

            async def emit(kind, **body):
                nonlocal counter
                counter += 1
                await ws.send(
                    json.dumps({"type": kind, "event_id": str(counter), **body})
                )

            try:
                await emit(
                    "session.created",
                    session={"id": "s1", "model": "qwen3-asr-flash-realtime"},
                )
                async for message in ws:
                    item = json.loads(message)
                    if item["type"] == "session.update":
                        await emit(
                            "session.updated",
                            session={
                                "id": "s1",
                                "model": "qwen3-asr-flash-realtime",
                                **item["session"],
                            },
                        )
                    elif item["type"] == "input_audio_buffer.commit":
                        await emit("input_audio_buffer.committed", item_id="i1")
                    elif item["type"] == "session.finish":
                        times["completed"] = time.monotonic()
                        await emit(
                            "conversation.item.input_audio_transcription.completed",
                            item_id="i1",
                            content_index=0,
                            transcript=TEXT,
                        )
                        await asr_release.wait()
                        times["session_finished"] = time.monotonic()
                        await emit("session.finished")
                        asr_finished.set()
                        break
            except Exception as error:
                errors.append(type(error).__name__)

        async def https(reader, writer):
            try:
                header = await reader.readuntil(b"\r\n\r\n")
                length = next(
                    int(line.split(b":", 1)[1])
                    for line in header.split(b"\r\n")
                    if line.lower().startswith(b"content-length:")
                )
                bodies.append(json.loads(await reader.readexactly(length)))
                writer.write(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: text/event-stream\r\n"
                    b"Connection: close\r\n\r\n" + event("甲")
                )
                await writer.drain()
                await sse_release.wait()
                times["sse_completed"] = time.monotonic()
                writer.write(event("乙") + STOP + DONE)
                await writer.drain()
            except Exception as error:
                errors.append(type(error).__name__)
            finally:
                writer.close()
                await writer.wait_closed()

        async with serve(websocket, "127.0.0.1", 0, ssl=pipeline_tls[0]) as ws_server:
            https_server = await asyncio.start_server(
                https, "127.0.0.1", 0, ssl=pipeline_tls[0]
            )
            async with (
                https_server,
                httpx.AsyncClient(verify=pipeline_tls[1], trust_env=False) as http,
            ):
                session, connections, outcomes = configure(
                    realtime_sessions, ProviderClient(http=http)
                )
                port = ws_server.sockets[0].getsockname()[1]
                provider = session.store.load_provider("qwen")
                session.store.save_provider(
                    replace(
                        provider,
                        parameters={
                            "asr_protocol": "qwen_realtime",
                            "realtime_url": f"wss://127.0.0.1:{port}/realtime",
                        },
                    )
                )
                port = https_server.sockets[0].getsockname()[1]
                provider = session.store.load_provider("deepseek")
                session.store.save_provider(
                    replace(
                        provider,
                        base_url=f"https://127.0.0.1:{port}/v1",
                        model="synthetic-polish",
                    )
                )

                def factory(*args, **kwargs):
                    return QwenRealtimeSession(
                        *args, tls_context=pipeline_tls[1], **kwargs
                    )

                session.realtime_factory = factory
                session.inputs.before_character = lambda: times.setdefault(
                    "first_sent", time.monotonic()
                )
                await session.toggle()
                await session.task_context["realtime_start"]
                session.recorder.pcm_ready.emit(b"\1\0" * 2000)
                session.stop_recording()
                async with asyncio.timeout(3):
                    while session.inputs.written != "甲":
                        await asyncio.sleep(0.001)
                    assert not outcomes
                    if closure_first:
                        asr_release.set()
                        await asr_finished.wait()
                        assert not outcomes and session.inputs.written == "甲"
                        sse_release.set()
                    else:
                        sse_release.set()
                        while session.inputs.written != "甲乙":
                            await asyncio.sleep(0.001)
                        assert not outcomes
                        asr_release.set()
                        await asr_finished.wait()
                    while not outcomes:
                        await asyncio.sleep(0.001)
                assert outcomes[0]["outcome"] == "succeeded"
                assert session.inputs.written == "甲乙"
                assert len(bodies) == 1
                assert bodies[0]["messages"][-1]["content"] == TEXT
                assert times["completed"] < times["first_sent"]
                if closure_first:
                    assert (
                        times["first_sent"]
                        < times["session_finished"]
                        < times["sse_completed"]
                    )
                else:
                    assert (
                        times["first_sent"]
                        < times["sse_completed"]
                        < times["session_finished"]
                    )
                await session.close()
        assert not errors
        print(
            json.dumps(
                {
                    "kind": "synthetic_audio_local_TLS_WSS_SSE",
                    "closure_first": closure_first,
                    "events_ms": {k: (v - began) * 1000 for k, v in times.items()},
                    "cloud_requests": 0,
                    "physical_keyboard": False,
                }
            )
        )

    asyncio.run(run())
