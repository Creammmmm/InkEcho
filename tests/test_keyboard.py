import asyncio
import ctypes
import time
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from inkecho.platform.keyboard import (
    KeyboardError,
    KeyboardInput,
    _Event,
    _XDriver,
    _XTestDriver,
)
from inkecho.platform.output_pacing import FeedbackLevel, OutputPacer


class ImmediatePacer(OutputPacer):
    """Existing mapping tests replace elapsed time, not pacing safety checks."""

    async def _wait(self, token, active, deadline, until):
        self._check(token, active, deadline)


class Feedback:
    def __init__(self, *, level=FeedbackLevel.NONE, fail_close=False):
        self.capability = SimpleNamespace(level=level)
        self.callbacks = []
        self.bindings = []
        self.closed = False
        self.fail_close = fail_close
        self.polls = 0
        self.focus_revision = 0
        self.focus_watches = []

    def bind(self, top):
        self.bindings.append(top)
        return self.capability

    def set_callback(self, callback):
        self.callbacks.append(callback)

    def poll(self):
        assert not self.closed
        self.polls += 1

    def watch_focus(self, child):
        self.focus_watches.append(child)

    def close(self):
        self.closed = True
        if self.fail_close:
            raise RuntimeError("fixed observer cleanup failure")


class Driver:
    def __init__(self):
        self.window = 21
        self.events = []
        self.mapped = None
        self.applied = None
        self.closed = False
        self.conflict = False

    def focus(self):
        if self.window is None:
            raise KeyboardError("unsupported_target")
        return self.window

    def map(self, character):
        self.mapped = character
        if character != "\n":
            self.applied = character
        return 36 if character == "\n" else 248

    def verify(self):
        if self.conflict:
            raise KeyboardError("mapping_changed")

    def send(self, window, code, pressed):
        self.events.append((window, code, pressed))

    def restore(self):
        self.mapped = None
        self.applied = None

    def close(self):
        self.closed = True


def test_feedback_timeout_is_snapshotted_per_output_session():
    async def scenario():
        driver = Driver()
        inputs = KeyboardInput(driver_factory=lambda: driver)
        await inputs.connect()
        timeout = [0.04]
        inputs.set_feedback_timeout_reader(lambda: timeout[0])
        async with inputs.output_session():
            assert inputs._pacer.config.feedback_min == 0.04
            timeout[0] = 0.12
            assert inputs._pacer.config.feedback_min == 0.04
        async with inputs.output_session():
            assert inputs._pacer.config.feedback_min == 0.12
        await inputs.aclose()

    asyncio.run(scenario())


def test_mapping_wait_is_snapshotted_per_output_session(monkeypatch):
    async def scenario():
        driver = Driver()
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        wait = [0.04]
        inputs.set_mapping_wait_reader(lambda: wait[0])
        delays = []
        original_sleep = asyncio.sleep

        async def record_sleep(delay):
            delays.append(delay)
            await original_sleep(0)

        monkeypatch.setattr(asyncio, "sleep", record_sleep)
        async with inputs.output_session():
            await inputs.insert("甲乙", lambda: True)
            wait[0] = 0.08
            await inputs.insert("丙", lambda: True)
        assert delays == [0.1, 0.01, 0.01, 0.04, 0.01, 0.01, 0.04, 0.01, 0.01]
        delays.clear()
        async with inputs.output_session():
            await inputs.insert("甲乙", lambda: True)
        assert delays == [0.1, 0.01, 0.01, 0.08, 0.01, 0.01]
        await inputs.aclose()

    asyncio.run(scenario())


def fast_sleep(monkeypatch, action=lambda _count: None):
    original = asyncio.sleep
    count = 0

    async def sleep(_delay):
        nonlocal count
        count += 1
        action(count)
        await original(0)

    monkeypatch.setattr(asyncio, "sleep", sleep)


def test_connect_does_not_require_focus_or_permission_dialog():
    async def run():
        driver = Driver()
        driver.window = None
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        await inputs.authorize()
        assert inputs.authorized and inputs.connected
        assert driver.events == []
        await inputs.aclose()
        assert not inputs.authorized and driver.closed

    asyncio.run(run())


@pytest.mark.parametrize(
    "text", ["hello\tworld", "ab\x1bc", "ab\0c", "ab\x85", "ab\ud800"]
)
def test_whole_text_control_preflight_sends_nothing(text):
    async def run():
        driver = Driver()
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        with pytest.raises(KeyboardError, match="unsupported_text"):
            await inputs.insert(text, lambda: True)
        assert driver.events == [] and driver.mapped is None
        await inputs.aclose()

    asyncio.run(run())


def test_focus_is_refreshed_after_mapping_wait_and_between_characters(monkeypatch):
    driver = Driver()
    fast_sleep(
        monkeypatch, lambda count: setattr(driver, "window", 22 if count < 4 else 23)
    )

    async def run():
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        await inputs.insert("中Ω", lambda: True)
        assert driver.events == [
            (22, 248, True),
            (22, 248, False),
            (23, 248, True),
            (23, 248, False),
        ]
        assert driver.mapped is None

    asyncio.run(run())


def test_cancel_after_mapping_wait_stops_all_presses_and_restores(monkeypatch):
    driver = Driver()
    allowed = True

    def cancel(_count):
        nonlocal allowed
        allowed = False

    fast_sleep(monkeypatch, cancel)

    async def run():
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await inputs.insert("中文字", lambda: allowed)
        assert driver.events == [] and driver.mapped is None

    asyncio.run(run())


def test_cancel_after_press_releases_only_and_does_not_replay(monkeypatch):
    driver = Driver()

    def cancel(count):
        if count == 2:
            raise asyncio.CancelledError

    fast_sleep(monkeypatch, cancel)

    async def run():
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        with pytest.raises(asyncio.CancelledError):
            await inputs.insert("中文字", lambda: True)
        assert driver.events == [(21, 248, True), (21, 248, False)]
        assert driver.mapped is None

    asyncio.run(run())


