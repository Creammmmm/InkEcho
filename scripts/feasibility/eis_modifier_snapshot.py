"""Observe modifier metadata on an explicitly supplied private EIS socket.

The caller obtains the socket from its isolated session's ConnectToEIS. This
module never opens a bus, portal, display or socket path. It binds keyboard
capability but never starts emulation or sends keys. Snapshots describe aggregate
logical modifiers, not a list of physically held keys.
"""

from __future__ import annotations

import asyncio
import ctypes as c
import math
import os

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
    device_generation changes when Mutter replaces its keyboard after a map edit.
    Always call close() in the harness's finally block. Single event-loop use only.
    """

    def __init__(self, fd: int):
        self._lib = _library()
        self._context = self._lib.ei_new_sender(None)
        self._devices = {}
        self._seat = None
        self._bound = False
        self._refreshing = False
        self._generation = 0
        self._revision = 0
        self._failure = None
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
                self._generation += 1
                lib.ei_device_ref(device)
                self._devices[device] = {
                    "generation": self._generation,
                    "resumed": False,
                    "snapshot": None,
                }
            return
        state = self._devices.get(device)
        if state is None:
            return
        if name == b"EI_EVENT_DEVICE_REMOVED":
            del self._devices[device]
            lib.ei_device_unref(device)
        elif name == b"EI_EVENT_DEVICE_PAUSED":
            state.update(resumed=False, snapshot=None)
        elif name == b"EI_EVENT_DEVICE_RESUMED":
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
        if not isinstance(timeout, (float, int)) or not math.isfinite(timeout):
            raise ObserverError("invalid_timeout")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + min(max(timeout, 0), 30)
        while True:
            snapshot = self.dispatch()
            if snapshot is not None and (
                after_revision is None or snapshot["revision"] > after_revision
            ):
                return snapshot
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise ObserverError("snapshot_timeout")
            await asyncio.sleep(min(0.01, remaining))

    async def refresh_snapshot(self, timeout: float = 3) -> dict:
        """Rebind this observer's keyboard to request a real initial snapshot.

        Mutter 50.1 recreates a keyboard on map changes without always sending
        unchanged modifier state. Rebinding reaches its initial-state callback.
        This sends capability requests only, never keyboard/emulation events.
        Cancellation may leave this observer unbound; the caller must close it.
        """
        if not isinstance(timeout, (float, int)) or not math.isfinite(timeout):
            raise ObserverError("invalid_timeout")
        if self._refreshing:
            raise ObserverError("busy")
        self.dispatch()
        if self._seat is None:
            raise ObserverError("keyboard_unavailable")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + min(max(timeout, 0), 30)
        seat = self._seat
        revision = self._revision
        self._refreshing = True
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
                remaining = deadline - loop.time()
                if remaining <= 0:
                    raise ObserverError("snapshot_timeout")
                if self._devices:
                    await asyncio.sleep(min(0.01, remaining))
            if self._seat != seat:
                raise ObserverError("keyboard_unavailable")
            self._lib.ei_seat_bind_capabilities(seat, c.c_int(KEYBOARD), c.c_void_p())
            self._bound = True
            return await self.wait_snapshot(
                timeout=max(0, deadline - loop.time()), after_revision=revision
            )
        finally:
            self._refreshing = False

    def close(self) -> None:
        """Disconnect the observation context; never Stop the caller's session."""
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
