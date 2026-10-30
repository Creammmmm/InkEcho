"""Observe modifier metadata on a caller-owned EIS session socket.

The caller obtains the socket from its authorized session's ConnectToEIS. This
module never opens a bus, portal, display or socket path. It binds keyboard
capability but never starts emulation or sends keys. Snapshots describe aggregate
logical modifiers, not a list of physically held keys.
"""

from __future__ import annotations

import asyncio
import ctypes as c
import math
import os
import stat

KEYBOARD = 1 << 2
ERRORS = {
    "library_unavailable",
    "invalid_fd",
    "connect_failed",
    "disconnected",
    "closed",
    "snapshot_timeout",
    "event_overflow",
    "ambiguous_keyboard",
    "invalid_timeout",
    "keyboard_unavailable",
    "busy",
    "invalid_keymap",
    "keymap_changed",
    "snapshot_changed",
}


class ObserverError(RuntimeError):
    def __init__(self, code: str):
        self.code = code if code in ERRORS else "connect_failed"
        super().__init__(self.code)


def _library():
    try:
        lib = c.CDLL("libei.so.1")
        signatures = {
            "ei_new_sender": ([c.c_void_p], c.c_void_p),
            "ei_unref": ([c.c_void_p], c.c_void_p),
            "ei_setup_backend_fd": ([c.c_void_p, c.c_int], c.c_int),
            "ei_dispatch": ([c.c_void_p], None),
            "ei_get_fd": ([c.c_void_p], c.c_int),
            "ei_get_event": ([c.c_void_p], c.c_void_p),
            "ei_event_unref": ([c.c_void_p], c.c_void_p),
            "ei_event_get_type": ([c.c_void_p], c.c_int),
            "ei_event_type_to_string": ([c.c_int], c.c_char_p),
            "ei_event_get_seat": ([c.c_void_p], c.c_void_p),
            "ei_seat_has_capability": ([c.c_void_p, c.c_int], c.c_bool),
            # Variadic capabilities terminated by NULL; only fixed argument here.
            "ei_seat_bind_capabilities": ([c.c_void_p], None),
            "ei_seat_unbind_capabilities": ([c.c_void_p], None),
            "ei_seat_ref": ([c.c_void_p], c.c_void_p),
            "ei_seat_unref": ([c.c_void_p], c.c_void_p),
            "ei_event_get_device": ([c.c_void_p], c.c_void_p),
            "ei_device_has_capability": ([c.c_void_p, c.c_int], c.c_bool),
            "ei_device_keyboard_get_keymap": ([c.c_void_p], c.c_void_p),
            "ei_keymap_get_type": ([c.c_void_p], c.c_int),
            "ei_keymap_get_fd": ([c.c_void_p], c.c_int),
            "ei_keymap_get_size": ([c.c_void_p], c.c_size_t),
            "ei_device_ref": ([c.c_void_p], c.c_void_p),
            "ei_device_unref": ([c.c_void_p], c.c_void_p),
            "ei_log_set_handler": ([c.c_void_p, c.c_void_p], None),
        }
        for suffix in ("mods_depressed", "mods_latched", "mods_locked", "group"):
            signatures[f"ei_event_keyboard_get_xkb_{suffix}"] = (
                [c.c_void_p],
                c.c_uint32,
            )
        for name, (arguments, result) in signatures.items():
            function = getattr(lib, name)
            function.argtypes = arguments
            function.restype = result
        return lib
    except (OSError, AttributeError):
        raise ObserverError("library_unavailable") from None


