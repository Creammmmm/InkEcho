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
        self.focus = None
        self.authorized = False
        self.authorizations = 0
        self.destinations = []
        self.inserted = []

    async def connect(self):
        pass

    async def authorize(self):
        self.authorized = True
        self.authorizations += 1

    async def insert(self, text, can_continue, *, deadline=None):
        if can_continue():
            self.destinations.append(self.focus)
            self.inserted.append(text)
            return len(text)

    async def aclose(self):
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


def test_focus_change_during_keyring_wait_does_not_cancel_recording(factory):
    async def scenario():
        session = factory()

        async def key(_reference):
            session.inputs.focus = "another-window"
            await asyncio.sleep(0)
            return "disposable-test-key"

        session.key = key
        await session.toggle()
        assert session.controller.state == State.RECORDING
        session.inputs.focus = "final-window"
        session.recorder.stop()
        await complete(session)
        assert session.inputs.destinations == ["final-window"]
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "phase", [State.RECORDING, State.TRANSCRIBING, State.POLISHING]
)
def test_focus_switches_continue_and_deliver_to_final_focus(factory, phase):
    async def scenario():
        entered, release = asyncio.Event(), asyncio.Event()

        class DelayedClient(Client):
            async def transcribe(self, *args):
                if phase == State.TRANSCRIBING:
                    entered.set()
                    await release.wait()
                return await super().transcribe(*args)

            async def polish(self, *args):
                if phase == State.POLISHING:
                    entered.set()
                    await release.wait()
                return await super().polish(*args)

        session = factory(client=DelayedClient())
        session.store.save_settings(replace(session.settings, polishing_enabled=True))
        await session.toggle()
        assert session.inputs.focus is None
        if phase != State.RECORDING:
            session.recorder.stop()
            await entered.wait()
        session.inputs.focus = "chosen-during-processing"
        session.controller.tick()
        assert session.controller.state == phase
        release.set()
        if phase == State.RECORDING:
            session.recorder.stop()
        await complete(session)
        assert session.controller.outcome == State.SUCCEEDED
        assert session.inputs.destinations == ["chosen-during-processing"]
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
        session.inputs.focus = "different-window"
        await pending
        assert session.recorder.recording
        assert session.controller.task is not None
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


def test_first_toggle_connects_input_while_recording(factory):
    async def scenario():
        session = factory()
        await session.toggle()
        assert session.connected
        assert session.recorder.recording
        await session.close()

    asyncio.run(scenario())


def test_wayland_recording_has_no_target_requirement(factory, monkeypatch):
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


def test_denied_keyboard_permission_stops_recording_without_output(factory):
    from inkecho.platform.keyboard import KeyboardError

    async def scenario():
        session = factory()
        problems, diagnostics = [], []
        session.problem.connect(problems.append)
        session.diagnostic.connect(diagnostics.append)

        async def denied():
            raise KeyboardError("permission_denied")

        session.inputs.authorize = denied
        await session.toggle()
        assert not session.recorder.recording
        assert len(problems) == 1 and "系统未允许键盘输入" in problems[0]
        assert diagnostics == ["permission_denied"]
        assert session.inputs.inserted == [] and session.controller.task is None
        await session.close()

    asyncio.run(scenario())


def test_cancel_during_input_connection_stops_existing_recording(factory):
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


def test_known_incompatible_protocol_is_rejected_before_permission_key_and_audio(
    factory,
):
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
        session.inputs.authorize = forbidden
        session.key = forbidden
        await session.toggle()
        assert not session.recorder.recording
        assert session.controller.task is None
        assert diagnostics == ["protocol"]
        assert len(problems) == 1
        assert "当前连接方式与模型能力或协议不匹配" in problems[0]
        assert "所选供应商支持的语音识别模型与对应转写方式" in problems[0]
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


