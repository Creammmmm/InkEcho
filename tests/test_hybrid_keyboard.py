import asyncio
import time

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

    async def _insert_prefix(
        self, text, can_continue, *, deadline, on_first_sent, selected
    ):
        assert self.driver.mapped is None
        self.events.append(("begin",))
        count = 0
        try:
            for char in text:
                if not selected():
                    break
                assert can_continue() and time.monotonic() < deadline
                self.events.append(("native", char))
                on_first_sent(time.monotonic())
                count += 1
                if self.after_key:
                    self.after_key()
        finally:
            self.events.append(("finish",))
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
