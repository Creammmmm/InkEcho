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
    from synthetic_providers import SYNTHETIC_PROVIDERS

    for provider in SYNTHETIC_PROVIDERS:
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


def test_feedback_timeout_uses_recording_task_settings_snapshot(factory):
    class SnapshotInputs(Inputs):
        def set_receiver_feedback_wait_reader(self, reader):
            self.read_receiver_wait = reader

        def set_feedback_timeout_reader(self, reader):
            self.read_timeout = reader

        def set_mapping_wait_reader(self, reader):
            self.read_mapping_wait = reader

    async def scenario():
        template = factory()
        inputs = SnapshotInputs()
        session = Session(
            template.store, inputs=inputs, recorder=Recorder(), client=Client()
        )
        session.key = template.key
        await session.toggle()
        assert inputs.read_receiver_wait() == 0.04
        assert inputs.read_timeout() == 0.04
        assert inputs.read_mapping_wait() == 0.04
        session.store.save_settings(
            replace(
                session.store.load_settings(),
                receiver_feedback_wait_ms=80,
                x11_feedback_timeout_ms=120,
                x11_mapping_wait_ms=80,
            )
        )
        assert inputs.read_receiver_wait() == 0.04
        assert inputs.read_timeout() == 0.04
        assert inputs.read_mapping_wait() == 0.04
        session.cancel()
        await asyncio.sleep(0)
        session.last_toggle = 0
        await session.toggle()
        assert inputs.read_receiver_wait() == 0.08
        assert inputs.read_timeout() == 0.12
        assert inputs.read_mapping_wait() == 0.08
        session.cancel()
        await session.close()

    asyncio.run(scenario())


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
        ("unsupported_target", "当前窗口或桌面环境暂不支持"),
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
        assert type(session.inputs.keyboard) is KeyboardInput
        assert not session.inputs.keyboard.connected
        calls = []

        class DisplayOnly:
            # Deliberately no focus, mapping or send API: preparation must not use it.
            def __init__(self):
                calls.append("connect")

            def close(self):
                calls.append("close")

        session.inputs.keyboard._factory = DisplayOnly
        session.key = template.key
        await session.initialize()
        assert not session.inputs.authorized and calls == []
        await session.toggle()
        assert session.recorder.recording
        assert session.controller.state == State.RECORDING
        await asyncio.sleep(0)
        assert calls == []
        await session.close()
        assert calls == []
        assert not session.inputs.connected

    asyncio.run(scenario())


def test_output_method_is_snapshotted_and_cancel_releases_bridge(factory):
    from inkecho.platform.output_router import OutputRouter

    class Bridge:
        def __init__(self):
            self.closed = False
            self.owner = None

        async def connect(self, *, expected_owner):
            self.owner = expected_owner

        async def aclose(self):
            self.closed = True

    async def scenario():
        session = factory()
        keyboard, bridge = session.inputs, Bridge()
        session.inputs = OutputRouter(keyboard, bridge_factory=lambda: bridge)

        async def verified_owner():
            return ":1.42"

        session.inputs._explicit_fcitx_detector = verified_owner
        session.store.save_settings(replace(session.settings, output_method="fcitx"))
        await session.toggle()
        await asyncio.wait_for(session.task_context["input_authorization"], 1)
        assert session.inputs.selected == "fcitx"
        assert bridge.owner == ":1.42"
        session.store.save_settings(replace(session.settings, output_method="keyboard"))
        assert session.inputs.selected == "fcitx"
        assert keyboard.authorizations == 0
        session.cancel()
        await asyncio.gather(*tuple(session.cleanup_tasks))
        assert bridge.closed and session.inputs.selected is None
        await session.close()

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
        assert "已尝试发送文字" in statuses
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