def test_initialize_does_not_request_permission_and_authorization_is_reused(factory):
    async def scenario():
        session = factory()
        await session.initialize()
        assert session.inputs.authorizations == 0
        await session.toggle()
        assert session.inputs.authorizations == 1 and session.recorder.recording
        session.cancel()
        session.last_toggle = 0
        await session.toggle()
        assert session.inputs.authorizations == 1 and session.recorder.recording
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("denied", [False, True])
def test_cancel_during_authorization_cannot_start_late_recording(factory, denied):
    from inkecho.platform.keyboard import KeyboardError

    async def scenario():
        session = factory()
        entered, release = asyncio.Event(), asyncio.Event()
        problems = []
        session.problem.connect(problems.append)

        async def authorize():
            entered.set()
            await release.wait()
            if denied:
                raise KeyboardError("permission_denied")
            session.inputs.authorized = True

        session.inputs.authorize = authorize
        pending = asyncio.create_task(session.toggle())
        await entered.wait()
        session.cancel()
        release.set()
        await pending
        assert not session.recorder.recording and session.controller.task is None
        assert not problems
        await session.close()

    asyncio.run(scenario())


def test_cancelled_pending_delivery_cannot_type_or_finish_a_new_task(factory):
    async def scenario():
        session = factory()
        entered, release = asyncio.Event(), asyncio.Event()

        async def delayed_insert(text, can_continue, *, deadline=None):
            entered.set()
            try:
                await release.wait()
            except asyncio.CancelledError:
                await release.wait()
            if can_continue():
                session.inputs.inserted.append(text)

        session.inputs.insert = delayed_insert
        await session.toggle()
        session.recorder.stop()
        await entered.wait()
        old_pending = list(session.pending)
        session.cancel()
        session.last_toggle = 0
        await session.toggle()
        new_id = session.controller.task.id
        release.set()
        await asyncio.gather(*old_pending, return_exceptions=True)
        assert not session.inputs.inserted
        assert session.controller.task.id == new_id
        assert session.controller.state == State.RECORDING
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("session_closed", "键盘输入连接已断开"),
        ("unsupported_target", "原生 Wayland 应用暂不支持"),
        ("mapping_changed", "键盘布局发生变化"),
    ],
)
def test_keyboard_delivery_error_has_one_specific_notice(factory, code, message):
    from inkecho.platform.keyboard import KeyboardError

    async def scenario():
        session = factory()
        problems, diagnostics = [], []
        session.problem.connect(problems.append)
        session.diagnostic.connect(diagnostics.append)

        async def failed_insert(*_args, **_kwargs):
            raise KeyboardError(code)

        session.inputs.insert = failed_insert
        await session.toggle()
        session.recorder.stop()
        await complete(session)
        assert session.controller.outcome == State.FAILED
        assert diagnostics == [code]
        assert len(problems) == 1 and message in problems[0]
        assert session.input_failure is None
        await session.close()

    asyncio.run(scenario())


def test_default_keyboard_lifecycle_does_not_inspect_focus(factory):
    from inkecho.platform.keyboard import KeyboardInput

    async def scenario():
        template = factory()
        await template.close()
        session = Session(template.store, recorder=Recorder(), client=Client())
        assert type(session.inputs) is KeyboardInput
        assert not session.inputs.connected
        calls = []

        class DisplayOnly:
            # Deliberately no focus, mapping or send API: preparation must not use it.
            def __init__(self):
                calls.append("connect")

            def close(self):
                calls.append("close")

        session.inputs._factory = DisplayOnly
        session.key = template.key
        await session.initialize()
        assert session.inputs.authorized and calls == ["connect"]
        await session.toggle()
        assert session.recorder.recording
        assert session.controller.state == State.RECORDING
        await session.close()
        assert calls == ["connect", "close"]
        assert not session.inputs.connected

    asyncio.run(scenario())


def test_explicit_ui_authorization_is_cancelled_with_the_session(factory):
    async def scenario():
        session = factory()
        entered, cancelled = asyncio.Event(), asyncio.Event()

        async def authorize():
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        session.inputs.authorize = authorize
        task = session.spawn_ui(session.authorize_input())
        await entered.wait()
        session.cancel()
        assert not await task
        assert cancelled.is_set() and not session.recorder.recording
        await session.close()

    asyncio.run(scenario())


