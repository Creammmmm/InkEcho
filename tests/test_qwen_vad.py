"""Qwen VAD multi-item protocol; synthetic loopback audio, no cloud or microphone."""

import asyncio
import json
import time
from dataclasses import replace

import pytest
from test_realtime import MODEL, certificate, provider  # noqa: F401
from websockets.asyncio.server import serve

from inkecho.asr_streaming import create_streaming_session
from inkecho.providers import ProviderError
from inkecho.qwen_vad import MAX_ITEMS, QwenVadSession
from inkecho.realtime import QwenRealtimeSession, RealtimeConfig


def ready_session():
    session = QwenVadSession(
        RealtimeConfig("wss://fixture.invalid/ws", MODEL, server_vad=True), "synthetic"
    )
    loop = asyncio.get_running_loop()
    session._ready = loop.create_future()
    session._ready.set_result(None)
    session._done = loop.create_future()
    session._began = time.monotonic()
    return session


def test_official_vad_selection_and_explicit_manual_gateway():
    official = RealtimeConfig.from_provider(provider())
    assert official.server_vad
    assert isinstance(
        create_streaming_session(
            provider(), official, "synthetic", qwen_factory=QwenRealtimeSession
        ),
        QwenVadSession,
    )
    custom = replace(
        provider(),
        parameters={
            "asr_protocol": "qwen_realtime",
            "realtime_url": "wss://fixture.invalid/ws",
        },
    )
    assert not RealtimeConfig.from_provider(custom).server_vad
    explicit = replace(
        custom, parameters={**custom.parameters, "turn_detection": "server_vad"}
    )
    assert RealtimeConfig.from_provider(explicit).server_vad
    manual = replace(
        provider(),
        parameters={"asr_protocol": "qwen_realtime", "turn_detection": "manual"},
    )
    assert not RealtimeConfig.from_provider(manual).server_vad


def test_vad_keeps_commit_order_even_when_finals_arrive_out_of_order():
    async def scenario():
        session = ready_session()
        previews, completed = [], []
        session.set_preview_callback(previews.append)
        session.set_completed_callback(completed.append)
        for item, previous in (("one", None), ("two", "one")):
            await session._event(
                {
                    "type": "input_audio_buffer.committed",
                    "item_id": item,
                    "previous_item_id": previous,
                }
            )
        for item, text in (("two", "乙"), ("one", "甲")):
            await session._event(
                {
                    "type": "conversation.item.input_audio_transcription.completed",
                    "item_id": item,
                    "transcript": text,
                }
            )
        assert not completed and previews[-1] == "甲乙"
        session._finish_sent = True
        await session._event({"type": "session.finished"})
        assert session._done.result() == "甲乙" and completed[0].text == "甲乙"
        await session.aclose()
        assert not session._items and not session._committed

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "mode",
    [
        "missing_final",
        "missing_commit",
        "conflicting_final",
        "wrong_previous",
        "early_finish",
        "invalid_index",
    ],
)
def test_vad_rejects_incomplete_or_conflicting_protocol(mode):
    async def scenario():
        session = ready_session()
        await session._event(
            {"type": "input_audio_buffer.speech_started", "item_id": "one"}
        )
        if mode == "missing_commit":
            event = {
                "type": "conversation.item.input_audio_transcription.completed",
                "item_id": "one",
                "transcript": "甲",
            }
        else:
            await session._event(
                {"type": "input_audio_buffer.committed", "item_id": "one"}
            )
            if mode == "wrong_previous":
                event = {
                    "type": "input_audio_buffer.committed",
                    "item_id": "two",
                    "previous_item_id": "unknown",
                }
            elif mode == "invalid_index":
                event = {
                    "type": "conversation.item.input_audio_transcription.completed",
                    "item_id": "one",
                    "transcript": "甲",
                    "content_index": True,
                }
            elif mode == "conflicting_final":
                await session._event(
                    {
                        "type": "conversation.item.input_audio_transcription.completed",
                        "item_id": "one",
                        "transcript": "甲",
                    }
                )
                event = {
                    "type": "conversation.item.input_audio_transcription.completed",
                    "item_id": "one",
                    "transcript": "乙",
                }
            else:
                session._finish_sent = mode != "early_finish"
                event = {"type": "session.finished"}
        with pytest.raises(ProviderError, match="response"):
            await session._event(event)
        assert not session._done.done()
        await session.aclose()

    asyncio.run(scenario())


def test_vad_duplicate_identical_final_is_not_duplicated_and_no_speech_is_empty():
    async def scenario():
        session = ready_session()
        await session._event({"type": "input_audio_buffer.committed", "item_id": "one"})
        event = {
            "type": "conversation.item.input_audio_transcription.completed",
            "item_id": "one",
            "transcript": "甲",
        }
        await session._event(event)
        await session._event(event)
        assert session._text() == "甲"
        await session.aclose()
        empty = ready_session()
        empty._finish_sent = True
        await empty._event({"type": "session.finished"})
        assert empty._done.result() == ""
        await empty.aclose()

    asyncio.run(scenario())