@pytest.mark.parametrize("empty", ["", " \n\t", ProviderError("empty")])
def test_no_speech_is_quiet_and_does_not_polish_or_emit_text(factory, empty):
    class NoSpeech(Client):
        async def transcribe(self, *_args):
            if isinstance(empty, Exception):
                raise empty
            return Result(empty, Usage(), 0.1)

        async def polish(self, *_args):
            raise AssertionError("No speech must not enter polishing")

    async def scenario():
        session = factory(client=NoSpeech())
        session.store.save_settings(replace(session.settings, polishing_enabled=True))
        problems, diagnostics, states, statuses = [], [], [], []
        session.problem.connect(problems.append)
        session.diagnostic.connect(diagnostics.append)
        session.state_changed.connect(states.append)
        session.status.connect(statuses.append)
        await session.initialize()
        await session.toggle()
        session.recorder.stop()
        await complete(session)
        assert not problems
        assert not diagnostics
        assert "failed" not in states
        assert session.controller.failure == Failure.EMPTY
        assert session.controller.state == State.IDLE
        assert "未识别到内容，本次已结束。" in statuses
        assert not session.inputs.inserted
        assert session.task_context is None
        assert not session.keys
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("code", ["authentication", "network", "response", "timeout"])
def test_real_transcription_errors_are_not_silenced_as_no_speech(factory, code):
    class Broken(Client):
        async def transcribe(self, *_args):
            raise ProviderError(code)

    async def scenario():
        session = factory(client=Broken())
        problems, diagnostics = [], []
        session.problem.connect(problems.append)
        session.diagnostic.connect(diagnostics.append)
        await session.initialize()
        await session.toggle()
        session.recorder.stop()
        await complete(session)
        assert problems
        assert code in diagnostics
        assert session.controller.failure == Failure.TRANSCRIPTION
        assert not session.inputs.inserted
        await session.close()

    asyncio.run(scenario())


def test_no_pcm_recording_ends_quietly_and_releases_task(factory):
    async def scenario():
        session = factory()
        problems, diagnostics, states = [], [], []
        session.problem.connect(problems.append)
        session.diagnostic.connect(diagnostics.append)
        session.state_changed.connect(states.append)
        await session.toggle()
        session.recorder.failed.emit("empty_recording")
        assert session.controller.failure == Failure.EMPTY
        assert session.controller.task is None
        assert session.controller.state == State.IDLE
        assert not session.recorder.recording
        assert not session.task_context
        assert not session.keys
        assert not problems
        assert not diagnostics
        assert "failed" not in states
        assert not session.inputs.inserted
        await session.close()

    asyncio.run(scenario())


def test_input_maintenance_blocks_recording_until_cancelled_worker_finishes(factory):
    import threading

    async def scenario():
        session = factory()
        started, release = threading.Event(), threading.Event()

        def operation():
            started.set()
            assert release.wait(5)

        action = asyncio.create_task(session.run_input_maintenance(operation))
        try:
            for _ in range(200):
                if started.is_set():
                    break
                await asyncio.sleep(0.01)
            assert started.is_set()
            action.cancel()
            with pytest.raises(asyncio.CancelledError):
                await action
            assert session.input_maintenance_active
            await session.toggle()
            assert not session.recorder.recording
            assert session.controller.task is None
        finally:
            release.set()
            await asyncio.gather(*tuple(session.input_maintenance_tasks))
            await session.close()
        assert not session.input_maintenance_active

    asyncio.run(scenario())


def test_queued_input_maintenance_rechecks_recording_and_cancel(factory):
    import threading

    from inkecho.app import InputMaintenanceBusy

    async def scenario():
        session = factory()
        started, release = threading.Event(), threading.Event()
        calls = []

        def first():
            started.set()
            assert release.wait(5)

        action = asyncio.create_task(session.run_input_maintenance(first))
        try:
            for _ in range(200):
                if started.is_set():
                    break
                await asyncio.sleep(0.01)
            assert started.is_set()
            queued = asyncio.create_task(
                session.run_input_maintenance(lambda: calls.append("late"))
            )
            cancelled = asyncio.create_task(
                session.run_input_maintenance(lambda: calls.append("cancelled"))
            )
            await asyncio.sleep(0)
            cancelled.cancel()
            with pytest.raises(asyncio.CancelledError):
                await cancelled
            session.preparing = True
            release.set()
            await action
            with pytest.raises(InputMaintenanceBusy):
                await queued
            assert calls == []
        finally:
            release.set()
            session.preparing = False
            await asyncio.gather(
                *tuple(session.input_maintenance_tasks), return_exceptions=True
            )
            await session.close()

    asyncio.run(scenario())


