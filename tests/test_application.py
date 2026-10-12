"""Orchestration regressions; real desktop acceptance is recorded separately."""

import asyncio
import gc
from dataclasses import replace

import pytest
from PySide6.QtCore import QObject, Signal

from inkecho.app import AudioError, Session
from inkecho.config import ConfigStore
from inkecho.core import Failure, State
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


@pytest.mark.parametrize("transcribing", [False, True])
def test_focus_cancellation_reports_reason_and_safe_diagnostic(factory, transcribing):
    async def scenario():
        session = factory()
        problems, diagnostics = [], []
        session.problem.connect(problems.append)
        session.diagnostic.connect(diagnostics.append)
        await session.initialize()
        await session.toggle()
        if transcribing:
            session.recorder.stop()
            assert session.controller.state == State.TRANSCRIBING
        session.inputs.generation += 1
        session._focus_lost()
        await asyncio.gather(*session.pending, return_exceptions=True)
        assert session.controller.outcome == State.CANCELLED
        assert session.controller.failure == Failure.FOCUS
        assert session.controller.state == State.IDLE
        assert not session.recorder.recording
        assert not session.inputs.inserted
        assert diagnostics == ["target_changed"]
        assert len(problems) == 1
        assert "目标焦点或光标发生变化" in problems[0]
        assert "重新点击编辑器正文" in problems[0]
        await session.close()

    asyncio.run(scenario())


def test_captured_preparation_focus_loss_reports_reason(factory):
    async def scenario():
        session = factory()
        problems, diagnostics = [], []
        session.problem.connect(problems.append)
        session.diagnostic.connect(diagnostics.append)

        async def key(_reference):
            session._focus_lost()
            await asyncio.sleep(0)
            return "disposable-test-key"

        session.key = key
        await session.toggle()
        assert diagnostics == ["target_changed"]
        assert len(problems) == 1
        assert "目标焦点或光标发生变化" in problems[0]
        assert not session.recorder.recording
        assert session.controller.task is None
        await session.close()

    asyncio.run(scenario())


def test_explicit_cancel_does_not_claim_target_focus_changed(factory):
    async def scenario():
        session = factory()
        problems, diagnostics = [], []
        session.problem.connect(problems.append)
        session.diagnostic.connect(diagnostics.append)
        await session.toggle()
        session.cancel()
        assert session.controller.outcome == State.CANCELLED
        assert session.controller.failure is None
        assert not problems
        assert not diagnostics
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


def test_disabled_polishing_does_not_load_unused_provider_or_prompt(factory):
    async def scenario():
        session = factory()
        session.store.save_settings(
            replace(
                session.settings,
                polishing_enabled=False,
                polishing_provider="removed-provider",
                prompt="removed-prompt",
            )
        )
        await session.initialize()
        await session.toggle()
        assert session.recorder.recording
        session.recorder.stop()
        await complete(session)
        assert session.inputs.inserted == ["你好 InkEcho"]
        await session.close()

    asyncio.run(scenario())


def test_first_toggle_waits_for_input_connection(factory):
    async def scenario():
        session = factory()
        await session.toggle()
        assert session.connected
        assert session.recorder.recording
        await session.close()

    asyncio.run(scenario())


def test_wayland_valid_target_uses_same_guarded_recording_path(factory, monkeypatch):
    async def scenario():
        session = factory()
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        await session.initialize()
        await session.toggle()
        assert session.recorder.recording
        session.recorder.stop()
        await complete(session)
        assert session.inputs.inserted == ["你好 InkEcho"]
        await session.close()

    asyncio.run(scenario())


def test_unsupported_wayland_target_is_visible_before_key_or_audio(
    factory, monkeypatch
):
    from inkecho.platform.accessibility import UnsupportedTarget

    async def scenario():
        session = factory()
        monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
        problems, diagnostics = [], []
        session.problem.connect(problems.append)
        session.diagnostic.connect(diagnostics.append)

        async def unsupported():
            raise UnsupportedTarget("No EditableText")

        async def unexpected_key(_reference):
            raise AssertionError("Unsupported target must not read credentials")

        session.inputs.capture_target = unsupported
        session.key = unexpected_key
        await session.initialize()
        await session.toggle()
        assert not session.recorder.recording
        assert len(problems) == 1
        assert "可编辑辅助功能接口" in problems[0]
        assert diagnostics == ["desktop_unavailable"]
        await session.close()

    asyncio.run(scenario())