class EISModifierObserver:
    """A bounded asyncio observer; caller retains ownership of its original fd.

    Use wait_snapshot(after_revision=previous["revision"]) after an action when
    a fresh change is required. A timeout never manufactures a zero state. The
    device_generation identifies EIS device lifetimes, not a keymap hash. A
    rebind also changes it. Always close in finally. Single event-loop use only;
    concurrent waits/refreshes are rejected. No synchronous Wayland roundtrips.
    """

    def __init__(self, fd: int):
        self._lib = _library()
        self._context = self._lib.ei_new_sender(None)
        self._devices = {}
        self._seat = None
        self._bound = False
        self._generation = 0
        self._revision = 0
        self._failure = None
        self._waiting = False
        self._reader = None
        # Keep the callback alive; never print server/library error bodies.
        self._log_handler = c.CFUNCTYPE(
            None, c.c_void_p, c.c_int, c.c_char_p, c.c_void_p
        )(lambda *_arguments: None)
        if not self._context:
            raise ObserverError("connect_failed")
        self._lib.ei_log_set_handler(self._context, self._log_handler)
        try:
            try:
                duplicate = os.dup(fd)
            except (OSError, TypeError, OverflowError):
                raise ObserverError("invalid_fd") from None
            # The library owns duplicate, including teardown on setup failure.
            if self._lib.ei_setup_backend_fd(self._context, duplicate) < 0:
                raise ObserverError("connect_failed")
        except BaseException:
            self.close()
            raise

    def _event(self, event) -> None:
        lib = self._lib
        name = lib.ei_event_type_to_string(lib.ei_event_get_type(event))
        if name == b"EI_EVENT_DISCONNECT":
            self._failure = "disconnected"
            return
        if name == b"EI_EVENT_SEAT_ADDED":
            seat = lib.ei_event_get_seat(event)
            if lib.ei_seat_has_capability(seat, KEYBOARD):
                if self._seat is not None:
                    self._failure = "ambiguous_keyboard"
                    return
                self._seat = lib.ei_seat_ref(seat)
                lib.ei_seat_bind_capabilities(seat, c.c_int(KEYBOARD), c.c_void_p())
                self._bound = True
            return
        if name == b"EI_EVENT_SEAT_REMOVED":
            if lib.ei_event_get_seat(event) == self._seat:
                for device in self._devices:
                    lib.ei_device_unref(device)
                self._devices.clear()
                lib.ei_seat_unref(self._seat)
                self._seat = None
                self._bound = False
            return
        if name not in {
            b"EI_EVENT_DEVICE_ADDED",
            b"EI_EVENT_DEVICE_REMOVED",
            b"EI_EVENT_DEVICE_PAUSED",
            b"EI_EVENT_DEVICE_RESUMED",
            b"EI_EVENT_KEYBOARD_MODIFIERS",
        }:
            return
        device = lib.ei_event_get_device(event)
        if name == b"EI_EVENT_DEVICE_ADDED":
            if lib.ei_device_has_capability(device, KEYBOARD):
                keymap = self._read_keymap(device)
                self._generation += 1
                lib.ei_device_ref(device)
                self._devices[device] = {
                    "generation": self._generation,
                    "resumed": False,
                    "snapshot": None,
                    "keymap": keymap,
                }
            return
        state = self._devices.get(device)
        if state is None:
            return
        if name == b"EI_EVENT_DEVICE_REMOVED":
            del self._devices[device]
            lib.ei_device_unref(device)
        elif name == b"EI_EVENT_DEVICE_PAUSED":
            state.update(resumed=False, snapshot=None, keymap=None)
        elif name == b"EI_EVENT_DEVICE_RESUMED":
            if state["keymap"] is None:
                state["keymap"] = self._read_keymap(device)
            state["resumed"] = True
        elif name == b"EI_EVENT_KEYBOARD_MODIFIERS":
            self._revision += 1
            state["snapshot"] = {
                "revision": self._revision,
                "device_generation": state["generation"],
                "depressed": lib.ei_event_keyboard_get_xkb_mods_depressed(event),
                "latched": lib.ei_event_keyboard_get_xkb_mods_latched(event),
                "locked": lib.ei_event_keyboard_get_xkb_mods_locked(event),
                "group": lib.ei_event_keyboard_get_xkb_group(event),
            }

    def _read_keymap(self, device) -> bytes:
        # libei 1.5 owns this fd; never close it or move its file offset.
        keymap = self._lib.ei_device_keyboard_get_keymap(device)
        if not keymap or self._lib.ei_keymap_get_type(keymap) != 1:
            raise ObserverError("invalid_keymap")
        fd = self._lib.ei_keymap_get_fd(keymap)
        size = self._lib.ei_keymap_get_size(keymap)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or not 0 < size <= 4_000_000:
                raise ObserverError("invalid_keymap")
            if info.st_size < size:
                raise ObserverError("invalid_keymap")
            data = os.pread(fd, size, 0)
            # Mutter 50.1 advertises strlen(keymap), excluding the terminating
            # NUL (unlike wl_keyboard.keymap). Normalize only in local memory.
            text = data[:-1] if data.endswith(b"\0") else data
            if (
                len(data) != size
                or b"\0" in text
                or not text.lstrip().startswith(b"xkb_keymap")
            ):
                raise ObserverError("invalid_keymap")
            text.decode("utf-8")
        except (OSError, ValueError, OverflowError, UnicodeError):
            raise ObserverError("invalid_keymap") from None
        return text + b"\0"

    def keymap_bytes(
        self,
        device_generation: int | None = None,
        *,
        expected_revision: int | None = None,
    ) -> bytes:
        """Return current canonical XKB bytes, optionally requiring a generation.

        Pass both generation and revision from a modifier snapshot to reject
        intervening device or modifier changes. On snapshot_changed, acquire and
        validate a fresh modifier snapshot before retrying. This copies no bytes
        into diagnostic state or logs. The caller still validates XKB semantics
        and separately checks map ownership.
        """
        if self._waiting:
            raise ObserverError("busy")
        snapshot = self.dispatch()
        if snapshot is None:
            raise ObserverError("keyboard_unavailable")
        if (
            device_generation is not None
            and snapshot["device_generation"] != device_generation
        ):
            raise ObserverError("keymap_changed")
        if expected_revision is not None and snapshot["revision"] != expected_revision:
            raise ObserverError("snapshot_changed")
        return next(iter(self._devices.values()))["keymap"]

    def dispatch(self) -> dict | None:
        """Drain a bounded event batch; return current valid metadata, if known."""
        if not self._context:
            raise ObserverError("closed")
        if self._failure:
            raise ObserverError(self._failure)
        self._lib.ei_dispatch(self._context)
        for _ in range(512):
            event = self._lib.ei_get_event(self._context)
            if not event:
                break
            try:
                self._event(event)
            except ObserverError as error:
                self._failure = error.code
                raise
            finally:
                self._lib.ei_event_unref(event)
        else:
            self._failure = "event_overflow"
        if self._failure:
            raise ObserverError(self._failure)
        if len(self._devices) > 1:
            raise ObserverError("ambiguous_keyboard")
        for state in self._devices.values():
            if state["resumed"] and state["snapshot"] is not None:
                return dict(state["snapshot"])
        return None

    async def wait_snapshot(
        self, timeout: float = 3, after_revision: int | None = None
    ) -> dict:
        """Wait at most timeout seconds; no text/key events are generated."""
        deadline = self._deadline(timeout)
        if self._waiting:
            raise ObserverError("busy")
        self._waiting = True
        try:
            return await self._wait_snapshot(deadline, after_revision)
        finally:
            self._waiting = False

    @staticmethod
    def _deadline(timeout):
        if not isinstance(timeout, (float, int)) or not math.isfinite(timeout):
            raise ObserverError("invalid_timeout")
        return asyncio.get_running_loop().time() + min(max(timeout, 0), 30)

    async def _readable(self, deadline):
        loop = asyncio.get_running_loop()
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise ObserverError("snapshot_timeout")
        fd = self._lib.ei_get_fd(self._context)
        if fd < 0:
            raise ObserverError("disconnected")
        ready = loop.create_future()

        def wake():
            if not ready.done():
                ready.set_result(None)

        try:
            loop.add_reader(fd, wake)
        except (OSError, ValueError, NotImplementedError):
            raise ObserverError("connect_failed") from None
        self._reader = (loop, fd, ready)
        try:
            await asyncio.wait_for(ready, remaining)
        except TimeoutError:
            raise ObserverError("snapshot_timeout") from None
        finally:
            if self._reader is not None and self._reader[2] is ready:
                loop.remove_reader(fd)
                self._reader = None

    async def _wait_snapshot(self, deadline, after_revision=None):
        while True:
            snapshot = self.dispatch()
            if snapshot is not None and (
                after_revision is None or snapshot["revision"] > after_revision
            ):
                return snapshot
            await self._readable(deadline)

    async def refresh_snapshot(self, timeout: float = 3) -> dict:
        """Rebind this observer's keyboard to request a real initial snapshot.

        Mutter 50.1 recreates a keyboard on map changes without always sending
        unchanged modifier state. Rebinding reaches its initial-state callback.
        This sends capability requests only, never keyboard/emulation events.
        An interrupted refresh invalidates the observer; the caller must close it.
        """
        deadline = self._deadline(timeout)
        if self._waiting:
            raise ObserverError("busy")
        self.dispatch()
        if self._seat is None:
            raise ObserverError("keyboard_unavailable")
        seat = self._seat
        revision = self._revision
        self._waiting = True
        try:
            for state in self._devices.values():
                state["snapshot"] = None
            if self._bound:
                self._lib.ei_seat_unbind_capabilities(
                    seat, c.c_int(KEYBOARD), c.c_void_p()
                )
                self._bound = False
            while self._devices:
                self.dispatch()
                if self._seat != seat:
                    raise ObserverError("keyboard_unavailable")
                if self._devices:
                    await self._readable(deadline)
            if self._seat != seat:
                raise ObserverError("keyboard_unavailable")
            self._lib.ei_seat_bind_capabilities(seat, c.c_int(KEYBOARD), c.c_void_p())
            self._bound = True
            return await self._wait_snapshot(deadline, after_revision=revision)
        except BaseException:
            # A partially completed rebind cannot promise a current snapshot.
            self._failure = self._failure or "keyboard_unavailable"
            raise
        finally:
            self._waiting = False

    def close(self) -> None:
        """Disconnect the observation context; never Stop the caller's session."""
        if self._reader is not None:
            loop, fd, ready = self._reader
            loop.remove_reader(fd)
            self._reader = None
            if not ready.done():
                ready.set_result(None)
        for device in self._devices:
            self._lib.ei_device_unref(device)
        self._devices.clear()
        if self._seat is not None:
            self._lib.ei_seat_unref(self._seat)
            self._seat = None
        self._bound = False
        if self._context:
            self._lib.ei_unref(self._context)
            self._context = None
