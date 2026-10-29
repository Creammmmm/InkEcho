import asyncio
import time
from contextlib import asynccontextmanager

import pytest

from inkecho.platform.hybrid_keyboard import HybridKeyboardInput
from inkecho.platform.keyboard import KeyboardError, KeyboardInput


class Driver:
    def __init__(self, events):
        self.events = events
        self.is_x = True
        self.mapped = None
        self.applied = None
        self.after_map = None
        self.error = None

    def focus(self):
        if self.error:
            raise KeyboardError(self.error)
        if not self.is_x:
            raise KeyboardError("unsupported_target")
        return 42

    def map(self, char):
        self.mapped = char
        if char != "\n":
            self.applied = char
        self.events.append(("map", char))
        if self.after_map:
            self.after_map()
        return 248

    def verify(self):
        pass

    def send(self, window, code, pressed):
        self.events.append(("x", self.mapped, pressed))

    def restore(self):
        self.events.append(("restore", self.mapped))
        self.mapped = None
        self.applied = None

    def close(self):
        self.restore()


class Native:
    connected = authorized = True

    def __init__(self, driver, events):
        self.driver, self.events = driver, events
        self.after_key = None

    async def connect(self):
        pass

    async def authorize(self, parent_window=""):
        pass

    @asynccontextmanager
    async def output_session(self):
        assert self.driver.mapped is None
        self.events.append(("begin",))
        try:
            yield
        finally:
            self.events.append(("finish",))

    async def _insert_prefix(
        self, text, can_continue, *, deadline, on_first_sent, selected
    ):
        assert self.driver.mapped is None
        count = 0
        for char in text:
            if not selected():
                break
            assert can_continue() and time.monotonic() < deadline
            self.events.append(("native", char))
            on_first_sent(time.monotonic())
            count += 1
            if self.after_key:
                self.after_key()
        return count

    async def aclose(self):
        pass


async def setup():
    events = []
    driver = Driver(events)
    x11 = KeyboardInput(driver_factory=lambda: driver)
    native = Native(driver, events)
    hybrid = HybridKeyboardInput(native=native, x11=x11)
    await hybrid.connect()
    return hybrid, driver, native, events


def test_hybrid_feedback_timeout_snapshot_survives_backend_switch():
    async def run():
        hybrid, driver, native, _events = await setup()
        timeout = [0.04]
        hybrid.set_feedback_timeout_reader(lambda: timeout[0])
        async with hybrid.output_session():
            driver.is_x = False
            assert await hybrid.insert("甲", lambda: True) == 1
            timeout[0] = 0.12
            driver.is_x = True
            assert await hybrid.insert("乙", lambda: True) == 1
            assert hybrid.x11._pacer.config.feedback_min == 0.04
        async with hybrid.output_session():
            assert await hybrid.insert("丙", lambda: True) == 1
            assert hybrid.x11._pacer.config.feedback_min == 0.12
        await hybrid.aclose()

    asyncio.run(run())


def test_hybrid_mapping_wait_snapshot_survives_backend_switch():
    async def run():
        hybrid, driver, native, _events = await setup()
        wait = [0.04]
        hybrid.set_mapping_wait_reader(lambda: wait[0])
        async with hybrid.output_session():
            driver.is_x = False
            assert await hybrid.insert("甲", lambda: True) == 1
            wait[0] = 0.08
            driver.is_x = True
            assert await hybrid.insert("乙", lambda: True) == 1
            assert hybrid.x11._output_mapping_wait == 0.04
        async with hybrid.output_session():
            assert await hybrid.insert("丙", lambda: True) == 1
            assert hybrid.x11._output_mapping_wait == 0.08
        await hybrid.aclose()

    asyncio.run(run())


def test_x_map_wait_switches_before_press_without_replaying_prefix():
    async def run():
        hybrid, driver, native, events = await setup()
        driver.after_map = lambda: setattr(driver, "is_x", False)
        callbacks = []
        assert (
            await hybrid.insert("中文", lambda: True, on_first_sent=callbacks.append)
            == 2
        )
        assert not [event for event in events if event[0] == "x"]
        assert [("native", char) for char in "中文"] == [
            event for event in events if event[0] == "native"
        ]
        assert events.index(("restore", "中")) < events.index(("begin",))
        assert len(callbacks) == 1

    asyncio.run(run())


