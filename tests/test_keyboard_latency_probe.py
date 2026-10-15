"""Environment guards only; these tests do not establish guest desktop support."""

import asyncio
import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = (
    Path(__file__).resolve().parents[1] / "scripts/validation/keyboard_latency_probe.py"
)
SPEC = importlib.util.spec_from_file_location("keyboard_latency_probe", PATH)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


@pytest.fixture
def guest(monkeypatch):
    state = {
        "release": 'ID=ubuntu\nVERSION_ID="24.04"\nPRETTY_NAME="Ubuntu 24.04 LTS"\n',
        "virt": "kvm\n",
        "login": "User=1000\nType=x11\nDesktop=ubuntu\n",
        "calls": [],
    }

    def open_release(path, *args, **kwargs):
        assert path == Path("/etc/os-release")
        return io.StringIO(state["release"])

    def command(arguments, **options):
        assert options == {"text": True, "timeout": 3}
        state["calls"].append(arguments)
        if arguments == ["/usr/bin/systemd-detect-virt", "--vm"]:
            return state["virt"]
        assert arguments == [
            "/usr/bin/loginctl",
            "show-session",
            "c2",
            "--property=User",
            "--property=Type",
            "--property=Desktop",
        ]
        return state["login"]

    monkeypatch.setattr(probe.Path, "open", open_release)
    monkeypatch.setattr(probe.subprocess, "check_output", command)
    monkeypatch.setattr(probe.os, "getuid", lambda: 1000)
    monkeypatch.setattr(probe.platform, "release", lambda: "fixture-kernel")
    for key, value in {
        "XDG_SESSION_TYPE": "x11",
        "DISPLAY": ":0",
        "XDG_SESSION_ID": "c2",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    return state


@pytest.mark.parametrize("virt", ["kvm", "qemu"])
def test_guest_gate_uses_actual_os_vm_and_current_user_graphical_login(guest, virt):
    guest["virt"] = virt + "\n"
    result = probe.verify_ubuntu24_vm_x11()
    assert result == {
        "os_id": "ubuntu",
        "os_version": "24.04",
        "os_pretty_name": "Ubuntu 24.04 LTS",
        "kernel": "fixture-kernel",
        "virtualization": virt,
        "session_type": "x11",
        "session_desktop": "ubuntu",
        "session_user_matches_process": True,
        "wayland_display_present": False,
    }
    assert len(guest["calls"]) == 2


@pytest.mark.parametrize(
    "release", ["ID=ubuntu\nVERSION_ID=26.04", "ID=debian\nVERSION_ID=24.04", ""]
)
def test_label_cannot_replace_actual_ubuntu24_os(guest, release):
    guest["release"] = release
    with pytest.raises(RuntimeError, match="Actual Ubuntu 24.04"):
        probe.verify_ubuntu24_vm_x11()
    assert not guest["calls"]


@pytest.mark.parametrize("virt", ["none", "docker", "oracle", "vmware", ""])
def test_guest_requires_real_kvm_or_qemu(guest, virt):
    guest["virt"] = virt
    with pytest.raises(RuntimeError, match="KVM/QEMU"):
        probe.verify_ubuntu24_vm_x11()


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("XDG_SESSION_TYPE", "wayland"),
        ("DISPLAY", ""),
        ("WAYLAND_DISPLAY", "wayland-0"),
        ("WAYLAND_DISPLAY", ""),
    ],
)
def test_guest_environment_cannot_relabel_wayland_or_missing_display(
    guest, monkeypatch, key, value
):
    monkeypatch.setenv(key, value)
    with pytest.raises(RuntimeError, match="X11 environment"):
        probe.verify_ubuntu24_vm_x11()


@pytest.mark.parametrize(
    "login", ["User=1000\nType=tty", "User=1001\nType=x11", "Type=x11", "User=1000"]
)
def test_env_x11_cannot_replace_logind_graphical_login_and_owner(guest, login):
    guest["login"] = login
    with pytest.raises(RuntimeError, match="actual graphical X11"):
        probe.verify_ubuntu24_vm_x11()


