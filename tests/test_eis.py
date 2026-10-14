import asyncio
import os
from collections import Counter, deque

import pytest

from inkecho.platform import eis

MAP = b"xkb_keymap { /* owned synthetic fixture */ };\0"


class Library:
    """Event-driven fake libei with real local readiness and keymap descriptors."""

    def __init__(self):
        self.read_fd, self.write_fd = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
        self.maps = {}
        self.queue = deque()
        self.refs = Counter()
        self.released_events = []
        self.calls = []
        self.duplicate = None
        self.setup_result = 0
        self.auto_rebind = False
        self.device = 10
        self.map_format = 1
        self.map_size = None
        self.keymap_fd = None
        self.add_map(10, MAP)

    def add_map(self, device, data):
        fd = os.memfd_create("owned-eis-test", os.MFD_CLOEXEC)
        os.write(fd, data)
        self.maps[device] = fd

    def emit(self, name, device=10, **metadata):
        self.queue.append(dict(name=name, device=device, **metadata))
        os.write(self.write_fd, b"x")

    def ready_device(self, device=10, **metadata):
        self.emit("DEVICE_ADDED", device)
        self.emit("DEVICE_RESUMED", device)
        self.emit("KEYBOARD_MODIFIERS", device, **metadata)

    def ei_new_sender(self, _data):
        return 1

    def ei_log_set_handler(self, *_args):
        pass

    def ei_setup_backend_fd(self, _context, duplicate):
        self.duplicate = duplicate
        return self.setup_result

    def ei_unref(self, _context):
        self.calls.append("close")
        if self.duplicate is not None:
            os.close(self.duplicate)
            self.duplicate = None

    def ei_get_fd(self, _context):
        return self.read_fd

    def ei_dispatch(self, _context):
        while True:
            try:
                os.read(self.read_fd, 4096)
            except BlockingIOError:
                break

    def ei_get_event(self, _context):
        return self.queue.popleft() if self.queue else None

    def ei_event_get_type(self, event):
        return event["name"]

    def ei_event_type_to_string(self, name):
        return ("EI_EVENT_" + name).encode()

    def ei_event_unref(self, event):
        self.released_events.append(event["name"])

    def ei_event_get_seat(self, event):
        return event.get("seat", 2)

    def ei_seat_has_capability(self, *_args):
        return True

    def ei_seat_ref(self, seat):
        self.refs[seat] += 1
        return seat

    def ei_seat_unref(self, seat):
        self.refs[seat] -= 1

    def ei_seat_bind_capabilities(self, *_args):
        self.calls.append("bind")
        if self.auto_rebind:
            self.device += 1
            self.add_map(self.device, MAP.replace(b"fixture", b"new map"))
            self.ready_device(self.device, locked=16, group=1)

    def ei_seat_unbind_capabilities(self, *_args):
        self.calls.append("unbind")
        if self.auto_rebind:
            self.emit("DEVICE_REMOVED", self.device)

    def ei_event_get_device(self, event):
        assert event["name"].startswith(("DEVICE_", "KEYBOARD_"))
        return event["device"]

    def ei_device_has_capability(self, *_args):
        return True

    def ei_device_ref(self, device):
        self.refs[device] += 1
        return device

    def ei_device_unref(self, device):
        self.refs[device] -= 1

    def ei_device_keyboard_get_keymap(self, device):
        return device

    def ei_keymap_get_type(self, _keymap):
        return self.map_format

    def ei_keymap_get_fd(self, keymap):
        return self.maps[keymap] if self.keymap_fd is None else self.keymap_fd

    def ei_keymap_get_size(self, keymap):
        return (
            os.fstat(self.maps[keymap]).st_size
            if self.map_size is None
            else self.map_size
        )

    def ei_event_keyboard_get_xkb_mods_depressed(self, event):
        return event.get("depressed", 0)

    def ei_event_keyboard_get_xkb_mods_latched(self, event):
        return event.get("latched", 0)

    def ei_event_keyboard_get_xkb_mods_locked(self, event):
        return event.get("locked", 0)

    def ei_event_keyboard_get_xkb_group(self, event):
        return event.get("group", 0)

    def cleanup(self):
        if self.duplicate is not None:
            os.close(self.duplicate)
        for fd in {*self.maps.values(), self.read_fd, self.write_fd}:
            os.close(fd)


@pytest.fixture
def backend(monkeypatch):
    lib = Library()
    monkeypatch.setattr(eis, "_library", lambda: lib)
    try:
        yield lib
    finally:
        lib.cleanup()


def observer_for(lib):
    observer = eis.EISModifierObserver(lib.read_fd)
    lib.emit("SEAT_ADDED")
    lib.ready_device(locked=16)
    return observer