def test_session_close_waits_for_cancelled_maintenance_worker(factory):
    import threading

    async def scenario():
        session = factory()
        started, release = threading.Event(), threading.Event()

        def operation():
            started.set()
            assert release.wait(5)

        action = asyncio.create_task(session.run_input_maintenance(operation))
        try:
            for _ in range(200):
                if started.is_set():
                    break
                await asyncio.sleep(0.01)
            assert started.is_set()
            action.cancel()
            with pytest.raises(asyncio.CancelledError):
                await action
            closing = asyncio.create_task(session.close())
            await asyncio.sleep(0.02)
            assert not closing.done()
            assert session.input_maintenance_active
            release.set()
            await asyncio.wait_for(closing, 2)
            assert not session.input_maintenance_active
        finally:
            release.set()
            await asyncio.gather(
                *tuple(session.input_maintenance_tasks), return_exceptions=True
            )
            session.timer.stop()

    asyncio.run(scenario())


def test_auto_explicit_enable_authorizes_fallback_but_recording_does_not(factory):
    from inkecho.platform.output_router import OutputRouter

    async def scenario():
        session = factory()
        keyboard = session.inputs
        authorize = keyboard.authorize

        async def authorize_with_parent(_parent=""):
            await authorize()

        keyboard.authorize = authorize_with_parent
        session.inputs = OutputRouter(keyboard)
        session.store.save_settings(replace(session.settings, output_method="auto"))
        assert await session.authorize_input("auto")
        assert keyboard.authorizations == 0
        await session.inputs.discard_task()
        assert await session.authorize_input()
        assert keyboard.authorizations == 1
        assert session.inputs.selected is None
        await session.close()

    asyncio.run(scenario())


def test_ibus_normal_output_reports_unconfirmed_without_replay_or_success(factory):
    from test_output_router import Bridge, Keyboard

    from inkecho.platform.output_router import OutputRouter

    async def scenario():
        session = factory()
        session.store.save_settings(
            replace(session.settings, polishing_enabled=False, output_method="ibus")
        )
        keyboard, bridge = Keyboard(), Bridge()
        session.inputs = OutputRouter(keyboard, ibus_factory=lambda: bridge)
        outcomes, problems, diagnostics = [], [], []
        session.finished.connect(outcomes.append)
        session.problem.connect(problems.append)
        session.diagnostic.connect(diagnostics.append)
        await session.toggle()
        session.recorder.stop()
        await complete(session)
        assert bridge.sent == ["你好 InkEcho"]
        assert keyboard.sent == []
        assert outcomes[0]["outcome"] == "unconfirmed"
        assert outcomes[0]["characters"] == len("你好 InkEcho")
        assert diagnostics == ["ibus_delivery_unknown"]
        assert problems == []
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("reason", ["unsupported_compositor", "unsupported_target"])
@pytest.mark.parametrize("phase", ["connect", "send"])
def test_auto_fcitx_zero_prefix_keyboard_failure_reports_failure_and_closes(
    factory, reason, phase
):
    from test_output_router import Bridge, Keyboard

    from inkecho.platform.fcitx5 import FcitxOutputError
    from inkecho.platform.keyboard import KeyboardError
    from inkecho.platform.output_router import OutputRouter

    class NoTarget(Bridge):
        async def insert(self, text, can_continue, **kwargs):
            assert can_continue()
            raise FcitxOutputError("no_target", accepted=0, unsent_offset=0)

    class BrokenKeyboard(Keyboard):
        async def connect(self):
            self.connects += 1
            if phase == "connect":
                raise KeyboardError(reason)

        async def insert(self, text, can_continue, **kwargs):
            assert can_continue()
            raise KeyboardError(reason)

    async def scenario():
        session = factory()
        session.store.save_settings(
            replace(session.settings, polishing_enabled=False, output_method="auto")
        )
        bridge, keyboard = NoTarget(), BrokenKeyboard()
        session.inputs = OutputRouter(keyboard, bridge_factory=lambda: bridge)

        async def detect():
            return ("fcitx", ":1.42")

        session.inputs._system_detector = detect
        outcomes, problems, diagnostics = [], [], []
        session.finished.connect(outcomes.append)
        session.problem.connect(problems.append)
        session.diagnostic.connect(diagnostics.append)
        await session.toggle()
        session.recorder.stop()
        await complete(session)
        assert [item["outcome"] for item in outcomes] == ["failed"]
        assert outcomes[0]["characters"] == 0
        assert diagnostics == [reason] and len(problems) == 1
        assert bridge.closed and keyboard.connects == 1 and not keyboard.sent
        assert session.inputs.selected is None
        if reason == "unsupported_compositor":
            assert "Ubuntu 24.04" in problems[0] and "Ubuntu on Xorg" in problems[0]
        else:
            assert "当前窗口或桌面环境暂不支持" in problems[0]
            assert "原生 Wayland 应用暂不支持" not in problems[0]
        await session.close()

    asyncio.run(scenario())


