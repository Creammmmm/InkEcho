"""Synthetic orchestration; WSS protocol and real microphones have separate gates."""

import asyncio
import time
from dataclasses import replace

import pytest
from PySide6.QtCore import QObject, Signal

from inkecho.app import Session
from inkecho.config import ConfigStore
from inkecho.core import State
from inkecho.providers import ProviderError, Result, Usage


class Recorder(QObject):
    level = Signal(float)
    pcm_ready = Signal(bytes)
    finished = Signal(bytes, float)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.recording = False
        self.options = None

    def start(self, _device, **options):
        self.options = options
        self.recording = True
        return True

    def stop(self):
        self.recording = False
        self.finished.emit(b"", 1.0)

    def cancel(self):
        self.recording = False


class Inputs:
    connected = True
    authorized = True

    def __init__(self):
        self.inserted = []

    async def insert(self, text, can_continue, *, deadline=None):
        assert can_continue()
        self.inserted.append(text)
        return len(text)

    async def aclose(self):
        pass


class NoHttp:
    async def transcribe(self, *_args):
        pytest.fail("Explicit realtime must not upload a completed HTTP recording")


class Connection:
    def __init__(self, _config, _key, **kwargs):
        self.active = kwargs["active"]
        self.deadline = kwargs["deadline"]
        self.timeout = kwargs["timeout_seconds"]
        self.started = asyncio.Event()
        self.start_release = asyncio.Event()
        self.start_release.set()
        self.failure = asyncio.Event()
        self.pcm = []
        self.finished = 0
        self.closed = False
        self.finish_release = None

    async def start(self):
        self.started.set()
        await self.start_release.wait()

    def feed_nowait(self, pcm):
        assert self.active() and not self.closed
        self.pcm.append(pcm)

    async def finish(self):
        self.finished += 1
        if self.finish_release is not None:
            try:
                await self.finish_release.wait()
            except asyncio.CancelledError:
                await self.finish_release.wait()
        return Result("实时识别。", Usage(), 0)

    async def wait_failure(self):
        await self.failure.wait()
        if self.closed:
            raise asyncio.CancelledError
        raise ProviderError("network")

    async def aclose(self):
        self.closed = True
        self.failure.set()


@pytest.fixture
def sessions(tmp_path):
    store = ConfigStore(tmp_path)
    store.initialize()
    provider = store.load_provider("qwen")
    store.save_provider(
        replace(
            provider,
            model="qwen3-asr-flash-realtime",
            parameters={
                "asr_protocol": "qwen_realtime",
                "realtime_url": "wss://fixture.invalid/realtime",
            },
        )
    )

    def create(*, factory=Connection):
        connections = []

        def connect(*args, **kwargs):
            connection = factory(*args, **kwargs)
            connections.append(connection)
            return connection

        session = Session(
            store,
            inputs=Inputs(),
            recorder=Recorder(),
            client=NoHttp(),
            realtime_factory=connect,
        )

        async def key(_reference):
            return "synthetic-not-a-key"

        session.key = key
        return session, connections

    return create


async def settle(session):
    for _ in range(50):
        await asyncio.sleep(0)
        if not session.pending:
            return
    raise AssertionError("Synthetic task did not settle")


def test_realtime_upload_begins_during_recording_and_stop_waits_for_final(sessions):
    async def scenario():
        session, connections = sessions()
        await session.toggle()
        connection = connections[0]
        await connection.started.wait()
        assert session.recorder.recording
        assert session.recorder.options["streaming"] is True
        session.recorder.pcm_ready.emit(b"\1\0" * 2000)
        assert connection.pcm == [b"\1\0" * 2000]
        assert connection.finished == 0 and not session.inputs.inserted
        session.stop_recording()
        await settle(session)
        assert connection.finished == 1 and connection.closed
        assert session.inputs.inserted == ["实时识别。"]
        events = session.last_performance["events_ms"]
        assert events["asr_started"] < events["recording_stop_requested"]
        assert events["asr_completed"] >= events["recording_stopped"]
        await session.close()

    asyncio.run(scenario())