@pytest.mark.parametrize(
    "change,code", [("native", "unsupported_target"), ("layout", "mapping_changed")]
)
def test_async_focus_or_layout_change_prevents_press(monkeypatch, change, code):
    driver = Driver()

    def changed(_count):
        if change == "native":
            driver.window = None
        else:
            driver.conflict = True

    fast_sleep(monkeypatch, changed)

    async def run():
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        with pytest.raises(KeyboardError, match=code):
            await inputs.insert("字", lambda: True)
        assert driver.events == [] and driver.mapped is None

    asyncio.run(run())


def test_busy_and_close_cancel_waiting_delivery(monkeypatch):
    async def run():
        driver = Driver()
        entered = asyncio.Event()

        async def waiting(_delay):
            entered.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(asyncio, "sleep", waiting)
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        task = asyncio.create_task(inputs.insert("字", lambda: True))
        await entered.wait()
        with pytest.raises(KeyboardError, match="busy"):
            await inputs.insert("other", lambda: True)
        await inputs.aclose()
        assert task.cancelled() and driver.closed and driver.events == []
        assert driver.mapped is None

    asyncio.run(run())


def test_newlines_normalized_use_return_code(monkeypatch):
    fast_sleep(monkeypatch)

    async def run():
        driver = Driver()
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        assert await inputs.insert("\r\n\r", lambda: True) == 2
        assert driver.events == [(21, 36, True), (21, 36, False)] * 2

    asyncio.run(run())


def mapping_driver(rows):
    driver = _XDriver.__new__(_XDriver)
    driver.first, driver.count = 8, len(rows)
    driver.width = None
    driver.slot = driver.applied = driver.pending_symbol = None
    driver._mapping = lambda: (2, tuple(symbol for row in rows for symbol in row))
    driver._write = lambda values: rows.__setitem__(
        driver.slot - driver.first, tuple(values)
    )
    return driver


def mapped_keyboard(monkeypatch, action=lambda _count: None):
    """Exercise production mapping/cleanup with only X hardware calls replaced."""
    rows = [(97, 65), (0, 0)]
    driver = mapping_driver(rows)
    writes = []
    original_write = driver._write

    def write(values):
        original_write(values)
        writes.append(tuple(values))

    driver._write = write
    driver.focus = lambda: 21
    driver._checked = nullcontext
    driver.display = None
    driver.x11 = SimpleNamespace(XKeysymToKeycode=lambda *_args: 36)
    events = []
    driver.send = lambda window, code, pressed: events.append((window, code, pressed))
    driver.close = lambda: None
    fast_sleep(monkeypatch, action)
    return (
        KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer()),
        driver,
        rows,
        writes,
        events,
    )


def test_full_unicode_sample_uses_one_final_restore_not_per_character(monkeypatch):
    inputs, driver, rows, writes, events = mapped_keyboard(monkeypatch)
    text = "你好 InkEcho，世界！ café Ω 😀\n第二行。" * 5
    assert len(text) == 140 and len(text.replace("\n", "")) == 135

    async def run():
        await inputs.connect()
        assert await inputs.insert(text, lambda: True) == len(text)
        assert len(writes) == 136 and writes[-1] == (0, 0)
        # Every earlier write represents a real printable symbol, never a clear.
        assert all(any(row) for row in writes[:-1])
        assert rows == [(97, 65), (0, 0)]
        assert [event[2] for event in events] == [True, False] * 140
        assert driver.applied is None and inputs._task is None
        await inputs.aclose()

    asyncio.run(run())


def test_consecutive_insertions_each_release_the_owned_mapping(monkeypatch):
    inputs, driver, rows, writes, events = mapped_keyboard(monkeypatch)

    async def run():
        await inputs.connect()
        for text in ("中\nΩ", "é你"):
            before = len(writes)
            assert await inputs.insert(text, lambda: True) == len(text)
            assert len(writes) - before == len(text.replace("\n", "")) + 1
            assert rows[1] == (0, 0) and driver.applied is None
        assert [event[1] for event in events[:6]] == [9, 9, 36, 36, 9, 9]
        await inputs.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("action", ["cancel", "error"])
def test_press_followed_by_cancel_or_error_releases_and_restores_real_row(
    monkeypatch, action
):
    active = True

    def stop(count):
        nonlocal active
        if count == 2:
            if action == "error":
                raise KeyboardError("injection_failed")
            active = False

    inputs, driver, rows, writes, events = mapped_keyboard(monkeypatch, stop)

    async def run():
        await inputs.connect()
        with pytest.raises(KeyboardError) as caught:
            await inputs.insert("中文", lambda: active)
        assert caught.value.code == (
            "input_cancelled" if action == "cancel" else "injection_failed"
        )
        assert events == [(21, 9, True), (21, 9, False)]
        assert rows[1] == (0, 0) and len(writes) == 2
        assert driver.applied is None and inputs._task is None
        await inputs.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("text", ["中文", "中\n", "中"])
def test_production_retained_slot_foreign_change_is_never_overwritten(
    monkeypatch, text
):
    rows = None

    def change(count):
        if count == 3:
            rows[1] = (91, 92)

    inputs, driver, rows, writes, events = mapped_keyboard(monkeypatch, change)

    async def run():
        await inputs.connect()
        with pytest.raises(KeyboardError) as caught:
            await inputs.insert(text, lambda: True)
        assert caught.value.code == "mapping_changed"
        assert rows[1] == (91, 92) and len(writes) == 1
        assert events == [(21, 9, True), (21, 9, False)]
        assert driver.applied is None and inputs._task is None
        await inputs.aclose()

    asyncio.run(run())


