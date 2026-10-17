"""Fixture controls; no microphone, desktop or cloud acceptance here."""

import asyncio
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts/validation/performance_package_probe.py"
)
SPEC = importlib.util.spec_from_file_location("performance_package_probe", PATH)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


@pytest.fixture
def controls(monkeypatch):
    monkeypatch.syspath_prepend(str(PATH.parent))
    import keyboard_latency_probe

    calls = []
    metadata = {"os_id": "fixture-ubuntu", "session_user_matches_process": True}

    def verified():
        calls.append(True)
        return metadata

    monkeypatch.setattr(keyboard_latency_probe, "verify_ubuntu24_vm_x11", verified)
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)
    return SimpleNamespace(
        keyboard=keyboard_latency_probe, calls=calls, metadata=metadata
    )


def arguments(**changes):
    return SimpleNamespace(
        **{
            "owned_xwayland_live_mic": False,
            "owned_ubuntu24_vm_x11": False,
            "xdotool": None,
            **changes,
        }
    )


def test_default_remains_synthetic_capture_and_delivery_offscreen(controls):
    mode = probe.configure_environment(arguments())
    assert mode == {
        "real_microphone": False,
        "real_desktop_input": False,
        "environment_metadata": None,
    }
    assert probe.os.environ["QT_QPA_PLATFORM"] == "offscreen"
    assert not controls.calls


def test_existing_host_mode_retains_real_microphone_and_real_input(
    controls, monkeypatch
):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    mode = probe.configure_environment(
        arguments(owned_xwayland_live_mic=True, xdotool="/fixture")
    )
    assert mode["real_microphone"] and mode["real_desktop_input"]
    assert mode["environment_metadata"] is None
    assert "QT_QPA_PLATFORM" not in probe.os.environ and not controls.calls


@pytest.mark.parametrize("platform", [None, "xcb"])
def test_vm_mode_verifies_guest_and_uses_real_input_but_synthetic_audio(
    controls, monkeypatch, platform
):
    if platform is not None:
        monkeypatch.setenv("QT_QPA_PLATFORM", platform)
    monkeypatch.setenv("QT_IM_MODULE", "compose")
    monkeypatch.setenv("GTK_IM_MODULE", "gtk-im-context-simple")
    mode = probe.configure_environment(
        arguments(owned_ubuntu24_vm_x11=True, xdotool="/fixture")
    )
    assert mode == {
        "real_microphone": False,
        "real_desktop_input": True,
        "environment_metadata": controls.metadata,
    }
    assert controls.calls == [True]
    assert probe.os.environ.get("QT_QPA_PLATFORM") == platform
    assert probe.os.environ["QT_IM_MODULE"] == "compose"
    assert probe.os.environ["GTK_IM_MODULE"] == "gtk-im-context-simple"


@pytest.mark.parametrize("platform", ["offscreen", "minimal", "wayland", ""])
def test_vm_refuses_a_fake_or_non_x11_qt_desktop(controls, monkeypatch, platform):
    monkeypatch.setenv("QT_QPA_PLATFORM", platform)
    with pytest.raises(RuntimeError, match="actual X11 Qt"):
        probe.configure_environment(
            arguments(owned_ubuntu24_vm_x11=True, xdotool="/fixture")
        )
    assert controls.calls == [True]
    assert probe.os.environ["QT_QPA_PLATFORM"] == platform


def test_vm_gate_failure_is_not_ignored_and_does_not_enable_offscreen(
    controls, monkeypatch
):
    def refused():
        raise RuntimeError("actual guest check failed")

    monkeypatch.setattr(controls.keyboard, "verify_ubuntu24_vm_x11", refused)
    with pytest.raises(RuntimeError, match="actual guest"):
        probe.configure_environment(
            arguments(owned_ubuntu24_vm_x11=True, xdotool="/fixture")
        )
    assert "QT_QPA_PLATFORM" not in probe.os.environ


