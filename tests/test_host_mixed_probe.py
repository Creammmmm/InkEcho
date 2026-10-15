import importlib.util
import json
from pathlib import Path

import pytest

VALIDATION = Path(__file__).resolve().parents[1] / "scripts/validation"
SPEC = importlib.util.spec_from_file_location(
    "host_mixed_probe", VALIDATION / "host_mixed_wayland_probe.py"
)


@pytest.fixture
def probe(monkeypatch):
    # The standalone harness imports its adjacent native probe helper.
    monkeypatch.syspath_prepend(str(VALIDATION))
    module = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(module)
    monkeypatch.setattr(module.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(module, "parent_pid", lambda pid: 10 if pid == 12 else 99)
    monkeypatch.setattr(
        module, "process_start", lambda pid: "123" if pid == 12 else "0"
    )
    return module


@pytest.fixture
def state():
    return {
        "browser_pid": 12,
        "browser_parent_pid": 10,
        "browser_start": "123",
        "phase": 0,
        "backend_confirmed": True,
        "allowed": True,
        "sampled_at": 99.9,
    }


@pytest.mark.parametrize("phase", [0, 1, 2])
def test_fresh_owned_identity_permits_each_delivery_phase(
    probe, tmp_path, state, phase
):
    path = tmp_path / "guard.json"
    path.write_text(json.dumps({**state, "phase": phase}))
    assert probe.worker_guard(path, 10)


@pytest.mark.parametrize(
    "changed",
    [
        {"sampled_at": 99.749},
        {"sampled_at": 100.001},
        {"phase": -1},
        {"phase": 3},
        {"browser_pid": 99},
        {"browser_parent_pid": 99},
        {"browser_start": "122"},
        {"backend_confirmed": False},
        {"allowed": False},
    ],
)
def test_guard_rejects_stale_foreign_or_transition_state(
    probe, tmp_path, state, changed
):
    path = tmp_path / "guard.json"
    path.write_text(json.dumps({**state, **changed}))
    assert not probe.worker_guard(path, 10)


@pytest.mark.parametrize(
    "attribute,result", [("parent_pid", 11), ("process_start", "124")]
)
def test_live_identity_change_invalidates_previously_allowed_state(
    probe, tmp_path, monkeypatch, state, attribute, result
):
    path = tmp_path / "guard.json"
    path.write_text(json.dumps(state))
    assert probe.worker_guard(path, 10)
    monkeypatch.setattr(probe, attribute, lambda _pid: result)
    assert not probe.worker_guard(path, 10)


@pytest.mark.parametrize("content", ["{", "{}", "null"])
def test_incomplete_guard_state_fails_closed(probe, tmp_path, content):
    path = tmp_path / "guard.json"
    path.write_text(content)
    assert not probe.worker_guard(path, 10)


@pytest.mark.parametrize(
    "command",
    [
        (
            b"/opt/google/chrome/chrome\0--ozone-platform=x11\0"
            b"--user-data-dir=/tmp/owned/profile\0"
        ),
        (
            b"/opt/google/chrome/chrome --ozone-platform=x11 "
            b"--user-data-dir=/tmp/owned/profile\0"
        ),
    ],
)
def test_known_options_accept_original_argv_and_chrome_process_title(probe, command):
    assert probe.known_option_present(command, b"--ozone-platform=x11")
    assert probe.known_option_present(command, b"--user-data-dir=/tmp/owned/profile")


@pytest.mark.parametrize(
    "command",
    [
        b"chrome --ozone-platform=x11-extra\0",
        b"chrome prefix--ozone-platform=x11\0",
        b"chrome --other=--ozone-platform=x11\0",
        b"chrome --ozone-platform=wayland\0",
        b"chrome\0--other=title --ozone-platform=x11\0",
    ],
)
def test_known_options_reject_partial_embedded_or_foreign_flags(probe, command):
    assert not probe.known_option_present(command, b"--ozone-platform=x11")


def test_private_profile_requires_whole_known_path(probe):
    expected = b"--user-data-dir=/tmp/owned/profile"
    assert not probe.known_option_present(
        b"chrome --user-data-dir=/tmp/owned/profile-user\0", expected
    )


@pytest.mark.parametrize("flag", ["--map-settle", "--key-settle"])
@pytest.mark.parametrize("value", ["-0.001", "0.101", "nan", "inf"])
def test_settle_flags_reject_out_of_range_before_package_or_host_access(
    probe, monkeypatch, flag, value
):
    def forbidden(_root):
        pytest.fail("Invalid delay reached package loading")

    monkeypatch.setattr(probe, "load_package", forbidden)
    monkeypatch.setattr(
        probe.sys, "argv", ["probe", "--package-root", "/unused", flag, value]
    )
    with pytest.raises(SystemExit) as error:
        probe.main()
    assert error.value.code == 2


@pytest.mark.parametrize("flag", ["--map-settle", "--key-settle"])
@pytest.mark.parametrize("value", ["0", "0.03", "0.1"])
def test_settle_flags_accept_bounded_values_before_host_access(
    probe, monkeypatch, flag, value
):
    class PackageBoundary(Exception):
        pass

    def stop_before_host(_root):
        raise PackageBoundary

    monkeypatch.setattr(probe, "load_package", stop_before_host)
    monkeypatch.setattr(
        probe.sys,
        "argv",
        [
            "probe",
            "--package-root",
            "/unused",
            "--run-host",
            "--output",
            "/unused",
            flag,
            value,
        ],
    )
    with pytest.raises(PackageBoundary):
        probe.main()


@pytest.mark.parametrize("field", ["textarea", "contenteditable"])
def test_field_choices_reach_package_boundary_without_host_access(
    probe, monkeypatch, field
):
    class PackageBoundary(Exception):
        pass

    def stop_before_host(_root):
        raise PackageBoundary

    monkeypatch.setattr(probe, "load_package", stop_before_host)
    monkeypatch.setattr(
        probe.sys,
        "argv",
        [
            "probe",
            "--package-root",
            "/unused",
            "--run-host",
            "--output",
            "/unused",
            "--field",
            field,
        ],
    )
    with pytest.raises(PackageBoundary):
        probe.main()


def test_foreign_field_choice_rejected_before_package_access(probe, monkeypatch):
    def forbidden(_root):
        pytest.fail("Invalid field reached package loading")

    monkeypatch.setattr(probe, "load_package", forbidden)
    monkeypatch.setattr(
        probe.sys,
        "argv",
        [
            "probe",
            "--package-root",
            "/unused",
            "--field",
            "user-window",
        ],
    )
    with pytest.raises(SystemExit) as error:
        probe.main()
    assert error.value.code == 2