def test_router_cleanup_failure_is_forwarded_to_session_diagnostics(factory):
    class DiagnosticsInputs(Inputs):
        def set_diagnostic_handler(self, handler):
            self.handler = handler

    async def scenario():
        template = factory()
        inputs = DiagnosticsInputs()
        session = Session(
            template.store, inputs=inputs, recorder=Recorder(), client=Client()
        )
        reports = []
        session.diagnostic.connect(reports.append)
        inputs.handler("input_cleanup_failed")
        assert reports == ["input_cleanup_failed"]
        await session.close()
        await template.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("mode", ["auto", "keyboard", "fcitx", "ibus"])
def test_recording_snapshots_each_output_mode_before_async_authorization(factory, mode):
    class SnapshotInputs(Inputs):
        def __init__(self):
            super().__init__()
            self.modes = []

        async def prepare_task(self, selected, **kwargs):
            self.modes.append(selected)

        async def discard_task(self):
            pass

    async def scenario():
        session = factory()
        inputs = SnapshotInputs()
        session.inputs = inputs
        session.store.save_settings(replace(session.settings, output_method=mode))
        await session.toggle()
        session.store.save_settings(
            replace(session.store.load_settings(), output_method="keyboard")
        )
        await asyncio.wait_for(session.task_context["input_authorization"], 1)
        assert inputs.modes == [mode]
        session.cancel()
        await session.close()

    asyncio.run(scenario())


def test_unknown_input_error_is_sanitized_before_diagnostics(factory):
    from inkecho.platform.output_router import OutputRouterError

    session = factory()
    diagnostics = []
    session.diagnostic.connect(diagnostics.append)
    session.input_problem(OutputRouterError("private input details"))
    assert diagnostics == ["injection_failed"]
    asyncio.run(session.close())


@pytest.mark.parametrize("accepted,uncertain", [(2, False), (2, True), (0, True)])
def test_fcitx_failed_output_records_only_acknowledged_attempts(
    factory, accepted, uncertain
):
    from test_output_router import Bridge, Keyboard

    from inkecho.platform.fcitx5 import FcitxOutputError
    from inkecho.platform.output_router import OutputRouter

    class Partial(Bridge):
        async def insert(self, text, can_continue, **kwargs):
            raise FcitxOutputError(
                "delivery_unknown" if uncertain else "owner_changed",
                accepted=accepted,
                uncertain=uncertain,
            )

    async def scenario():
        session = factory()
        session.store.save_settings(
            replace(session.settings, polishing_enabled=False, output_method="auto")
        )
        keyboard, bridge = Keyboard(), Partial()
        router = OutputRouter(keyboard, bridge_factory=lambda: bridge)

        async def detect():
            return ("fcitx", ":1.42")

        router._system_detector = detect
        session.inputs = router
        outcomes = []
        session.finished.connect(outcomes.append)
        await session.toggle()
        session.recorder.stop()
        await complete(session)
        assert outcomes[0]["outcome"] == "failed"
        assert outcomes[0]["characters"] == accepted
        assert keyboard.sent == []
        await session.close()

    asyncio.run(scenario())