def test_fd_readiness_snapshot_and_generation_bound_map(backend):
    async def run():
        observer = eis.EISModifierObserver(backend.read_fd)
        try:

            async def publish():
                await asyncio.sleep(0)
                backend.emit("SEAT_ADDED")
                backend.ready_device(depressed=4, locked=16, group=1)

            task = asyncio.create_task(publish())
            state = await observer.wait_snapshot(timeout=0.2)
            await task
            assert state == dict(
                revision=1,
                device_generation=1,
                depressed=4,
                latched=0,
                locked=16,
                group=1,
            )
            assert observer.keymap_bytes(state["device_generation"]) == MAP
            assert observer._reader is None
            assert backend.calls == ["bind"]
            assert os.lseek(backend.maps[10], 0, os.SEEK_CUR) == len(MAP)
        finally:
            observer.close()
        assert not any(backend.refs.values())
        os.fstat(backend.read_fd)  # Caller retains its descriptor.

    asyncio.run(run())


def test_pause_remove_and_new_device_never_reuse_old_state(backend):
    async def run():
        observer = observer_for(backend)
        try:
            first = await observer.wait_snapshot()
            backend.emit("DEVICE_PAUSED")
            assert observer.dispatch() is None
            assert observer._devices[10]["keymap"] is None
            with pytest.raises(eis.ObserverError, match="keyboard_unavailable"):
                observer.keymap_bytes()
            backend.emit("DEVICE_REMOVED")
            backend.add_map(11, MAP.replace(b"fixture", b"replacement"))
            backend.emit("DEVICE_ADDED", 11)
            backend.emit("DEVICE_RESUMED", 11)
            with pytest.raises(eis.ObserverError, match="snapshot_timeout"):
                await observer.wait_snapshot(timeout=0.001)
            backend.emit("KEYBOARD_MODIFIERS", 11, locked=18)
            second = await observer.wait_snapshot(after_revision=first["revision"])
            assert second["device_generation"] > first["device_generation"]
            assert second["locked"] == 18
            with pytest.raises(eis.ObserverError, match="keymap_changed"):
                observer.keymap_bytes(first["device_generation"])
            assert b"replacement" in observer.keymap_bytes(second["device_generation"])
        finally:
            observer.close()
        assert not any(backend.refs.values())

    asyncio.run(run())


def test_refresh_requires_new_device_and_real_nonzero_snapshot(backend):
    async def run():
        observer = observer_for(backend)
        try:
            first = await observer.wait_snapshot()
            backend.auto_rebind = True
            second = await observer.refresh_snapshot(timeout=0.2)
            assert second["revision"] > first["revision"]
            assert second["device_generation"] > first["device_generation"]
            assert (second["locked"], second["group"]) == (16, 1)
            assert b"new map" in observer.keymap_bytes(second["device_generation"])
            assert backend.calls == ["bind", "unbind", "bind"]
        finally:
            observer.close()
        assert not any(backend.refs.values())

    asyncio.run(run())


@pytest.mark.parametrize("refresh", [False, True])
def test_cancel_removes_reader_and_close_is_idempotent(backend, refresh):
    async def run():
        observer = observer_for(backend)
        state = await observer.wait_snapshot()
        task = asyncio.create_task(
            observer.refresh_snapshot()
            if refresh
            else observer.wait_snapshot(after_revision=state["revision"])
        )
        await asyncio.sleep(0)
        assert observer._reader is not None
        with pytest.raises(eis.ObserverError, match="busy"):
            await observer.wait_snapshot()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert observer._reader is None
        if refresh:
            with pytest.raises(eis.ObserverError, match="keyboard_unavailable"):
                observer.dispatch()
        observer.close()
        observer.close()
        assert not any(backend.refs.values())
        assert backend.calls.count("close") == 1

    asyncio.run(run())


def test_close_wakes_pending_wait(backend):
    async def run():
        observer = eis.EISModifierObserver(backend.read_fd)
        task = asyncio.create_task(observer.wait_snapshot())
        await asyncio.sleep(0)
        observer.close()
        with pytest.raises(eis.ObserverError, match="closed"):
            await asyncio.wait_for(task, 0.2)
        assert observer._reader is None

    asyncio.run(run())


def test_timeout_is_not_zero_state_and_does_not_leave_reader(backend):
    async def run():
        observer = eis.EISModifierObserver(backend.read_fd)
        try:
            with pytest.raises(eis.ObserverError, match="snapshot_timeout"):
                await observer.wait_snapshot(timeout=0.001)
            assert observer._reader is None
            assert not observer._waiting
        finally:
            observer.close()

    asyncio.run(run())


@pytest.mark.parametrize("timeout", [float("inf"), float("nan"), "secret"])
def test_invalid_timeout_is_sanitized(backend, timeout):
    async def run():
        observer = eis.EISModifierObserver(backend.read_fd)
        try:
            with pytest.raises(eis.ObserverError, match="^invalid_timeout$"):
                await observer.wait_snapshot(timeout=timeout)
        finally:
            observer.close()

    asyncio.run(run())


