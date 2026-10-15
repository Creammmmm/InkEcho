"""Plan guards and source/protocol synthetic comparison; never live credentials."""

import asyncio
import importlib.util
import json
import socket
import sys
import wave
from pathlib import Path

import pytest

PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts/validation/performance_cloud_comparison.py"
)
SPEC = importlib.util.spec_from_file_location("performance_cloud_comparison", PATH)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


@pytest.fixture
def planned_files(tmp_path, monkeypatch):
    """Tiny local files test plan logic, not authenticity of a real artifact."""
    package = tmp_path / "appdir/packages"
    package.mkdir(parents=True)
    content = package / "fixed.py"
    content.write_text("# synthetic inventory fixture\n")
    (package / "link").symlink_to("fixed.py")
    inventory = package.parent / "usr/share/doc/inkecho/inventory.json"
    inventory.parent.mkdir(parents=True)
    inventory.write_text(
        json.dumps(
            {
                "application": "0.1.0a13",
                "files": {"packages/fixed.py": probe.digest(content)},
                "symlinks": {"packages/link": "fixed.py"},
            }
        )
    )
    artifact = tmp_path / "fixture.AppImage"
    artifact.write_bytes(b"not a real artifact")
    wav = tmp_path / "fixture.wav"
    with wave.open(str(wav), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(bytes(564644))
    monkeypatch.setattr(probe, "WAV", wav)
    monkeypatch.setattr(probe, "WAV_SHA", probe.digest(wav))
    monkeypatch.setattr(probe, "INVENTORY_SHA", probe.digest(inventory))
    monkeypatch.setattr(probe, "ARTIFACT_SHA", probe.digest(artifact))
    # Product code pins artifact byte size; fake only the Path.stat for this file.
    original_stat = Path.stat

    def stat(path, *args, **kwargs):
        if path == artifact:
            from types import SimpleNamespace

            return SimpleNamespace(st_size=108907000)
        return original_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat)
    return artifact, package


