"""Orchestrator safety acceptance; fake IO, not a desktop compatibility claim."""

import asyncio
from dataclasses import replace

import pytest
from PySide6.QtCore import QObject, Signal
from qasync import QEventLoop

from inkecho.app import Session
from inkecho.config import ConfigStore
from inkecho.core import State
from inkecho.providers import ProviderError, Result, Usage


class Inputs:
    def __init__(self):
        self.focus = None
        self.authorized = False
        self.delivered = []

    async def connect(self):
        pass

    async def authorize(self):
        self.authorized = True

    async def insert(self, text, can_continue, *, deadline=None):
        if not can_continue():
            raise RuntimeError("Invalid task")
        self.delivered.append(text)
        return len(text)

    async def aclose(self):
        pass


class Recorder(QObject):
    level = Signal(float)
    finished = Signal(bytes, float)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.starts = 0

    def start(self, *_args, **_kwargs):
        self.starts += 1
        return True

    def cancel(self):
        pass


class Secrets:
    def get(self, _reference):
        return "temporary-test-key"


class Client:
    async def transcribe(self, *_args):
        return Result("识别原文", Usage(), 0.01)

    async def polish(self, *_args):
        raise ProviderError("network")


@pytest.fixture
def setup(tmp_path, monkeypatch, qt_app):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    store = ConfigStore(tmp_path)
    store.initialize()
    # Legacy configured-user fixture; first-run now intentionally stays empty.
    from inkecho.config import DEFAULT_PROVIDERS

    for provider in DEFAULT_PROVIDERS:
        store.save_provider(provider)
    store.save_settings(
        replace(
            store.load_settings(),
            transcription_provider="qwen",
            polishing_provider="deepseek",
        )
    )
    for provider in store.providers():
        store.save_provider(replace(provider, model="test-model"))
    return store, Inputs(), Recorder()


def test_focus_change_during_key_lookup_does_not_prevent_recording(setup):
    async def run():
        store, inputs, recorder = setup
        session = Session(store, inputs=inputs, recorder=recorder, secrets=Secrets())
        requested, release = asyncio.Event(), asyncio.Event()

        async def delayed_key(_reference):
            requested.set()
            await release.wait()
            return "temporary-test-key"

        session.key = delayed_key
        await session.initialize()
        task = asyncio.create_task(session.toggle())
        try:
            await asyncio.wait_for(requested.wait(), 2)
            inputs.focus = "new-window"
            release.set()
            await task
            assert recorder.starts == 1
            assert session.controller.state == State.RECORDING
        finally:
            await session.close()

    asyncio.run(asyncio.wait_for(run(), 5))


def test_late_provider_reply_cannot_change_a_new_recording(setup):
    async def run():
        store, inputs, recorder = setup
        started, release = asyncio.Event(), asyncio.Event()

        class LateClient(Client):
            async def transcribe(self, *_args):
                started.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    await release.wait()  # Exercise an adversarial late callback.
                return Result("迟到结果", Usage(), 2)

        session = Session(
            store,
            inputs=inputs,
            recorder=recorder,
            client=LateClient(),
            secrets=Secrets(),
        )

        async def key(_reference):
            return "temporary-test-key"

        session.key = key
        try:
            await session.initialize()
            await session.toggle()
            recorder.finished.emit(b"fake audio", 1)
            await asyncio.wait_for(started.wait(), 2)
            old_task = next(iter(session.pending))
            session.cancel()
            session.last_toggle = 0
            await session.toggle()
            new_id = session.controller.task.id
            expected = session.metrics.copy()
            release.set()
            await old_task
            assert session.controller.task.id == new_id
            assert session.controller.state == State.RECORDING
            assert session.metrics == expected
            assert not inputs.delivered
        finally:
            release.set()
            await session.close()

    asyncio.run(asyncio.wait_for(run(), 5))


@pytest.mark.parametrize("fallback", [True, False])
def test_polishing_failure_policy_reaches_delivery_or_failure(setup, fallback):
    async def run():
        store, inputs, recorder = setup
        store.save_settings(
            replace(
                store.load_settings(),
                polishing_enabled=True,
                polishing_fallback=fallback,
            )
        )
        session = Session(
            store, inputs=inputs, recorder=recorder, client=Client(), secrets=Secrets()
        )

        async def key(_reference):
            return "temporary-test-key"

        session.key = key
        try:
            await session.initialize()
            await session.toggle()
            recorder.finished.emit(b"fake audio", 1)
            for _ in range(20):
                await asyncio.sleep(0)
                if not session.controller.task:
                    break
            assert inputs.delivered == (["识别原文"] if fallback else [])
            assert session.controller.outcome == (
                State.SUCCEEDED if fallback else State.FAILED
            )
            assert not session.keys
        finally:
            await session.close()

    asyncio.run(asyncio.wait_for(run(), 5))


def test_qasync_credential_worker_and_delivery_complete(setup, qt_app):
    """Exercise the real threaded key lookup on the UI's actual event loop."""

    async def run():
        store, inputs, recorder = setup
        session = Session(
            store, inputs=inputs, recorder=recorder, client=Client(), secrets=Secrets()
        )
        finished = asyncio.Event()
        session.finished.connect(lambda _result: finished.set())
        try:
            await session.initialize()
            await session.toggle()
            assert recorder.starts == 1
            recorder.finished.emit(b"fake audio", 1)
            await finished.wait()
            assert inputs.delivered == ["识别原文"]
            assert session.controller.outcome == State.SUCCEEDED
            assert not session.keys
        finally:
            await session.close()

    with QEventLoop(qt_app) as loop:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(asyncio.wait_for(run(), 5))
    asyncio.set_event_loop(None)