@pytest.mark.parametrize("session", ["", "--all", "c2\nType=x11", "a" * 65])
def test_session_selector_requires_bounded_literal_id(guest, monkeypatch, session):
    monkeypatch.setenv("XDG_SESSION_ID", session)
    with pytest.raises(RuntimeError, match="session ID"):
        probe.verify_ubuntu24_vm_x11()
    assert not guest["calls"]


def test_environment_gate_must_not_ignore_detection_failure(guest, monkeypatch):
    def failed(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "fixture")

    monkeypatch.setattr(probe.subprocess, "check_output", failed)
    with pytest.raises(subprocess.CalledProcessError):
        probe.verify_ubuntu24_vm_x11()


def test_cli_vm_gate_runs_before_qt_loop_or_input(guest, monkeypatch):
    guest["release"] = "ID=ubuntu\nVERSION_ID=26.04"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(PATH),
            "--environment",
            "ubuntu24-vm-x11",
            "--qt-loop",
            "--xdotool",
            "/fixture",
            "--targets",
            "gtk",
            "vte",
            "--repeat",
            "5",
        ],
    )
    with pytest.raises(RuntimeError, match="Actual Ubuntu 24.04"):
        probe.main()
    assert not guest["calls"]


@pytest.mark.parametrize("limit", ["0", "-1", str(len(probe.SAMPLE)), "10000"])
def test_cancel_cli_rejects_nonprefix_limits_before_environment_checks(
    monkeypatch, limit
):
    monkeypatch.setattr(
        sys, "argv", [str(PATH), "--cancel-after", limit, "--targets", "gtk"]
    )
    with pytest.raises(SystemExit) as caught:
        probe.main()
    assert caught.value.code == 2


@pytest.mark.parametrize("targets", [["vte"], ["chrome-textarea"], ["gtk", "vte"]])
def test_cancel_cli_is_only_for_owned_gtk(monkeypatch, targets):
    monkeypatch.setattr(
        sys, "argv", [str(PATH), "--cancel-after", "3", "--targets", *targets]
    )
    with pytest.raises(SystemExit) as caught:
        probe.main()
    assert caught.value.code == 2


class ControlledInput:
    """Pure control double; makes no desktop/input capability claims."""

    def __init__(self, events, failure=None, at=None):
        self.events, self.failure, self.at = events, failure, at

    async def insert(self, text, active, *, on_first_sent):
        from inkecho.platform.keyboard import KeyboardError

        for index, _ in enumerate(text):
            if not active():
                raise KeyboardError("input_cancelled")
            self.events.append(True)
            try:
                if index == 0:
                    on_first_sent(0.0)
                if self.at == index + 1:
                    raise self.failure
            finally:
                self.events.append(False)
        return len(text)


def test_normal_insert_control_has_no_cancellation_or_count_change():
    events, first = [], []
    assert asyncio.run(
        probe.insert_sample(ControlledInput(events), "hello", events, first)
    ) == (5, False)
    assert events == [True, False] * 5 and first == [0.0]


def test_limit_active_false_only_after_successful_nth_press_and_releases():
    events, first = [], []
    result = asyncio.run(
        probe.insert_sample(ControlledInput(events), "hello", events, first, 3)
    )
    assert result == (3, True)
    assert events == [True, False] * 3 and first == [0.0]


@pytest.mark.parametrize("cancel_after", [None, 3])
@pytest.mark.parametrize("presses", [2, 3])
def test_async_cancel_is_expected_only_with_explicit_exact_boundary(
    cancel_after, presses
):
    events, first = [], []
    inputs = ControlledInput(events, asyncio.CancelledError(), presses)
    if cancel_after == presses:
        assert asyncio.run(
            probe.insert_sample(inputs, "hello", events, first, cancel_after)
        ) == (3, True)
    else:
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(
                probe.insert_sample(inputs, "hello", events, first, cancel_after)
            )
    assert events == [True, False] * presses


