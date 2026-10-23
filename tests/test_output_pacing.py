"""Synthetic scheduler checks; these do not validate any desktop feedback."""

import asyncio
import time
from dataclasses import replace

import pytest

from inkecho.platform.output_pacing import (
    FeedbackLevel,
    OutputPacer,
    PacingConfig,
    PacingScopeChanged,
)


class Clock:
    def __init__(self):
        self.now = 10.0

    def __call__(self):
        return self.now


class AdvancingPacer(OutputPacer):
    """Exercise interval decisions without relying on wall-clock precision."""

    def __init__(self, clock):
        super().__init__(clock=clock)
        self.waits = []

    async def _wait(self, token, active, deadline, until):
        self._check(token, active, deadline)
        self.waits.append(until - self.clock())
        self.clock.now = until
        self._check(token, active, deadline)


async def ready(pacer, token, *, mapping=False, deadline=None, active=lambda: True):
    await pacer.before_send(
        token,
        mapping_changed=mapping,
        active=active,
        deadline=time.monotonic() + 1 if deadline is None else deadline,
    )


@pytest.mark.parametrize("level", FeedbackLevel)
def test_first_character_adds_no_wait_or_draw_dependency(level):
    async def run():
        clock = Clock()
        pacer = AdvancingPacer(clock)
        token = pacer.bind(level)
        await ready(pacer, token, mapping=True, deadline=20)
        assert pacer.waits == []
        assert pacer.snapshot(token).pending == 0

    asyncio.run(run())


def test_mapping_changes_wait_but_cached_characters_do_not():
    async def run():
        clock = Clock()
        pacer = AdvancingPacer(clock)
        token = pacer.bind(FeedbackLevel.NONE)
        await ready(pacer, token, mapping=True, deadline=20)
        pacer.sent(token, mapping_changed=True)
        clock.now += 0.01
        await ready(pacer, token, mapping=True, deadline=20)
        assert pacer.waits == pytest.approx([0.05])
        pacer.sent(token)
        clock.now += 0.03
        await ready(pacer, token, mapping=False, deadline=20)
        assert pacer.waits == pytest.approx([0.05])

    asyncio.run(run())


def test_idle_future_and_pre_send_hints_cannot_bank_credit():
    clock = Clock()
    pacer = OutputPacer(clock=clock)
    token = pacer.bind(FeedbackLevel.DRAW)
    assert not pacer.observe(token)
    pacer.sent(token)
    assert not pacer.observe(token)
    assert not pacer.observe(token, at=11)
    assert not pacer.observe(token, at=9)
    clock.now += 0.02
    assert pacer.observe(token)
    for _ in range(1000):
        clock.now += 0.02
        assert not pacer.observe(token)
    assert pacer.snapshot(token).pending == pacer.snapshot(token).budget == 1
    with pytest.raises(RuntimeError, match="budget"):
        pacer.sent(token)


def test_draw_hints_raise_budget_slowly_with_an_absolute_cap_and_mapping_floor():
    async def run():
        clock = Clock()
        pacer = AdvancingPacer(clock)
        token = pacer.bind(FeedbackLevel.DRAW)
        deadline = 1000
        for cycle in range(120):
            budget = pacer.snapshot(token).budget
            for _ in range(budget):
                await ready(pacer, token, mapping=True, deadline=deadline)
                pacer.sent(token, mapping_changed=True)
                clock.now += 0.02
            assert pacer.observe(token)
            await ready(pacer, token, mapping=True, deadline=deadline)
            snapshot = pacer.snapshot(token)
            assert snapshot.budget <= 4
            assert snapshot.mapping_interval >= 0.020
            if cycle < 3:
                assert snapshot.budget == 1
        assert pacer.snapshot(token).budget == 4
        assert pacer.snapshot(token).mapping_interval == 0.020

    asyncio.run(run())


