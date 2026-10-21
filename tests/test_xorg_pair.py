"""Production Xorg pair transactions with only X hardware calls replaced."""

import asyncio
import ctypes
from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from inkecho.platform.keyboard import (
    KeyboardError,
    KeyboardInput,
    _ModifierMap,
    _XTestDriver,
)


def hardware(monkeypatch, *, modifiers=(181, 182), blocked=False):
    rows = [(97, 65), (0, 0), (0, 0), (0, 0), (0, 0), (98, 66)]
    if blocked:
        rows[4] = (99, 67)
    driver = _XTestDriver.__new__(_XTestDriver)
    driver.first, driver.count = 180, len(rows)
    driver.width = None
    driver.slot = driver.applied = driver.pending_symbol = None
    driver._pair_applied, driver._pair_pending, driver._batch = {}, {}, {}
    driver.display, driver.root = 100, 1
    driver._checked = nullcontext
    driver._mapping = lambda: (2, tuple(value for row in rows for value in row))
    modifier_bytes = (ctypes.c_ubyte * 8)(*modifiers)
    modifier_map = _ModifierMap(1, modifier_bytes)
    writes, events, focus = [], [], [21]

    def change(_display, first, width, values, count):
        writes.append((first, width, tuple(values[: width * count]), count))
        for index in range(count):
            rows[first - driver.first + index] = tuple(
                values[index * width : (index + 1) * width]
            )
        return 1

    driver.x11 = SimpleNamespace(
        XChangeKeyboardMapping=change,
        XGetModifierMapping=lambda *_: ctypes.pointer(modifier_map),
        XFreeModifiermap=lambda *_: 0,
        XKeysymToKeycode=lambda *_: 36,
    )
    driver.focus = lambda: focus[0]
    driver.send = lambda window, code, pressed: events.append((window, code, pressed))
    driver.close = driver.restore
    original_sleep = asyncio.sleep

    async def sleep(_delay):
        await original_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", sleep)
    return driver, rows, writes, events, focus


def test_pair_request_excludes_modifiers_and_batches_new_symbols(monkeypatch):
    driver, rows, writes, events, _ = hardware(monkeypatch)
    before = rows.copy()

    async def run():
        inputs = KeyboardInput(driver_factory=lambda: driver)
        await inputs.connect()
        assert await inputs.insert("中文Ωé字", lambda: True) == 5
        assert [write[3] for write in writes] == [2, 2, 2, 1, 1]
        assert [write[0] for write in writes] == [183, 183, 183, 183, 184]
        # The final unused row retains its prior owned é symbol until cleanup.
        assert writes[2][2][2:] == (0x010000E9,) * 2
        assert [event[1] for event in events if event[2]] == [183, 184, 183, 184, 183]
        assert rows == before and driver.applied is None
        assert not driver._pair_pending and not driver._pair_applied
        await inputs.aclose()

    asyncio.run(run())


def test_no_legal_adjacent_pair_refuses_without_any_write_or_press(monkeypatch):
    driver, rows, writes, events, _ = hardware(monkeypatch, blocked=True)
    before = rows.copy()

    async def run():
        inputs = KeyboardInput(driver_factory=lambda: driver)
        await inputs.connect()
        with pytest.raises(KeyboardError, match="mapping_changed"):
            await inputs.insert("中文", lambda: True)
        assert not writes and not events and rows == before
        await inputs.aclose()

    asyncio.run(run())


def test_return_and_stream_fragments_reuse_existing_pair_without_idle_mapping(
    monkeypatch,
):
    driver, rows, writes, events, _ = hardware(monkeypatch)
    before = rows.copy()
    delays = []
    original_sleep = asyncio.sleep

    async def sleep(delay):
        delays.append(delay)
        await original_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", sleep)

    async def run():
        inputs = KeyboardInput(driver_factory=lambda: driver)
        await inputs.connect()
        async with inputs.output_session():
            assert not writes
            await inputs.insert("\n", lambda: True)
            assert not writes
            await inputs.insert("中文", lambda: True)
            await inputs.insert("文中\n", lambda: True)
            assert len(writes) == 1 and writes[0][3] == 2
            await inputs.insert("新", lambda: True)
            assert len(writes) == 2
        assert rows == before and [write[3] for write in writes] == [2, 2, 1, 1]
        assert [event[1] for event in events if event[2]] == [
            36,
            183,
            184,
            184,
            183,
            36,
            183,
        ]
        assert delays.count(0.1) == 1
        await inputs.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("phase", ["grace", "pressed", "expired"])
