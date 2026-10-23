"""Bounded output pacing; progress hints never acknowledge displayed characters.

This model does not send input, select focus, or retry anything. Adapters retain
their key timing and mapping ownership checks. INPUT adapters must keep their
existing single-request transport; only DRAW adapters use the hint budget.
"""

import asyncio
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum


def _finite_number(value) -> bool:
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


class FeedbackLevel(StrEnum):
    NONE = "none"
    INPUT = "input"
    DRAW = "draw"


class PacingScopeChanged(Exception):
    """The observation target changed; only unattempted input may reselect.

    This is deliberately distinct from task cancellation. A transport may catch
    it before a physical press, recheck the task and select the current target.
    It must never catch it after a press as permission to replay that input.
    """


@dataclass(frozen=True)
class PacingConfig:
    """Experimental bounds, not validated desktop defaults.

    Mapping intervals apply only to actual map changes. Physical press/release
    floors belong to the transport and must not be removed by this controller.
    """

    mapping_min: float = 0.020
    mapping_initial: float = 0.060
    mapping_max: float = 0.120
    reuse_fallback: float = 0.020
    feedback_min: float = 0.080
    feedback_max: float = 0.250
    coalesce: float = 0.016
    max_inflight: int = 4

    def __post_init__(self):
        values = (
            self.mapping_min,
            self.mapping_initial,
            self.mapping_max,
            self.reuse_fallback,
            self.feedback_min,
            self.feedback_max,
            self.coalesce,
        )
        if any(not _finite_number(value) or value < 0 for value in values):
            raise ValueError("Invalid pacing bounds")
        if not 0 < self.mapping_min <= self.mapping_initial <= self.mapping_max:
            raise ValueError("Invalid mapping bounds")
        if not 0 < self.feedback_min <= self.feedback_max or self.coalesce <= 0:
            raise ValueError("Invalid feedback bounds")
        if type(self.max_inflight) is not int or not 1 <= self.max_inflight <= 4:
            raise ValueError("Invalid in-flight bound")


@dataclass
class _Scope:
    token: int
    level: FeedbackLevel
    changed: asyncio.Event = field(default_factory=asyncio.Event)
    valid: bool = True
    sent: int = 0
    budget: int = 1
    successes: int = 0
    last_sent: float | None = None
    last_mapping: float | None = None
    last_hint: float | None = None
    hint: bool = False
    latency: float | None = None
    jitter: float = 0.0
    interval: float = 0.0
    input_baselines: dict[bool | None, float] = field(default_factory=dict)
    input_delay: float = 0.0
    last_ack: float | None = None
    deadline: float | None = None


@dataclass(frozen=True)
class PacingSnapshot:
    """Fixed numerical diagnostics; no user text or target contents."""

    token: int
    level: FeedbackLevel
    budget: int
    pending: int
    mapping_interval: float
    input_delay: float