def test_native_segment_finishes_before_x11_and_callback_is_once():
    async def run():
        hybrid, driver, native, events = await setup()
        driver.is_x = False
        native.after_key = lambda: setattr(driver, "is_x", True)
        callbacks = []
        assert (
            await hybrid.insert("中ab", lambda: True, on_first_sent=callbacks.append)
            == 3
        )
        assert [event for event in events if event[0] == "native"] == [("native", "中")]
        assert [event[1] for event in events if event[0] == "x" and event[2]] == [
            "a",
            "b",
        ]
        assert events.index(("finish",)) < events.index(("map", "a"))
        assert len(callbacks) == 1

    asyncio.run(run())


def test_all_native_keeps_one_transaction():
    async def run():
        hybrid, driver, native, events = await setup()
        driver.is_x = False
        assert await hybrid.insert("中文abc", lambda: True) == 5
        assert events.count(("begin",)) == events.count(("finish",)) == 1

    asyncio.run(run())


@pytest.mark.parametrize("code", ["injection_failed", "mapping_changed"])
def test_probe_errors_never_become_native_fallback(code):
    async def run():
        hybrid, driver, native, events = await setup()
        driver.error = code
        with pytest.raises(KeyboardError, match=code):
            await hybrid.insert("中", lambda: True)
        assert not events

    asyncio.run(run())


def test_invalid_tail_rejected_before_any_emission():
    async def run():
        hybrid, driver, native, events = await setup()
        with pytest.raises(KeyboardError, match="unsupported_text"):
            await hybrid.insert("safe😀", lambda: True)
        assert not events

    asyncio.run(run())


def test_zero_progress_selection_yields_and_cancellation_stops():
    async def run():
        hybrid, driver, native, events = await setup()
        driver.after_map = lambda: setattr(driver, "is_x", False)
        active = True
        native.after_key = None
        original = native._insert_prefix

        async def no_progress(*args, **kwargs):
            driver.is_x = True
            return 0

        native._insert_prefix = no_progress

        async def cancel():
            nonlocal active
            await asyncio.sleep(0.025)
            active = False

        task = asyncio.create_task(cancel())
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await hybrid.insert("中", lambda: active)
        await task
        assert not [event for event in events if event[0] in {"native", "x"}]
        native._insert_prefix = original

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["press", "restore"])
def test_ambiguous_emission_or_cleanup_error_never_replays(failure):
    async def run():
        hybrid, driver, native, events = await setup()
        if failure == "press":

            def send(window, code, pressed):
                events.append(("attempt", pressed))
                if pressed:
                    driver.is_x = False
                    raise KeyboardError("injection_failed")

            driver.send = send
        else:

            def restore():
                events.append(("restore_failed",))
                raise KeyboardError("mapping_changed")

            driver.restore = restore
        with pytest.raises(KeyboardError):
            await hybrid.insert("中", lambda: True)
        assert not [event for event in events if event[0] == "native"]

    asyncio.run(run())


@pytest.mark.parametrize("deadline", [float("nan"), float("inf"), True, "soon", 0])
def test_invalid_or_expired_deadline_has_no_emission(deadline):
    async def run():
        hybrid, driver, native, events = await setup()
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await hybrid.insert("中", lambda: True, deadline=deadline)
        assert not events

    asyncio.run(run())


def test_display_unavailable_uses_native_but_other_connect_errors_propagate():
    async def run():
        events = []
        driver = Driver(events)
        native = Native(driver, events)
        driver.is_x = False

        def unavailable():
            raise KeyboardError("display_unavailable")

        hybrid = HybridKeyboardInput(
            native=native, x11=KeyboardInput(driver_factory=unavailable)
        )
        await hybrid.connect()
        assert await hybrid.insert("中", lambda: True) == 1
        assert ("native", "中") in events

        def broken():
            raise KeyboardError("injection_failed")

        hybrid = HybridKeyboardInput(
            native=native, x11=KeyboardInput(driver_factory=broken)
        )
        with pytest.raises(KeyboardError, match="injection_failed"):
            await hybrid.connect()

    asyncio.run(run())


def test_authorization_forwarding_and_close_always_closes_both():
    async def run():
        hybrid, driver, native, events = await setup()

        async def authorize(parent):
            events.append(("authorize", parent))

        async def native_close():
            events.append(("native_close",))

        native.authorize, native.aclose = authorize, native_close
        await hybrid.authorize("owned-parent")
        assert ("authorize", "owned-parent") in events
        await hybrid.aclose()
        assert ("native_close",) in events
        assert not hybrid.connected and not hybrid.authorized
        with pytest.raises(KeyboardError, match="permission_required"):
            await hybrid.insert("中", lambda: True)

    asyncio.run(run())