def test_vad_bounds_item_count():
    async def scenario():
        session = ready_session()
        for number in range(MAX_ITEMS):
            session._item({"item_id": str(number)})
        with pytest.raises(ProviderError):
            session._item({"item_id": "overflow"})
        await session.aclose()

    asyncio.run(scenario())


def test_loopback_vad_previews_before_stop_and_finish_flushes_last_segment(
    certificate,  # noqa: F811
):
    async def scenario():
        server_context, client_context = certificate
        events, previews, finals, errors = [], [], [], []
        first_preview = asyncio.Event()

        async def handler(ws):
            counter = 0
            sent_first = False

            async def send(kind, **body):
                nonlocal counter
                counter += 1
                await ws.send(
                    json.dumps({"type": kind, "event_id": str(counter), **body})
                )

            await send("session.created", session={"id": "s1", "model": MODEL})
            try:
                async for wire in ws:
                    event = json.loads(wire)
                    events.append(event["type"])
                    if event["type"] == "session.update":
                        assert event["session"]["turn_detection"] == {
                            "type": "server_vad",
                            "threshold": 0.0,
                            "silence_duration_ms": 400,
                        }
                        await send(
                            "session.updated",
                            session={"id": "s1", "model": MODEL, **event["session"]},
                        )
                    elif (
                        event["type"] == "input_audio_buffer.append" and not sent_first
                    ):
                        sent_first = True
                        await send("input_audio_buffer.speech_started", item_id="one")
                        await send(
                            "conversation.item.input_audio_transcription.text",
                            item_id="one",
                            text="甲",
                            stash="草稿",
                        )
                        await send("input_audio_buffer.speech_stopped", item_id="one")
                        await send(
                            "input_audio_buffer.committed",
                            item_id="one",
                            previous_item_id=None,
                        )
                        await send(
                            "conversation.item.input_audio_transcription.completed",
                            item_id="one",
                            transcript="甲。",
                        )
                        await send("input_audio_buffer.speech_started", item_id="two")
                    elif event["type"] == "session.finish":
                        await send("input_audio_buffer.speech_stopped", item_id="two")
                        await send(
                            "input_audio_buffer.committed",
                            item_id="two",
                            previous_item_id="one",
                        )
                        await send(
                            "conversation.item.input_audio_transcription.completed",
                            item_id="two",
                            transcript="乙。",
                        )
                        await send("session.finished")
                        break
            except Exception as error:
                errors.append(type(error).__name__)

        async with serve(handler, "127.0.0.1", 0, ssl=server_context) as server:
            port = server.sockets[0].getsockname()[1]
            session = QwenVadSession(
                RealtimeConfig(f"wss://127.0.0.1:{port}/ws", MODEL, server_vad=True),
                "synthetic",
                tls_context=client_context,
            )

            def preview(text):
                previews.append(text)
                if text == "甲。":
                    first_preview.set()

            session.set_preview_callback(preview)
            session.set_completed_callback(finals.append)
            await session.start()
            session.feed_nowait(b"\x01\x00" * 1600)
            await asyncio.wait_for(first_preview.wait(), 1)
            assert not finals and not session._finishing
            result = await session.finish()
            assert result.text == "甲。乙。" and finals[0].text == result.text
            assert "input_audio_buffer.commit" not in events
            assert previews[:2] == ["甲草稿", "甲。"]
            assert not session._items and not errors

    asyncio.run(scenario())


def test_vad_cancel_clears_previews_and_never_completes_a_pending_segment():
    async def scenario():
        session = ready_session()
        finals = []
        session.set_completed_callback(finals.append)
        await session._event({"type": "input_audio_buffer.committed", "item_id": "one"})
        await session._event(
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "item_id": "one",
                "transcript": "甲",
            }
        )
        await session.aclose()
        assert not finals and not session._items and session._on_preview is None
        assert not session._done.done()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "mode", ["unknown", "duplicate_commit", "conflicting_id", "oversized_total"]
)
def test_vad_rejects_ambiguous_or_unbounded_events(mode):
    async def scenario():
        session = ready_session()
        if mode == "unknown":
            event = {"type": "unknown", "item_id": "one"}
        elif mode == "conflicting_id":
            event = {"type": "input_audio_buffer.committed", "item_id": ""}
        else:
            await session._event(
                {"type": "input_audio_buffer.committed", "item_id": "one"}
            )
            if mode == "duplicate_commit":
                event = {"type": "input_audio_buffer.committed", "item_id": "one"}
            else:
                await session._event(
                    {
                        "type": "conversation.item.input_audio_transcription.completed",
                        "item_id": "one",
                        "transcript": "a" * 100000,
                    }
                )
                await session._event(
                    {
                        "type": "input_audio_buffer.committed",
                        "item_id": "two",
                        "previous_item_id": "one",
                    }
                )
                event = {
                    "type": "conversation.item.input_audio_transcription.completed",
                    "item_id": "two",
                    "transcript": "b",
                }
        with pytest.raises(ProviderError):
            await session._event(event)
        assert not session._done.done()
        await session.aclose()

    asyncio.run(scenario())