def test_stopping_before_websocket_handshake_waits_without_second_audio_upload(
    sessions,
):
    async def scenario():
        def delayed(*args, **kwargs):
            connection = Connection(*args, **kwargs)
            connection.start_release.clear()
            return connection

        session, connections = sessions(factory=delayed)
        await session.toggle()
        connection = connections[0]
        session.recorder.pcm_ready.emit(b"\0\0" * 100)
        session.stop_recording()
        await asyncio.sleep(0)
        assert connection.finished == 0
        connection.start_release.set()
        await settle(session)
        assert connection.finished == 1
        assert session.inputs.inserted == ["实时识别。"]
        await session.close()

    asyncio.run(scenario())


def test_socket_failure_during_recording_stops_microphone_without_waiting_for_stop(
    sessions,
):
    async def scenario():
        session, connections = sessions()
        diagnostics = []
        session.diagnostic.connect(diagnostics.append)
        await session.toggle()
        await connections[0].started.wait()
        connections[0].failure.set()
        await settle(session)
        assert session.controller.outcome == State.FAILED
        assert not session.recorder.recording and connections[0].closed
        assert not session.inputs.inserted and connections[0].finished == 0
        assert "network" in diagnostics
        assert session.last_performance["events_ms"]["output_completed"] is None
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("action", ["cancel", "expire", "replace"])
def test_cancel_expiry_and_replacement_stop_pcm_and_ignore_late_final(sessions, action):
    async def scenario():
        session, connections = sessions()
        await session.toggle()
        connection = connections[0]
        connection.finish_release = asyncio.Event()
        session.recorder.pcm_ready.emit(b"\0\0" * 100)
        session.stop_recording()
        for _ in range(10):
            await asyncio.sleep(0)
            if connection.finished:
                break
        assert connection.finished == 1
        if action == "expire":
            session.controller.task.deadline = time.monotonic() - 1
            session.controller.tick()
        else:
            session.cancel()
        if action == "replace":
            session.last_toggle = 0
            await session.toggle()
            assert session.controller.state == State.RECORDING
        else:
            session.recorder.pcm_ready.emit(b"\0\0" * 100)
            assert len(connection.pcm) == 1
        connection.finish_release.set()
        for _ in range(20):
            await asyncio.sleep(0)
        assert connection.closed and not session.inputs.inserted
        if action == "replace":
            assert session.controller.state == State.RECORDING
            assert not connections[1].closed
        await session.close()

    asyncio.run(scenario())


def test_realtime_preflight_rejects_non_16k_before_keys_or_microphone(sessions):
    async def scenario():
        session, connections = sessions()
        session.store.save_settings(replace(session.settings, sample_rate=48000))

        async def forbidden(_reference):
            pytest.fail("Invalid realtime sample format must be rejected before keys")

        session.key = forbidden
        diagnostics = []
        session.diagnostic.connect(diagnostics.append)
        await session.toggle()
        assert diagnostics == ["configuration"]
        assert not connections and not session.recorder.recording
        await session.close()

    asyncio.run(scenario())


def test_realtime_constructor_failure_does_not_leave_recording_task(sessions):
    async def scenario():
        def rejected(*_args, **_kwargs):
            raise ProviderError("configuration")

        session, _connections = sessions(factory=rejected)
        await session.toggle()
        assert session.controller.task is None
        assert session.controller.outcome == State.FAILED
        assert not session.recorder.recording
        assert session.last_performance["outcome"] == "failed"
        await session.close()

    asyncio.run(scenario())


def test_explicit_realtime_rejects_known_http_model_before_external_access(sessions):
    async def scenario():
        session, connections = sessions()
        provider = session.store.load_provider("qwen")
        session.store.save_provider(replace(provider, model="qwen3-asr-flash"))

        async def forbidden(*_args, **_options):
            pytest.fail("Protocol preflight must precede keys or desktop authorization")

        session.key = forbidden
        session.authorize_input = forbidden
        diagnostics = []
        session.diagnostic.connect(diagnostics.append)
        await session.toggle()
        assert diagnostics == ["protocol"]
        assert not connections and not session.recorder.recording
        await session.close()

    asyncio.run(scenario())
