"""Pure fake-driver/fixture boundaries; no desktop, browser or network starts."""

import asyncio
import importlib.util
import time
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

ENTRY = Path(__file__).resolve().parents[1] / "scripts/validation/x11_acceptance.py"


@pytest.fixture
def entry(monkeypatch):
    monkeypatch.syspath_prepend(str(ENTRY.parent))
    spec = importlib.util.spec_from_file_location("x11_acceptance_test", ENTRY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Driver:
    root, active_atom, pid_atom = 1, 2, 3

    def __init__(self):
        self.pid, self.character, self.loan, self.closed = 0, "", False, False
        self.text, self.events = {}, []

    def _checked(self):
        return nullcontext()

    def _property(self, window, atom):
        return self.pid * 10 if atom == self.active_atom else self.pid

    def focus(self):
        return self.pid * 10 + 1  # Actual focused child differs from active top.

    def _mapping(self):
        return (1, (int(self.loan),))

    def _write(self, values):
        self.loan = bool(values[0])

    def map(self, character):
        self.character = character
        self._write([1])
        return 20

    def verify(self):
        pass

    def restore(self):
        self._write([0])

    def send(self, window, code, pressed):
        self.events.append((window, code, pressed))
        if pressed:
            self.text[self.pid] += self.character

    def close(self):
        self.restore()
        self.closed = True  # Production leaves its XDisplay pointer unchanged.


def fixture(driver, pid=21):
    def owned():
        if obj.process.poll() is not None:
            raise ValueError("identity_changed")

    obj = SimpleNamespace(
        process=SimpleNamespace(pid=pid, poll=lambda: None),
        assert_owned=owned,
        snapshot=lambda: {
            "text": driver.text.get(pid, ""),
            "document_focused": True,
            "field_focused": True,
            "sampled_at": time.monotonic(),
        },
        spawn_display=":pure-test-only",
        platform="x11",
    )
    return obj


@pytest.fixture
def controls(monkeypatch):
    monkeypatch.setenv("DISPLAY", ":pure-test-only")
    return Driver()


def test_child_focus_is_allowed_but_outside_pid_and_stale_dispatch_are_not(
    controls, entry
):
    controls.pid = 21
    target = fixture(controls)
    assert entry.owned_focus(controls, target, 211)
    assert not entry.owned_focus(controls, target, 21)
    controls.pid = 22
    assert not entry.owned_focus(controls, target, 221)


@pytest.mark.parametrize("kind", ["stale", "future", "field", "document", "exited"])
def test_guard_rejects_unverified_focus(controls, kind, entry):
    controls.pid = 21
    target = fixture(controls)
    state = target.snapshot()
    if kind in {"stale", "future"}:
        state["sampled_at"] += -1 if kind == "stale" else 1
    elif kind == "exited":
        target.process.poll = lambda: 0
    else:
        state[kind + "_focused"] = False
    target.snapshot = lambda: state
    assert not entry.owned_focus(controls, target, 211)


def test_observation_never_blocks_release_or_counts_failed_original(controls, entry):
    from inkecho.platform.keyboard import KeyboardError, KeyboardInput

    inputs = KeyboardInput(driver_factory=lambda: controls)
    asyncio.run(inputs.connect())
    counts = dict.fromkeys(entry.COUNTERS, 0)
    originals = inputs._send, controls._write, controls.restore
    with entry.observe(inputs, lambda window: False, counts):
        with pytest.raises(KeyboardError, match="input_cancelled"):
            inputs._send(211, 20, True)
        inputs._send(211, 20, False)
    assert counts["press"] == 0 and counts["release"] == 1
    assert (inputs._send, controls._write, controls.restore) == originals
    assert controls.events == [(211, 20, False)]


@pytest.mark.parametrize(
    "mode", ("textarea", "contenteditable", "cancel", "currentcursor")
)
def test_actual_keyboard_control_flow_with_synthetic_driver(
    controls, monkeypatch, tmp_path, mode, entry
):
    from inkecho.platform import keyboard

    original = keyboard.KeyboardInput
    monkeypatch.setattr(
        keyboard, "KeyboardInput", lambda: original(driver_factory=lambda: controls)
    )
    monkeypatch.setattr(entry, "desktop", lambda scope: {"pure_test": True})
    sleeps = []

    async def sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(entry.asyncio, "sleep", sleep)
    browsers = []

    class Browser:
        def __init__(self, root, *, field, platform):
            self.__dict__.update(fixture(controls, 21 + len(browsers)).__dict__)
            self.errors, self.close_count = [], 0
            browsers.append(self)

        def start(self, *, reviewed):
            assert reviewed
            controls.pid = self.process.pid
            controls.text[controls.pid] = ""

        def close(self):
            assert controls.closed  # Close producer before target.
            self.close_count += 1
            return 0

    monkeypatch.setattr(entry, "NaturalOwnedBrowser", Browser)
    args = SimpleNamespace(work_root=tmp_path / "exclusive", scope="pure", mode=mode)
    report = {"passed": False}
    asyncio.run(entry.run(args, report))
    assert report["passed"] and report["driver_closed"] and controls.closed
    assert report["counts"]["guard_rejections"] == 0
    assert all(browser.close_count == 1 for browser in browsers)
    assert 0.5 in sleeps
    if mode == "cancel":
        assert report["expected_error"] == "input_cancelled"
        assert report["counts"]["press"] == report["counts"]["release"] == 8
        assert list(controls.text.values()) == [entry.SAMPLE[:8]]
    elif mode == "currentcursor":
        assert report["acknowledged_split"] == [5, len(entry.SAMPLE) - 5]
        assert list(controls.text.values()) == [entry.SAMPLE[:5], entry.SAMPLE[5:]]


def test_failed_original_send_is_not_counted_as_success(controls, entry):
    from inkecho.platform.keyboard import KeyboardInput

    inputs = KeyboardInput(driver_factory=lambda: controls)
    asyncio.run(inputs.connect())

    def failed(*args):
        raise ValueError("fixed_failure")

    inputs._send = failed
    counts = dict.fromkeys(entry.COUNTERS, 0)
    with entry.observe(inputs, lambda window: True, counts):
        with pytest.raises(ValueError, match="fixed_failure"):
            inputs._send(211, 20, True)
    assert counts["press"] == counts["release"] == 0
