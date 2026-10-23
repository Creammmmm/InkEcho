"""Synthetic Xlib feedback tests; these do not establish desktop support."""

import ctypes as C
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from inkecho.platform.output_pacing import FeedbackLevel
from inkecho.platform.x11_feedback import Event, Value, W, X11Feedback


class Function:
    def __init__(self, call):
        self.call = call

    def __call__(self, *args):
        return self.call(*args)


def put(pointer, kind, value):
    C.cast(pointer, C.POINTER(kind))[0] = value


class Driver:
    def __init__(self, *, counters=(11, 12), sync=True, damage=True):
        self.display = 123
        self.root = 1
        self.active_atom = 10
        self.counters = counters
        self.sync_enabled = sync
        self.damage_enabled = damage
        self.sync_version = self.damage_version = True
        self.query_counter = True
        self.counter_value = 100
        self.queue = []
        self.calls = []
        self.checks = 0
        self.fail = set()
        self.bad_window = False
        self.x11 = self.library(
            {
                "XPending": lambda *_: len(self.queue),
                "XNextEvent": self.next_event,
                "XSelectInput": lambda _d, window, mask: self.record(
                    "select", window, mask
                ),
                "XInternAtom": lambda *_: 9,
                "XGetWindowProperty": self.property,
                "XFree": lambda *_: 0,
            }
        )
        self.sync = self.library(
            {
                "XSyncQueryExtension": lambda _d, event, _error: self.extension(
                    event, 40, self.sync_enabled
                ),
                "XSyncInitialize": lambda *_: self.sync_version,
                "XSyncQueryCounter": self.counter,
                "XSyncCreateAlarm": lambda *_: self.record("alarm_create", 101) or 101,
                "XSyncDestroyAlarm": lambda _d, alarm: self.record(
                    "alarm_destroy", alarm
                ),
            }
        )
        self.damage = self.library(
            {
                "XDamageQueryExtension": lambda _d, event, _error: self.extension(
                    event, 70, self.damage_enabled
                ),
                "XDamageQueryVersion": lambda *_: self.damage_version,
                "XDamageCreate": self.create_damage,
                "XDamageSubtract": lambda _d, damage, *_: self.record(
                    "subtract", damage
                ),
                "XDamageDestroy": lambda _d, damage: self.record(
                    "damage_destroy", damage
                ),
            }
        )

    @staticmethod
    def library(functions):
        return SimpleNamespace(
            **{name: Function(call) for name, call in functions.items()}
        )

    def record(self, name, *args):
        self.calls.append((name, *args))
        if name in self.fail:
            raise RuntimeError("synthetic_xerror")
        return 0

    @staticmethod
    def extension(event, base, enabled):
        put(event, C.c_int, base)
        return enabled

    def loader(self, name):
        return {"libXext.so.6": self.sync, "libXdamage.so.1": self.damage}[name]

    @contextmanager
    def _checked(self):
        self.checks += 1
        yield
        if self.bad_window:
            raise RuntimeError("synthetic_bad_window")

    def property(
        self, _d, _w, _a, _off, _len, _delete, _type, kind, fmt, count, remaining, data
    ):
        self.buffer = (W * len(self.counters))(*self.counters)
        put(kind, W, 6)
        put(fmt, C.c_int, 32)
        put(count, W, len(self.counters))
        put(remaining, W, 0)
        put(data, C.c_void_p, C.cast(self.buffer, C.c_void_p).value)
        return 0

    def counter(self, _d, _counter, value):
        put(value, Value, Value.make(self.counter_value))
        return self.query_counter

    def create_damage(self, *_):
        self.record("damage_create", 102)
        self.queue.append(damage())  # Server's initial full-window region.
        return 102

    def next_event(self, _display, pointer):
        C.memmove(pointer, C.byref(self.queue.pop(0)), C.sizeof(Event))
        return 0


def counter(value=102, *, alarm=101, state=0):
    event = Event()
    event.alarm.type = 41
    event.alarm.alarm = alarm
    event.alarm.counter_value = Value.make(value)
    event.alarm.state = state
    return event


def damage(resource=102):
    event = Event()
    event.damage.type = 70
    event.damage.damage = resource
    return event


@pytest.fixture(autouse=True)
def xorg_environment(monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)


def bound(driver=None):
    driver = driver or Driver()
    now = [1.0]
    feedback = X11Feedback(driver, clock=lambda: now[0], library_loader=driver.loader)
    assert feedback.bind(200).level == FeedbackLevel.DRAW
    return driver, feedback, now


def test_external_resources_are_owned_and_target_counter_is_read_only():
    driver, feedback, _ = bound()
    assert feedback.capability.counter and feedback.capability.damage
    assert driver.calls[:3] == [
        ("alarm_create", 101),
        ("damage_create", 102),
        ("select", 200, (1 << 17) | (1 << 22)),
    ]
    feedback.close()
    assert ("alarm_destroy", 101) in driver.calls
    assert ("damage_destroy", 102) in driver.calls
    assert not any("counter_set" in name for name, *_ in driver.calls)