def test_cancel_during_input_connection_does_not_start_recording(factory):
    async def scenario():
        session = factory()
        entered = asyncio.Event()
        release = asyncio.Event()

        async def connect():
            entered.set()
            await release.wait()

        session.inputs.connect = connect
        pending = asyncio.create_task(session.toggle())
        await entered.wait()
        session.cancel()
        release.set()
        await pending
        assert not session.recorder.recording
        assert session.controller.task is None
        await session.close()

    asyncio.run(scenario())


def test_known_incompatible_protocol_is_rejected_before_target_key_and_audio(factory):
    async def scenario():
        session = factory()
        provider = session.store.load_provider("qwen")
        session.store.save_provider(replace(provider, model="qwen3-asr-flash-realtime"))
        problems, diagnostics = [], []
        session.problem.connect(problems.append)
        session.diagnostic.connect(diagnostics.append)

        async def forbidden(*args):
            raise AssertionError("Protocol preflight must run first")

        session.inputs.connect = forbidden
        session.inputs.capture_target = forbidden
        session.key = forbidden
        await session.toggle()
        assert not session.recorder.recording
        assert session.controller.task is None
        assert diagnostics == ["protocol"]
        assert len(problems) == 1
        assert "当前适配器不支持" in problems[0]
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "reason,code,message",
    [
        ("recording_timed_out", "recording_timed_out", "最长时限"),
        ("microphone_interrupted", "microphone_interrupted", "设备连接"),
        ("empty_recording", "empty_recording", "未收到有效录音数据"),
        ("untrusted-private-detail", "audio_failed", "录音失败"),
    ],
)
def test_recorder_reason_is_reported_once_and_sanitized(factory, reason, code, message):
    async def scenario():
        session = factory()
        problems, diagnostics = [], []
        session.problem.connect(problems.append)
        session.diagnostic.connect(diagnostics.append)
        await session.toggle()
        session.recorder.failed.emit(reason)
        assert session.controller.state == State.IDLE
        assert not session.recorder.recording
        assert diagnostics == [code]
        assert len(problems) == 1
        assert message in problems[0]
        assert "untrusted-private-detail" not in str(problems + diagnostics)
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("at_start", [True, False])
@pytest.mark.parametrize(
    "reason,code,message",
    [
        ("microphone_unavailable", "microphone_unavailable", "重新选择"),
        ("audio_format_unsupported", "audio_format_unsupported", "采样率"),
        ("untrusted-private-detail", "audio_failed", "录音失败"),
    ],
)
def test_microphone_test_preserves_safe_reason_and_releases_resources(
    factory, monkeypatch, at_start, reason, code, message
):
    async def scenario():
        session = factory()
        diagnostics = []
        unhandled = []
        asyncio.get_running_loop().set_exception_handler(
            lambda loop, context: unhandled.append(context)
        )
        session.diagnostic.connect(diagnostics.append)
        created = []

        class FailedRecorder(Recorder):
            def __init__(self, parent):
                super().__init__()
                created.append(self)

            def start(self, *args, **kwargs):
                if at_start:
                    self.failed.emit(reason)
                    return False
                self.recording = True
                return True

            def stop(self):
                self.failed.emit(reason)

        monkeypatch.setattr("inkecho.app.Recorder", FailedRecorder)
        with pytest.raises(AudioError) as caught:
            await session.sample_audio(seconds=0)
        assert caught.value.code == code
        assert message in str(caught.value)
        assert "untrusted-private-detail" not in str(caught.value)
        assert diagnostics == [code]
        assert not session.testing and not created[0].recording
        del caught
        gc.collect()
        await asyncio.sleep(0)
        assert unhandled == []
        await session.close()

    asyncio.run(scenario())


def test_old_audio_reason_is_cleared_before_cancel_and_next_task(factory):
    async def scenario():
        session = factory()
        problems, diagnostics = [], []
        session.problem.connect(problems.append)
        session.diagnostic.connect(diagnostics.append)
        await session.toggle()
        session.recorder.failed.emit("recording_timed_out")
        assert session.audio_failure is None
        session.last_toggle = 0
        await session.toggle()
        session.cancel()
        assert session.audio_failure is None
        session.last_toggle = 0
        await session.toggle()
        session.controller.fail(session.controller.task.id, Failure.AUDIO)
        assert diagnostics == ["recording_timed_out", "audio_failed"]
        assert len(problems) == 2
        assert "最长时限" in problems[0]
        assert "录音失败" in problems[1] and "最长时限" not in problems[1]
        await session.close()

    asyncio.run(scenario())