def test_progress_before_full_window_does_not_retire_later_input():
    async def run():
        clock = Clock()
        pacer = AdvancingPacer(clock)
        token = pacer.bind(FeedbackLevel.DRAW)
        for _ in range(4):
            pacer.sent(token)
            clock.now += 0.02
            assert pacer.observe(token)
            await ready(pacer, token, deadline=30)
        assert pacer.snapshot(token).budget == 2
        pacer.sent(token)
        clock.now += 0.02
        assert not pacer.observe(token)
        pacer.sent(token)
        assert not pacer.observe(token)
        clock.now += 0.02
        assert pacer.observe(token)
        await ready(pacer, token, deadline=30)
        assert pacer.snapshot(token).pending == 0

    asyncio.run(run())


def test_feedback_timeout_retires_only_scheduling_debt_and_backs_off():
    async def run():
        config = replace(PacingConfig(), feedback_min=0.001, feedback_max=0.002)
        pacer = OutputPacer(config)
        token = pacer.bind(FeedbackLevel.DRAW)
        deadline = time.monotonic() + 1
        await ready(pacer, token, deadline=deadline)
        pacer.sent(token)
        await ready(pacer, token, deadline=deadline)
        snapshot = pacer.snapshot(token)
        assert snapshot.pending == 0 and snapshot.budget == 1
        assert snapshot.mapping_interval == pytest.approx(0.090)
        # No sender exists in this model: timeout cannot replay a character.
        pacer.sent(token)
        await ready(pacer, token, deadline=deadline)
        assert pacer.snapshot(token).mapping_interval == 0.120

    asyncio.run(run())


def test_old_feedback_cannot_wake_new_target_even_when_xid_returns():
    async def run():
        pacer = OutputPacer()
        token_a1 = pacer.bind(FeedbackLevel.DRAW)
        token_b = pacer.bind(FeedbackLevel.DRAW)
        token_a2 = pacer.bind(FeedbackLevel.DRAW)
        assert len({token_a1, token_b, token_a2}) == 3
        pacer.sent(token_a2)
        waiter = asyncio.create_task(ready(pacer, token_a2))
        await asyncio.sleep(0)
        assert not pacer.observe(token_a1)
        assert not pacer.observe(token_b)
        await asyncio.sleep(0)
        assert not waiter.done()
        assert pacer.snapshot(token_a2).pending == 1
        assert pacer.observe(token_a2)
        await waiter
        assert pacer.snapshot(token_a2).pending == 0

    asyncio.run(run())


@pytest.mark.parametrize("action", ["invalidate", "replace", "task_cancel"])
def test_cancel_or_replacement_wakes_wait_without_feedback_timeout(action):
    async def run():
        config = replace(PacingConfig(), feedback_min=10, feedback_max=10)
        pacer = OutputPacer(config)
        token = pacer.bind(FeedbackLevel.DRAW)
        pacer.sent(token)
        waiter = asyncio.create_task(ready(pacer, token))
        await asyncio.sleep(0)
        if action == "invalidate":
            assert pacer.invalidate(token)
        elif action == "replace":
            pacer.bind(FeedbackLevel.NONE)
        else:
            waiter.cancel()
        expected = PacingScopeChanged if action == "replace" else asyncio.CancelledError
        with pytest.raises(expected):
            await asyncio.wait_for(waiter, 0.1)

    asyncio.run(run())


def test_inactive_and_expired_deadline_stop_before_wait_or_send():
    async def run():
        pacer = OutputPacer()
        token = pacer.bind(FeedbackLevel.DRAW)
        with pytest.raises(asyncio.CancelledError):
            await ready(pacer, token, active=lambda: False)
        with pytest.raises(asyncio.CancelledError):
            await ready(pacer, token, active=lambda: True)
        token = pacer.bind(FeedbackLevel.DRAW)
        with pytest.raises(asyncio.CancelledError):
            await ready(pacer, token, deadline=time.monotonic() - 1)
        assert not pacer.observe(token)
        with pytest.raises(asyncio.CancelledError):
            pacer.sent(token)

    asyncio.run(run())


