"""Owned X11 drawing hints on the keyboard driver's existing X connection.

Every operation stays on the owning event-loop thread and reuses its error trap.
No new thread, global error handler, target counter mutation or text read occurs.
Drawing hints are neither per-character receipts nor presentation confirmation.
"""

import ctypes as C
import os
import time
from collections.abc import Callable
from dataclasses import dataclass

from .output_pacing import FeedbackLevel

P = C.c_void_p
Int = C.c_int
U = C.c_uint
W = C.c_ulong


class Value(C.Structure):
    _fields_ = [("hi", Int), ("lo", U)]

    @classmethod
    def make(cls, number):
        return cls(number >> 32, number & 0xFFFFFFFF)

    def number(self):
        return (self.hi << 32) | self.lo


class Trigger(C.Structure):
    _fields_ = [
        ("counter", W),
        ("value_type", Int),
        ("wait_value", Value),
        ("test_type", Int),
    ]


class Attributes(C.Structure):
    _fields_ = [("trigger", Trigger), ("delta", Value), ("events", Int), ("state", Int)]


class AlarmEvent(C.Structure):
    _fields_ = [
        ("type", Int),
        ("serial", W),
        ("send_event", Int),
        ("display", P),
        ("alarm", W),
        ("counter_value", Value),
        ("alarm_value", Value),
        ("time", W),
        ("state", Int),
    ]


class Rectangle(C.Structure):
    _fields_ = [
        ("x", C.c_short),
        ("y", C.c_short),
        ("width", C.c_ushort),
        ("height", C.c_ushort),
    ]


class DamageEvent(C.Structure):
    _fields_ = [
        ("type", Int),
        ("serial", W),
        ("send_event", Int),
        ("display", P),
        ("drawable", W),
        ("damage", W),
        ("level", Int),
        ("more", Int),
        ("timestamp", W),
        ("area", Rectangle),
        ("geometry", Rectangle),
    ]


class DestroyEvent(C.Structure):
    _fields_ = [
        ("type", Int),
        ("serial", W),
        ("send_event", Int),
        ("display", P),
        ("event", W),
        ("window", W),
    ]


class PropertyEvent(C.Structure):
    _fields_ = [
        ("type", Int),
        ("serial", W),
        ("send_event", Int),
        ("display", P),
        ("window", W),
        ("atom", W),
        ("time", W),
        ("state", Int),
    ]


class FocusEvent(C.Structure):
    _fields_ = [
        ("type", Int),
        ("serial", W),
        ("send_event", Int),
        ("display", P),
        ("window", W),
        ("mode", Int),
        ("detail", Int),
    ]


class Event(C.Union):
    _fields_ = [
        ("type", Int),
        ("alarm", AlarmEvent),
        ("destroy", DestroyEvent),
        ("focus", FocusEvent),
        ("property", PropertyEvent),
        ("damage", DamageEvent),
        ("pad", C.c_long * 24),
    ]


@dataclass(frozen=True)
class FeedbackCapability:
    level: FeedbackLevel = FeedbackLevel.NONE
    counter: bool = False
    damage: bool = False
    reason: str = "not_bound"


