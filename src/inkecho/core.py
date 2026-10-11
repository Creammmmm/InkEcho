"""Single-task lifecycle with cancellation and captured-target safety."""

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class State(StrEnum):
    IDLE = "idle"
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    POLISHING = "polishing"
    INJECTING = "injecting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Failure(StrEnum):
    TARGET = "target_unavailable"
    FOCUS = "target_changed"
    TIMEOUT = "task_timed_out"
    AUDIO = "audio_failed"
    TRANSCRIPTION = "transcription_failed"
    POLISHING = "polishing_failed"
    EMPTY = "empty_result"
    INJECTION = "injection_failed"


class InputPort(Protocol):
    """A target includes a focus generation invalidated even after focus returns.

    inject dispatches asynchronous work and returns immediately. The adapter
    reports completion through injection_finished/injection_failed with task_id.
    It must check can_continue and actual focus before every delivery chunk.
    The callback alone cannot make an unverified backend safe. No clipboard use.
    """

    def target_is_current(self, target: object) -> bool: ...

    def inject(
        self,
        task_id: str,
        target: object,
        text: str,
        can_continue: Callable[[], bool],
    ) -> None: ...


@dataclass
class Task:
    id: str
    target: object = field(repr=False)
    deadline: float
    original: str = field(default="", repr=False)


class TaskController:
    """Call from one event-loop thread; provider replies must carry their task ID."""

    def __init__(
        self,
        inputs: InputPort,
        *,
        polish: bool = False,
        fallback: bool = True,
        timeout_seconds: float = 180,
        clock: Callable[[], float] = time.monotonic,
        on_state: Callable[[State], None] | None = None,
    ) -> None:
        if not 1 <= timeout_seconds <= 600:
            raise ValueError("Task timeout must be between 1 and 600 seconds.")
        self.inputs = inputs
        self.polish = polish
        self.fallback = fallback
        self.timeout_seconds = timeout_seconds
        self.clock = clock
        self.on_state = on_state
        self.state = State.IDLE
        self.task: Task | None = None
        self.outcome: State | None = None
        self.failure: Failure | None = None
        self._finishing = False

    def _state(self, state: State) -> None:
        self.state = state
        if self.on_state:
            self.on_state(state)

    def begin(self, target: object) -> str | None:
        """Start after the orchestrator has asynchronously captured the target."""
        if self.task or self._finishing:
            return None
        self.outcome = self.failure = None
        try:
            if not self.inputs.target_is_current(target):
                raise ValueError("No active target")
        except Exception:
            self._finish(State.FAILED, Failure.TARGET)
            return None
        self.task = Task(uuid.uuid4().hex, target, self.clock() + self.timeout_seconds)
        self._state(State.RECORDING)
        return self.task.id if self.task else None

    def _finish(self, outcome: State, failure: Failure | None = None) -> None:
        # Release text and target before notifying UI callbacks or starting new work.
        self.task = None
        self.outcome, self.failure = outcome, failure
        self._finishing = True
        try:
            self._state(outcome)
        finally:
            try:
                self._state(State.IDLE)
            finally:
                self._finishing = False

    def cancel(self) -> None:
        if self.task:
            self._finish(State.CANCELLED)

    def focus_changed(self) -> None:
        if self.task:
            self._finish(State.CANCELLED, Failure.FOCUS)

    def _valid(self, task_id: str, state: State | None = None) -> bool:
        if not self.task or self.task.id != task_id:
            return False
        if state is not None and self.state != state:
            return False
        if self.clock() >= self.task.deadline:
            self._finish(State.FAILED, Failure.TIMEOUT)
            return False
        try:
            current = self.inputs.target_is_current(self.task.target)
        except Exception:
            current = False
        if not current:
            self.focus_changed()
            return False
        return True

    def tick(self) -> None:
        """Check deadline/focus while awaiting asynchronous recording or replies."""
        if self.task:
            self._valid(self.task.id)

    def recording_stopped(self, task_id: str) -> bool:
        if not self._valid(task_id, State.RECORDING):
            return False
        self._state(State.TRANSCRIBING)
        return True

    def transcribed(self, task_id: str, text: str) -> None:
        if not self._valid(task_id, State.TRANSCRIBING):
            return
        if not text.strip():
            self._finish(State.FAILED, Failure.EMPTY)
        elif self.polish:
            self.task.original = text
            self._state(State.POLISHING)
        else:
            self._inject(task_id, text)

    def polished(self, task_id: str, text: str) -> None:
        if not self._valid(task_id, State.POLISHING):
            return
        if text.strip():
            self._inject(task_id, text)
        else:
            self.polishing_failed(task_id)

    def polishing_failed(self, task_id: str) -> None:
        if not self._valid(task_id, State.POLISHING):
            return
        if self.fallback:
            self._inject(task_id, self.task.original)
        else:
            self._finish(State.FAILED, Failure.POLISHING)

    def fail(self, task_id: str, failure: Failure) -> None:
        if self._valid(task_id):
            self._finish(State.FAILED, failure)

    def _inject(self, task_id: str, text: str) -> None:
        self._state(State.INJECTING)
        if not self._valid(task_id, State.INJECTING):
            return
        try:
            self.inputs.inject(
                task_id,
                self.task.target,
                text,
                lambda: self._valid(task_id, State.INJECTING),
            )
        except Exception:
            self.injection_failed(task_id)

    def injection_finished(self, task_id: str) -> None:
        if self._valid(task_id, State.INJECTING):
            self._finish(State.SUCCEEDED)

    def injection_failed(self, task_id: str) -> None:
        if self._valid(task_id, State.INJECTING):
            self._finish(State.FAILED, Failure.INJECTION)