def test_initial_damage_and_bind_drain_do_not_emit_credit():
    driver, feedback, _ = bound()
    seen = []
    feedback.set_callback(seen.append)
    feedback.poll()
    assert not seen and not driver.queue
    assert ("subtract", 102) in driver.calls


def test_counter_even_progress_and_damage_coalesce_without_character_counts():
    driver, feedback, now = bound()
    seen = []
    feedback.set_callback(seen.append)
    driver.queue.extend([counter(101), counter(104), damage(), counter(104)])
    feedback.poll()
    assert seen == [1.0]
    now[0] += 0.001
    driver.queue.append(counter(108))
    feedback.poll()
    assert seen == [1.0]
    now[0] += 0.016
    driver.queue.extend([counter(109), damage()])
    feedback.poll()
    assert seen == [1.0, now[0]]


def test_foreign_resources_unknown_events_and_old_even_values_are_not_hints():
    driver, feedback, _ = bound()
    seen = []
    feedback.set_callback(seen.append)
    driver.queue.extend([counter(102, alarm=999), damage(999), counter(100), Event()])
    feedback.poll()
    assert seen == []


def test_poll_is_bounded_and_idle_poll_has_no_checked_roundtrip():
    driver, feedback, _ = bound()
    checks = driver.checks
    feedback.poll()
    assert driver.checks == checks
    driver.queue.extend(Event() for _ in range(500))
    feedback.poll()
    assert len(driver.queue) == 500 - feedback.MAX_EVENTS
    assert feedback.capability.reason == "event_backlog"


@pytest.mark.parametrize(
    "sync,damage_enabled,expected",
    [
        (False, True, "damage_only"),
        (True, False, "counter_only"),
        (False, False, "feedback_unavailable"),
    ],
)
def test_partial_capabilities_are_honest(sync, damage_enabled, expected):
    driver = Driver(sync=sync, damage=damage_enabled)
    feedback = X11Feedback(driver, library_loader=driver.loader)
    capability = feedback.bind(200)
    assert capability.reason == expected
    assert capability.counter is sync
    assert capability.damage is damage_enabled


def test_basic_resize_counter_is_not_extended_drawing_progress():
    driver = Driver(counters=(11,), damage=False)
    feedback = X11Feedback(driver, library_loader=driver.loader)
    assert feedback.bind(200).level == FeedbackLevel.NONE
    assert not feedback.alarm


def test_no_counter_can_still_report_damage_only_hint():
    driver = Driver(counters=())
    feedback = X11Feedback(driver, library_loader=driver.loader)
    assert feedback.bind(200).reason == "damage_only"


@pytest.mark.parametrize(
    "attribute", ["sync_version", "damage_version", "query_counter"]
)
def test_failed_version_or_counter_query_never_claims_failed_capability(attribute):
    driver = Driver()
    setattr(driver, attribute, False)
    feedback = X11Feedback(driver, library_loader=driver.loader)
    cap = feedback.bind(200)
    if attribute == "damage_version":
        assert not cap.damage and cap.counter
    else:
        assert not cap.counter and cap.damage


def test_missing_libraries_degrades_without_touching_target():
    driver = Driver()

    def absent(_name):
        raise OSError("synthetic_missing_library")

    feedback = X11Feedback(driver, library_loader=absent)
    assert feedback.bind(200).level == FeedbackLevel.NONE
    assert not driver.calls


@pytest.mark.parametrize(
    "session,wayland", [("wayland", "wayland-0"), ("x11", "wayland-0"), ("", "")]
)
def test_xwayland_and_unknown_desktop_not_promoted_without_measurement(
    monkeypatch, session, wayland
):
    monkeypatch.setenv("XDG_SESSION_TYPE", session)
    monkeypatch.setenv("WAYLAND_DISPLAY", wayland)
    driver = Driver()
    feedback = X11Feedback(driver, library_loader=driver.loader)
    assert feedback.bind(200).reason == "desktop_unverified"
    assert not driver.calls


def test_bad_window_during_bind_is_feedback_failure_not_transport_exception():
    driver = Driver()
    driver.bad_window = True
    feedback = X11Feedback(driver, library_loader=driver.loader)
    assert feedback.bind(200).level == FeedbackLevel.NONE
    assert feedback.cleanup_errors > 0
    assert feedback.alarm == feedback.damage == 0
    # The caller remains able to perform its independent transport restoration.
    assert driver.record("mapping_restore") == 0