def test_busy_rejects_second_owner_and_close_cancels_first_then_restores():
    async def run():
        hybrid, driver, native, events = await setup()
        task = asyncio.create_task(hybrid.insert("中文", lambda: True))
        await asyncio.sleep(0)
        with pytest.raises(KeyboardError, match="busy"):
            await hybrid.insert("other", lambda: True)
        await hybrid.aclose()
        assert task.cancelled()
        assert driver.mapped is None
        assert not hybrid._busy

    asyncio.run(run())


def test_close_preserves_unexpected_owner_error_and_still_closes_both():
    async def run():
        hybrid, driver, native, events = await setup()
        ready = asyncio.Event()

        async def owner():
            ready.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                raise ValueError("owned callback failed") from None

        async def native_close():
            events.append(("native_close",))

        native.aclose = native_close
        task = asyncio.create_task(owner())
        hybrid._task = task
        await ready.wait()
        with pytest.raises(ValueError, match="owned callback failed"):
            await hybrid.aclose()
        assert not hybrid.x11.connected
        assert ("native_close",) in events
        assert task.done()

    asyncio.run(run())


def test_initial_grace_switch_and_reentry_create_new_mapping_loans(monkeypatch):
    original = asyncio.sleep
    waits = []

    async def run():
        hybrid, driver, native, events = await setup()
        changed = False

        async def sleep(delay):
            nonlocal changed
            waits.append(delay)
            if delay == 0.1 and not changed:
                changed = True
                driver.is_x = False
            await original(0)

        monkeypatch.setattr(asyncio, "sleep", sleep)
        native.after_key = lambda: setattr(driver, "is_x", True)
        assert await hybrid.insert("中文", lambda: True) == 2
        assert [event for event in events if event[0] == "native"] == [("native", "中")]
        assert [event[1] for event in events if event[0] == "x" and event[2]] == ["文"]
        assert waits.count(0.1) == 2
        assert driver.applied is None
        assert events.index(("restore", "中")) < events.index(("begin",))
        assert events.index(("finish",)) < events.index(("map", "文"))

    asyncio.run(run())


def test_output_session_retains_backend_until_route_changes_between_fragments():
    async def run():
        hybrid, driver, _native, events = await setup()
        driver.is_x = False
        callbacks = []
        async with hybrid.output_session():
            assert events == []
            await hybrid.insert("中", lambda: True, on_first_sent=callbacks.append)
            await hybrid.insert("文", lambda: True, on_first_sent=callbacks.append)
            assert events.count(("begin",)) == 1
            assert events.count(("finish",)) == 0
            driver.is_x = True
            await hybrid.insert("a", lambda: True)
            assert events.index(("finish",)) < events.index(("map", "a"))
            driver.is_x = False
            await hybrid.insert("字", lambda: True)
            assert events.index(("restore", "a")) < len(events) - 1
        assert events.count(("begin",)) == events.count(("finish",)) == 2
        assert len(callbacks) == 2
        await hybrid.aclose()

    asyncio.run(run())


def test_empty_scope_never_reads_focus_and_failed_owner_cannot_resume():
    async def run():
        hybrid, driver, _native, events = await setup()
        driver.error = "mapping_changed"
        async with hybrid.output_session():
            assert await hybrid.insert("", lambda: True) == 0
        assert events == []
        driver.error = None
        with pytest.raises(KeyboardError, match="injection_failed"):
            async with hybrid.output_session():
                await hybrid.insert("中", lambda: True)
                with pytest.raises(KeyboardError, match="unsupported_text"):
                    await hybrid.insert("😀", lambda: True)
                assert driver.applied is None
                with pytest.raises(KeyboardError, match="input_cancelled"):
                    await hybrid.insert("tail", lambda: True)
        await hybrid.aclose()

    asyncio.run(run())