def test_plan_has_no_credentials_network_runtime_or_config(planned_files, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("plan must remain stdlib/read-only")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(probe.importlib, "import_module", forbidden)
    monkeypatch.setattr(probe.subprocess, "run", forbidden)
    artifact, package = planned_files
    before = {
        path: path.read_bytes() for path in package.parent.rglob("*") if path.is_file()
    }
    plan = probe.make_plan(artifact, package)
    assert plan["budget"] == {"asr_calls": 2, "polishing_calls": 2, "total_calls": 4}
    assert plan["configuration_A"]["polishing_streaming"] is False
    assert plan["configuration_B"]["polishing_streaming"] is True
    assert plan["polishing"]["max_tokens_per_call"] == 128
    assert plan["live_ready"] is False
    assert plan["plan_sha256"] == probe.fingerprint(
        {k: v for k, v in plan.items() if k != "plan_sha256"}
    )
    assert before == {
        path: path.read_bytes() for path in package.parent.rglob("*") if path.is_file()
    }


@pytest.mark.parametrize(
    "damage", ["wave", "artifact", "inventory", "source", "symlink"]
)
def test_plan_rejects_changed_fixed_inputs(planned_files, damage):
    artifact, package = planned_files
    if damage == "wave":
        probe.WAV.write_bytes(b"wrong")
    elif damage == "artifact":
        artifact.write_bytes(b"wrong")
    elif damage == "inventory":
        (package.parent / "usr/share/doc/inkecho/inventory.json").write_text("{}")
    elif damage == "source":
        (package / "fixed.py").write_text("# altered\n")
    else:
        (package / "link").unlink()
        (package / "link").symlink_to("/tmp")
    with pytest.raises(ValueError):
        probe.make_plan(artifact, package)


def test_unreviewed_plan_never_spawns_worker(planned_files, monkeypatch, capsys):
    artifact, package = planned_files

    def forbidden(*_args, **_kwargs):
        raise AssertionError("must preflight first")

    monkeypatch.setattr(probe.subprocess, "run", forbidden)
    assert (
        probe.main(
            [
                "--appimage",
                str(artifact),
                "--package-root",
                str(package),
                "--offline",
                "--accept-plan-sha",
                "wrong",
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["status"] == "failed"


def test_live_flag_is_absent_and_rejected_before_reading_any_file(monkeypatch):
    monkeypatch.setattr(probe, "make_plan", lambda *_args: pytest.fail("no preflight"))
    with pytest.raises(SystemExit) as result:
        probe.main(["--package-root", "/unread", "--live"])
    assert result.value.code == 2


def test_runtime_requires_selected_shipped_python(tmp_path):
    with pytest.raises(ValueError, match="shipped_python_required"):
        probe.audit_runtime(tmp_path / "packages")


def test_comparison_fixture_has_no_sensitive_persistence_calls():
    text = PATH.with_name("performance_comparison_fixture.py").read_text()
    assert "SecretStore" not in text and "keyring" not in text
    assert "write_text" not in text and "write_bytes" not in text


@pytest.mark.parametrize("scenario", probe.SCENARIOS)
def test_source_session_real_tls_two_arms_and_current_cursor(scenario, monkeypatch):
    monkeypatch.syspath_prepend(str(PATH.parent))
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance() or QApplication([])
    application.setQuitOnLastWindowClosed(False)
    report = asyncio.run(probe.run_offline([scenario]))
    assert report["evidence_kind"] == "source_protocol_synthetic_display"
    assert not report["cloud_validated"] and not report["desktop_validated"]
    # Source imports here; the CLI worker separately audits actual package imports.
    assert len(report["results"]) == 2
    serialized = json.dumps(report, ensure_ascii=False)
    assert "固定转写" not in serialized and "中Ω" not in serialized
    assert "local-fixture-not-a-cloud-key" not in serialized
    for result in report["results"]:
        probe.validate_result(result)
        if scenario in {"normal", "focus"}:
            assert (
                result["performance"]["durations_ms"]["stop_to_first_character_ms"] > 0
            )
            assert result["characters_sent"] == 6
        if scenario == "normal":
            events = result["performance"]["events_ms"]
            assert (events["first_character_sent"] < events["polishing_completed"]) == (
                result["configuration"] == "B"
            )
        if scenario == "late":
            assert result["characters_sent"] == 0
            assert result["late_response_attempted"]


def test_acceptance_does_not_silently_pass_false_metadata():
    with pytest.raises(ValueError, match="comparison_acceptance_failed"):
        probe.validate_result(
            {
                name: False
                for name in (
                    "audio_matches",
                    "exact_expected",
                    "no_tail_or_replay",
                    "recording_without_focus_reads",
                    "matched_releases",
                    "first_timestamp_from_press",
                    "driver_closed_and_mapping_released",
                )
            }
        )


def test_plan_entry_imports_no_application_runtime_in_clean_process():
    import subprocess

    program = (
        "import runpy,sys; "
        f"runpy.run_path({str(PATH)!r},run_name='not_main'); "
        "names=('inkecho','PySide6','httpx','websockets','keyring'); "
        "assert not any(n.startswith(names) "
        "for n in sys.modules)"
    )
    result = subprocess.run([sys.executable, "-I", "-c", program], capture_output=True)
    assert result.returncode == 0


def accepted_metadata(scenario="normal", arm="A"):
    required = (
        "audio_matches",
        "exact_expected",
        "no_tail_or_replay",
        "recording_without_focus_reads",
        "matched_releases",
        "first_timestamp_from_press",
        "driver_closed_and_mapping_released",
    )
    return {
        **dict.fromkeys(required, True),
        "scenario": scenario,
        "configuration": arm,
        "calls": {
            "http_asr": int(arm == "A"),
            "wss_asr": int(arm == "B"),
            "polishing": int(scenario != "late"),
        },
        "performance": {
            "outcome": "cancelled" if scenario == "late" else "succeeded",
            "events_ms": {
                "first_character_sent": 2 if arm == "A" else 0,
                "polishing_completed": 1,
            },
        },
        "polish_input_exact": True,
        "late_response_attempted": True,
    }


@pytest.mark.parametrize("arm", ["A", "B"])
def test_cli_acceptance_itself_enforces_normal_output_order(arm):
    result = accepted_metadata(arm=arm)
    probe.validate_result(result)
    result["performance"]["events_ms"]["first_character_sent"] = 0 if arm == "A" else 2
    with pytest.raises(ValueError, match="comparison_output_order_failed"):
        probe.validate_result(result)


def test_cli_acceptance_requires_actual_late_response_attempt():
    result = accepted_metadata("late")
    probe.validate_result(result)
    result["late_response_attempted"] = False
    with pytest.raises(ValueError, match="comparison_late_response_not_exercised"):
        probe.validate_result(result)


def test_package_label_without_audited_origins_is_rejected():
    with pytest.raises(ValueError, match="audited_package_origins_required"):
        asyncio.run(probe.run_offline([], runtime_kind="package"))


def test_worker_environment_matches_apprun_and_isolates_user_locations(tmp_path):
    package = tmp_path / "AppDir/packages"
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    environment = probe.worker_environment(package, isolated)
    assert environment["LD_LIBRARY_PATH"] == str(package.parent / "usr/lib/inkecho")
    assert environment["PYTHONHOME"] == str(package.parent / "usr")
    assert environment["QT_PLUGIN_PATH"] == str(package / "PySide6/Qt/plugins")
    assert environment["PYTHONDONTWRITEBYTECODE"] == "1"
    assert (
        "DBUS_SESSION_BUS_ADDRESS" not in environment and "DISPLAY" not in environment
    )
    for name in (
        "HOME",
        "TMPDIR",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "XDG_RUNTIME_DIR",
    ):
        path = Path(environment[name])
        assert path.is_relative_to(isolated) and path.is_dir()
        assert path.stat().st_mode & 0o777 == 0o700


def test_production_profiles_checked_with_no_socket(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("profile check must not connect")

    monkeypatch.setattr(socket, "socket", forbidden)
    assert probe.verify_production_profiles()
