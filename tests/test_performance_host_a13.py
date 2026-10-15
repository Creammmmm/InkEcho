"""Host runner controls only: no application, X request, microphone or VM."""

import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

PATH = (
    Path(__file__).resolve().parents[1] / "scripts/validation/performance_host_a13.py"
)
SPEC = importlib.util.spec_from_file_location("performance_host_a13", PATH)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


@pytest.mark.parametrize("mode", probe.MODES)
def test_fixed_commands_use_only_packaged_runtime_and_explicit_owned_modes(mode):
    manifest = {"appdir": "/artifact", "xdotool": "/owned-xdotool"}
    command = probe.command(manifest, Path("/exclusive"), mode)
    assert command[0] == "/artifact/usr/bin/python3"
    assert not {"--source-root", "--pacing", "--restore-policy"}.intersection(command)
    if mode == "pipeline-microphone":
        assert "--owned-xwayland-live-mic" in command
        assert "--owned-ubuntu24-vm-x11" not in command
    elif mode == "ui-native":
        assert "ui-helper" in command
    else:
        assert command[command.index("--environment") + 1] == "host-xwayland"
        assert "--qt-loop" in command
        assert ("--cancel-after" in command) is (mode == "cancel12")


def test_observation_timeout_never_terminates_or_kills_known_producer(
    tmp_path, monkeypatch
):
    class Process:
        pid = 42

        def wait(self, timeout):
            raise subprocess.TimeoutExpired(["fixed"], timeout)

        def poll(self):
            return None

        def terminate(self):
            pytest.fail("A live producer was terminated")

        def kill(self):
            pytest.fail("A live producer was killed")

    def spawned(*_args, **options):
        assert options["start_new_session"] is True
        return Process()

    monkeypatch.setattr(probe.subprocess, "Popen", spawned)
    monkeypatch.setattr(probe, "process_start", lambda _pid: "fixed-start")
    log = tmp_path / "owned.log"
    result = probe.observe(["fixed"], {}, log, 1)
    assert result["running"] and result["exit_code"] is None
    identity = json.loads(log.with_suffix(".identity.json").read_text())
    assert identity["pid"] == 42 and identity["start_ticks"] == "fixed-start"
    assert identity["argv"] == ["fixed"]
    assert probe.live_records([result]) == [result]


def test_previous_live_observation_blocks_next_mode_before_any_launch(
    tmp_path, monkeypatch
):
    first = tmp_path / "default20"
    first.mkdir()
    (first / "acceptance.json").write_text(
        json.dumps(
            {
                "passed": True,
                "processes": [{"pid": 42, "start_ticks": "same", "running": True}],
            }
        )
    )
    monkeypatch.setattr(probe, "process_start", lambda _pid: "same")
    monkeypatch.setattr(
        probe.subprocess, "Popen", lambda *_a, **_kw: pytest.fail("launched")
    )
    with pytest.raises(RuntimeError, match="previous_mode_not_passed_and_terminal"):
        probe.run_mode(tmp_path, {}, "cancel12")
    assert not (tmp_path / "cancel12").exists()


def test_missing_xdg_session_id_uses_read_only_graphical_session_lookup(monkeypatch):
    monkeypatch.delenv("XDG_SESSION_ID", raising=False)
    calls = []

    def checked(argv, **_options):
        calls.append(argv)
        if argv[0] == "gdbus":
            stdout = "(false,)"
        elif argv[1] == "show-user":
            stdout = "42"
        else:
            stdout = f"User={os.getuid()}\nType=wayland\nLockedHint=no\n"
        return SimpleNamespace(returncode=0, stdout=stdout)

    monkeypatch.setattr(probe.subprocess, "run", checked)
    result = probe.preflight()
    assert result["runnable"] and result["logind_graphical_session_verified"]
    assert calls[1][:3] == ["loginctl", "show-user", str(os.getuid())]
    assert all("unlock" not in argv and "lock-session" not in argv for argv in calls)


@pytest.mark.parametrize("reply", ["(true,)", "unexpected"])
def test_locked_or_unknown_session_is_not_an_input_support_failure(monkeypatch, reply):
    calls = []

    def checked(argv, **_options):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout=reply)

    monkeypatch.setattr(probe.subprocess, "run", checked)
    result = probe.preflight()
    assert not result["runnable"] and len(calls) == 1


@pytest.mark.parametrize("model,accepted", [("", True), ("unexpected-model", False)])
def test_ui_toggle_requires_actual_empty_model_from_its_disposable_profile(
    tmp_path, model, accepted
):
    (tmp_path / "providers").mkdir()
    (tmp_path / "config.json").write_text(
        json.dumps({"transcription_provider": "qwen"})
    )
    (tmp_path / "providers/qwen.json").write_text(json.dumps({"model": model}))
    assert probe.empty_disposable_model(tmp_path) is accepted


def test_partial_receipt_from_still_running_producer_is_not_treated_as_success(
    tmp_path,
):
    path = tmp_path / "receipt.json"
    path.write_text('{"passed":')
    assert probe.read_result(path) == {}


def test_manifest_digest_is_required_before_snapshot_reads(tmp_path):
    (tmp_path / "manifest.json").write_text("{}")
    with pytest.raises(RuntimeError, match="reviewed_manifest_required"):
        probe.load_manifest(tmp_path, "not-the-digest")