class X11Feedback:
    """Only owns its Alarm/Damage/listening mask, never the target's counters.

    The driver's display must be dedicated to keyboard/feedback events. No other
    event consumer may read it concurrently. Polling is bounded and callbacks
    run after X operations, capturing the caller's fixed pacing generation.
    """

    MAX_EVENTS = 64
    COALESCE_SECONDS = 0.016

    def __init__(
        self,
        driver,
        *,
        clock=time.monotonic,
        library_loader=C.CDLL,
        allow_xwayland=False,
    ):
        self.driver = driver
        self.clock = clock
        self.loader = library_loader
        self.allow_xwayland = allow_xwayland
        self.capability = FeedbackCapability()
        self.callback: Callable[[float], None] | None = None
        self.window = self.counter = self.alarm = self.damage = 0
        self.sync = self.dmg = None
        self.sync_base = self.damage_base = None
        self.property_atom = 0
        self._last_even = None
        self._last_hint = None
        self._initial_damage = True
        self._selected_masks = {}
        self._focus_child = 0
        self.focus_revision = 0
        self.cleanup_errors = 0

    @staticmethod
    def _bind_functions(library, specs):
        for name, (arguments, result) in specs.items():
            function = getattr(library, name)
            function.argtypes, function.restype = arguments, result

    def _libraries(self):
        self.x = self.driver.x11
        self._bind_functions(
            self.x,
            {
                "XPending": ([P], Int),
                "XNextEvent": ([P, C.POINTER(Event)], Int),
                "XSelectInput": ([P, W, C.c_long], Int),
            },
        )
        try:
            self.sync = self.loader("libXext.so.6")
            self._bind_functions(
                self.sync,
                {
                    "XSyncQueryExtension": ([P, C.POINTER(Int), C.POINTER(Int)], Int),
                    "XSyncInitialize": ([P, C.POINTER(Int), C.POINTER(Int)], Int),
                    "XSyncQueryCounter": ([P, W, C.POINTER(Value)], Int),
                    "XSyncCreateAlarm": ([P, W, C.POINTER(Attributes)], W),
                    "XSyncDestroyAlarm": ([P, W], Int),
                },
            )
        except (OSError, AttributeError):
            self.sync = None
        try:
            self.dmg = self.loader("libXdamage.so.1")
            self._bind_functions(
                self.dmg,
                {
                    "XDamageQueryExtension": ([P, C.POINTER(Int), C.POINTER(Int)], Int),
                    "XDamageQueryVersion": ([P, C.POINTER(Int), C.POINTER(Int)], Int),
                    "XDamageCreate": ([P, W, Int], W),
                    "XDamageSubtract": ([P, W, W, W], None),
                    "XDamageDestroy": ([P, W], None),
                },
            )
        except (OSError, AttributeError):
            self.dmg = None

    def _counters(self):
        kind, count, remaining, fmt, data = W(), W(), W(), Int(), P()
        status = self.x.XGetWindowProperty(
            self.driver.display,
            self.window,
            self.property_atom,
            0,
            2,
            0,
            6,
            C.byref(kind),
            C.byref(fmt),
            C.byref(count),
            C.byref(remaining),
            C.byref(data),
        )
        try:
            if status or kind.value != 6 or fmt.value != 32 or remaining.value:
                return []
            return list(C.cast(data, C.POINTER(W))[: count.value]) if data else []
        finally:
            if data:
                self.x.XFree(data)

    def bind(self, top_xid: int) -> FeedbackCapability:
        self.close()
        if not self.allow_xwayland and (
            os.environ.get("XDG_SESSION_TYPE", "").lower() != "x11"
            or os.environ.get("WAYLAND_DISPLAY")
        ):
            self.capability = FeedbackCapability(reason="desktop_unverified")
            return self.capability
        if type(top_xid) is not int or top_xid <= 1:
            self.capability = FeedbackCapability(reason="invalid_window")
            return self.capability
        self.window = top_xid
        self._initial_damage = True
        self._last_hint = self._last_even = None
        try:
            self._libraries()
            with self.driver._checked():
                display = self.driver.display
                self.property_atom = self.x.XInternAtom(
                    display, b"_NET_WM_SYNC_REQUEST_COUNTER", 1
                )
                counters = self._counters() if self.property_atom else []
                event, error, major, minor = Int(), Int(), Int(), Int()
                if (
                    self.sync
                    and self.sync.XSyncQueryExtension(
                        display, C.byref(event), C.byref(error)
                    )
                    and self.sync.XSyncInitialize(
                        display, C.byref(major), C.byref(minor)
                    )
                ):
                    self.sync_base = event.value
                    if len(counters) == 2 and counters[1]:
                        self.counter = counters[1]
                        value = Value()
                        if (
                            self.sync.XSyncQueryCounter(
                                display, self.counter, C.byref(value)
                            )
                            and value.number() < (1 << 63) - 1
                        ):
                            self._last_even = value.number() - value.number() % 2
                            attributes = Attributes(
                                Trigger(
                                    self.counter, 0, Value.make(value.number() + 1), 2
                                ),
                                Value.make(1),
                                1,
                                0,
                            )
                            self.alarm = self.sync.XSyncCreateAlarm(
                                display, 63, C.byref(attributes)
                            )
                major, minor = Int(1), Int(1)
                if (
                    self.dmg
                    and self.dmg.XDamageQueryExtension(
                        display, C.byref(event), C.byref(error)
                    )
                    and self.dmg.XDamageQueryVersion(
                        display, C.byref(major), C.byref(minor)
                    )
                    and major.value == 1
                ):
                    self.damage_base = event.value
                    self.damage = self.dmg.XDamageCreate(display, self.window, 3)
                if self.alarm or self.damage:
                    self.x.XSelectInput(display, self.window, (1 << 17) | (1 << 22))
                    self._selected_masks[self.window] = (1 << 17) | (1 << 22)
            if self.alarm or self.damage:
                self.capability = FeedbackCapability(
                    FeedbackLevel.DRAW,
                    bool(self.alarm),
                    bool(self.damage),
                    "counter_and_damage"
                    if self.alarm and self.damage
                    else "counter_only"
                    if self.alarm
                    else "damage_only",
                )
                # No callback is attached until bind returns; drain initial
                # already-queued events without converting them into credits.
                self.poll()
            else:
                self.capability = FeedbackCapability(reason="feedback_unavailable")
        except Exception:
            self._degrade("feedback_unavailable")
        return self.capability

    def watch_focus(self, child_xid: int) -> None:
        """Observe output-only scope changes without selecting or moving focus."""
        if self.capability.level != FeedbackLevel.DRAW:
            return
        if type(child_xid) is not int or child_xid <= 1:
            self._degrade("invalid_focus")
            return
        try:
            with self.driver._checked():
                for window, mask in [(self.driver.root, 1 << 22), (child_xid, 1 << 21)]:
                    merged = self._selected_masks.get(window, 0) | mask
                    self.x.XSelectInput(self.driver.display, window, merged)
                    self._selected_masks[window] = merged
            self._focus_child = child_xid
        except Exception:
            self._degrade("focus_unavailable")

    def set_callback(self, callback: Callable[[float], None]) -> None:
        self.callback = (
            callback if self.capability.level == FeedbackLevel.DRAW else None
        )

    def poll(self) -> None:
        if self.capability.level != FeedbackLevel.DRAW:
            return
        hint = subtract = scope_changed = False
        try:
            # Reading queued events needs no synchronous roundtrip/error-handler
            # change on every idle poll. All our writes are trapped below.
            for _ in range(self.MAX_EVENTS):
                if not self.x.XPending(self.driver.display):
                    break
                event = Event()
                self.x.XNextEvent(self.driver.display, C.byref(event))
                if (
                    event.type in (9, 10)
                    and event.focus.window == self._focus_child
                    and self._focus_child
                ) or (
                    event.type == 28
                    and event.property.window == self.driver.root
                    and event.property.atom == self.driver.active_atom
                    and self._focus_child
                ):
                    self.focus_revision += 1
                    scope_changed = True
                    continue
                if (event.type == 17 and event.destroy.window == self.window) or (
                    event.type == 28
                    and event.property.window == self.window
                    and event.property.atom == self.property_atom
                ):
                    self._degrade("target_changed")
                    return
                if (
                    self.alarm
                    and event.type == self.sync_base + 1
                    and event.alarm.alarm == self.alarm
                ):
                    if event.alarm.state != 0:
                        self._degrade("counter_unavailable")
                        return
                    value = event.alarm.counter_value.number()
                    if value % 2 == 0 and (
                        self._last_even is None or value > self._last_even
                    ):
                        self._last_even = value
                        hint = True
                if (
                    self.damage
                    and event.type == self.damage_base
                    and event.damage.damage == self.damage
                ):
                    subtract = True
                    if not self._initial_damage:
                        hint = True
                    self._initial_damage = False
            if self.x.XPending(self.driver.display):
                # A focus event may be buried after this bounded batch. Fall
                # back rather than granting a stale hint or busy-waiting.
                self._degrade("event_backlog")
                return
            if subtract:
                with self.driver._checked():
                    self.dmg.XDamageSubtract(self.driver.display, self.damage, 0, 0)
            now = self.clock()
            if (
                hint
                and not scope_changed
                and self.callback
                and (
                    self._last_hint is None
                    or now - self._last_hint >= self.COALESCE_SECONDS
                )
            ):
                self._last_hint = now
                self.callback(now)
        except Exception:
            self._degrade("feedback_lost")

    def _degrade(self, reason):
        self.close()
        self.capability = FeedbackCapability(reason=reason)

    def close(self) -> None:
        self.callback = None
        self.capability = FeedbackCapability(reason="closed")
        # Separate traps ensure a vanished Damage does not skip Alarm cleanup.
        for name, library, function in [
            ("alarm", self.sync, "XSyncDestroyAlarm"),
            ("damage", self.dmg, "XDamageDestroy"),
        ]:
            resource = getattr(self, name)
            setattr(self, name, 0)
            if resource and library:
                try:
                    with self.driver._checked():
                        getattr(library, function)(self.driver.display, resource)
                except Exception:
                    self.cleanup_errors += 1  # Never obstruct key/map cleanup.
        selected, self._selected_masks = self._selected_masks, {}
        for window in selected:
            try:
                with self.driver._checked():
                    self.x.XSelectInput(self.driver.display, window, 0)
            except Exception:
                self.cleanup_errors += 1
        self._focus_child = 0
        self.window = self.counter = 0
        self.sync_base = self.damage_base = None