def test_ibus_partial_acknowledgement_is_counted_without_replay(factory, tmp_path):
    from test_ibus import Bus, trusted_owner
    from test_output_router import Keyboard

    from inkecho.platform.ibus import Client, IBusBridge
    from inkecho.platform.output_router import OutputRouter

    async def scenario():
        runtime = tmp_path / "ibus-runtime"
        runtime.mkdir(mode=0o700)
        bus = Bus()
        bus.outcomes = ["attempted", TimeoutError("synthetic unknown")]
        keyboard = Keyboard()
        session = factory()
        session.store.save_settings(
            replace(session.settings, polishing_enabled=False, output_method="ibus")
        )
        session.inputs = OutputRouter(
            keyboard,
            ibus_factory=lambda: IBusBridge(
                runtime_dir=str(runtime),
                client_factory=lambda cap: Client(
                    cap, bus_factory=lambda: bus, owner_verifier=trusted_owner
                ),
            ),
        )
        outcomes, diagnostics = [], []
        session.finished.connect(outcomes.append)
        session.diagnostic.connect(diagnostics.append)
        await session.toggle()
        session.recorder.stop()
        await complete(session)
        assert outcomes[0]["outcome"] == "failed"
        assert outcomes[0]["characters"] == 1
        assert diagnostics == ["ibus_delivery_unknown"]
        assert keyboard.sent == []
        assert [m.body[1] for m in bus.calls if m.member == "Commit"] == ["你", "好"]
        await session.close()

    asyncio.run(scenario())


def test_unconfirmed_task_cleans_up_and_new_task_can_be_cancelled(factory):
    from test_output_router import Bridge, Keyboard

    from inkecho.platform.output_router import OutputRouter

    async def scenario():
        session = factory()
        session.store.save_settings(
            replace(session.settings, polishing_enabled=False, output_method="ibus")
        )
        bridges = []

        def bridge_factory():
            bridge = Bridge()
            bridges.append(bridge)
            return bridge

        session.inputs = OutputRouter(Keyboard(), ibus_factory=bridge_factory)
        outcomes = []
        session.finished.connect(outcomes.append)
        await session.toggle()
        session.recorder.stop()
        await complete(session)
        assert [x["outcome"] for x in outcomes] == ["unconfirmed"]
        assert session.controller.state == State.IDLE
        assert session.controller.task is None and bridges[0].closed
        assert session.inputs.selected is None
        session.last_toggle = 0  # Do not test the independent shortcut debounce.
        await session.toggle()
        assert session.controller.state == State.RECORDING
        session.cancel()
        await complete(session)
        assert [x["outcome"] for x in outcomes] == ["unconfirmed", "cancelled"]
        assert len(bridges) == 2 and bridges[1].closed
        await session.close()

    asyncio.run(scenario())


