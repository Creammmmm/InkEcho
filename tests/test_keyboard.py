import asyncio
import ctypes
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from inkecho.platform.keyboard import KeyboardError, KeyboardInput, _Event, _XDriver


class Driver:
    def __init__(self):
        self.window = 21
        self.events = []
        self.mapped = None
        self.closed = False
        self.conflict = False

    def focus(self):
        if self.window is None:
            raise KeyboardError("unsupported_target")
        return self.window

    def map(self, character):
        self.mapped = character
        return 36 if character == "\n" else 248

    def verify(self):
        if self.conflict:
            raise KeyboardError("mapping_changed")

    def send(self, window, code, pressed):
        self.events.append((window, code, pressed))

    def restore(self):
        self.mapped = None

    def close(self):
        self.closed = True


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
        inputs = KeyboardInput(driver_factory=lambda: driver)
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
        inputs = KeyboardInput(driver_factory=lambda: driver)
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
        inputs = KeyboardInput(driver_factory=lambda: driver)
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
        inputs = KeyboardInput(driver_factory=lambda: driver)
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
        inputs = KeyboardInput(driver_factory=lambda: driver)
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
        inputs = KeyboardInput(driver_factory=lambda: driver)
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
        inputs = KeyboardInput(driver_factory=lambda: driver)
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
        inputs = KeyboardInput(driver_factory=lambda: driver)
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
    return KeyboardInput(driver_factory=lambda: driver), driver, rows, writes, events


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
        inputs = KeyboardInput(driver_factory=lambda: driver)
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
        inputs = KeyboardInput(driver_factory=lambda: driver)
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
        inputs = KeyboardInput(driver_factory=lambda: driver)
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