@pytest.mark.parametrize("case", ["format", "huge", "short", "pipe", "nul", "utf8"])
def test_rejects_unbounded_or_invalid_keymap_without_logging_bytes(backend, case):
    observer = eis.EISModifierObserver(backend.read_fd)
    if case == "format":
        backend.map_format = 99
    elif case == "huge":
        backend.map_size = 4_000_001
    elif case == "short":
        backend.map_size = len(MAP) + 1
    elif case == "pipe":
        backend.keymap_fd = backend.read_fd
    else:
        os.ftruncate(backend.maps[10], 0)
        os.pwrite(
            backend.maps[10],
            b"xkb_keymap secret" + (b"\xff\0" if case == "utf8" else b"\0embedded\0"),
            0,
        )
    backend.ready_device()
    try:
        with pytest.raises(eis.ObserverError, match="^invalid_keymap$"):
            observer.dispatch()
        assert backend.released_events == ["DEVICE_ADDED"]
    finally:
        observer.close()
    assert not any(backend.refs.values())


def test_disconnect_and_unknown_event_release(backend):
    observer = eis.EISModifierObserver(backend.read_fd)
    backend.emit("FUTURE_EVENT")
    backend.emit("DISCONNECT")
    try:
        with pytest.raises(eis.ObserverError, match="^disconnected$"):
            observer.dispatch()
        assert backend.released_events == ["FUTURE_EVENT", "DISCONNECT"]
    finally:
        observer.close()


def test_failed_setup_closes_owned_duplicate_not_callers_fd(backend):
    backend.setup_result = -1
    with pytest.raises(eis.ObserverError, match="^connect_failed$"):
        eis.EISModifierObserver(backend.read_fd)
    assert backend.duplicate is None
    os.fstat(backend.read_fd)
    assert str(eis.ObserverError("sensitive detail")) == "connect_failed"


def test_seat_removal_invalidates_state_before_device_notifications(backend):
    observer = observer_for(backend)
    assert observer.dispatch() is not None
    backend.emit("SEAT_REMOVED")
    try:
        assert observer.dispatch() is None
        with pytest.raises(eis.ObserverError, match="keyboard_unavailable"):
            observer.keymap_bytes()
        assert not any(backend.refs.values())
        backend.emit("DEVICE_REMOVED")
        assert observer.dispatch() is None
    finally:
        observer.close()


def test_ambiguous_devices_are_not_arbitrarily_selected(backend):
    observer = observer_for(backend)
    backend.add_map(11, MAP)
    backend.ready_device(11)
    try:
        with pytest.raises(eis.ObserverError, match="ambiguous_keyboard"):
            observer.keymap_bytes()
    finally:
        observer.close()
    assert not any(backend.refs.values())


def test_event_batch_is_bounded_and_each_processed_event_is_released(backend):
    observer = eis.EISModifierObserver(backend.read_fd)
    for _ in range(513):
        backend.emit("FUTURE_EVENT")
    try:
        with pytest.raises(eis.ObserverError, match="event_overflow"):
            observer.dispatch()
        assert len(backend.released_events) == 512
    finally:
        observer.close()


def test_refresh_timeout_invalidates_old_snapshot(backend):
    async def run():
        observer = observer_for(backend)
        await observer.wait_snapshot()
        try:
            with pytest.raises(eis.ObserverError, match="snapshot_timeout"):
                await observer.refresh_snapshot(timeout=0.001)
            assert observer._reader is None
            with pytest.raises(eis.ObserverError, match="keyboard_unavailable"):
                observer.keymap_bytes()
        finally:
            observer.close()

    asyncio.run(run())


def test_keymap_read_rejects_new_held_modifier_in_same_generation(backend):
    async def run():
        observer = observer_for(backend)
        try:
            before = await observer.wait_snapshot()
            assert before["depressed"] == 0
            backend.emit("KEYBOARD_MODIFIERS", depressed=4, locked=16)
            with pytest.raises(eis.ObserverError, match="^snapshot_changed$"):
                observer.keymap_bytes(
                    before["device_generation"], expected_revision=before["revision"]
                )
            after = await observer.wait_snapshot(after_revision=before["revision"])
            assert after["device_generation"] == before["device_generation"]
            assert after["depressed"] == 4
            assert (
                observer.keymap_bytes(
                    after["device_generation"], expected_revision=after["revision"]
                )
                == MAP
            )
        finally:
            observer.close()

    asyncio.run(run())


@pytest.mark.parametrize("wire_has_nul", [False, True])
def test_mutter_strlen_keymap_is_normalized_without_changing_server_fd(
    backend, wire_has_nul
):
    # Mutter 50.1 add_keyboard_device sends exactly strlen(data) bytes; Wayland
    # snapshots include NUL. Both must compare equal after local normalization.
    wire = MAP if wire_has_nul else MAP[:-1]
    fd = backend.maps[10]
    os.ftruncate(fd, 0)
    os.pwrite(fd, wire, 0)
    observer = observer_for(backend)
    try:
        state = observer.dispatch()
        assert (
            observer.keymap_bytes(
                state["device_generation"], expected_revision=state["revision"]
            )
            == MAP
        )
        assert os.fstat(fd).st_size == len(wire)
        assert os.pread(fd, len(wire), 0) == wire
    finally:
        observer.close()
