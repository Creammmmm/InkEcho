"""Mock-adapter safety tests, not desktop compatibility evidence."""

import pytest

from inkecho.core import Failure, State, TaskController


class Inputs:
    def __init__(self):
        self.generation = 1
        self.written = ""
        self.before_character = lambda: None
        self.controller = None
        self.pending = None
        self.defer = False

    def capture_target(self):
        return self.generation

    def target_is_current(self, target):
        return target == self.generation

    def inject(self, task_id, target, text, can_continue):
        if self.defer:
            self.pending = (task_id, target, text, can_continue)
            return
        for character in text:
            self.before_character()
            if not can_continue() or not self.target_is_current(target):
                return
            self.written += character
        self.controller.injection_finished(task_id)


@pytest.fixture
def setup():
    inputs = Inputs()
    states = []
    clock = [0.0]
    core = TaskController(inputs, on_state=states.append, clock=lambda: clock[0])
    inputs.controller = core
    return core, inputs, states, clock


def transcribing(core):
    task_id = core.begin(core.inputs.capture_target())
    assert core.recording_stopped(task_id)
    return task_id


def test_success_records_all_states_then_clears_task(setup):
    core, inputs, states, _ = setup
    task_id = transcribing(core)
    core.transcribed(task_id, "你好，world!\n🙂")
    assert inputs.written == "你好，world!\n🙂"
    assert states == [
        State.RECORDING,
        State.TRANSCRIBING,
        State.INJECTING,
        State.SUCCEEDED,
        State.IDLE,
    ]
    assert core.task is None and core.outcome == State.SUCCEEDED


def test_only_one_task_and_unique_ids(setup):
    core, _, _, _ = setup
    first = core.begin(core.inputs.capture_target())
    assert core.begin(core.inputs.capture_target()) is None
    core.cancel()
    assert core.begin(core.inputs.capture_target()) != first


@pytest.mark.parametrize("polish", [False, True])
def test_cancelled_and_stale_replies_never_inject(setup, polish):
    core, inputs, _, _ = setup
    core.polish = polish
    old = transcribing(core)
    core.transcribed(old, "first") if polish else None
    core.cancel()
    new = core.begin(core.inputs.capture_target())
    core.transcribed(old, "late transcript")
    core.polished(old, "late polish")
    core.polishing_failed(old)
    core.fail(old, Failure.TRANSCRIPTION)
    assert core.task.id == new and inputs.written == ""


@pytest.mark.parametrize(
    "phase", [State.RECORDING, State.TRANSCRIBING, State.POLISHING]
)
def test_focus_generation_change_even_away_and_back_cancels(setup, phase):
    core, inputs, _, _ = setup
    core.polish = True
    task_id = core.begin(core.inputs.capture_target())
    if phase != State.RECORDING:
        core.recording_stopped(task_id)
    if phase == State.POLISHING:
        core.transcribed(task_id, "original")
    inputs.generation += 2  # Same window can return with a different generation.
    core.tick()
    core.transcribed(task_id, "late")
    core.polished(task_id, "late")
    assert core.outcome == State.CANCELLED and core.failure == Failure.FOCUS
    assert inputs.written == ""


def test_focus_event_permanently_invalidates_task(setup):
    core, inputs, _, _ = setup
    task_id = transcribing(core)
    core.focus_changed()
    core.transcribed(task_id, "late")
    assert inputs.written == ""


@pytest.mark.parametrize("fallback", [True, False])
@pytest.mark.parametrize("empty", [True, False])
def test_polishing_failure_policy(setup, fallback, empty):
    core, inputs, _, _ = setup
    core.polish, core.fallback = True, fallback
    task_id = transcribing(core)
    core.transcribed(task_id, "original")
    if empty:
        core.polished(task_id, " \n")
    else:
        core.polishing_failed(task_id)
    assert inputs.written == ("original" if fallback else "")
    assert core.outcome == (State.SUCCEEDED if fallback else State.FAILED)


def test_polishing_success(setup):
    core, inputs, _, _ = setup
    core.polish = True
    task_id = transcribing(core)
    core.transcribed(task_id, "original")
    core.polished(task_id, "polished")
    assert inputs.written == "polished" and core.task is None