def test_cancel_after_x11_dispatch_counts_attempt_once_and_resets(factory, monkeypatch):
    from test_keyboard import Driver, ImmediatePacer, fast_sleep

    from inkecho.platform.keyboard import KeyboardInput
    from inkecho.platform.output_router import OutputRouter

    fast_sleep(monkeypatch)

    async def scenario():
        session = factory()
        session.store.save_settings(
            replace(session.settings, polishing_enabled=False, output_method="keyboard")
        )
        driver = Driver()
        keyboard = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        original = keyboard.insert

        async def cancel_first(text, active, **kwargs):
            callback = kwargs.get("on_first_sent")

            def sent(at):
                if callback:
                    callback(at)
                session.cancel()

            kwargs["on_first_sent"] = sent
            return await original(text, active, **kwargs)

        keyboard.insert = cancel_first
        session.inputs = OutputRouter(keyboard)
        outcomes = []
        session.finished.connect(outcomes.append)
        await session.toggle()
        session.recorder.stop()
        for _ in range(500):
            await asyncio.sleep(0)
            if outcomes and not session.pending:
                break
        assert outcomes[0]["outcome"] == "cancelled"
        assert outcomes[0]["characters"] == 1
        assert [event[2] for event in driver.events] == [True, False]
        session.last_toggle = 0
        await session.toggle()
        session.cancel()
        for _ in range(500):
            await asyncio.sleep(0)
            if len(outcomes) == 2 and not session.pending:
                break
        assert outcomes[1]["outcome"] == "cancelled"
        assert outcomes[1]["characters"] == 0
        assert [event[2] for event in driver.events] == [True, False]
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("fail_on_press", [False, True])
def test_x11_failed_dispatch_records_only_completed_presses(
    factory, monkeypatch, fail_on_press
):
    from test_keyboard import Driver, ImmediatePacer, fast_sleep

    from inkecho.platform.keyboard import KeyboardError, KeyboardInput
    from inkecho.platform.output_router import OutputRouter

    fast_sleep(monkeypatch)

    class Broken(Driver):
        def send(self, window, code, pressed):
            super().send(window, code, pressed)
            if pressed == fail_on_press:
                raise KeyboardError("injection_failed")

    async def scenario():
        session = factory()
        session.store.save_settings(
            replace(session.settings, polishing_enabled=False, output_method="keyboard")
        )
        driver = Broken()
        session.inputs = OutputRouter(
            KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        )
        outcomes = []
        session.finished.connect(outcomes.append)
        await session.toggle()
        session.recorder.stop()
        for _ in range(500):
            await asyncio.sleep(0)
            if outcomes and not session.pending:
                break
        assert outcomes[0]["outcome"] == "failed"
        assert outcomes[0]["characters"] == (0 if fail_on_press else 1)
        assert [event[2] for event in driver.events] == [True, False]
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("callback_error", ["generic", "keyboard"])
def test_x11_first_dispatch_callback_failure_counts_attempt_and_cleans_up(
    factory, monkeypatch, callback_error
):
    from test_keyboard import Driver, ImmediatePacer, fast_sleep

    from inkecho.platform.keyboard import KeyboardError, KeyboardInput
    from inkecho.platform.output_router import OutputRouter

    fast_sleep(monkeypatch)

    async def scenario():
        session = factory()
        session.store.save_settings(
            replace(session.settings, polishing_enabled=False, output_method="keyboard")
        )
        driver = Driver()
        keyboard = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        original = keyboard.insert

        async def fails(text, active, **kwargs):
            def sent(_at):
                if callback_error == "keyboard":
                    raise KeyboardError("injection_failed")
                raise RuntimeError("synthetic callback fault")

            kwargs["on_first_sent"] = sent
            return await original(text, active, **kwargs)

        keyboard.insert = fails
        session.inputs = OutputRouter(keyboard)
        outcomes = []
        session.finished.connect(outcomes.append)
        await session.toggle()
        session.recorder.stop()
        for _ in range(500):
            await asyncio.sleep(0)
            if outcomes and not session.pending:
                break
        assert outcomes[0]["outcome"] == "failed"
        assert outcomes[0]["characters"] == 1
        assert [event[2] for event in driver.events] == [True, False]
        assert driver.applied is None and session.inputs.selected is None
        await session.close()

    asyncio.run(scenario())


@pytest.mark.parametrize("ending", ["cancel", "generic", "keyboard"])
def test_stream_second_segment_counts_once(factory, monkeypatch, ending):
    from test_keyboard import Driver, ImmediatePacer, fast_sleep

    from inkecho.platform.keyboard import KeyboardError, KeyboardInput
    from inkecho.platform.output_router import OutputRouter

    fast_sleep(monkeypatch)

    async def scenario():
        first_completed = asyncio.Event()

        class Streaming(Client):
            async def polish_stream(self, *_args):
                on_delta = _args[-1]
                await on_delta("甲")
                await first_completed.wait()
                await on_delta("乙")
                return Result("甲乙", Usage(), 0)

        session = factory(client=Streaming())
        session.store.save_settings(
            replace(
                session.settings,
                polishing_enabled=True,
                polishing_streaming=True,
                output_method="keyboard",
            )
        )
        driver = Driver()
        keyboard = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        original = keyboard.insert
        fragments = []

        async def insert(text, active, **kwargs):
            fragments.append(text)
            if len(fragments) == 2:
                callback = kwargs.get("on_first_sent")

                def sent(at):
                    if callback:
                        callback(at)
                    if ending == "cancel":
                        session.cancel()
                    elif ending == "generic":
                        raise RuntimeError("synthetic callback fault")
                    else:
                        raise KeyboardError("injection_failed")

                kwargs["on_first_sent"] = sent
            result = await original(text, active, **kwargs)
            if len(fragments) == 1:
                first_completed.set()
            return result

        keyboard.insert = insert
        session.inputs = OutputRouter(keyboard)
        outcomes = []
        session.finished.connect(outcomes.append)
        await session.toggle()
        session.recorder.stop()
        for _ in range(1000):
            await asyncio.sleep(0)
            if outcomes and not session.pending:
                break
        assert fragments == ["甲", "乙"]
        assert outcomes[0]["outcome"] == (
            "cancelled" if ending == "cancel" else "failed"
        )
        assert outcomes[0]["characters"] == 2
        assert [event[2] for event in driver.events] == [True, False, True, False]
        await session.close()

    asyncio.run(scenario())