@pytest.mark.parametrize(
    "code", ["injection_failed", "unsupported_target", "mapping_changed"]
)
def test_non_cancellation_errors_are_never_accepted_at_exact_boundary(code):
    from inkecho.platform.keyboard import KeyboardError

    events, first = [], []
    with pytest.raises(KeyboardError) as caught:
        asyncio.run(
            probe.insert_sample(
                ControlledInput(events, KeyboardError(code), 3),
                "hello",
                events,
                first,
                3,
            )
        )
    assert caught.value.code == code and events == [True, False] * 3


def test_system_fixture_environment_drops_packaged_runtime_without_mutating_parent(
    monkeypatch,
):
    dropped = {
        "PYTHONHOME": "/fixture-package/python3.13",
        "PYTHONPATH": "/fixture-package/modules",
        "LD_LIBRARY_PATH": "/fixture-package/lib",
        "WAYLAND_DISPLAY": "wayland-0",
    }
    preserved = {
        "DISPLAY": ":1",
        "XAUTHORITY": "/fixture-session/Xauthority",
        "DBUS_SESSION_BUS_ADDRESS": "unix:path=/fixture-session/bus",
        "XDG_SESSION_ID": "c2",
        "XDG_RUNTIME_DIR": "/fixture-session",
        "GTK_IM_MODULE": "gtk-im-context-simple",
        "QT_IM_MODULE": "compose",
        "XMODIFIERS": "@im=none",
    }
    for key, value in {**dropped, **preserved}.items():
        monkeypatch.setenv(key, value)
    child = probe.fixture_environment()
    assert not any(key in child for key in dropped)
    assert all(child[key] == value for key, value in preserved.items())
    assert child["GDK_BACKEND"] == "x11"
    assert all(probe.os.environ[key] == value for key, value in dropped.items())


def test_fixture_stderr_is_separate_persistent_and_cannot_overwrite_evidence(tmp_path):
    output = tmp_path / "new-run.json"
    path, stream = probe.fixture_stderr(output, "gtk")
    assert path == tmp_path / "new-run-fixture-gtk.log"
    with stream:
        stream.write(b"private fixture stderr only")
    with pytest.raises(FileExistsError):
        probe.fixture_stderr(output, "gtk")
    assert path.read_bytes() == b"private fixture stderr only"


def test_readiness_failure_has_fixed_metadata_without_stderr_or_environment(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(probe.time, "monotonic", lambda: 16.0)
    metadata = probe.readiness_metadata(
        "vte",
        "target_not_ready",
        SimpleNamespace(poll=lambda: None),
        tmp_path / "missing-ready.json",
        ["10", "11"],
        10.0,
    )
    assert metadata == {
        "target": "vte",
        "reason": "target_not_ready",
        "process_alive": True,
        "readyfile_exists": False,
        "visible_window_count": 2,
        "elapsed_seconds": 6.0,
    }
    assert "target_not_ready" in str(probe.TargetReadinessError(metadata))


@pytest.mark.parametrize("mapping_error", [False, True])
def test_failure_keeps_prior_targets_press_counts_and_only_known_error_code(
    mapping_error,
):
    from inkecho.platform.keyboard import KeyboardError

    def mapping():
        if mapping_error:
            raise RuntimeError("private mapping details")
        return "original"

    report = {"passed": True, "targets": [{"target": "gtk", "exact": True}]}
    error = probe.probe_failure(
        report,
        "vte",
        "inserting",
        KeyboardError("unsupported_target"),
        [True, False, True],
        [1.0],
        SimpleNamespace(_mapping=mapping),
        "original",
        None,
    )
    assert report["targets"] == [{"target": "gtk", "exact": True}]
    assert not report["passed"]
    failure = report["failure"]
    assert failure["phase"] == "inserting" and failure["target"] == "vte"
    assert failure["keyboard_error_code"] == "unsupported_target"
    assert failure["presses_sent"] == 2 and failure["releases_sent"] == 1
    assert failure["first_callback_count"] == 1
    assert failure["map_restored"] is (None if mapping_error else True)
    assert "private" not in str(error)


def test_freeform_failure_is_not_copied_into_report():
    report = {"passed": True, "targets": []}
    error = probe.probe_failure(
        report,
        "gtk",
        "focusing",
        RuntimeError("private body and env secret"),
        [],
        [],
        SimpleNamespace(_mapping=lambda: ()),
        (),
        None,
    )
    assert "keyboard_error_code" not in report["failure"]
    assert "private" not in str(error) and "secret" not in str(error)


def test_main_writes_prior_results_and_failure_json_then_exits_nonzero(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "failed-run.json"
    report = {
        "passed": False,
        "targets": [{"target": "gtk", "exact": True}],
        "failure": {"target": "vte", "phase": "inserting", "reason": "target_failed"},
    }

    async def failed(_args):
        raise probe.ProbeFailure(report)

    monkeypatch.setattr(probe, "measure", failed)
    monkeypatch.setenv("XDG_SESSION_TYPE", "wayland")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(PATH),
            "--targets",
            "gtk",
            "vte",
            "--xdotool",
            "/fixture",
            "--output",
            str(output),
        ],
    )
    with pytest.raises(SystemExit) as caught:
        probe.main()
    assert caught.value.code == 1
    import json

    assert json.loads(output.read_text()) == report
    console = capsys.readouterr()
    assert json.loads(console.out) == report
    assert console.err == "Owned keyboard validation failed; see failure metadata.\n"


