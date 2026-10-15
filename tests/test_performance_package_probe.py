"""Mode-selection controls; no microphone, desktop or cloud acceptance here."""

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