def test_failed_next_symbol_write_restores_previous_owned_mapping(monkeypatch):
    inputs, driver, rows, writes, events = mapped_keyboard(monkeypatch)
    original_write = driver._write
    calls = 0

    def fail(values):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardError("injection_failed")
        original_write(values)

    driver._write = fail

    async def run():
        await inputs.connect()
        with pytest.raises(KeyboardError) as caught:
            await inputs.insert("中文", lambda: True)
        assert caught.value.code == "injection_failed"
        assert rows[1] == (0, 0) and len(writes) == 2
        assert events == [(21, 9, True), (21, 9, False)]
        assert driver.pending_symbol is None and inputs._task is None
        await inputs.aclose()

    asyncio.run(run())


def test_async_cancel_during_press_restores_retained_production_row(monkeypatch):
    def cancel(count):
        if count == 2:
            raise asyncio.CancelledError

    inputs, driver, rows, writes, events = mapped_keyboard(monkeypatch, cancel)

    async def run():
        await inputs.connect()
        with pytest.raises(asyncio.CancelledError):
            await inputs.insert("中文", lambda: True)
        assert events == [(21, 9, True), (21, 9, False)]
        assert rows[1] == (0, 0) and len(writes) == 2
        assert driver.applied is None and inputs._task is None
        await inputs.aclose()

    asyncio.run(run())


def test_mapping_only_uses_empty_slot_and_restores_its_own_row():
    rows = [(97, 65), (0, 0), (0, 0)]
    driver = mapping_driver(rows)
    assert driver.map("中") == 10
    assert rows == [(97, 65), (0, 0), (0x1004E2D, 0x1004E2D)]
    rows[0] = (98, 66)  # A concurrent unrelated layout change must survive.
    driver.restore()
    assert rows == [(98, 66), (0, 0), (0, 0)]


def test_external_slot_change_is_not_overwritten_during_cleanup():
    rows = [(97, 65), (0, 0)]
    driver = mapping_driver(rows)
    driver.map("中")
    rows[1] = (99, 67)
    with pytest.raises(KeyboardError, match="mapping_changed"):
        driver.verify()
    driver.restore()
    assert rows[1] == (99, 67)


def test_all_slots_occupied_does_not_change_any_mapping():
    rows = [(97, 65), (98, 66)]
    driver = mapping_driver(rows)
    with pytest.raises(KeyboardError, match="mapping_changed"):
        driver.map("中")
    assert rows == [(97, 65), (98, 66)]


def test_x_error_trap_preserves_foreign_display_handler_and_restores_it():
    kind = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
    delegated = []
    previous = kind(lambda display, event: delegated.append(display) or 0)
    previous_pointer = ctypes.cast(previous, ctypes.c_void_p).value

    class Xlib:
        handler = previous_pointer
        pending = [200, 100]

        def XSetErrorHandler(self, handler):
            old = self.handler
            self.handler = (
                handler.value if isinstance(handler, ctypes.c_void_p) else handler
            )
            return old

        def XSync(self, *_):
            pending, self.pending = self.pending, []
            for display in pending:
                kind(self.handler)(display, None)

    driver = _XDriver.__new__(_XDriver)
    driver.x11, driver.display = Xlib(), 100
    with pytest.raises(KeyboardError, match="injection_failed"):
        with driver._checked():
            pass
    assert delegated == [200]
    assert driver.x11.handler == previous_pointer


def test_send_uses_owner_mask_zero_modifiers_and_exact_release_window():
    calls = []

    class Xlib:
        def XSendEvent(self, display, window, propagate, mask, pointer):
            event = ctypes.cast(pointer, ctypes.POINTER(_Event)).contents.key
            calls.append(
                (window, propagate, mask, event.state, event.type, event.keycode)
            )
            return 1

    driver = _XDriver.__new__(_XDriver)
    driver.x11, driver.display, driver.root = Xlib(), 100, 1
    from contextlib import nullcontext

    driver._checked = nullcontext
    driver.send(22, 248, True)
    driver.send(22, 248, False)
    assert calls == [(22, 0, 0, 0, 2, 248), (22, 0, 0, 0, 3, 248)]


def test_unknown_errors_never_expose_details():
    error = KeyboardError("private server detail")
    assert str(error) == error.code == "injection_failed"


def test_xorg_xtest_events_follow_global_focus_and_release_without_modifier_guard():
    calls = []
    driver = _XTestDriver.__new__(_XTestDriver)
    driver.display = 100
    driver._checked = nullcontext
    driver.xtst = SimpleNamespace(
        XTestFakeKeyEvent=lambda *args: calls.append(args) or 1
    )
    driver.send(22, 248, True)
    driver.send(99, 248, False)
    assert calls == [(100, 248, 1, 0), (100, 248, 0, 0)]


@pytest.mark.parametrize("held,mask", [(True, 0), (False, 1), (False, 2), (False, 8)])
def test_xorg_refuses_physical_keys_or_modifiers_without_mutating_them(held, mask):
    driver = _XTestDriver.__new__(_XTestDriver)
    driver.display, driver.root = 100, 1
    driver._checked = nullcontext

    def query_keys(display, keys):
        if held:
            keys[3] = b"\x01"
        return 1

    def query_pointer(*args):
        ctypes.cast(args[-1], ctypes.POINTER(ctypes.c_uint))[0] = mask
        return 1

    driver.x11 = SimpleNamespace(XQueryKeymap=query_keys, XQueryPointer=query_pointer)
    with pytest.raises(KeyboardError, match="keys_held"):
        driver.focus()


def test_xorg_preserves_numlock_for_identical_level_unicode_row(monkeypatch):
    driver = _XTestDriver.__new__(_XTestDriver)
    driver.display, driver.root = 100, 1
    driver._checked = nullcontext

    def query_pointer(*args):
        ctypes.cast(args[-1], ctypes.POINTER(ctypes.c_uint))[0] = 16
        return 1

    driver.x11 = SimpleNamespace(XQueryKeymap=lambda *_: 1, XQueryPointer=query_pointer)
    monkeypatch.setattr(_XDriver, "focus", lambda self: 22)
    assert driver.focus() == 22