def test_idle_scope_foreign_busy_preserves_owner_and_close_cleans_loan():
    async def run():
        hybrid, driver, _native, events = await setup()
        ready = asyncio.Event()
        resume = asyncio.Event()

        async def owner():
            async with hybrid.output_session():
                await hybrid.insert("中", lambda: True)
                ready.set()
                await resume.wait()
                await hybrid.insert("文", lambda: True)
                await asyncio.Event().wait()

        task = asyncio.create_task(owner())
        await ready.wait()
        assert driver.applied == "中"
        with pytest.raises(KeyboardError, match="busy"):
            await hybrid.insert("foreign", lambda: True)
        resume.set()
        while not any(e == ("x", "文", False) for e in events):
            await asyncio.sleep(0)
        await hybrid.aclose()
        assert task.cancelled()
        assert driver.applied is None

    asyncio.run(run())


@pytest.mark.parametrize("deadline", [True, float("nan"), float("inf")])
def test_nonfinite_scope_deadline_never_acquires_mapping(deadline):
    async def run():
        hybrid, _driver, _native, events = await setup()
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await hybrid.insert("中", lambda: True, deadline=deadline)
        assert events == []
        await hybrid.aclose()

    asyncio.run(run())


def test_scope_default_deadline_is_not_renewed_after_idle_expiry(monkeypatch):
    async def run():
        hybrid, driver, _native, events = await setup()
        clock = time.monotonic()
        from types import SimpleNamespace

        monkeypatch.setattr(
            "inkecho.platform.hybrid_keyboard.time",
            SimpleNamespace(monotonic=lambda: clock),
        )
        with pytest.raises(KeyboardError, match="injection_failed"):
            async with hybrid.output_session():
                await hybrid.insert("中", lambda: True, deadline=clock + 10)
                clock += 11
                with pytest.raises(KeyboardError, match="input_cancelled"):
                    await hybrid.insert("tail", lambda: True)
                assert driver.applied is None
                assert [e for e in events if e[0] == "x" and e[2]] == [
                    ("x", "中", True)
                ]
        await hybrid.aclose()

    asyncio.run(run())


def test_xwayland_only_after_explicit_unsupported_native_and_stop_on_switch():
    async def run():
        hybrid, driver, native, events = await setup()

        async def unsupported(_parent=""):
            raise KeyboardError("unsupported_compositor")

        native.authorize = unsupported
        await hybrid.authorize()
        assert hybrid.authorized
        driver.after_map = lambda: setattr(driver, "is_x", False)
        with pytest.raises(KeyboardError, match="unsupported_compositor"):
            await hybrid.insert("甲乙", lambda: True)
        assert not [event for event in events if event[0] in ("x", "native")]
        await hybrid.aclose()

    asyncio.run(run())


def test_xwayland_only_preserves_prefix_and_never_replays_on_native_switch():
    async def run():
        hybrid, driver, native, events = await setup()

        async def unsupported(_parent=""):
            raise KeyboardError("unsupported_compositor")

        native.authorize = unsupported
        await hybrid.authorize()
        original = driver.send

        def switch(window, code, pressed):
            original(window, code, pressed)
            if not pressed:
                driver.is_x = False

        driver.send = switch
        with pytest.raises(KeyboardError, match="unsupported_compositor"):
            await hybrid.insert("甲乙", lambda: True)
        assert [event for event in events if event[0] == "x" and event[2]] == [
            ("x", "甲", True)
        ]
        assert not [event for event in events if event[0] == "native"]
        await hybrid.aclose()

    asyncio.run(run())


def test_xwayland_only_never_bypasses_other_authorization_errors():
    async def run():
        hybrid, _driver, native, _events = await setup()

        async def denied(_parent=""):
            raise KeyboardError("permission_required")

        native.authorize = denied
        with pytest.raises(KeyboardError, match="permission_required"):
            await hybrid.authorize()
        assert not hybrid._xonly
        await hybrid.aclose()

    asyncio.run(run())


def test_xwayland_only_cancellation_stops_after_first_character():
    async def run():
        hybrid, driver, native, events = await setup()

        async def unsupported(_parent=""):
            raise KeyboardError("unsupported_compositor")

        native.authorize = unsupported
        await hybrid.authorize()
        active = True
        original = driver.send

        def cancel(window, code, pressed):
            nonlocal active
            original(window, code, pressed)
            if not pressed:
                active = False

        driver.send = cancel
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await hybrid.insert("甲乙", lambda: active)
        assert [event for event in events if event[0] == "x" and event[2]] == [
            ("x", "甲", True)
        ]
        assert not [event for event in events if event[0] == "native"]
        await hybrid.aclose()

    asyncio.run(run())
