"""Per-task monotonic milestones; never accept audio, text or provider metadata."""

import math
import time
from collections.abc import Callable

EVENTS = (
    "recording_started",
    "recording_stop_requested",
    "recording_stopped",
    "asr_started",
    "asr_completed",
    "polishing_started",
    "polishing_first_segment",
    "polishing_completed",
    "first_character_sent",
    "output_completed",
    "task_finished",
)

DURATIONS = {
    "stop_to_audio_ready_ms": ("recording_stop_requested", "recording_stopped"),
    "asr_ms": ("asr_started", "asr_completed"),
    "polishing_to_first_segment_ms": ("polishing_started", "polishing_first_segment"),
    "polishing_ms": ("polishing_started", "polishing_completed"),
    "stop_to_first_character_ms": ("recording_stop_requested", "first_character_sent"),
    "audio_ready_to_first_character_ms": ("recording_stopped", "first_character_sent"),
    "output_ms": ("first_character_sent", "output_completed"),
    "stop_to_output_completed_ms": ("recording_stop_requested", "output_completed"),
    "stop_to_task_finished_ms": ("recording_stop_requested", "task_finished"),
}


def validate_snapshot(snapshot: dict) -> dict:
    """Return a detached, fixed-schema copy suitable for diagnostic persistence."""
    valid = (
        type(snapshot) is dict
        and set(snapshot) == {"schema_version", "outcome", "events_ms", "durations_ms"}
        and type(snapshot["schema_version"]) is int
        and snapshot["schema_version"] == 1
        and type(snapshot["outcome"]) is str
        and snapshot["outcome"] in {"succeeded", "failed", "cancelled"}
    )
    if not valid:
        raise ValueError("Invalid performance metadata.")
    result = {"schema_version": 1, "outcome": snapshot["outcome"]}
    for field, keys in (("events_ms", EVENTS), ("durations_ms", DURATIONS)):
        values = snapshot[field]
        if type(values) is not dict or set(values) != set(keys):
            raise ValueError("Invalid performance metadata.")
        for value in values.values():
            if value is not None and (
                type(value) not in (int, float)
                or not 0 <= value <= 86_400_000
                or not math.isfinite(value)
            ):
                raise ValueError("Invalid performance metadata.")
        result[field] = values.copy()
    return result


class TaskTiming:
    """Fixed metadata schema, first observation wins, terminal snapshots are closed.

    A send milestone means transport dispatch, not proof that an application
    rendered the character. Missing observations stay None, never estimated.
    """

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._started = clock()
        self._events: dict[str, float] = {}
        self._outcome: str | None = None

    def mark(self, event: str, *, at: float | None = None) -> None:
        if event not in EVENTS:
            raise ValueError("Unknown performance milestone.")
        if self._outcome is None and event not in self._events:
            now = self._clock()
            observed = now if at is None else at
            if (
                type(observed) not in (int, float)
                or not self._started <= observed <= now
                or not math.isfinite(observed)
            ):
                raise ValueError("Invalid performance observation time.")
            self._events[event] = observed - self._started

    def finish(self, outcome: str) -> dict:
        if outcome not in {"succeeded", "failed", "cancelled"}:
            raise ValueError("Unknown task outcome.")
        if self._outcome is None:
            self.mark("task_finished")
            self._outcome = outcome
        return self.snapshot()

    def snapshot(self) -> dict:
        def duration(start, end):
            if start not in self._events or end not in self._events:
                return None
            return round(max(0.0, self._events[end] - self._events[start]) * 1000, 3)

        return {
            "schema_version": 1,
            "outcome": self._outcome,
            "events_ms": {
                name: round(self._events[name] * 1000, 3)
                if name in self._events
                else None
                for name in EVENTS
            },
            "durations_ms": {
                name: duration(start, end) for name, (start, end) in DURATIONS.items()
            },
        }