@pytest.fixture
def scene_controls(monkeypatch):
    state = SimpleNamespace(
        calls=[], candidates="101\n102\n", foreign={102}, unknown=False
    )
    args = SimpleNamespace(
        environment="ubuntu24-vm-x11",
        verified_session_id="c2",
        xdotool="/fixture/xdotool",
    )
    process = SimpleNamespace(pid=2000, poll=lambda: None)
    monkeypatch.setattr(probe, "start_time", lambda _pid: "owned-start")
    monkeypatch.setattr(probe.time, "monotonic", lambda: 10.0)

    def read(command, **options):
        state.calls.append(command)
        assert 0 < options["timeout"] <= 0.4
        assert options["stderr"] == subprocess.DEVNULL
        if command[0] == "/fixture/xdotool":
            assert command == [
                "/fixture/xdotool",
                "search",
                "--limit",
                "8",
                "--pid",
                "2000",
            ]
            return state.candidates
        if command[0] == "/usr/bin/loginctl":
            assert command == [
                "/usr/bin/loginctl",
                "show-session",
                "c2",
                "--property=LockedHint",
                "--value",
            ]
            return "yes\n"
        if command[0] == "/usr/bin/gdbus":
            assert command[-1] == "org.gnome.ScreenSaver.GetActive"
            return "(false,)\n"
        if "-root" in command:
            return (
                "_NET_CURRENT_DESKTOP(CARDINAL) = 2\n"
                "_NET_ACTIVE_WINDOW(WINDOW): window id # 0x1234\n"
                "private title never retained"
            )
        window = int(command[2])
        if command[-1] == "_NET_WM_PID":
            return "_NET_WM_PID(CARDINAL) = " + str(
                9999 if window in state.foreign else 2000
            )
        assert window not in state.foreign
        if command[0] == "/usr/bin/xwininfo":
            return "private window title\n  Map State: IsUnviewable\n"
        assert command[0] == "/usr/bin/xprop"
        atom = "private-unknown-atom" if state.unknown else "_NET_WM_STATE_HIDDEN"
        return (
            "WM_STATE(WM_STATE):\n  window state: Normal\n"
            f"_NET_WM_STATE(ATOM) = {atom}\n_NET_WM_DESKTOP(CARDINAL) = 2\n"
        )

    monkeypatch.setattr(probe.subprocess, "check_output", read)
    return args, process, state