def test_successful_map_write_followed_by_read_failure_still_restores_owned_slot():
    rows = [(97, 65), (0, 0)]
    driver = mapping_driver(rows)
    original_row = driver._row
    read_count = 0

    def fail_readback_once():
        nonlocal read_count
        read_count += 1
        if read_count == 2:
            raise KeyboardError("injection_failed")
        return original_row()

    driver._row = fail_readback_once
    with pytest.raises(KeyboardError, match="injection_failed"):
        driver.map("中")
    assert rows[1] == (0x1004E2D, 0x1004E2D)
    driver.restore()
    assert rows == [(97, 65), (0, 0)]


def test_failed_readback_cleanup_never_overwrites_external_replacement():
    rows = [(97, 65), (99, 67)]
    driver = mapping_driver(rows)
    driver.slot, driver.width, driver.pending_symbol = 9, 2, 0x1004E2D
    with pytest.raises(KeyboardError, match="mapping_changed"):
        driver.restore()
    assert rows[1] == (99, 67)


def test_canonical_trailing_zero_width_change_does_not_leave_owned_mapping():
    rows = [(97, 65), (0, 0)]
    driver = mapping_driver(rows)
    driver.map("中")
    original_row = driver._row
    driver._row = lambda: (*original_row(), 0, 0)
    driver.verify()
    driver.restore()
    assert rows == [(97, 65), (0, 0)]


def test_first_sent_callback_is_once_after_successful_press(monkeypatch):
    fast_sleep(monkeypatch)

    async def run():
        import time

        driver = Driver()
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        observed = []
        began = time.monotonic()

        def first_sent(sent_at):
            assert driver.events == [(21, 248, True)]
            assert began <= sent_at <= time.monotonic()
            observed.append(sent_at)

        assert inputs.supports_first_sent_callback
        assert await inputs.insert("中文", lambda: True, on_first_sent=first_sent) == 2
        assert len(observed) == 1
        await inputs.aclose()

    asyncio.run(run())


def test_first_sent_callback_failure_still_releases_and_stops(monkeypatch):
    fast_sleep(monkeypatch)

    async def run():
        driver = Driver()
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()

        def failed(_sent_at):
            raise RuntimeError("fixture callback failed")

        with pytest.raises(RuntimeError, match="fixture callback failed"):
            await inputs.insert("中文", lambda: True, on_first_sent=failed)
        assert driver.events == [(21, 248, True), (21, 248, False)]
        assert driver.mapped is None and inputs._task is None
        await inputs.aclose()

    asyncio.run(run())


def test_no_first_sent_callback_when_press_fails(monkeypatch):
    fast_sleep(monkeypatch)

    async def run():
        driver = Driver()
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        observed = []
        original = driver.send

        def send(window, code, pressed):
            if pressed:
                raise KeyboardError("injection_failed")
            original(window, code, pressed)

        driver.send = send
        with pytest.raises(KeyboardError):
            await inputs.insert("中文", lambda: True, on_first_sent=observed.append)
        assert observed == [] and driver.events == [(21, 248, False)]
        assert driver.mapped is None
        await inputs.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("character", ["A", " ", "é", "Ω", "😀"])
def test_printable_characters_use_literal_unicode_keysyms(character):
    rows = [(97, 65), (0, 0)]
    driver = mapping_driver(rows)
    assert driver.map(character) == 9
    assert rows[1] == (0x01000000 | ord(character),) * 2
    driver.restore()
    assert rows == [(97, 65), (0, 0)]


def test_output_session_entry_and_idle_do_not_focus_or_map(monkeypatch):
    inputs, driver, rows, writes, events = mapped_keyboard(monkeypatch)
    driver.focus = lambda: pytest.fail("Idle sessions must not capture focus")

    async def run():
        await inputs.connect()
        async with inputs.output_session():
            await asyncio.sleep(0)
            assert not writes and not events and rows[1] == (0, 0)
        assert inputs._output_owner is None and driver.applied is None

    asyncio.run(run())


def test_output_session_retains_real_mapping_across_150_separate_insertions(
    monkeypatch,
):
    inputs, driver, rows, writes, events = mapped_keyboard(monkeypatch)
    sample = "你好，InkEcho！ café Ω 😀\n第二行。" * 6

    async def run():
        await inputs.connect()
        async with inputs.output_session():
            for character in sample:
                assert await inputs.insert(character, lambda: True) == 1
                await asyncio.sleep(0)  # A real suspension between all fragments.
                assert driver.applied is not None and inputs._task is None
                assert all(any(row) for row in writes)
        assert len(sample) == 150 and len(writes) == 145
        assert writes[-1] == (0, 0)
        assert rows == [(97, 65), (0, 0)] and driver.applied is None
        assert [event[2] for event in events] == [True, False] * 150
        assert inputs._output_owner is None
        # Outside a session the public single-insert cleanup remains unchanged.
        assert await inputs.insert("外", lambda: True) == 1
        assert len(writes) == 147 and rows[1] == (0, 0)

    asyncio.run(run())