def test_absolute_deadline_is_not_extended_by_feedback_or_fragments():
    async def run():
        pacer = OutputPacer()
        token = pacer.bind(FeedbackLevel.DRAW)
        deadline = time.monotonic() + 0.005
        await ready(pacer, token, deadline=deadline)
        with pytest.raises(asyncio.CancelledError):
            await ready(pacer, token, deadline=deadline + 1)
        with pytest.raises(asyncio.CancelledError):
            await ready(pacer, token, deadline=deadline)
        token = pacer.bind(FeedbackLevel.DRAW)
        await ready(pacer, token, deadline=deadline)
        pacer.sent(token)
        with pytest.raises(asyncio.CancelledError):
            await ready(pacer, token, deadline=deadline)
        assert not pacer.observe(token)

    asyncio.run(run())


def test_input_ack_is_not_draw_feedback_and_only_congestion_adds_delay():
    async def run():
        clock = Clock()
        pacer = AdvancingPacer(clock)
        token = pacer.bind(FeedbackLevel.INPUT)
        assert pacer.ack(token, started=9.95, completed=10)
        await ready(pacer, token, deadline=30)
        pacer.sent(token)
        assert not pacer.observe(token)
        assert pacer.waits == []
        clock.now = 11
        assert pacer.ack(token, started=10.95, completed=11)
        assert pacer.snapshot(token).input_delay == 0
        clock.now = 12
        assert pacer.ack(token, started=11.5, completed=12)
        assert pacer.snapshot(token).input_delay == 0.120
        await ready(pacer, token, deadline=30)
        assert pacer.waits == pytest.approx([0.120])
        assert pacer.snapshot(token).pending == 0
        assert pacer.reset_input(token)
        assert pacer.snapshot(token).input_delay == 0
        assert not pacer.ack(token, started=11.5, completed=12)
        clock.now = 13
        assert pacer.ack(token, started=12.95, completed=13)
        assert pacer.snapshot(token).input_delay == 0

    asyncio.run(run())


def test_ack_and_reset_from_old_scope_cannot_change_new_scope():
    pacer = OutputPacer()
    old = pacer.bind(FeedbackLevel.INPUT)
    new = pacer.bind(FeedbackLevel.INPUT)
    assert not pacer.ack(old, started=1, completed=2)
    assert not pacer.reset_input(old)
    assert not pacer.ack(new, started=2, completed=1)
    assert not pacer.ack(new, started=0, completed=float("inf"))
    assert pacer.snapshot(new).input_delay == 0
    draw = pacer.bind(FeedbackLevel.DRAW)
    assert not pacer.ack(draw, started=1, completed=2)
    assert not pacer.reset_input(draw)


def test_input_mapping_and_cache_rtt_estimates_do_not_contaminate_each_other():
    clock = Clock()
    pacer = OutputPacer(clock=clock)
    token = pacer.bind(FeedbackLevel.INPUT)
    for duration, changed in [(0.050, True), (0.010, False)] * 30:
        clock.now += 1
        assert pacer.ack(
            token,
            started=clock.now - duration,
            completed=clock.now,
            mapping_changed=changed,
        )
        assert pacer.snapshot(token).input_delay == 0
    clock.now += 1
    assert pacer.ack(
        token, started=clock.now - 0.200, completed=clock.now, mapping_changed=False
    )
    assert pacer.snapshot(token).input_delay > 0
    # A legacy worker is an independent unknown-cost bucket with a fresh start.
    clock.now += 1
    assert pacer.ack(token, started=clock.now - 0.030, completed=clock.now)
    assert pacer.snapshot(token).input_delay == 0
    assert not pacer.ack(
        token, started=clock.now - 0.010, completed=clock.now, mapping_changed=1
    )