@pytest.mark.parametrize("kind", ["destroy", "property", "alarm"])
def test_destroyed_or_replaced_counter_invalidates_and_detaches_callback(kind):
    driver, feedback, _ = bound()
    seen = []
    feedback.set_callback(seen.append)
    event = Event()
    if kind == "destroy":
        event.destroy.type, event.destroy.window = 17, 200
    elif kind == "property":
        event.property.type, event.property.window, event.property.atom = 28, 200, 9
    else:
        event = counter(state=1)
    driver.queue.extend([event, counter(104)])
    feedback.poll()
    assert feedback.capability.level == FeedbackLevel.NONE
    assert feedback.callback is None and not seen


def test_unrelated_window_or_property_does_not_invalidate():
    driver, feedback, _ = bound()
    unrelated = Event()
    unrelated.property.type, unrelated.property.window, unrelated.property.atom = (
        28,
        200,
        999,
    )
    foreign = Event()
    foreign.destroy.type, foreign.destroy.window = 17, 999
    driver.queue.extend([unrelated, foreign])
    feedback.poll()
    assert feedback.capability.level == FeedbackLevel.DRAW


def test_cleanup_is_idempotent_separate_best_effort_and_never_destroys_counter():
    driver, feedback, _ = bound()
    driver.fail.add("alarm_destroy")
    feedback.close()
    assert feedback.cleanup_errors == 1
    assert ("damage_destroy", 102) in driver.calls
    calls = list(driver.calls)
    feedback.close()
    assert driver.calls == calls


def test_old_callback_detached_on_rebind():
    driver, feedback, _ = bound()
    old, fresh = [], []
    feedback.set_callback(old.append)
    feedback.bind(201)
    feedback.set_callback(fresh.append)
    driver.queue.append(counter(104))
    feedback.poll()
    assert not old and len(fresh) == 1


def test_damage_subtract_failure_degrades_and_callback_does_not_escape():
    driver, feedback, _ = bound()
    feedback.set_callback(lambda _at: pytest.fail("must not emit failed damage"))
    driver.fail.add("subtract")
    driver.queue.append(damage())
    feedback.poll()
    assert feedback.capability.level == FeedbackLevel.NONE


def test_signed_counter_maximum_does_not_wrap_alarm_threshold():
    driver = Driver()
    driver.counter_value = (1 << 63) - 1
    feedback = X11Feedback(driver, library_loader=driver.loader)
    cap = feedback.bind(200)
    assert cap.reason == "damage_only" and not cap.counter
    assert not any(call[0] == "alarm_create" for call in driver.calls)


def test_watch_focus_uses_only_own_root_child_masks_and_merges_top_child():
    driver, feedback, _ = bound()
    feedback.watch_focus(200)
    assert ("select", 1, 1 << 22) in driver.calls
    assert ("select", 200, (1 << 17) | (1 << 22) | (1 << 21)) in driver.calls
    feedback.close()
    assert driver.calls[-2:] == [("select", 200, 0), ("select", 1, 0)]


def test_root_focus_bounce_invalidates_generation_without_drawing_credit():
    driver, feedback, _ = bound()
    feedback.watch_focus(201)
    seen = []
    feedback.set_callback(seen.append)
    active = Event()
    active.property.type, active.property.window, active.property.atom = 28, 1, 10
    driver.queue.extend([counter(102), active, active, damage()])
    feedback.poll()
    assert feedback.focus_revision == 2
    assert seen == []
    # Merely observing focus does not cancel the transport or destroy its map.
    assert feedback.capability.level == FeedbackLevel.DRAW
    feedback.bind(200)
    assert feedback.focus_revision == 2  # Monotonic across close/rebind.


def test_same_top_child_focus_out_and_in_separate_generations():
    driver, feedback, _ = bound()
    feedback.watch_focus(201)
    for event_type in (10, 9):
        event = Event()
        event.focus.type, event.focus.window = event_type, 201
        driver.queue.append(event)
    feedback.poll()
    assert feedback.focus_revision == 2


def test_unobserved_child_focus_does_not_invalidate_or_credit():
    driver, feedback, _ = bound()
    feedback.watch_focus(201)
    event = Event()
    event.focus.type, event.focus.window = 10, 999
    driver.queue.append(event)
    feedback.poll()
    assert feedback.focus_revision == 0


def test_backlog_never_credits_hint_before_buried_focus_change():
    driver, feedback, _ = bound()
    feedback.watch_focus(201)
    seen = []
    feedback.set_callback(seen.append)
    event = Event()
    event.focus.type, event.focus.window = 10, 201
    driver.queue.extend([counter(102), *[Event() for _ in range(64)], event])
    feedback.poll()
    assert not seen
    assert feedback.capability.reason == "event_backlog"
    assert feedback.callback is None and feedback.alarm == feedback.damage == 0


def test_watch_focus_failure_degrades_without_blocking_cleanup():
    driver, feedback, _ = bound()
    driver.fail.add("select")
    feedback.watch_focus(201)
    assert feedback.capability.reason == "focus_unavailable"
    assert feedback.cleanup_errors == 1
    assert ("alarm_destroy", 101) in driver.calls
    assert ("damage_destroy", 102) in driver.calls