@pytest.mark.parametrize("vm", [False, True])
def test_owned_modes_require_xdotool(controls, monkeypatch, vm):
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    with pytest.raises(RuntimeError, match="xdotool"):
        probe.configure_environment(
            arguments(owned_ubuntu24_vm_x11=vm, owned_xwayland_live_mic=not vm)
        )


def test_host_mode_cannot_silently_become_x11_vm_mode(controls, monkeypatch):
    monkeypatch.setenv("XDG_SESSION_TYPE", "x11")
    with pytest.raises(RuntimeError, match="Wayland/XWayland"):
        probe.configure_environment(
            arguments(owned_xwayland_live_mic=True, xdotool="/fixture")
        )
    assert not controls.calls


def test_direct_control_rejects_two_desktop_modes(controls):
    with pytest.raises(RuntimeError, match="Choose one"):
        probe.configure_environment(
            arguments(owned_xwayland_live_mic=True, owned_ubuntu24_vm_x11=True)
        )
    assert not controls.calls


def test_cli_rejects_two_desktop_modes_before_any_environment_or_qt(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(PATH),
            "--package-root",
            "/not-read",
            "--output",
            "/not-written",
            "--owned-xwayland-live-mic",
            "--owned-ubuntu24-vm-x11",
        ],
    )
    with pytest.raises(SystemExit) as caught:
        probe.main()
    assert caught.value.code == 2


@pytest.mark.parametrize(
    "name,parts,delay,expected",
    [
        ("normal", probe.PARTS, 0.35, probe.FINAL),
        ("one-character-fast", list(probe.FINAL), 0.001, probe.FINAL),
        ("one-character-fast-long", list(probe.FINAL * 6), 0.001, probe.FINAL * 6),
        ("one-character-paced-long", list(probe.FINAL * 6), 0.07, probe.FINAL * 6),
    ],
)
def test_sse_profile_uses_only_fixed_fixture_text(name, parts, delay, expected):
    actual_parts, actual_delay = probe.fixture_sse_profile(name)
    assert actual_parts == parts and actual_delay == delay
    assert "".join(actual_parts) == expected
    assert actual_parts is not probe.PARTS


@pytest.mark.parametrize("name", ["", "fast", None])
def test_sse_profile_rejects_unknown_names(name):
    with pytest.raises(ValueError, match="Unknown fixed SSE"):
        probe.fixture_sse_profile(name)


@pytest.mark.parametrize("overlap", [False, True])
def test_normal_requires_overlap_but_character_profiles_report_actual_order(overlap):
    assert probe.streaming_timing_accepted("normal", overlap) is overlap
    assert probe.streaming_timing_accepted("one-character-fast", overlap) is True
    assert probe.streaming_timing_accepted("one-character-fast-long", overlap) is True
    assert probe.streaming_timing_accepted("one-character-paced-long", overlap) is True


@pytest.mark.parametrize(
    "profile", ["one-character-fast-long", "one-character-paced-long"]
)
def test_long_sse_cli_profile_is_explicit_and_accepted_before_file_checks(
    monkeypatch, tmp_path, profile
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(PATH),
            "--package-root",
            str(tmp_path / "not-existing"),
            "--output",
            str(tmp_path / "not-written"),
            "--fixture-sse-profile",
            profile,
        ],
    )
    with pytest.raises(FileNotFoundError):
        probe.main()
    assert not (tmp_path / "not-written").exists()


def test_unknown_sse_cli_profile_is_refused_before_reading_files(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(PATH),
            "--package-root",
            "/not-read",
            "--output",
            "/not-written",
            "--fixture-sse-profile",
            "unrecognized",
        ],
    )
    with pytest.raises(SystemExit) as caught:
        probe.main()
    assert caught.value.code == 2