def test_production_session_selects_vad_and_gates_final_on_finish_and_consent(
    certificate,  # noqa: F811
    monkeypatch,
    tmp_path,
):
    from PySide6.QtCore import QCoreApplication
    from test_application_realtime import Inputs, NoHttp, Recorder

    import inkecho.realtime as wire
    from inkecho.app import Session
    from inkecho.config import ConfigStore, Settings

    app = QCoreApplication.instance() or QCoreApplication([])
    assert app is not None

    async def scenario():
        server_context, client_context = certificate
        previewed, finish_sent, consent_entered, consent_release = (
            asyncio.Event() for _ in range(4)
        )
        errors, commands = [], []

        async def handler(ws):
            counter = 0
            first = False

            async def emit(kind, **body):
                nonlocal counter
                counter += 1
                await ws.send(
                    json.dumps({"type": kind, "event_id": str(counter), **body})
                )

            await emit("session.created", session={"id": "s1", "model": MODEL})
            try:
                async for message in ws:
                    event = json.loads(message)
                    commands.append(event["type"])
                    if event["type"] == "session.update":
                        await emit(
                            "session.updated",
                            session={"id": "s1", "model": MODEL, **event["session"]},
                        )
                    elif event["type"] == "input_audio_buffer.append" and not first:
                        first = True
                        await emit("input_audio_buffer.speech_started", item_id="one")
                        await emit("input_audio_buffer.speech_stopped", item_id="one")
                        await emit(
                            "input_audio_buffer.committed",
                            item_id="one",
                            previous_item_id=None,
                        )
                        await emit(
                            "conversation.item.input_audio_transcription.completed",
                            item_id="one",
                            transcript="首句。",
                        )
                        await emit("input_audio_buffer.speech_started", item_id="two")
                    elif event["type"] == "session.finish":
                        await emit(
                            "input_audio_buffer.committed",
                            item_id="two",
                            previous_item_id="one",
                        )
                        await emit(
                            "conversation.item.input_audio_transcription.completed",
                            item_id="two",
                            transcript="尾句。",
                        )
                        await emit("session.finished")
                        finish_sent.set()
                        break
            except Exception as error:
                errors.append(type(error).__name__)

        async with serve(handler, "127.0.0.1", 0, ssl=server_context) as server:
            port = server.sockets[0].getsockname()[1]
            direct = wire._DirectConnect

            def local_socket(_url, **options):
                options["ssl"] = client_context
                return direct(f"wss://127.0.0.1:{port}/ws", **options)

            monkeypatch.setattr(wire, "_DirectConnect", local_socket)
            store = ConfigStore(tmp_path)
            store.initialize()
            store.save_provider(provider())
            store.save_settings(
                replace(
                    Settings(),
                    transcription_provider=provider().id,
                    polishing_enabled=False,
                )
            )
            session = Session(
                store, recorder=Recorder(), inputs=Inputs(), client=NoHttp()
            )
            session.inputs.authorized = False
            done = asyncio.get_running_loop().create_future()
            session.finished.connect(
                lambda result: done.set_result(result) if not done.done() else None
            )

            async def key(_reference):
                return "synthetic"

            async def consent():
                consent_entered.set()
                await consent_release.wait()
                session.inputs.authorized = True

            session.key = key
            session.inputs.authorize = consent
            session.preview.connect(
                lambda text: previewed.set() if text == "首句。" else None
            )
            toggle = asyncio.create_task(session.toggle())
            await asyncio.wait_for(consent_entered.wait(), 1)
            assert isinstance(session.task_context["realtime"], QwenVadSession)
            session.recorder.pcm_ready.emit(b"\x01\x00" * 1600)
            await asyncio.wait_for(previewed.wait(), 1)
            assert session.recorder.recording and not session.inputs.inserted
            session.stop_recording()
            await asyncio.wait_for(finish_sent.wait(), 1)
            for _ in range(10):
                await asyncio.sleep(0)
            assert not session.inputs.inserted
            consent_release.set()
            await toggle
            await asyncio.wait_for(done, 1)
            assert session.inputs.inserted == ["首句。尾句。"]
            assert "input_audio_buffer.commit" not in commands and not errors
            await session.close()

    asyncio.run(scenario())