def test_session_connection_reflects_backend_disconnect(factory):
    async def scenario():
        session = factory()
        session.inputs.connected = True
        await session.initialize()
        assert session.connected
        session.inputs.connected = False
        assert not session.connected
        await session.close()

    asyncio.run(scenario())


def test_display_failure_stops_recording_and_prevents_output(factory):
    from inkecho.platform.keyboard import KeyboardError, KeyboardInput

    async def scenario():
        session = factory()
        problems, diagnostics = [], []
        session.problem.connect(problems.append)
        session.diagnostic.connect(diagnostics.append)

        def unavailable():
            raise KeyboardError("display_unavailable")

        session.inputs = KeyboardInput(driver_factory=unavailable)
        await session.toggle()
        assert not session.recorder.recording and not session.controller.task
        assert diagnostics == ["display_unavailable"]
        assert len(problems) == 1 and "无法连接桌面" in problems[0]
        await session.close()

    asyncio.run(scenario())


def test_sent_character_metrics_use_keyboard_normalized_count(factory):
    class NewlineClient(Client):
        async def transcribe(self, *_args):
            return Result("甲\r\n乙", Usage(), 0.1)

    async def scenario():
        session = factory(client=NewlineClient())
        session.store.save_settings(replace(session.settings, polishing_enabled=False))
        outcomes, statuses = [], []
        session.finished.connect(outcomes.append)
        session.status.connect(statuses.append)

        async def normalized_insert(text, can_continue, *, deadline=None):
            assert text == "甲\r\n乙" and can_continue()
            return 3  # Keyboard emits one newline for the provider's CRLF pair.

        session.inputs.insert = normalized_insert
        await session.toggle()
        session.recorder.stop()
        await complete(session)
        assert outcomes[0]["outcome"] == "succeeded"
        assert outcomes[0]["characters"] == 3
        assert "按键已发送" in statuses
        assert all("已输入到目标" not in text for text in statuses)
        await session.close()

    asyncio.run(scenario())


def test_keyboard_cleanup_failure_does_not_interrupt_application_shutdown(factory):
    from inkecho.platform.keyboard import KeyboardError

    async def scenario():
        session = factory()
        diagnostics, problems = [], []
        session.diagnostic.connect(diagnostics.append)
        session.problem.connect(problems.append)
        await session.toggle()
        assert session.recorder.recording

        async def failed_close():
            raise KeyboardError("mapping_changed")

        session.inputs.aclose = failed_close
        await session.close()
        assert not session.timer.isActive()
        assert not session.recorder.recording and not session.controller.task
        assert diagnostics == ["mapping_changed"]
        assert problems == []

    asyncio.run(scenario())


def test_unexpected_keyboard_cleanup_error_is_not_hidden(factory):
    async def scenario():
        session = factory()

        async def failed_close():
            raise ValueError("unexpected test failure")

        session.inputs.aclose = failed_close
        with pytest.raises(ValueError, match="unexpected test failure"):
            await session.close()
        assert not session.timer.isActive()

    asyncio.run(scenario())


def test_performance_is_separate_from_finished_statistics_and_missing_send_is_honest(
    factory,
):
    from inkecho.statistics import Statistics

    async def scenario():
        session = factory()
        session.store.save_settings(replace(session.settings, polishing_enabled=True))
        reports, outcomes = [], []
        session.performance.connect(reports.append)
        session.finished.connect(outcomes.append)
        await session.toggle()
        session.last_toggle = 0
        await session.toggle()
        await complete(session)
        assert len(reports) == 1
        assert reports[0] == session.last_performance
        events = reports[0]["events_ms"]
        assert events["recording_stop_requested"] is not None
        assert events["asr_completed"] >= events["asr_started"]
        assert events["polishing_first_segment"] is not None
        assert events["output_completed"] is not None
        assert events["first_character_sent"] is None
        assert reports[0]["durations_ms"]["stop_to_first_character_ms"] is None
        Statistics(session.store.root / "test-statistics.json").record(**outcomes[0])
        assert session.task_timing is None
        await session.close()

    asyncio.run(scenario())


