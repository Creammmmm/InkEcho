"""Orchestration regressions; real desktop acceptance is recorded separately."""

import asyncio
from dataclasses import replace

import pytest
from PySide6.QtCore import QObject, Signal

from inkecho.app import Session
from inkecho.config import ConfigStore
from inkecho.core import State
from inkecho.providers import ProviderError, Result, Usage


class Inputs:
    def __init__(self):
        self.generation = 0
        self.inserted = []

    async def connect(self):
        pass

    async def capture_target(self):
        return self.generation

    def target_is_current(self, target):
        return target == self.generation

    async def inject(self, target, text, can_continue):
        if self.target_is_current(target) and can_continue():
            self.inserted.append(text)

    def close(self):
        pass


class Recorder(QObject):
    level = Signal(float)
    finished = Signal(bytes, float)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.recording = False

    def start(self, *_args, **_kwargs):
        self.recording = True
        return True

    def stop(self):
        self.recording = False
        self.finished.emit(b"test-wav", 2)

    def cancel(self):
        self.recording = False


class Client:
    async def transcribe(self, *_args):
        return Result("你好 InkEcho", Usage(), 0.1)

    async def polish(self, *_args):
        return Result("你好，InkEcho。", Usage(3, 4, 7), 0.1)


@pytest.fixture
def factory(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    store = ConfigStore(tmp_path)
    store.initialize()
    store.save_provider(replace(store.load_provider("qwen"), model="test-asr"))
    store.save_provider(replace(store.load_provider("deepseek"), model="test-polish"))

    def create(**kwargs):
        session = Session(
            store,
            inputs=Inputs(),
            recorder=Recorder(),
            client=kwargs.get("client", Client()),
        )

        async def key(_reference):
            return "disposable-test-key"

        session.key = key
        return session

    return create


async def complete(session):
    for _ in range(20):
        await asyncio.sleep(0)
        if not session.pending:
            return
    raise AssertionError("Workflow did not finish")


def test_successful_transcription_and_polishing(factory):
    async def scenario():
        session = factory()
        session.store.save_settings(replace(session.settings, polishing_enabled=True))
        outcomes = []
        session.finished.connect(outcomes.append)
        await session.initialize()
        await session.toggle()
        assert session.recorder.recording
        session.recorder.stop()
        await complete(session)
        assert session.inputs.inserted == ["你好，InkEcho。"]
        assert outcomes[0]["outcome"] == "succeeded"
        assert outcomes[0]["usage"].total_tokens == 7
        await session.close()

    asyncio.run(scenario())


def test_provider_authentication_has_specific_safe_message(factory):
    class FailedClient(Client):
        async def transcribe(self, *_args):
            raise ProviderError("authentication")

    async def scenario():
        session = factory(client=FailedClient())
        messages = []
        session.status.connect(messages.append)
        await session.initialize()
        await session.toggle()
        session.recorder.stop()
        await complete(session)
        assert session.controller.outcome == State.FAILED
        assert "服务拒绝了密钥或账户权限。" in messages
        assert not session.inputs.inserted
        await session.close()

    asyncio.run(scenario())


def test_focus_change_during_keyring_wait_cannot_retarget(factory):
    async def scenario():
        session = factory()
        await session.initialize()

        async def key(_reference):
            session.inputs.generation += 1
            await asyncio.sleep(0)
            return "disposable-test-key"

        session.key = key
        await session.toggle()
        assert session.controller.task is None
        assert not session.recorder.recording
        assert not session.inputs.inserted
        await session.close()

    asyncio.run(scenario())


def test_bad_microphone_identifier_does_not_leave_active_task(factory):
    async def scenario():
        session = factory()
        session.store.save_settings(replace(session.settings, microphone="not-hex"))
        await session.initialize()
        await session.toggle()
        assert session.controller.task is None
        assert session.controller.outcome == State.FAILED
        await session.close()

    asyncio.run(scenario())


def test_recorder_exception_releases_task(factory):
    async def scenario():
        session = factory()

        def broken(*_args, **_kwargs):
            raise OSError("device disconnected")

        session.recorder.start = broken
        await session.initialize()
        await session.toggle()
        assert session.controller.task is None
        assert session.controller.outcome == State.FAILED
        await session.close()

    asyncio.run(scenario())


def test_cancel_without_running_asyncio_loop(factory):
    session = factory()
    session.cancel()
    assert session.controller.task is None
    session.timer.stop()


def test_focus_switch_during_intentional_delay_is_allowed(factory):
    async def scenario():
        session = factory()
        await session.initialize()
        pending = session.spawn(session.toggle(delay=0.02))
        await asyncio.sleep(0)
        session.inputs.generation += 1
        session._focus_lost()
        await pending
        assert session.recorder.recording
        assert session.controller.task.target == 1
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("late_error", [False, True])
def test_cancel_resistant_polishing_key_cannot_change_new_task(factory, late_error):
    from inkecho.security import CredentialError

    async def scenario():
        session = factory()
        session.store.save_settings(replace(session.settings, polishing_enabled=True))
        await session.initialize()
        waiting = asyncio.Event()
        release = asyncio.Event()

        async def key(reference):
            if reference == session.store.load_provider("deepseek").key_ref:
                waiting.set()
                try:
                    await release.wait()
                except asyncio.CancelledError:
                    await release.wait()
                if late_error:
                    raise CredentialError("stale error")
            return "stale-key"

        session.key = key
        pending = session.spawn(session.toggle())
        await waiting.wait()
        session.cancel()
        session.keys = {"transcription": "new-task-key"}
        messages = []
        session.status.connect(messages.append)
        release.set()
        await pending
        assert session.keys == {"transcription": "new-task-key"}
        assert not session.recorder.recording
        assert "stale error" not in messages
        await session.close()

    asyncio.run(scenario())


def test_running_task_keeps_provider_and_prompt_snapshot(factory):
    received = []

    class CaptureClient(Client):
        async def transcribe(self, provider, key, audio):
            received.append((provider, key))
            return await super().transcribe(provider, key, audio)

        async def polish(self, provider, key, text, prompt):
            received.append((provider, key, prompt))
            return await super().polish(provider, key, text, prompt)

    async def scenario():
        session = factory(client=CaptureClient())
        session.store.save_settings(replace(session.settings, polishing_enabled=True))
        original = session.store.load_provider("qwen")
        await session.initialize()
        await session.toggle()
        session.store.save_provider(
            replace(original, base_url="https://changed.invalid", key_ref="changed-key")
        )
        session.recorder.stop()
        await complete(session)
        assert received[0] == (original, "disposable-test-key")
        assert received[1][2] == session.store.load_prompt(session.settings.prompt).body
        assert session.task_context is None
        await session.close()

    asyncio.run(scenario())
