"""RAM-only draft display never supplies final recognition or keyboard output."""

import asyncio
from dataclasses import replace

import test_application_realtime as fixtures
from test_realtime import certificate  # noqa: F401

from inkecho.config import DEFAULT_PROVIDERS, ConfigStore
from inkecho.core import State
from inkecho.realtime import QwenRealtimeSession, RealtimeConfig


def test_preview_is_replaceable_and_independent_of_final():
    async def scenario():
        connection = QwenRealtimeSession(
            RealtimeConfig(
                "wss://fixture.invalid/realtime", "qwen3-asr-flash-realtime"
            ),
            "synthetic-not-a-key",
            timeout_seconds=1,
            deadline=None,
            active=lambda: True,
        )
        previews, completed = [], []
        connection.set_preview_callback(previews.append)
        connection.set_completed_callback(completed.append)
        connection._ready = asyncio.get_running_loop().create_future()
        connection._ready.set_result(None)
        connection._done = asyncio.get_running_loop().create_future()
        event = {
            "type": "conversation.item.input_audio_transcription.text",
            "text": "你好",
            "stash": "世界",
            "content_index": 0,
        }
        await connection._event(event)
        await connection._event({**event, "stash": "朋友"})
        assert previews == ["你好世界", "你好朋友"]
        assert completed == [] and connection._transcript is None
        assert not connection._done.done()
        for bad in (
            {"text": []},
            {"stash": 12},
            {"text": "x" * 100001},
            {"content_index": False},
        ):
            await connection._event({**event, **bad})
        assert len(previews) == 2
        await connection.aclose()
        await connection._event(event)
        assert len(previews) == 2

    asyncio.run(scenario())


class PreviewConnection(fixtures.Connection):
    def set_preview_callback(self, callback):
        self.preview_callback = callback


def test_session_preview_cancellation_and_replaced_task(tmp_path):
    async def scenario():
        store = ConfigStore(tmp_path)
        store.initialize()
        for provider in DEFAULT_PROVIDERS:
            store.save_provider(provider)
        create = fixtures.sessions.__wrapped__(tmp_path)
        session, connections = create(factory=PreviewConnection)
        session.store.save_settings(
            replace(
                session.store.load_settings(),
                transcription_provider="qwen",
                polishing_enabled=False,
            )
        )
        previews = []
        session.preview.connect(previews.append)
        await session.toggle()
        old = connections[0]
        await old.started.wait()
        old.preview_callback("临时草稿")
        assert previews[-1] == "临时草稿"
        assert session.controller.state == State.RECORDING
        assert session.inputs.inserted == []
        session.cancel()
        assert previews[-1] == ""
        old.preview_callback("取消后的迟到草稿")
        assert previews[-1] == ""
        await fixtures.settle(session)
        session.last_toggle = 0
        await session.toggle()
        await connections[1].started.wait()
        old.preview_callback("旧任务草稿")
        assert previews[-1] == ""
        connections[1].preview_callback("新草稿")
        assert previews[-1] == "新草稿"
        session.cancel()
        await session.close()

    asyncio.run(scenario())


def test_unconfigured_recording_requests_saved_voice_model(tmp_path):
    async def scenario():
        store = ConfigStore(tmp_path)
        store.initialize()
        for provider in DEFAULT_PROVIDERS:
            store.save_provider(provider)
        create = fixtures.sessions.__wrapped__(tmp_path)
        session, _ = create()
        session.store.save_settings(
            replace(
                session.store.load_settings(),
                transcription_provider="",
            )
        )
        problems = []
        session.problem.connect(problems.append)
        await session.toggle()
        assert problems and "保存语音模型" in problems[-1]
        assert not session.recorder.recording
        await session.close()

    asyncio.run(scenario())


def test_actual_local_wss_preview_never_replaces_final(certificate):  # noqa: F811
    from test_realtime import FINAL, exercise

    async def operation(connection, state):
        previews, finals = [], []
        connection.set_preview_callback(previews.append)
        connection.set_completed_callback(lambda result: finals.append(result.text))
        await connection.start()
        connection.feed_nowait(b"\1\0" * 2000)
        result = await connection.finish()
        assert previews == ["wrong previewdraft"]
        assert finals == [FINAL] and result.text == FINAL

    asyncio.run(exercise(certificate, operation))


def test_completed_blocks_late_draft_and_malformed_drafts_preserve_final():
    async def scenario():
        connection = QwenRealtimeSession(
            RealtimeConfig(
                "wss://fixture.invalid/realtime", "qwen3-asr-flash-realtime"
            ),
            "synthetic-not-a-key",
            timeout_seconds=1,
            active=lambda: True,
        )
        previews, completed = [], []
        connection.set_preview_callback(previews.append)
        connection.set_completed_callback(lambda result: completed.append(result.text))
        loop = asyncio.get_running_loop()
        connection._ready, connection._done = loop.create_future(), loop.create_future()
        connection._ready.set_result(None)
        draft = {
            "type": "conversation.item.input_audio_transcription.text",
            "content_index": 0,
            "text": "前缀",
            "stash": "草稿",
        }
        await connection._event(draft)
        for values in (
            {"text": None},
            {"stash": {"secret": "not rendered"}},
            {"text": "x" * 100000, "stash": "x"},
        ):
            await connection._event({**draft, **values})
        assert previews == ["前缀草稿"]
        connection._commit_sent = True
        await connection._event(
            {"type": "input_audio_buffer.committed", "item_id": "i1"}
        )
        await connection._event(
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "item_id": "i1",
                "content_index": 0,
                "transcript": "最终正文",
            }
        )
        assert completed == ["最终正文"] and not connection._done.done()
        await connection._event({**draft, "text": "最终后的迟到草稿"})
        assert previews == ["前缀草稿"]
        assert connection._transcript == "最终正文"
        connection._finish_sent = True
        await connection._event({"type": "session.finished"})
        assert connection._done.result() == "最终正文"
        await connection.aclose()

    asyncio.run(scenario())


def test_http_recording_emits_no_synthetic_live_text(tmp_path):
    from inkecho.app import Session
    from inkecho.providers import Result, Usage

    async def scenario():
        store = ConfigStore(tmp_path)
        store.initialize()
        provider = next(item for item in DEFAULT_PROVIDERS if item.id == "qwen")
        store.save_provider(replace(provider, model="qwen3-asr-flash", parameters={}))
        store.save_settings(
            replace(
                store.load_settings(),
                transcription_provider="qwen",
                polishing_enabled=False,
            )
        )

        class HttpClient:
            async def transcribe(self, *_args):
                return Result("HTTP最终正文", Usage(), 0)

        def no_realtime(*_args, **_kwargs):
            raise AssertionError("HTTP must not create a streaming connection")

        session = Session(
            store,
            inputs=fixtures.Inputs(),
            recorder=fixtures.Recorder(),
            client=HttpClient(),
            realtime_factory=no_realtime,
        )

        async def key(_reference):
            return "synthetic-not-a-key"

        session.key = key
        previews = []
        session.preview.connect(previews.append)
        await session.toggle()
        assert session.recorder.recording
        assert not any(previews)
        session.recorder.finished.emit(b"synthetic-wav", 1.0)
        await fixtures.settle(session)
        assert not any(previews)
        assert session.inputs.inserted == ["HTTP最终正文"]
        await session.close()

    asyncio.run(scenario())