class CountingDriver:
    """In-memory calls for instrumentation, not an X11 compatibility claim."""

    root, active_atom, pid_atom = 1, 2, 3

    def __init__(self):
        self.mapping = None
        self.window = 21
        self.writes = []
        self.events = []
        self.fail_write = self.fail_restore = False

    @property
    def applied(self):
        return self.mapping

    def _property(self, _window, atom):
        return self.window if atom == self.active_atom else 42

    def focus(self):
        return self.window

    def _write(self, value):
        if self.fail_write:
            raise RuntimeError("fixed write failure")
        self.writes.append(value)
        self.mapping = value
        return "fixed write result"

    def map(self, character):
        if character == "\n":
            return 36
        self._write(character)
        return 248

    def verify(self):
        pass

    def send(self, window, code, pressed):
        self.events.append((window, code, pressed))

    def restore(self):
        if self.fail_restore:
            raise RuntimeError("fixed restore failure")
        if self.mapping is not None:
            self._write(None)
        return "fixed restore result"

    def close(self):
        self.restore()


async def observed_inputs(folder):
    from inkecho.platform.keyboard import KeyboardInput

    driver = CountingDriver()
    inputs = KeyboardInput(driver_factory=lambda: driver)
    await inputs.connect()
    owned = probe.OwnedTarget("/not-invoked", folder, inputs)
    owned.window, owned.started = 21, "fixed identity"
    owned.process = SimpleNamespace(pid=42, poll=lambda: None)
    owned.identity = lambda: "fixed identity"
    owned.observe_input()
    return owned, inputs, driver


def test_observer_counts_real_inserts_and_successful_calls_without_extra_restore(
    tmp_path,
):
    async def run():
        owned, inputs, driver = await observed_inputs(tmp_path)
        assert await inputs.insert("中\nΩ", lambda: True) == 3
        assert await inputs.insert("好", lambda: True) == 1
        assert driver.writes == ["中", "Ω", None, "好", None]
        assert owned.mapping_counts == {
            "mapping_writes": 5,
            "successful_restore_calls": 2,
            "completed_insert_calls": 2,
        }
        assert len(driver.events) == 8 and driver.mapping is None
        # Release-to-restore observes each insertion's last release only.
        assert owned.summary()["release_to_restore"]["count"] == 2

    asyncio.run(run())


def test_observer_leaves_cancel_release_and_cleanup_to_production(tmp_path):
    from inkecho.platform.keyboard import KeyboardError

    async def run():
        owned, inputs, driver = await observed_inputs(tmp_path)
        allowed = True

        def cancel(_when):
            nonlocal allowed
            allowed = False

        with pytest.raises(KeyboardError, match="input_cancelled"):
            await inputs.insert("中文", lambda: allowed, on_first_sent=cancel)
        assert driver.events == [(21, 248, True), (21, 248, False)]
        assert driver.writes == ["中", None] and driver.mapping is None
        assert owned.mapping_counts == {
            "mapping_writes": 2,
            "successful_restore_calls": 1,
            "completed_insert_calls": 0,
        }

    asyncio.run(run())


def test_observer_propagates_failures_and_only_counts_successful_calls(tmp_path):
    async def run():
        owned, _inputs, driver = await observed_inputs(tmp_path)
        driver.fail_write = True
        with pytest.raises(RuntimeError, match="fixed write failure"):
            driver._write("中")
        driver.fail_restore = True
        with pytest.raises(RuntimeError, match="fixed restore failure"):
            driver.restore()
        assert not any(owned.mapping_counts.values())
        driver.fail_write = driver.fail_restore = False
        assert driver._write("中") == "fixed write result"
        assert driver.restore() == "fixed restore result"
        assert driver.writes == ["中", None]
        assert owned.mapping_counts["mapping_writes"] == 2
        assert owned.mapping_counts["successful_restore_calls"] == 1

    asyncio.run(run())


def test_observer_keeps_owned_focus_guard_before_press(tmp_path):
    async def run():
        owned, inputs, driver = await observed_inputs(tmp_path)
        driver.window = 99
        with pytest.raises(RuntimeError, match="outside owned desktop"):
            await inputs.insert("中", lambda: True)
        # The production finally releases its attempted key and restores its row.
        assert driver.events == [(99, 248, False)]
        assert driver.writes == ["中", None] and driver.mapping is None
        assert owned.mapping_counts["completed_insert_calls"] == 0

    asyncio.run(run())