def test_output_session_owner_blocks_nested_sessions_and_other_tasks(monkeypatch):
    inputs, driver, rows, writes, _events = mapped_keyboard(monkeypatch)

    async def run():
        await inputs.connect()
        async with inputs.output_session():
            await inputs.insert("甲", lambda: True)
            with pytest.raises(KeyboardError, match="busy"):
                async with inputs.output_session():
                    pytest.fail("Nested output session entered")

            async def outsider():
                with pytest.raises(KeyboardError, match="busy"):
                    await inputs.insert("外", lambda: True)
                with pytest.raises(KeyboardError, match="busy"):
                    async with inputs.output_session():
                        pytest.fail("Foreign output session entered")

            await asyncio.create_task(outsider())
            assert len(writes) == 1 and driver.applied is not None
            await inputs.insert("乙", lambda: True)
        assert len(writes) == 3 and rows[1] == (0, 0)

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["invalid_text", "foreign_row", "expired"])
def test_caught_fragment_failure_restores_and_poisoned_session_cannot_continue(
    monkeypatch, failure
):
    inputs, driver, rows, writes, events = mapped_keyboard(monkeypatch)

    async def run():
        await inputs.connect()
        with pytest.raises(KeyboardError, match="injection_failed"):
            async with inputs.output_session():
                await inputs.insert("甲", lambda: True)
                if failure == "foreign_row":
                    rows[1] = (91, 92)
                with pytest.raises(KeyboardError) as caught:
                    await inputs.insert(
                        "\t" if failure == "invalid_text" else "乙",
                        lambda: True,
                        deadline=0 if failure == "expired" else None,
                    )
                assert (
                    caught.value.code
                    == {
                        "invalid_text": "unsupported_text",
                        "foreign_row": "mapping_changed",
                        "expired": "input_cancelled",
                    }[failure]
                )
                assert driver.applied is None
                assert rows[1] == ((91, 92) if failure == "foreign_row" else (0, 0))
                with pytest.raises(KeyboardError, match="input_cancelled"):
                    await inputs.insert("不得继续", lambda: True)
        assert len(writes) == (1 if failure == "foreign_row" else 2)
        assert [event[2] for event in events] == [True, False]
        assert inputs._output_owner is None and not inputs._output_failed

    asyncio.run(run())


def test_output_session_cleanup_failure_does_not_overwrite_foreign_row(monkeypatch):
    inputs, driver, rows, writes, events = mapped_keyboard(monkeypatch)

    async def run():
        await inputs.connect()
        with pytest.raises(KeyboardError, match="mapping_changed"):
            async with inputs.output_session():
                await inputs.insert("甲", lambda: True)
                rows[1] = (91, 92)
        assert rows[1] == (91, 92) and len(writes) == 1
        assert driver.applied is None and inputs._output_owner is None
        assert [event[2] for event in events] == [True, False]

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["cancel", "callback_error"])
def test_output_session_press_failure_releases_and_restores_real_row(
    monkeypatch, failure
):
    inputs, driver, rows, writes, events = mapped_keyboard(monkeypatch)

    async def run():
        await inputs.connect()

        def fail(_sent_at):
            if failure == "cancel":
                raise asyncio.CancelledError
            raise RuntimeError("fixed callback failure")

        expected = asyncio.CancelledError if failure == "cancel" else RuntimeError
        with pytest.raises(expected):
            async with inputs.output_session():
                await inputs.insert("甲乙", lambda: True, on_first_sent=fail)
        assert events == [(21, 9, True), (21, 9, False)]
        assert len(writes) == 2 and rows[1] == (0, 0)
        assert driver.applied is None and inputs._output_owner is None
        assert inputs._task is None

    asyncio.run(run())


def test_output_session_refreshes_focus_between_fragments_and_after_mapping_wait(
    monkeypatch,
):
    calls = 0
    driver = None

    def switch(_count):
        nonlocal calls
        calls += 1
        if calls == 4:
            driver.focus = lambda: 23

    inputs, driver, rows, _writes, events = mapped_keyboard(monkeypatch, switch)

    async def run():
        await inputs.connect()
        async with inputs.output_session():
            await inputs.insert("甲", lambda: True)
            driver.focus = lambda: 22
            await inputs.insert("乙", lambda: True)
        assert events == [(21, 9, True), (21, 9, False), (23, 9, True), (23, 9, False)]
        assert rows[1] == (0, 0)

    asyncio.run(run())


@pytest.mark.parametrize("phase", ["idle", "pressed"])
def test_aclose_joins_output_owner_before_closing_real_driver(monkeypatch, phase):
    inputs, driver, rows, writes, events = mapped_keyboard(monkeypatch)
    entered = asyncio.Event()
    closed = []

    def close_display(_display):
        assert inputs._output_owner is None and rows[1] == (0, 0)
        closed.append(True)

    driver.x11.XCloseDisplay = close_display
    driver.close = _XDriver.close.__get__(driver)

    async def run():
        await inputs.connect()

        async def consume():
            async with inputs.output_session():
                await inputs.insert(
                    "甲乙" if phase == "pressed" else "甲",
                    lambda: True,
                    on_first_sent=lambda _at: (
                        entered.set() if phase == "pressed" else None
                    ),
                )
                entered.set()
                await asyncio.Event().wait()

        owner = asyncio.create_task(consume())
        await entered.wait()
        await inputs.aclose()
        assert owner.cancelled() and closed == [True]
        assert inputs._driver is None and inputs._output_owner is None
        assert events == [(21, 9, True), (21, 9, False)]
        assert len(writes) == 2 and rows[1] == (0, 0)

    asyncio.run(run())


def test_same_owner_aclose_never_reuses_closed_driver_even_for_invalid_text(
    monkeypatch,
):
    inputs, driver, rows, writes, _events = mapped_keyboard(monkeypatch)
    closed = []

    def close_display(_display):
        closed.append(True)
        driver.restore = lambda: pytest.fail("Closed driver accessed by context")

    driver.x11.XCloseDisplay = close_display
    driver.close = _XDriver.close.__get__(driver)

    async def run():
        await inputs.connect()
        with pytest.raises(KeyboardError, match="session_closed"):
            async with inputs.output_session():
                await inputs.insert("甲", lambda: True)
                await inputs.aclose()
                with pytest.raises(KeyboardError, match="unsupported_text"):
                    await inputs.insert("\t", lambda: True)
                with pytest.raises(KeyboardError, match="session_closed"):
                    await inputs.insert("乙", lambda: True)
        assert closed == [True] and inputs._driver is None
        assert inputs._output_owner is None and rows[1] == (0, 0) and len(writes) == 2

    asyncio.run(run())