def test_cancel_and_deadline_release_keys_and_both_rows(monkeypatch, phase):
    driver, rows, writes, events, _ = hardware(monkeypatch)
    before = rows.copy()
    active = True
    calls = 0
    original_sleep = asyncio.sleep

    async def sleep(_delay):
        nonlocal active, calls
        calls += 1
        if phase == "grace" and calls == 1:
            active = False
        elif phase == "pressed" and calls == 2:
            raise asyncio.CancelledError
        await original_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", sleep)

    async def run():
        inputs = KeyboardInput(driver_factory=lambda: driver)
        await inputs.connect()
        expected = asyncio.CancelledError if phase == "pressed" else KeyboardError
        with pytest.raises(expected):
            await inputs.insert(
                "中文", lambda: active, deadline=0 if phase == "expired" else None
            )
        assert rows == before and not driver._pair_pending
        assert events == (
            [(21, 183, True), (21, 183, False)] if phase == "pressed" else []
        )
        if phase == "expired":
            assert not writes
        else:
            assert [write[3] for write in writes] == [2, 1, 1]
        await inputs.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["before_write", "after_write", "second_readback"])
def test_pair_transaction_failure_restores_every_owned_row(monkeypatch, failure):
    driver, rows, writes, events, _ = hardware(monkeypatch)
    before = rows.copy()
    original = driver.x11.XChangeKeyboardMapping
    read = driver._row
    failed = False

    def change(*args):
        nonlocal failed
        if args[-1] == 2 and failure != "second_readback" and not failed:
            failed = True
            if failure == "after_write":
                original(*args)
            raise KeyboardError("injection_failed")
        return original(*args)

    def readback():
        nonlocal failed
        if (
            failure == "second_readback"
            and writes
            and driver.slot == 184
            and not failed
        ):
            failed = True
            raise KeyboardError("injection_failed")
        return read()

    driver.x11.XChangeKeyboardMapping = change
    driver._row = readback

    async def run():
        inputs = KeyboardInput(driver_factory=lambda: driver)
        await inputs.connect()
        with pytest.raises(KeyboardError, match="injection_failed"):
            await inputs.insert("中文", lambda: True)
        assert rows == before and not events
        assert not driver._pair_applied and not driver._pair_pending
        await inputs.aclose()

    asyncio.run(run())


def test_foreign_change_preserved_but_other_owned_row_still_restored(monkeypatch):
    driver, rows, writes, events, _ = hardware(monkeypatch)
    original_sleep = asyncio.sleep

    async def sleep(_delay):
        rows[4] = (91, 92)
        await original_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", sleep)

    async def run():
        inputs = KeyboardInput(driver_factory=lambda: driver)
        await inputs.connect()
        with pytest.raises(KeyboardError, match="mapping_changed"):
            await inputs.insert("中文", lambda: True)
        assert rows[3] == (0, 0) and rows[4] == (91, 92)
        assert [write[0] for write in writes] == [183, 183]
        assert not events
        with pytest.raises(KeyboardError, match="mapping_changed"):
            await inputs.aclose()
        assert rows[4] == (91, 92)

    asyncio.run(run())


def test_focus_changes_and_normalized_readback_do_not_retarget_old_window(monkeypatch):
    driver, rows, _writes, events, focus = hardware(monkeypatch)
    original_row = driver._row
    driver._row = lambda: (*original_row(), 0, 0)
    original_sleep = asyncio.sleep
    calls = 0

    async def sleep(_delay):
        nonlocal calls
        calls += 1
        if calls == 4:
            focus[0] = 22
        await original_sleep(0)

    monkeypatch.setattr(asyncio, "sleep", sleep)

    async def run():
        inputs = KeyboardInput(driver_factory=lambda: driver)
        await inputs.connect()
        assert await inputs.insert("中文", lambda: True) == 2
        assert events == [
            (21, 183, True),
            (21, 183, False),
            (22, 184, True),
            (22, 184, False),
        ]
        assert rows[3:5] == [(0, 0), (0, 0)]
        await inputs.aclose()

    asyncio.run(run())