def test_empty_transcript_fails_without_polishing(setup):
    core, inputs, _, _ = setup
    core.transcribed(transcribing(core), " \n")
    assert core.failure == Failure.EMPTY and inputs.written == ""


def test_late_results_past_deadline_cannot_inject(setup):
    core, inputs, _, clock = setup
    task_id = transcribing(core)
    clock[0] = 180
    core.transcribed(task_id, "late")
    assert core.failure == Failure.TIMEOUT and inputs.written == ""


def test_out_of_order_callbacks_are_ignored(setup):
    core, inputs, _, _ = setup
    task_id = core.begin(core.inputs.capture_target())
    core.transcribed(task_id, "too early")
    core.polished(task_id, "too early")
    assert core.state == State.RECORDING and inputs.written == ""


def test_cancel_during_injection_stops_remaining_characters(setup):
    core, inputs, _, _ = setup
    inputs.before_character = lambda: core.cancel() if inputs.written else None
    core.transcribed(transcribing(core), "abc")
    assert inputs.written == "a" and core.outcome == State.CANCELLED


def test_last_moment_focus_loss_blocks_injection(setup):
    core, inputs, _, _ = setup
    inputs.before_character = lambda: setattr(inputs, "generation", 2)
    core.transcribed(transcribing(core), "abc")
    assert inputs.written == "" and core.failure == Failure.FOCUS


def test_adapter_exception_is_sanitized_and_new_task_can_start(setup):
    core, inputs, _, _ = setup

    def broken():
        raise RuntimeError("secret key and transcript must never be exposed")

    inputs.before_character = broken
    core.transcribed(transcribing(core), "private text")
    assert core.failure == Failure.INJECTION and core.task is None
    assert "secret" not in str(core.failure)
    assert core.begin(core.inputs.capture_target()) is not None


def test_state_callback_can_cancel_before_injection(setup):
    core, inputs, _, _ = setup
    core.on_state = lambda state: core.cancel() if state == State.INJECTING else None
    core.transcribed(transcribing(core), "late")
    assert inputs.written == "" and core.outcome == State.CANCELLED


def test_terminal_callback_cannot_restart_until_idle(setup):
    core, _, _, _ = setup
    restarts = []
    core.on_state = lambda state: (
        restarts.append(core.begin(core.inputs.capture_target()))
        if state == State.SUCCEEDED
        else None
    )
    core.transcribed(transcribing(core), "done")
    assert restarts == [None] and core.state == State.IDLE
    assert core.begin(core.inputs.capture_target()) is not None


def test_async_delivery_waits_for_matching_completion(setup):
    core, inputs, _, _ = setup
    inputs.defer = True
    task_id = transcribing(core)
    core.transcribed(task_id, "queued")
    assert core.state == State.INJECTING and core.outcome is None
    core.injection_finished("wrong-id")
    assert core.state == State.INJECTING
    core.injection_finished(task_id)
    assert core.outcome == State.SUCCEEDED


@pytest.mark.parametrize("completion", ["injection_finished", "injection_failed"])
def test_async_delivery_after_cancel_cannot_affect_next_task(setup, completion):
    core, inputs, _, _ = setup
    inputs.defer = True
    old = transcribing(core)
    core.transcribed(old, "queued")
    can_continue = inputs.pending[-1]
    core.cancel()
    new = core.begin(inputs.capture_target())
    assert not can_continue()
    getattr(core, completion)(old)
    assert core.task.id == new and core.state == State.RECORDING


@pytest.mark.parametrize("raising_state", [State.CANCELLED, State.IDLE])
def test_observer_exception_does_not_strand_lifecycle(setup, raising_state):
    core, _, _, _ = setup
    core.begin(core.inputs.capture_target())

    def observe(state):
        if state == raising_state:
            raise RuntimeError("Observer failed")

    core.on_state = observe
    with pytest.raises(RuntimeError, match="Observer failed"):
        core.cancel()
    assert core.task is None and core.state == State.IDLE
    assert core.outcome == State.CANCELLED
    core.on_state = None
    assert core.begin(core.inputs.capture_target()) is not None