def test_wayland_hybrid_cancel_after_native_ack_counts_dispatch(factory, monkeypatch):
    from test_hybrid_keyboard import Driver
    from test_keyboard import fast_sleep
    from test_wayland_keyboard import connected

    from inkecho.platform.hybrid_keyboard import HybridKeyboardInput
    from inkecho.platform.keyboard import KeyboardInput
    from inkecho.platform.output_router import OutputRouter

    fast_sleep(monkeypatch)

    async def scenario():
        session = factory()
        session.store.save_settings(
            replace(session.settings, polishing_enabled=False, output_method="keyboard")
        )
        driver = Driver([])
        driver.is_x = False
        native, process = await connected()
        await native.authorize()
        hybrid = HybridKeyboardInput(
            native=native, x11=KeyboardInput(driver_factory=lambda: driver)
        )
        original = hybrid.insert

        async def cancel_first(text, active, **kwargs):
            callback = kwargs.get("on_first_sent")

            def sent(at):
                if callback:
                    callback(at)
                session.cancel()

            kwargs["on_first_sent"] = sent
            return await original(text, active, **kwargs)

        hybrid.insert = cancel_first
        session.inputs = OutputRouter(hybrid)
        outcomes = []
        session.finished.connect(outcomes.append)
        await session.toggle()
        session.recorder.stop()
        for _ in range(1000):
            await asyncio.sleep(0)
            if outcomes and not session.pending:
                break
        assert outcomes[0]["outcome"] == "cancelled"
        assert outcomes[0]["characters"] == 1
        assert [r["value"] for r in process.requests if r["op"] == "key"] == ["你"]
        await session.close()

    asyncio.run(scenario())


def test_wayland_hybrid_cancel_before_worker_reply_does_not_claim_dispatch(factory):
    from test_hybrid_keyboard import Driver
    from test_wayland_keyboard import connected

    from inkecho.platform.hybrid_keyboard import HybridKeyboardInput
    from inkecho.platform.keyboard import KeyboardInput
    from inkecho.platform.output_router import OutputRouter

    async def scenario():
        entered = asyncio.Event()
        pending = []

        def handle(_process, request):
            if request["op"] == "key":
                pending.append(request)
                entered.set()
                return True
            return False

        session = factory()
        session.store.save_settings(
            replace(session.settings, polishing_enabled=False, output_method="keyboard")
        )
        driver = Driver([])
        driver.is_x = False
        native, process = await connected(handle)
        await native.authorize()
        session.inputs = OutputRouter(
            HybridKeyboardInput(
                native=native, x11=KeyboardInput(driver_factory=lambda: driver)
            )
        )
        outcomes = []
        session.finished.connect(outcomes.append)
        await session.toggle()
        session.recorder.stop()
        await asyncio.wait_for(entered.wait(), 2)
        session.cancel()
        assert outcomes[0]["characters"] == 0  # finished was already emitted
        process.reply(pending[0], count=1)  # Late ACK cannot rewrite that event.
        for _ in range(500):
            await asyncio.sleep(0)
            if outcomes and not session.pending:
                break
        assert outcomes[0]["outcome"] == "cancelled"
        assert outcomes[0]["characters"] == 0
        assert [r["value"] for r in process.requests if r["op"] == "key"] == ["你"]
        await session.close()

    asyncio.run(scenario())