def test_send_callback_marks_dispatch_not_insert_call_and_ignores_stale_reply(factory):
    async def scenario():
        session = factory()
        entered, sent, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        callbacks = []

        async def insert(text, can_continue, *, deadline=None, on_first_sent):
            callbacks.append(on_first_sent)
            entered.set()
            await sent.wait()
            assert can_continue()
            on_first_sent()
            await release.wait()
            return len(text)

        session.inputs.supports_first_sent_callback = True
        session.inputs.insert = insert
        await session.toggle()
        old_id = session.controller.task.id
        session.recorder.stop()
        await entered.wait()
        assert (
            session.task_timing.snapshot()["events_ms"]["first_character_sent"] is None
        )
        sent.set()
        await asyncio.sleep(0)
        assert session.task_timing.snapshot()["events_ms"]["first_character_sent"] >= 0
        release.set()
        await complete(session)
        old_snapshot = session.last_performance
        callbacks[0]()
        assert session.last_performance == old_snapshot
        session.last_toggle = 0
        await session.toggle()
        session.mark_timing(old_id, "first_character_sent")
        callbacks[0]()
        assert (
            session.task_timing.snapshot()["events_ms"]["first_character_sent"] is None
        )
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("outcome", [State.CANCELLED, State.FAILED])
def test_cancel_and_failure_emit_partial_performance_without_fake_completion(
    factory, outcome
):
    async def scenario():
        session = factory()
        reports = []
        session.performance.connect(reports.append)
        await session.toggle()
        task_id = session.controller.task.id
        if outcome == State.CANCELLED:
            session.cancel()
        else:
            session.controller.fail(task_id, Failure.AUDIO)
        assert len(reports) == 1 and reports[0]["outcome"] == outcome.value
        assert reports[0]["events_ms"]["recording_started"] is not None
        assert reports[0]["events_ms"]["task_finished"] is not None
        assert reports[0]["events_ms"]["output_completed"] is None
        session.mark_timing(task_id, "first_character_sent")
        assert reports[0]["events_ms"]["first_character_sent"] is None
        await session.close()
        assert len(reports) == 1

    asyncio.run(scenario())


def test_session_closes_provider_after_pending_and_ui_requests_are_cancelled(factory):
    events = []

    class ClosingClient(Client):
        async def aclose(self):
            events.append("closed")

    async def scenario():
        session = factory(client=ClosingClient())
        started = [asyncio.Event(), asyncio.Event()]

        async def pending(index):
            started[index].set()
            try:
                await asyncio.Event().wait()
            finally:
                events.append(f"cancelled-{index}")

        session.spawn(pending(0))
        session.spawn_ui(pending(1))
        await asyncio.gather(*(event.wait() for event in started))
        await session.close()
        assert set(events[:2]) == {"cancelled-0", "cancelled-1"}
        assert events[2:] == ["closed"]

    asyncio.run(scenario())


def test_stop_button_path_records_request_before_synchronous_audio_ready(factory):
    async def scenario():
        session = factory()
        await session.toggle()
        session.stop_recording()
        await complete(session)
        events = session.last_performance["events_ms"]
        assert events["recording_stop_requested"] <= events["recording_stopped"]
        await session.close()

    asyncio.run(scenario())


def test_session_credentials_use_only_explicit_config_root(tmp_path, monkeypatch):
    from inkecho.security import CredentialError, FileCredentialStore

    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "unrelated"))

    async def scenario():
        sessions = [
            Session(ConfigStore(tmp_path / name), inputs=Inputs(), client=Client())
            for name in ("first", "second")
        ]
        first, second = sessions
        try:
            assert first.secrets.root == first.store.root
            await first.save_key("provider/synthetic", "synthetic-key")
            assert await first.key("provider/synthetic") == "synthetic-key"
            assert FileCredentialStore(first.store.root).get("provider/synthetic") == (
                "synthetic-key"
            )
            with pytest.raises(CredentialError, match="重新填写"):
                await second.key("provider/synthetic")
            await first.save_key("provider/synthetic", None)
            with pytest.raises(CredentialError, match="重新填写"):
                await first.key("provider/synthetic")
            assert not (tmp_path / "unrelated").exists()
        finally:
            for session in sessions:
                await session.close()

    asyncio.run(scenario())
