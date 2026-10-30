"""Single-task lifecycle with cancellation, deadlines and stale-reply protection."""

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
    UNCONFIRMED = "unconfirmed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Failure(StrEnum):
    TIMEOUT = "task_timed_out"
    AUDIO = "audio_failed"
    TRANSCRIPTION = "transcription_failed"
    POLISHING = "polishing_failed"
    EMPTY = "empty_result"
    INJECTION = "injection_failed"


class InputPort(Protocol):
    """Deliver to current focus, checking task validity before each key event.

    inject dispatches asynchronous work and reports completion with the task ID.
    Focus changes are intentional; cancellation and expired tasks stop delivery.
    No clipboard is used.
    """

    def inject(
        self,
        task_id: str,
        text: str,
        can_continue: Callable[[], bool],
    ) -> None: ...


@dataclass
class Task:
    id: str
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

    def begin(self) -> str | None:
        """Start without inspecting or remembering a desktop input target."""
        if self.task or self._finishing:
            return None
        self.outcome = self.failure = None
        self.task = Task(uuid.uuid4().hex, self.clock() + self.timeout_seconds)
        self._state(State.RECORDING)
        return self.task.id if self.task else None

    def _finish(self, outcome: State, failure: Failure | None = None) -> None:
        # Release text before notifying UI callbacks or starting new work.
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

    def _valid(self, task_id: str, state: State | None = None) -> bool:
        if not self.task or self.task.id != task_id:
            return False
        if state is not None and self.state != state:
            return False
        if self.clock() >= self.task.deadline:
            self._finish(State.FAILED, Failure.TIMEOUT)
            return False
        return True

    def tick(self) -> None:
        """Check deadlines while awaiting asynchronous recording or replies."""
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
                text,
                lambda: self._valid(task_id, State.INJECTING),
            )
        except Exception:
            self.injection_failed(task_id)

    def injection_finished(self, task_id: str) -> None:
        if self._valid(task_id, State.INJECTING):
            self._finish(State.SUCCEEDED)

    def injection_unconfirmed(self, task_id: str) -> None:
        """All dispatches completed, but target receipt cannot be confirmed."""
        if self._valid(task_id, State.INJECTING):
            self._finish(State.UNCONFIRMED)

    def begin_streaming_output(self, task_id: str) -> bool:
        """Enter output once; streamed text never has an original-text replay path."""
        if not self._valid(task_id, State.POLISHING):
            return False
        self.task.original = ""
        self._state(State.INJECTING)
        return self._valid(task_id, State.INJECTING)

    def resume_unsent_streaming_preparation(self, task_id: str, original: str) -> bool:
        """Coordinator-only rollback after a typed whole-task-zero route marker.

        No attempted or ambiguous transport result authorizes this transition.
        Task validity and the absolute deadline remain unchanged.
        """
        if (
            not self._valid(task_id, State.INJECTING)
            or not isinstance(original, str)
            or not original
            or self.task.original != ""
        ):
            return False
        self.task.original = original
        self._state(State.POLISHING)
        return self._valid(task_id, State.POLISHING)

    def injection_failed(self, task_id: str) -> None:
        if self._valid(task_id, State.INJECTING):
            self._finish(State.FAILED, Failure.INJECTION)