def test_output_session_cannot_enter_during_standalone_insertion(monkeypatch):
    inputs, driver, rows, writes, events = mapped_keyboard(monkeypatch)
    entered = asyncio.Event()

    async def blocked_mapping_wait(_delay):
        entered.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(asyncio, "sleep", blocked_mapping_wait)

    async def run():
        await inputs.connect()
        pending = asyncio.create_task(inputs.insert("甲", lambda: True))
        await entered.wait()
        with pytest.raises(KeyboardError, match="busy"):
            async with inputs.output_session():
                pytest.fail("Session stole an in-flight standalone mapping")
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        assert not events and len(writes) == 2 and rows[1] == (0, 0)
        assert driver.applied is None and inputs._output_owner is None

    asyncio.run(run())


def test_sequential_output_sessions_belong_to_distinct_tasks(monkeypatch):
    inputs, driver, rows, writes, _events = mapped_keyboard(monkeypatch)

    async def run():
        await inputs.connect()

        async def consume(character):
            async with inputs.output_session():
                assert inputs._output_owner is asyncio.current_task()
                await inputs.insert(character, lambda: True)
            assert inputs._output_owner is None and rows[1] == (0, 0)

        first = asyncio.create_task(consume("甲"))
        await first
        second = asyncio.create_task(consume("乙"))
        await second
        assert first is not second and len(writes) == 4
        assert driver.applied is None

    asyncio.run(run())


def test_aclose_still_closes_driver_if_cancelled_owner_raises_unexpected_error(
    monkeypatch,
):
    inputs, driver, rows, writes, _events = mapped_keyboard(monkeypatch)
    entered = asyncio.Event()
    closed = []
    driver.x11.XCloseDisplay = lambda _display: closed.append(True)
    driver.close = _XDriver.close.__get__(driver)

    async def run():
        await inputs.connect()

        async def consume():
            async with inputs.output_session():
                await inputs.insert("甲", lambda: True)
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    raise RuntimeError("fixed consumer failure")

        owner = asyncio.create_task(consume())
        await entered.wait()
        with pytest.raises(RuntimeError, match="fixed consumer failure"):
            await inputs.aclose()
        assert owner.done() and closed == [True]
        assert rows[1] == (0, 0) and len(writes) == 2
        assert inputs._driver is None and inputs._output_owner is None

    asyncio.run(run())


def test_first_real_mapping_grace_survives_newline_and_stream_fragments(monkeypatch):
    delays = []
    original = asyncio.sleep

    async def sleep(delay):
        delays.append(delay)
        await original(0)

    monkeypatch.setattr(asyncio, "sleep", sleep)

    async def run():
        driver = Driver()
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        async with inputs.output_session():
            await inputs.insert("\n", lambda: True)
            await inputs.insert("中", lambda: True)
            await inputs.insert("文", lambda: True)
        # Return does not change the map; only its press/release floors apply.
        assert delays == [0.01, 0.01] + [0.1, 0.01, 0.01] + [0.04, 0.01, 0.01]
        assert driver.applied is None
        delays.clear()
        await inputs.insert("a", lambda: True)
        await inputs.insert("b", lambda: True)
        assert delays == [0.1, 0.01, 0.01] * 2

    asyncio.run(run())


def test_cancel_during_initial_mapping_grace_emits_nothing(monkeypatch):
    active = True
    original = asyncio.sleep

    async def sleep(delay):
        nonlocal active
        assert delay == 0.1
        active = False
        await original(0)

    monkeypatch.setattr(asyncio, "sleep", sleep)

    async def run():
        driver = Driver()
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await inputs.insert("中文", lambda: active)
        assert driver.events == [] and driver.applied is None

    asyncio.run(run())


def test_real_pair_mapping_needed_is_read_only_and_tracks_cache_revision():
    driver = _XTestDriver.__new__(_XTestDriver)
    driver._batch = {"甲": 183, "乙": 184}
    driver._map_revision = 7
    driver._mapping = lambda: pytest.fail("A map-cost query must not read or write X")
    driver._write = lambda _values: pytest.fail("A map-cost query must not mutate X")
    assert not driver.mapping_needed("甲", 0)
    assert not driver.mapping_needed("乙", 0)
    assert not driver.mapping_needed("\n", 0)
    assert driver.mapping_needed("丙", 0)
    assert driver._map_revision == 7 and driver._batch == {"甲": 183, "乙": 184}


def test_pacing_precedes_mapping_and_cached_characters_have_no_map_sleep(monkeypatch):
    original_sleep = asyncio.sleep
    operations, delays = [], []

    async def sleep(delay):
        delays.append(delay)
        await original_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", sleep)

    class Pacer(ImmediatePacer):
        async def before_send(self, token, **options):
            operations.append(("before", options["mapping_changed"]))
            await super().before_send(token, **options)

    class CachedDriver(Driver):
        def __init__(self):
            super().__init__()
            self._map_revision = 0
            self._batch = {}

        mapping_needed = _XTestDriver.mapping_needed

        def prepare(self, text, index):
            if self.mapping_needed(text, index):
                operations.append(("map-write", text[index]))
                self._batch = dict.fromkeys(text[index : index + 2], 248)
                self._map_revision += 1

    async def run():
        driver = CachedDriver()
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=Pacer())
        await inputs.connect()
        assert await inputs.insert("甲乙甲丙", lambda: True) == 4
        assert operations == [
            ("before", True),
            ("map-write", "甲"),
            ("before", False),
            ("before", False),
            ("before", True),
            ("map-write", "丙"),
        ]
        assert delays == [0.1, 0.01, 0.01] + [0.01, 0.01] * 2 + [0.04, 0.01, 0.01]
        assert driver._map_revision == 2
        assert [event[2] for event in driver.events] == [True, False] * 4

    asyncio.run(run())