@pytest.fixture
def audio_environment(tmp_path, monkeypatch):
    runtime = tmp_path / "host-runtime"
    runtime.mkdir(mode=0o700)
    (runtime / "pulse").mkdir()
    sockets = {runtime / name for name in ("wayland-0", "pipewire-0", "pulse/native")}
    for path in sockets:
        path.touch()
    actual_stat = Path.stat

    def fake_socket_metadata(path, *arguments, **options):
        metadata = actual_stat(path, *arguments, **options)
        if path in sockets:
            values = list(metadata)
            values[0] = stat.S_IFSOCK | 0o666
            return os.stat_result(values)
        return metadata

    monkeypatch.setattr(Path, "stat", fake_socket_metadata)
    for key, value in {
        "XDG_RUNTIME_DIR": str(runtime),
        "XDG_SESSION_TYPE": "wayland",
        "XDG_CURRENT_DESKTOP": "ubuntu:GNOME",
        "DISPLAY": ":fixed",
        "WAYLAND_DISPLAY": "wayland-0",
        "XDG_CONFIG_HOME": "/unchanged-parent-config",
    }.items():
        monkeypatch.setenv(key, value)
    for key in (
        "PULSE_SERVER",
        "PIPEWIRE_REMOTE",
        "PIPEWIRE_RUNTIME_DIR",
        "PULSE_RUNTIME_PATH",
    ):
        monkeypatch.delenv(key, raising=False)
    return runtime


@pytest.mark.parametrize(
    "native,microphone", [(False, False), (True, False), (False, True)]
)
def test_only_microphone_preserves_host_audio_runtime_and_all_profiles_stay_private(
    tmp_path, audio_environment, native, microphone
):
    folder = tmp_path / "owned-profile"
    result = probe.environment(Path("/package"), folder, native, microphone=microphone)
    assert result["XDG_RUNTIME_DIR"] == str(
        audio_environment if microphone else folder / "runtime"
    )
    for name in ("CONFIG", "DATA", "STATE", "CACHE"):
        assert result[f"XDG_{name}_HOME"] == str(folder / name.lower())
    assert result["TMPDIR"] == str(folder / "tmp")
    assert result["WAYLAND_DISPLAY"] == str(audio_environment / "wayland-0")
    assert probe.os.environ["XDG_RUNTIME_DIR"] == str(audio_environment)
    assert probe.os.environ["XDG_CONFIG_HOME"] == "/unchanged-parent-config"


@pytest.mark.parametrize(
    "override",
    ["PULSE_SERVER", "PIPEWIRE_REMOTE", "PIPEWIRE_RUNTIME_DIR", "PULSE_RUNTIME_PATH"],
)
def test_microphone_rejects_any_unreviewed_audio_endpoint_override(
    tmp_path, audio_environment, monkeypatch, override
):
    monkeypatch.setenv(override, "unreviewed-endpoint")
    with pytest.raises(
        probe.AudioEnvironmentError, match="audio_endpoint_override_not_allowed"
    ):
        probe.environment(Path("/package"), tmp_path / "owned", False, microphone=True)
    assert probe.os.environ[override] == "unreviewed-endpoint"


@pytest.mark.parametrize(
    "invalid", ["permissions", "owner", "missing_socket", "not_socket"]
)
def test_microphone_requires_owned_secure_runtime_with_existing_local_socket(
    audio_environment, monkeypatch, invalid
):
    if invalid == "permissions":
        audio_environment.chmod(0o755)
    elif invalid == "owner":
        actual_uid = probe.os.getuid()
        monkeypatch.setattr(probe.os, "getuid", lambda: actual_uid + 1)
    elif invalid == "missing_socket":
        (audio_environment / "pipewire-0").unlink()
        (audio_environment / "pulse/native").unlink()
    else:
        monkeypatch.setattr(probe.stat, "S_ISSOCK", lambda _mode: False)
    with pytest.raises(probe.AudioEnvironmentError):
        probe.host_audio_runtime(dict(probe.os.environ))


def test_follow_up_plan_refuses_control_rerun_and_still_gates_ui_after_microphone(
    tmp_path,
):
    plan = {"modes": ["pipeline-microphone", "ui-native"]}
    with pytest.raises(RuntimeError, match="mode_not_in_reviewed_plan"):
        probe.run_mode(tmp_path, plan, "default20")
    folder = tmp_path / "pipeline-microphone"
    folder.mkdir()
    (folder / "acceptance.json").write_text(
        json.dumps({"passed": False, "processes": []})
    )
    with pytest.raises(RuntimeError, match="previous_mode_not_passed_and_terminal"):
        probe.run_mode(tmp_path, plan, "ui-native")
    assert not (tmp_path / "ui-native").exists()


def test_prior_controls_reject_arbitrary_passed_json_without_reviewed_manifest(
    tmp_path,
):
    (tmp_path / "manifest.json").write_text('{"passed": true}')
    with pytest.raises(RuntimeError, match="reviewed_r2_manifest_required"):
        probe.controls_reference(tmp_path)


def test_prior_receipt_must_match_pinned_reviewed_hash(tmp_path, monkeypatch):
    (tmp_path / "manifest.json").write_text("{}")
    (tmp_path / "receipt.json").write_text('{"passed": true}')
    monkeypatch.setattr(
        probe, "R2_MANIFEST_SHA", probe.digest(tmp_path / "manifest.json")
    )
    monkeypatch.setattr(
        probe, "R2_REFERENCES", {"receipt.json": "different-reviewed-hash"}
    )
    with pytest.raises(RuntimeError, match="reviewed_r2_receipt_changed"):
        probe.controls_reference(tmp_path)