def test_notready_scene_contains_only_verified_owned_window_and_fixed_state(
    scene_controls,
):
    args, process, state = scene_controls
    scene = probe.readiness_scene(args, process, "owned-start")
    assert scene == {
        "current_desktop": 2,
        "active_window": 0x1234,
        "locked_hint": True,
        "screensaver_active": False,
        "owned_windows": [
            {
                "window": 101,
                "pid_matches": True,
                "map_state": "IsUnviewable",
                "wm_state": "Normal",
                "net_wm_state": ["_NET_WM_STATE_HIDDEN"],
                "desktop": 2,
            }
        ],
    }
    assert "private" not in json.dumps(scene)
    assert all(
        "windowmap" not in command
        and "windowactivate" not in command
        and "windowfocus" not in command
        for command in state.calls
    )


@pytest.mark.parametrize("environment", ["host-xwayland", "private-xvfb"])
def test_lock_screen_queries_only_run_for_verified_vm_mode(scene_controls, environment):
    args, process, state = scene_controls
    args.environment = environment
    scene = probe.readiness_scene(args, process, "owned-start")
    assert scene["locked_hint"] is None and scene["screensaver_active"] is None
    assert not any(
        command[0] in {"/usr/bin/loginctl", "/usr/bin/gdbus"} for command in state.calls
    )


@pytest.mark.parametrize("session", [None, "--all", "c2\nType=x11", "x" * 65])
def test_lock_screen_query_refuses_unverified_or_unbounded_session_id(
    scene_controls, session
):
    args, process, state = scene_controls
    args.verified_session_id = session
    probe.readiness_scene(args, process, "owned-start")
    assert not any(
        command[0] in {"/usr/bin/loginctl", "/usr/bin/gdbus"} for command in state.calls
    )


def test_scene_limits_window_collection_to_eight_and_drops_unknown_atoms(
    scene_controls,
):
    args, process, state = scene_controls
    state.candidates = "\n".join(str(window) for window in range(101, 121))
    state.unknown = True
    scene = probe.readiness_scene(args, process, "owned-start")
    assert len(scene["owned_windows"]) == 7
    assert all(
        entry["window"] <= 108 and entry["net_wm_state"] is None
        for entry in scene["owned_windows"]
    )
    assert "private" not in json.dumps(scene)


def test_scene_rejects_reused_pid_before_collecting_window_state(
    scene_controls, monkeypatch
):
    args, process, state = scene_controls
    monkeypatch.setattr(probe, "start_time", lambda _pid: "different-start")
    scene = probe.readiness_scene(args, process, "owned-start")
    assert scene["owned_windows"] == []
    assert not any("-id" in command for command in state.calls)


def test_scene_diagnostic_failures_are_null_without_freeform_errors(
    scene_controls, monkeypatch
):
    args, process, _state = scene_controls

    def failed(*_args, **_kwargs):
        raise RuntimeError("private stderr and environment")

    monkeypatch.setattr(probe.subprocess, "check_output", failed)
    scene = probe.readiness_scene(args, process, "owned-start")
    assert all(value is None for value in scene.values())
    assert "private" not in json.dumps(scene)


def test_scene_global_read_budget_stops_queries(scene_controls, monkeypatch):
    args, process, state = scene_controls
    times = iter([10.0, 10.0, 13.0])
    monkeypatch.setattr(probe.time, "monotonic", lambda: next(times, 13.0))
    scene = probe.readiness_scene(args, process, "owned-start")
    assert scene["current_desktop"] == 2 and scene["owned_windows"] is None
    assert len(state.calls) == 1


def test_mapping_counter_never_performs_or_defers_production_cleanup():
    calls = []
    driver = SimpleNamespace(
        _write=lambda values: calls.append(("write", values)),
        restore=lambda: calls.append(("restore",)),
    )
    original_write, original_restore = driver._write, driver.restore
    counts = {"mapping_writes": 0, "restore_calls": 0, "successful_restore_calls": 0}
    with probe.mapping_count_scope(driver, counts):
        driver._write([1])
        assert calls == [("write", [1])]
        driver.restore()
        assert calls[-1] == ("restore",)
    assert calls == [("write", [1]), ("restore",)]
    assert counts == {
        "mapping_writes": 1,
        "restore_calls": 1,
        "successful_restore_calls": 1,
    }
    assert driver._write == original_write and driver.restore == original_restore