@pytest.mark.parametrize("same_owner", [False, True])
@pytest.mark.parametrize("fail_close", [False, True])
def test_observer_stops_before_restore_and_driver_close(
    monkeypatch, same_owner, fail_close
):
    fast_sleep(monkeypatch)
    feedback = Feedback(fail_close=fail_close)
    driver = Driver()
    original_restore = driver.restore

    def restore():
        assert feedback.closed
        original_restore()

    def close():
        assert feedback.closed
        driver.closed = True

    driver.restore, driver.close = restore, close

    async def run():
        inputs = KeyboardInput(
            driver_factory=lambda: driver,
            pacer=ImmediatePacer(),
            feedback_factory=lambda _driver: feedback,
        )
        await inputs.connect()
        expected = (
            pytest.raises(KeyboardError, match="session_closed")
            if same_owner
            else nullcontext()
        )
        with expected:
            async with inputs.output_session():
                assert await inputs.insert("甲", lambda: True) == 1
                assert not feedback.closed
                if same_owner:
                    await inputs.aclose()
                    assert driver.closed and inputs._feedback_poll is None
        if not same_owner:
            await inputs.aclose()
        assert feedback.closed and inputs._feedback_poll is None and driver.closed
        assert [event[2] for event in driver.events] == [True, False]

    asyncio.run(run())


def test_child_focus_change_rebinds_generation_and_old_hint_cannot_credit_new_target(
    monkeypatch,
):
    fast_sleep(monkeypatch)
    feedback = Feedback(level=FeedbackLevel.DRAW)
    driver = Driver()
    driver.observation_target = lambda _window: 100
    pacer = ImmediatePacer()
    stale_results = []
    original_map = driver.map

    def map_character(character):
        if character == "乙":
            stale_results.append(feedback.callbacks[0](0.0))
            assert pacer.snapshot(inputs._pacing_token).pending == 0
        return original_map(character)

    driver.map = map_character
    inputs = KeyboardInput(
        driver_factory=lambda: driver,
        pacer=pacer,
        feedback_factory=lambda _driver: feedback,
    )

    async def run():
        await inputs.connect()
        async with inputs.output_session():
            await inputs.insert(
                "甲乙",
                lambda: True,
                on_first_sent=lambda _at: setattr(driver, "window", 22),
            )
        assert feedback.bindings == [100, 100]
        assert stale_results == [False]
        assert driver.events == [
            (21, 248, True),
            (21, 248, False),
            (22, 248, True),
            (22, 248, False),
        ]
        assert feedback.closed and driver.applied is None

    asyncio.run(run())


def test_pacing_and_default_absolute_deadline_persist_across_fragments(monkeypatch):
    fast_sleep(monkeypatch)
    driver = Driver()
    pacer = ImmediatePacer()
    inputs = KeyboardInput(driver_factory=lambda: driver, pacer=pacer)

    async def run():
        await inputs.connect()
        async with inputs.output_session():
            before = time.monotonic()
            await inputs.insert("甲", lambda: True)
            token, deadline = inputs._pacing_token, inputs._output_deadline
            assert before + 59 <= deadline <= before + 61
            await inputs.insert("乙", lambda: True)
            assert inputs._pacing_token == token and inputs._output_deadline == deadline
        assert inputs._output_deadline is None
        async with inputs.output_session():
            await inputs.insert("丙", lambda: True)
            assert inputs._pacing_token != token

    asyncio.run(run())


@pytest.mark.parametrize("deadline", [float("nan"), float("inf"), True, 10**1000])
def test_invalid_deadline_releases_scope_without_any_press(deadline):
    async def run():
        driver = Driver()
        inputs = KeyboardInput(driver_factory=lambda: driver)
        await inputs.connect()
        with pytest.raises(KeyboardError, match="input_cancelled"):
            await inputs.insert("甲", lambda: True, deadline=deadline)
        assert driver.events == [] and driver.applied is None
        assert inputs._output_owner is None and inputs._feedback_poll is None

    asyncio.run(run())


def test_cancel_during_draw_wait_releases_observer_and_mapping_without_tail():
    async def run():
        feedback = Feedback(level=FeedbackLevel.DRAW)
        driver = Driver()
        first = asyncio.Event()
        inputs = KeyboardInput(
            driver_factory=lambda: driver,
            feedback_factory=lambda _driver: feedback,
        )
        await inputs.connect()
        owner = asyncio.create_task(
            inputs.insert("甲乙", lambda: True, on_first_sent=lambda _at: first.set())
        )
        await first.wait()
        await asyncio.sleep(0.025)  # Enter the next character's DRAW wait.
        owner.cancel()
        with pytest.raises(asyncio.CancelledError):
            await owner
        assert [event[2] for event in driver.events] == [True, False]
        assert feedback.closed and driver.applied is None
        assert inputs._feedback_poll is None and inputs._output_owner is None

    asyncio.run(run())


def test_focus_round_trip_to_same_child_starts_new_generation_without_replaying(
    monkeypatch,
):
    fast_sleep(monkeypatch)
    feedback = Feedback(level=FeedbackLevel.DRAW)
    driver = Driver()
    pacer = ImmediatePacer()
    first_token, stale_results = [], []
    round_trip = False
    stale_checked = False
    original_poll = feedback.poll
    inputs = KeyboardInput(
        driver_factory=lambda: driver,
        pacer=pacer,
        feedback_factory=lambda _driver: feedback,
    )

    def poll():
        nonlocal round_trip, stale_checked
        original_poll()
        if round_trip:
            feedback.focus_revision += 2  # A -> B -> A; tuple is still (21, 21).
            round_trip = False
        if len(driver.events) >= 3 and not stale_checked:
            stale_checked = True
            assert inputs._pacing_token != first_token[0]
            stale_results.append(feedback.callbacks[0](time.monotonic()))
            assert pacer.snapshot(inputs._pacing_token).pending == 1
            assert not pacer._scope.hint

    feedback.poll = poll

    def first(_at):
        nonlocal round_trip
        first_token.append(inputs._pacing_token)
        round_trip = True

    async def run():
        await inputs.connect()
        assert await inputs.insert("甲乙", lambda: True, on_first_sent=first) == 2
        assert feedback.bindings == [21, 21]
        assert feedback.focus_watches == [21, 21]
        assert stale_results == [False]
        assert [event[2] for event in driver.events] == [True, False] * 2
        assert feedback.closed and driver.applied is None

    asyncio.run(run())