class OutputPacer:
    """One output owner, with separate wakeups for every target generation.

    Bind only during output. A new bind wakes and invalidates the previous
    generation, even when returning to the same XID. Adapters must capture the
    returned token in callbacks, never look up the latest token in a callback.
    """

    def __init__(
        self,
        config: PacingConfig | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.config = config or PacingConfig()
        self.clock = clock
        self._serial = 0
        self._scope: _Scope | None = None

    def bind(self, level: FeedbackLevel) -> int:
        level = FeedbackLevel(level)
        if self._scope is not None:
            self.invalidate(self._scope.token)
        self._serial += 1
        self._scope = _Scope(self._serial, level, interval=self.config.mapping_initial)
        return self._serial

    def invalidate(self, token: int) -> bool:
        scope = self._scope
        if scope is None or not scope.valid or scope.token != token:
            return False
        scope.valid = False
        scope.changed.set()
        return True

    def _current(self, token: int) -> _Scope:
        scope = self._scope
        if scope is not None and scope.token != token:
            raise PacingScopeChanged
        if scope is None or not scope.valid:
            raise asyncio.CancelledError
        return scope

    def snapshot(self, token: int) -> PacingSnapshot:
        scope = self._current(token)
        return PacingSnapshot(
            token,
            scope.level,
            scope.budget,
            scope.sent,
            scope.interval,
            scope.input_delay,
        )

    def observe(self, token: int, *, at: float | None = None) -> bool:
        """Accept at most one DRAW hint per outstanding bounded window.

        Use local receive time. Idle, duplicate and coalesced animation events
        cannot accumulate credit for future input. An accepted hint is weak
        scheduling evidence, never a statement that any character was drawn.
        """
        scope = self._scope
        now = self.clock()
        at = now if at is None else at
        if (
            scope is None
            or not scope.valid
            or scope.token != token
            or scope.level != FeedbackLevel.DRAW
            or scope.sent < scope.budget
            or scope.hint
            or not _finite_number(at)
            or at > now
            or scope.last_sent is None
            or at <= scope.last_sent
            or (
                scope.last_hint is not None
                and at - scope.last_hint < self.config.coalesce
            )
        ):
            return False
        delay = at - scope.last_sent
        if scope.latency is None:
            scope.latency = delay
        else:
            scope.jitter = 0.75 * scope.jitter + 0.25 * abs(delay - scope.latency)
            scope.latency = 0.875 * scope.latency + 0.125 * delay
        scope.last_hint, scope.hint = at, True
        scope.changed.set()
        return True

    def ack(
        self,
        token: int,
        *,
        started: float,
        completed: float,
        mapping_changed: bool | None = None,
    ) -> bool:
        """Observe an INPUT request RTT, without claiming target drawing.

        Ordinary serial ACK latency establishes a baseline. Only a rise above
        that baseline produces bounded extra delay. Transport timeout remains a
        transport failure; this method cannot turn it into successful delivery.
        """
        scope = self._scope
        if (
            scope is None
            or not scope.valid
            or scope.token != token
            or scope.level != FeedbackLevel.INPUT
            or (mapping_changed is not None and type(mapping_changed) is not bool)
            or not all(_finite_number(value) for value in (started, completed))
            or not 0 <= started <= completed <= self.clock()
            or (scope.last_ack is not None and completed <= scope.last_ack)
        ):
            return False
        latency = completed - started
        scope.last_ack = completed
        baseline = scope.input_baselines.get(mapping_changed)
        if baseline is None:
            scope.input_baselines[mapping_changed] = latency
            scope.input_delay = 0.0
        else:
            excess = max(0.0, latency - max(2 * baseline, baseline + 0.010))
            scope.input_delay = min(
                self.config.mapping_max,
                max(excess, scope.input_delay * 0.75),
            )
            # Rise slowly; a single stalled request must not erase the baseline.
            scope.input_baselines[mapping_changed] = baseline + (latency - baseline) * (
                0.02 if latency > baseline else 0.25
            )
        return True

    def reset_input(self, token: int) -> bool:
        """Drop invalid advisory samples without changing delivery semantics."""
        scope = self._scope
        if (
            scope is None
            or not scope.valid
            or scope.token != token
            or scope.level != FeedbackLevel.INPUT
        ):
            return False
        scope.input_baselines.clear()
        scope.input_delay = 0.0
        # Keep last_ack: duplicate old replies cannot become fresh samples.
        return True

    def sent(self, token: int, *, mapping_changed: bool = False) -> None:
        """Record actual attempted input once; the caller never retries it.

        Call after a physical press has been attempted. Failure/ambiguous
        delivery is handled by transport cleanup, not by rolling this back.
        """
        scope = self._current(token)
        now = self.clock()
        if scope.level == FeedbackLevel.DRAW:
            if scope.sent >= scope.budget:
                raise RuntimeError("Pacing budget exceeded")
            scope.sent += 1
        scope.last_sent = now
        if mapping_changed:
            scope.last_mapping = now

    def _check(self, token, active, deadline):
        self._current(token)
        try:
            allowed = active()
        except BaseException:
            self.invalidate(token)
            raise
        if not allowed or self.clock() >= deadline:
            self.invalidate(token)
            raise asyncio.CancelledError
        # active() may synchronously expire a task or replace this generation.
        return self._current(token)

    async def _wait(self, token, active, deadline, until):
        scope = self._check(token, active, deadline)
        while self.clock() < until:
            scope.changed.clear()
            duration = min(until, deadline, self.clock() + 0.010) - self.clock()
            if duration > 0:
                try:
                    await asyncio.wait_for(scope.changed.wait(), duration)
                except TimeoutError:
                    pass
                except asyncio.CancelledError:
                    self.invalidate(token)
                    raise
            scope = self._check(token, active, deadline)

    async def before_send(
        self,
        token: int,
        *,
        mapping_changed: bool,
        active: Callable[[], bool],
        deadline: float,
    ) -> None:
        """Wait within an unchanged absolute task deadline; never dispatch input.

        Task cancellation propagates immediately. Invalidate wakes waits on a
        lost target. A caller must reselect focus and recheck task validity after
        this await and immediately before its actual press.
        """
        if not _finite_number(deadline):
            self.invalidate(token)
            raise ValueError("Invalid deadline")
        scope = self._check(token, active, deadline)
        if scope.deadline is None:
            scope.deadline = deadline
        elif scope.deadline != deadline:
            self.invalidate(token)
            raise asyncio.CancelledError
        if scope.level == FeedbackLevel.DRAW and scope.sent >= scope.budget:
            estimate = (scope.latency or 0) * 2 + scope.jitter * 4
            timeout = min(
                self.config.feedback_max, max(self.config.feedback_min, estimate)
            )
            until = self.clock() + timeout
            while not scope.hint and self.clock() < until:
                scope.changed.clear()
                try:
                    await asyncio.wait_for(
                        scope.changed.wait(),
                        min(0.010, until - self.clock(), deadline - self.clock()),
                    )
                except TimeoutError:
                    pass
                except asyncio.CancelledError:
                    self.invalidate(token)
                    raise
                scope = self._check(token, active, deadline)
            if scope.hint:
                scope.successes += 1
                if scope.successes >= 4:
                    scope.budget = min(self.config.max_inflight, scope.budget + 1)
                    scope.interval = max(
                        self.config.mapping_min, scope.interval - 0.002
                    )
                    scope.successes = 0
            else:
                scope.budget, scope.successes = 1, 0
                scope.interval = min(self.config.mapping_max, scope.interval * 1.5)
            # A hint releases one finite window, not one credit per event. A
            # timeout also retires scheduling debt, never retries sent input.
            scope.sent, scope.hint = 0, False
        delay = 0.0
        if scope.level == FeedbackLevel.INPUT:
            delay = scope.input_delay
        elif mapping_changed and scope.last_mapping is not None:
            delay = max(0.0, scope.last_mapping + scope.interval - self.clock())
        elif scope.level == FeedbackLevel.NONE and scope.last_sent is not None:
            delay = max(
                0.0, scope.last_sent + self.config.reuse_fallback - self.clock()
            )
        if delay:
            await self._wait(token, active, deadline, self.clock() + delay)
        self._check(token, active, deadline)