def test_mapping_counter_restores_methods_but_does_not_mask_product_cleanup_failure():
    def fail():
        raise RuntimeError("fixture cleanup failed")

    driver = SimpleNamespace(_write=lambda _values: None, restore=fail)
    original_write, original_restore = driver._write, driver.restore
    counts = {"mapping_writes": 0, "restore_calls": 0, "successful_restore_calls": 0}
    with pytest.raises(RuntimeError, match="fixture cleanup failed"):
        with probe.mapping_count_scope(driver, counts):
            driver.restore()
    assert driver._write == original_write and driver.restore == original_restore
    assert counts["restore_calls"] == 1 and counts["successful_restore_calls"] == 0


def test_retired_candidate_cli_is_rejected(monkeypatch):
    monkeypatch.setattr(
        sys, "argv", [str(PATH), "--restore-policy", "end-of-insertion-candidate"]
    )
    with pytest.raises(SystemExit) as caught:
        probe.main()
    assert caught.value.code == 2


def test_source_root_is_strict_and_precedes_runtime_imports(tmp_path, monkeypatch):
    original_path = list(sys.path)
    monkeypatch.setattr(sys, "path", list(original_path))
    assert probe.prepare_source_root(tmp_path) == tmp_path.resolve()
    assert sys.path[0] == str(tmp_path.resolve())
    missing = tmp_path / "missing"
    with pytest.raises(FileNotFoundError):
        probe.prepare_source_root(missing)
    file = tmp_path / "not-a-directory"
    file.write_text("fixture")
    with pytest.raises(RuntimeError, match="directory"):
        probe.prepare_source_root(file)


@pytest.mark.parametrize(
    "escape", [None, "inkecho", "inkecho.platform.keyboard", "inkecho.runtime"]
)
def test_runtime_origins_verify_all_three_actual_module_paths_and_hashes(
    tmp_path, monkeypatch, escape
):
    root = tmp_path / "selected"
    root.mkdir()
    modules = {}
    for index, name in enumerate(
        ("inkecho", "inkecho.platform.keyboard", "inkecho.runtime")
    ):
        path = (tmp_path if escape == name else root) / f"module-{index}.py"
        path.write_text("# fixed fixture source\n")
        modules[name] = SimpleNamespace(__file__=str(path))
    monkeypatch.setattr(probe.importlib, "import_module", lambda name: modules[name])
    if escape is not None:
        with pytest.raises(RuntimeError, match="escaped"):
            probe.runtime_origins(root)
        return
    result = probe.runtime_origins(root)
    assert result["runtime_kind"] == "source" and result["expected_source_root"] == str(
        root
    )
    assert set(result["runtime_origins"]) == set(modules)
    assert all(len(item["sha256"]) == 64 for item in result["runtime_origins"].values())
    assert probe.runtime_origins(None)["runtime_kind"] == "unclassified"


def test_fixture_branch_ignores_source_root_to_keep_system_python_gi_clean(
    tmp_path, monkeypatch
):
    observed = []
    monkeypatch.setattr(probe, "fixture", lambda args: observed.append(args.fixture))

    def forbidden(*_args):
        raise AssertionError(
            "Fixture must not prepare or import an application runtime"
        )

    monkeypatch.setattr(probe, "prepare_source_root", forbidden)
    monkeypatch.setattr(probe, "runtime_origins", forbidden)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(PATH),
            "--fixture",
            "gtk",
            "--source-root",
            str(tmp_path / "does-not-exist"),
        ],
    )
    probe.main()
    assert observed == ["gtk"]


def test_already_cached_foreign_application_module_is_rejected(tmp_path, monkeypatch):
    from types import ModuleType

    root = tmp_path / "selected"
    root.mkdir()
    outside = tmp_path / "cached-package.py"
    outside.write_text("# cached foreign module\n")
    cached = ModuleType("inkecho")
    cached.__file__ = str(outside)
    monkeypatch.setitem(sys.modules, "inkecho", cached)
    with pytest.raises(RuntimeError, match="escaped"):
        probe.runtime_origins(root)