@pytest.mark.parametrize(
    "failure", ["poll", "callback", "backlog", "watch_focus", "watch_degrades"]
)
def test_observer_failure_continues_once_with_bounded_none_fallback(
    monkeypatch, failure
):
    fast_sleep(monkeypatch)
    feedback = Feedback(level=FeedbackLevel.DRAW)
    driver = Driver()

    def failed():
        raise RuntimeError("fixed observation failure")

    if failure == "poll":
        feedback.poll = failed
    elif failure == "callback":
        feedback.set_callback = lambda _callback: failed()
    elif failure == "watch_focus":
        feedback.watch_focus = lambda _window: failed()
    elif failure == "watch_degrades":

        def watch_degrades(_window):
            feedback.close()
            feedback.capability = SimpleNamespace(
                level=FeedbackLevel.NONE, reason="focus_unavailable"
            )

        feedback.watch_focus = watch_degrades
    else:

        def backlog():
            feedback.capability = SimpleNamespace(
                level=FeedbackLevel.NONE, reason="event_backlog"
            )

        feedback.poll = backlog

    async def run():
        inputs = KeyboardInput(
            driver_factory=lambda: driver,
            pacer=ImmediatePacer(),
            feedback_factory=lambda _driver: feedback,
        )
        await inputs.connect()
        async with inputs.output_session():
            assert await inputs.insert("甲乙", lambda: True) == 2
            assert inputs._pacing_level == FeedbackLevel.NONE
        assert [event[2] for event in driver.events] == [True, False] * 2
        assert feedback.closed and driver.applied is None
        assert inputs._feedback_poll is None

    asyncio.run(run())


@pytest.mark.parametrize("level", [FeedbackLevel.DRAW, FeedbackLevel.NONE])
def test_receiver_wait_is_snapshotted_and_capability_is_honest(level):
    async def run():
        driver, feedback = Driver(), Feedback(level=level)
        inputs = KeyboardInput(
            driver_factory=lambda: driver, feedback_factory=lambda _: feedback
        )
        await inputs.connect()
        value = [0.04]
        inputs.set_receiver_feedback_wait_reader(lambda: value[0])
        assert inputs.receiver_feedback_status == "not_checked"
        async with inputs.output_session():
            inputs._select_feedback(driver.window)
            assert inputs.receiver_feedback_status == (
                "available" if level == FeedbackLevel.DRAW else "unavailable"
            )
            assert inputs._pacer.config.receiver_wait_max == 0.04
            value[0] = 0.08
            assert inputs._pacer.config.receiver_wait_max == 0.04
        assert inputs.receiver_feedback_status == "not_checked"
        async with inputs.output_session():
            assert inputs._pacer.config.receiver_wait_max == 0.08
        await inputs.aclose()

    asyncio.run(run())


def test_press_dispatch_snapshot_is_task_scoped_and_precedes_callback(monkeypatch):
    fast_sleep(monkeypatch)

    async def scenario():
        driver = Driver()
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        snapshots = []
        async with inputs.output_session():
            assert (
                await inputs.insert(
                    "甲",
                    lambda: True,
                    on_first_sent=lambda _at: snapshots.append(
                        inputs.acknowledged_attempts
                    ),
                )
                == 1
            )
            assert await inputs.insert("乙", lambda: True) == 1
            assert inputs.acknowledged_attempts == 2
        assert snapshots == [1]
        assert inputs.acknowledged_attempts == 0
        async with inputs.output_session():
            assert inputs.acknowledged_attempts == 0
            assert await inputs.insert("丙", lambda: True) == 1
            assert inputs.acknowledged_attempts == 1
        await inputs.aclose()

    asyncio.run(scenario())


@pytest.mark.parametrize("failed_press", [False, True])
def test_press_dispatch_count_excludes_unknown_press_but_survives_release_failure(
    monkeypatch, failed_press
):
    fast_sleep(monkeypatch)

    class Broken(Driver):
        def send(self, window, code, pressed):
            if pressed == failed_press:
                raise KeyboardError("injection_failed")
            super().send(window, code, pressed)

    async def scenario():
        inputs = KeyboardInput(driver_factory=Broken, pacer=ImmediatePacer())
        await inputs.connect()
        with pytest.raises(KeyboardError) as result:
            await inputs.insert("甲", lambda: True)
        assert result.value.acknowledged_attempts == (0 if failed_press else 1)
        await inputs.aclose()

    asyncio.run(scenario())


def test_task_cancel_during_press_wait_preserves_only_completed_dispatch():
    async def scenario():
        driver = Driver()
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        first = asyncio.Event()
        seen = []

        async def output():
            async with inputs.output_session():
                try:
                    await inputs.insert(
                        "甲乙", lambda: True, on_first_sent=lambda _at: first.set()
                    )
                finally:
                    seen.append(inputs.acknowledged_attempts)

        task = asyncio.create_task(output())
        await asyncio.wait_for(first.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert seen == [1]
        assert [event[2] for event in driver.events] == [True, False]
        assert inputs.acknowledged_attempts == 0
        await inputs.aclose()

    asyncio.run(scenario())


def test_unknown_press_failure_is_not_counted_as_confirmed_dispatch(monkeypatch):
    fast_sleep(monkeypatch)

    class Unknown(Driver):
        def send(self, window, code, pressed):
            super().send(window, code, pressed)
            if pressed:
                raise KeyboardError("injection_failed")

    async def scenario():
        driver = Unknown()
        inputs = KeyboardInput(driver_factory=lambda: driver, pacer=ImmediatePacer())
        await inputs.connect()
        with pytest.raises(KeyboardError) as result:
            await inputs.insert("甲乙", lambda: True)
        assert result.value.acknowledged_attempts == 0
        assert [event[2] for event in driver.events] == [True, False]
        await inputs.aclose()

    asyncio.run(scenario())