@pytest.mark.parametrize("phase", ["draw", "mapping"])
def test_cancel_after_hint_and_during_mapping_wait_invalidates_generation(phase):
    async def run():
        config = replace(PacingConfig(), mapping_initial=1, mapping_max=1)
        pacer = OutputPacer(config)
        token = pacer.bind(FeedbackLevel.DRAW)
        pacer.sent(token, mapping_changed=True)
        if phase == "mapping":
            assert pacer.observe(token)
        waiter = asyncio.create_task(ready(pacer, token, mapping=True))
        await asyncio.sleep(0)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(waiter, 0.1)
        assert not pacer.observe(token)
        with pytest.raises(asyncio.CancelledError):
            pacer.sent(token)

    asyncio.run(run())


def test_active_exception_invalidates_only_its_own_generation():
    async def run():
        pacer = OutputPacer()
        token = pacer.bind(FeedbackLevel.INPUT)

        def failed_check():
            raise RuntimeError("owned task ended")

        with pytest.raises(RuntimeError, match="owned task ended"):
            await ready(pacer, token, active=failed_check)
        assert not pacer.ack(token, started=1, completed=2)

        token = pacer.bind(FeedbackLevel.INPUT)
        replacement = None

        def replaced_check():
            nonlocal replacement
            replacement = pacer.bind(FeedbackLevel.INPUT)
            raise RuntimeError("owned task replaced")

        with pytest.raises(RuntimeError, match="owned task replaced"):
            await ready(pacer, token, active=replaced_check)
        assert pacer.snapshot(replacement).level == FeedbackLevel.INPUT

    asyncio.run(run())


def test_active_callback_replacement_is_rechecked_before_return():
    async def run():
        pacer = OutputPacer()
        token = pacer.bind(FeedbackLevel.DRAW)

        def replace_but_allow():
            pacer.bind(FeedbackLevel.NONE)
            return True

        with pytest.raises(PacingScopeChanged):
            await ready(pacer, token, active=replace_but_allow)

    asyncio.run(run())


def test_real_task_cancel_is_not_downgraded_to_target_reselection():
    async def run():
        pacer = OutputPacer()
        old = pacer.bind(FeedbackLevel.DRAW)
        pacer.sent(old)
        waiter = asyncio.create_task(ready(pacer, old))
        await asyncio.sleep(0)
        new = pacer.bind(FeedbackLevel.DRAW)
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter
        # Cleanup of the cancelled old waiter must not expire the new target.
        assert pacer.snapshot(new).pending == 0

    asyncio.run(run())


def test_invalidate_during_event_clear_is_not_lost():
    async def run():
        pacer = OutputPacer()
        token = pacer.bind(FeedbackLevel.DRAW)
        pacer.sent(token)
        scope = pacer._scope
        original_clear = scope.changed.clear

        def invalidate_after_clear():
            original_clear()
            pacer.invalidate(token)

        scope.changed.clear = invalidate_after_clear
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(ready(pacer, token), 0.1)

    asyncio.run(run())


@pytest.mark.parametrize("value", [10**1000, "1", True, None, float("nan")])
def test_invalid_advisory_numbers_are_discarded_without_raising(value):
    clock = Clock()
    pacer = OutputPacer(clock=clock)
    draw = pacer.bind(FeedbackLevel.DRAW)
    pacer.sent(draw)
    if value is not None:  # None means use local receive time, not a raw sample.
        assert not pacer.observe(draw, at=value)
    token = pacer.bind(FeedbackLevel.INPUT)
    assert not pacer.ack(token, started=value, completed=10)
    assert not pacer.ack(token, started=1, completed=value)
    assert pacer.snapshot(token).input_delay == 0


@pytest.mark.parametrize(
    "changes",
    [
        {"mapping_min": 0},
        {"mapping_initial": 0.5},
        {"feedback_max": 0},
        {"coalesce": 0},
        {"mapping_max": float("nan")},
        {"max_inflight": 5},
        {"max_inflight": True},
    ],
)
def test_invalid_bounds_are_rejected(changes):
    with pytest.raises(ValueError):
        replace(PacingConfig(), **changes)
