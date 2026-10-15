"""Prepare and serially observe fixed a13 host checks, never kill a live producer.

Preparing and previewing do not open windows or record audio. Only an explicitly
reviewed run may use the desktop; native Wayland UI is not native input evidence.
"""

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import struct
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_SHA = "8dce4eedee71373a27e0e6507592b1240617412a8a6f114230b9a53f4d286a89"
PRODUCT_COMMIT = "eeb2d0ce8f8c5a6690b0ab54e0196da4254eb767"
BASELINE_SHA = "809f2bcfb7ba76ee250b18a9c175f0d625c336f8edd069b9b8e86da88c1b22e4"
MODES = ("default20", "cancel12", "pipeline-microphone", "ui-native")
TARGETS = ("chrome-textarea", "chrome-contenteditable", "gtk", "vte")
R2_MANIFEST_SHA = "06f158ada6b047f14493748cee6f0798531748575d9c37a65c2516623d7da4d6"
R2_REFERENCES = dict(
    zip(
        [
            "default20/acceptance.json",
            "default20/result.json",
            "default20/origins.json",
            "cancel12/acceptance.json",
            "cancel12/result.json",
            "cancel12/origins.json",
            "pipeline-microphone/acceptance.json",
            "pipeline-microphone/observer.log",
        ],
        [
            "507a6968cf1dcb03a5e2316a21fa8021d479940cd26efa5e7ebd52f1adc6ba85",
            "5f874bdb24b89deb21b29073b13ad67ea0c8611be3bd7692725a41de794b73be",
            "a897842168e271f2cbdbd9f6038eca7074edb4361c8bb3e504e80dad295732fe",
            "4c0ccd860b60378a990c4be9ce94d4956680f677576aa4a60ce6dc21a9c07f4f",
            "59b1adc24165f970ea7efb037b88f697987a21063d405a0887687a87bb5112f9",
            "a897842168e271f2cbdbd9f6038eca7074edb4361c8bb3e504e80dad295732fe",
            "94d783497d43a2384d769ab9dfac4394b3fefe90234dde9cbe14d16203020e9b",
            "83aa7e3e0f6aaead3e573ee7445d9c00a0e4fb0d2ecb90b5ec400891483ada2c",
        ],
        strict=True,
    )
)
TOOLS = (
    "keyboard_latency_probe.py",
    "performance_package_probe.py",
    "artifact_output_session_runtime_probe.py",
    "performance_host_a13.py",
)
FROZEN_TOOLS = {
    "keyboard_latency_probe.py": (
        "f0cb80b62727f9c03c26af8c929255bf99c41c349c8afe3769dc38b49d897344"
    ),
    "performance_package_probe.py": (
        "26ba7b1198846f9f1585d473aeee7c5767aebf20634c0d17627a105e4ae2bb0d"
    ),
    "artifact_output_session_runtime_probe.py": (
        "4d4ccd9bdd6a886eb02e1a5647923c66155d9481e11fa7a52fc626fa92cc3441"
    ),
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    with path.open("x") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def contained(root, relative):
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root):
        raise RuntimeError("path_escape")
    return path


def static_audit(appdir, artifact, sources, source_root):
    if digest(artifact) != ARTIFACT_SHA or len(sources) != 43:
        raise RuntimeError("artifact_or_source_identity_mismatch")
    inventory = json.loads(
        (appdir / "usr/share/doc/inkecho/inventory.json").read_text()
    )
    if inventory["application"] != "0.1.0a13":
        raise RuntimeError("unexpected_inventory_version")
    for relative, expected in inventory["files"].items():
        if digest(contained(appdir, relative)) != expected:
            raise RuntimeError("inventory_file_mismatch")
    for relative, target in inventory["symlinks"].items():
        path = appdir / relative
        if str(path.readlink()) != target or not path.resolve().is_relative_to(appdir):
            raise RuntimeError("inventory_symlink_mismatch")
    actual = {
        str(path.relative_to(appdir / "packages"))
        for path in (appdir / "packages/inkecho").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }
    if actual != set(sources):
        raise RuntimeError("application_source_set_mismatch")
    for relative, expected in sources.items():
        if (
            digest(contained(appdir / "packages", relative)) != expected
            or digest(contained(source_root, relative)) != expected
        ):
            raise RuntimeError("application_source_hash_mismatch")
    license_source = source_root.parent / "assets/licenses/websockets-LICENSE.txt"
    for relative in (
        "packages/websockets-15.0.1.dist-info/LICENSE",
        "usr/share/doc/inkecho/licenses/websockets-LICENSE.txt",
    ):
        if digest(contained(appdir, relative)) != digest(license_source):
            raise RuntimeError("websocket_license_mismatch")
    if inventory["python_distributions"].get("websockets") != "15.0.1":
        raise RuntimeError("websocket_version_mismatch")
    return {
        "inventory_files_verified": len(inventory["files"]),
        "inventory_links_verified": len(inventory["symlinks"]),
        "source_files_verified": 43,
        "websocket_license_copies_verified": 2,
    }


def controls_reference(source):
    """Only the already reviewed r2 receipts permit the two-mode follow-up."""
    if digest(source / "manifest.json") != R2_MANIFEST_SHA:
        raise RuntimeError("reviewed_r2_manifest_required")
    for relative, expected in R2_REFERENCES.items():
        if digest(contained(source, relative)) != expected:
            raise RuntimeError("reviewed_r2_receipt_changed")
    for mode in ("default20", "cancel12", "pipeline-microphone"):
        record = read_result(source / mode / "acceptance.json")
        if (
            record.get("artifact_sha256") != ARTIFACT_SHA
            or record.get("source_commit") != PRODUCT_COMMIT
            or any(
                item["running"] or item["exit_code"] is None
                for item in record["processes"]
            )
        ):
            raise RuntimeError("prior_observation_not_same_terminal_product")
        if mode != "pipeline-microphone" and record.get("passed") is not True:
            raise RuntimeError("prior_controls_not_passed")
    return {
        "root": str(source),
        "manifest_sha256": R2_MANIFEST_SHA,
        "files": dict(R2_REFERENCES),
        "controls": ["default20", "cancel12"],
        "failed_microphone_observation_retained": True,
    }


def prepare(output, appdir, controls_from=None):
    if output.parent != ROOT / "build" or not output.name.startswith("a13-host-"):
        raise RuntimeError("exclusive_a13_host_build_directory_required")
    baseline_path = ROOT / "build/performance-a13-source-before-build.json"
    if digest(baseline_path) != BASELINE_SHA:
        raise RuntimeError("build_baseline_changed")
    baseline = json.loads(baseline_path.read_text())
    if baseline["source_commit"] != PRODUCT_COMMIT:
        raise RuntimeError("unexpected_product_commit")
    sources = baseline["source_files"]
    artifact = ROOT / "dist/InkEcho-0.1.0a13-x86_64.AppImage"
    audit = static_audit(appdir, artifact, sources, ROOT / "src")
    prior = controls_reference(controls_from) if controls_from is not None else None
    for name, expected in FROZEN_TOOLS.items():
        if digest(ROOT / "scripts/validation" / name) != expected:
            raise RuntimeError("frozen_tool_changed")
    output.mkdir(mode=0o700, exist_ok=False)
    native = output / "native"
    (native / "bin").mkdir(parents=True)
    (native / "lib").mkdir()
    vendor = ROOT / "build/listening-test-tools/root/usr"
    for source, target in (
        (vendor / "bin/xdotool", native / "bin/xdotool"),
        (vendor / "lib/x86_64-linux-gnu/libxdo.so.3", native / "lib/libxdo.so.3"),
    ):
        shutil.copy2(source, target)
    xdotool = native / "xdotool"
    xdotool.write_text(
        "#!/bin/sh\nexport LD_LIBRARY_PATH="
        + shlex.quote(str(native / "lib"))
        + "\nexec "
        + shlex.quote(str(native / "bin/xdotool"))
        + ' "$@"\n'
    )
    xdotool.chmod(0o700)
    snapshot = output / "snapshot"
    files = ["src/" + relative for relative in sources]
    files += ["scripts/validation/" + name for name in TOOLS]
    files.append("assets/licenses/websockets-LICENSE.txt")
    for relative in files:
        destination = snapshot / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    manifest = {
        "version": "0.1.0a13",
        "source_commit": PRODUCT_COMMIT,
        "artifact": str(artifact),
        "artifact_sha256": ARTIFACT_SHA,
        "appdir": str(appdir),
        "xdotool": str(xdotool),
        "xdotool_sha256": digest(xdotool),
        "native_files": {
            str(path.relative_to(output)): digest(path)
            for path in (xdotool, native / "bin/xdotool", native / "lib/libxdo.so.3")
        },
        "inventory_sha256": digest(appdir / "usr/share/doc/inkecho/inventory.json"),
        "source_files": sources,
        "snapshot_files": {relative: digest(snapshot / relative) for relative in files},
        "static_audit": audit,
        "controls_from": prior,
        "modes": ["pipeline-microphone", "ui-native"] if prior else list(MODES),
    }
    write_json(output / "manifest.json", manifest)
    return {"output": str(output), "manifest_sha256": digest(output / "manifest.json")}


def load_manifest(output, expected):
    if digest(output / "manifest.json") != expected:
        raise RuntimeError("reviewed_manifest_required")
    manifest = json.loads((output / "manifest.json").read_text())
    prior = manifest.get("controls_from")
    if prior is not None:
        if controls_reference(Path(prior["root"])) != prior:
            raise RuntimeError("prior_control_reference_changed")
        if manifest["modes"] != ["pipeline-microphone", "ui-native"]:
            raise RuntimeError("unexpected_follow_up_modes")
    elif manifest["modes"] != list(MODES):
        raise RuntimeError("unexpected_initial_modes")
    if (
        manifest["artifact_sha256"] != ARTIFACT_SHA
        or manifest["source_commit"] != PRODUCT_COMMIT
    ):
        raise RuntimeError("wrong_artifact_manifest")
    for relative, checksum in manifest["snapshot_files"].items():
        if digest(contained(output / "snapshot", relative)) != checksum:
            raise RuntimeError("snapshot_changed")
    if digest(Path(manifest["xdotool"])) != manifest["xdotool_sha256"]:
        raise RuntimeError("xdotool_changed")
    for relative, checksum in manifest["native_files"].items():
        if digest(contained(output, relative)) != checksum:
            raise RuntimeError("native_fixture_tool_changed")
    if (
        digest(Path(manifest["appdir"]) / "usr/share/doc/inkecho/inventory.json")
        != (manifest["inventory_sha256"])
    ):
        raise RuntimeError("reviewed_inventory_changed")
    static_audit(
        Path(manifest["appdir"]),
        Path(manifest["artifact"]),
        manifest["source_files"],
        output / "snapshot/src",
    )
    return manifest


class AudioEnvironmentError(RuntimeError):
    """Fixed preflight codes; no audio connection or environment contents."""


def host_audio_runtime(env):
    if any(
        env.get(name)
        for name in (
            "PULSE_SERVER",
            "PIPEWIRE_REMOTE",
            "PIPEWIRE_RUNTIME_DIR",
            "PULSE_RUNTIME_PATH",
        )
    ):
        raise AudioEnvironmentError("audio_endpoint_override_not_allowed")
    runtime = Path(env.get("XDG_RUNTIME_DIR", "/nonexistent"))
    metadata = runtime.stat()
    if (
        not runtime.is_absolute()
        or not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        raise AudioEnvironmentError("owned_host_audio_runtime_required")
    sockets = 0
    for relative in ("pipewire-0", "pulse/native"):
        try:
            metadata = (runtime / relative).stat()
        except FileNotFoundError:
            continue
        if not stat.S_ISSOCK(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise AudioEnvironmentError("owned_local_audio_socket_required")
        sockets += 1
    if not sockets:
        raise AudioEnvironmentError("host_audio_socket_unavailable")
    return runtime


def environment(appdir, folder, native, *, microphone=False):
    env = dict(os.environ)
    if (
        env.get("XDG_SESSION_TYPE") != "wayland"
        or "GNOME" not in env.get("XDG_CURRENT_DESKTOP", "").upper().split(":")
        or not env.get("DISPLAY")
        or not env.get("WAYLAND_DISPLAY")
    ):
        raise RuntimeError("actual_host_wayland_with_xwayland_required")
    display = Path(env.get("WAYLAND_DISPLAY", ""))
    if not display.is_absolute():
        display = Path(env.get("XDG_RUNTIME_DIR", "/nonexistent")) / display
    if not stat.S_ISSOCK(display.stat().st_mode):
        raise RuntimeError("actual_wayland_socket_required")
    audio_runtime = host_audio_runtime(env) if microphone else None
    for key in ("PYTHONPATH", "PYTHONHOME", "LD_LIBRARY_PATH", "QT_PLUGIN_PATH"):
        env.pop(key, None)
    env.update(
        APPDIR=str(appdir),
        PYTHONHOME=str(appdir / "usr"),
        PYTHONPATH=str(appdir / "packages"),
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        QT_PLUGIN_PATH=str(appdir / "packages/PySide6/Qt/plugins"),
        LD_LIBRARY_PATH=str(appdir / "usr/lib/inkecho"),
        QT_QPA_PLATFORM="wayland" if native else "xcb",
        WAYLAND_DISPLAY=str(display),
        QT_IM_MODULE="compose",
        GTK_IM_MODULE="gtk-im-context-simple",
        TMPDIR=str(folder / "tmp"),
    )
    for name in ("CONFIG", "DATA", "STATE", "CACHE"):
        env[f"XDG_{name}_HOME"] = str(folder / name.lower())
    env["XDG_RUNTIME_DIR"] = str(audio_runtime or folder / "runtime")
    return env


def preflight():
    """Read-only lock/session checks; never change idle policy or unlock."""
    clean = dict(os.environ)
    for key in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH", "QT_PLUGIN_PATH"):
        clean.pop(key, None)
    try:
        response = subprocess.run(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                "org.gnome.ScreenSaver",
                "--object-path",
                "/org/gnome/ScreenSaver",
                "--method",
                "org.gnome.ScreenSaver.GetActive",
            ],
            env=clean,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"runnable": False, "code": "screen_lock_state_unavailable"}
    active = {"(true,)": True, "(false,)": False}.get(response.stdout.strip())
    if response.returncode != 0 or active is not False:
        return {
            "runnable": False,
            "code": "host_locked_or_lock_state_unknown",
            "screensaver_active": active,
        }
    # XDG_SESSION_ID is legitimately absent in the desktop app's environment.
    session = clean.get("XDG_SESSION_ID", "")
    if not session:
        try:
            display = subprocess.run(
                ["loginctl", "show-user", str(os.getuid()), "-p", "Display", "--value"],
                env=clean,
                capture_output=True,
                text=True,
                timeout=2,
            )
            session = display.stdout.strip() if display.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            session = ""
    result = {
        "runnable": True,
        "screensaver_active": False,
        "session_type": "wayland",
        "logind_graphical_session_verified": False,
    }
    if session:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session):
            return {"runnable": False, "code": "invalid_graphical_session_id"}
        try:
            response = subprocess.run(
                [
                    "loginctl",
                    "show-session",
                    session,
                    "-p",
                    "User",
                    "-p",
                    "Type",
                    "-p",
                    "LockedHint",
                ],
                env=clean,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.TimeoutExpired):
            return {"runnable": False, "code": "graphical_session_unavailable"}
        fields = dict(
            line.split("=", 1) for line in response.stdout.splitlines() if "=" in line
        )
        if (
            response.returncode != 0
            or fields.get("User") != str(os.getuid())
            or fields.get("Type") != "wayland"
            or fields.get("LockedHint") != "no"
        ):
            return {"runnable": False, "code": "graphical_session_not_ready"}
        result["logind_graphical_session_verified"] = True
    return result


def command(manifest, output, mode):
    appdir = Path(manifest["appdir"])
    tools = output / "snapshot/scripts/validation"
    folder = output / mode
    python = str(appdir / "usr/bin/python3")
    if mode == "ui-native":
        return [
            python,
            str(tools / "performance_host_a13.py"),
            "ui-helper",
            "--appdir",
            str(appdir),
            "--output",
            str(folder),
        ]
    entry = [
        python,
        str(tools / "artifact_output_session_runtime_probe.py"),
        "--package-root",
        str(appdir / "packages"),
        "--origins-output",
        str(folder / "origins.json"),
    ]
    if mode == "pipeline-microphone":
        return [
            *entry,
            "--tool",
            "performance_package_probe",
            "--",
            "--owned-xwayland-live-mic",
            "--xdotool",
            manifest["xdotool"],
            "--output",
            str(folder / "result.json"),
        ]
    targets = ["gtk"] if mode == "cancel12" else list(TARGETS)
    result = [
        *entry,
        "--tool",
        "keyboard_latency_probe",
        "--",
        "--environment",
        "host-xwayland",
        "--qt-loop",
        "--repeat",
        "5",
        "--xdotool",
        manifest["xdotool"],
        "--targets",
        *targets,
        "--output",
        str(folder / "result.json"),
    ]
    if mode == "cancel12":
        result.extend(["--cancel-after", "12"])
    return result


def process_start(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return None if fields[0] == "Z" else fields[19]
    except FileNotFoundError:
        return None


def observe(argv, env, log, seconds):
    with log.open("x") as stream:
        process = subprocess.Popen(
            argv,
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    record = {
        "pid": process.pid,
        "start_ticks": process_start(process.pid),
        "argv": argv,
        "log": str(log),
    }
    write_json(log.with_suffix(".identity.json"), record)
    try:
        process.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        pass  # Observation expiry never interrupts a key/map cleanup.
    status = process.poll()
    record.update(exit_code=status, running=status is None)
    return record


def read_result(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}  # A live process may not have finished writing its receipt.


def live_records(records):
    return [
        record
        for record in records
        if record["running"]
        and (
            record["start_ticks"] is None
            or process_start(record["pid"]) == record["start_ticks"]
        )
    ]


def origins_valid(report, manifest):
    appdir = Path(manifest["appdir"])
    if (
        report.get("runtime_kind") != "package"
        or report.get("version") != "0.1.0a13"
        or report.get("application_modules_verified") != 10
        or len(report.get("origins", {})) != 11
    ):
        return False
    inventory = json.loads(
        (appdir / "usr/share/doc/inkecho/inventory.json").read_text()
    )
    for name, origin in report["origins"].items():
        path = Path(origin["path"])
        if not path.is_relative_to(appdir / "packages"):
            return False
        checksum = origin["sha256"]
        if checksum != inventory["files"].get(str(path.relative_to(appdir))):
            return False
        if name != "websockets" and checksum != manifest["source_files"].get(
            str(path.relative_to(appdir / "packages"))
        ):
            return False
    return True


def run_mode(output, manifest, mode):
    plan = manifest.get("modes", list(MODES))
    if mode not in plan:
        raise RuntimeError("mode_not_in_reviewed_plan")
    for previous in plan[: plan.index(mode)]:
        record = json.loads((output / previous / "acceptance.json").read_text())
        if not record["passed"] or live_records(record["processes"]):
            raise RuntimeError("previous_mode_not_passed_and_terminal")
    folder = output / mode
    folder.mkdir(mode=0o700, exist_ok=False)
    try:
        env = environment(
            Path(manifest["appdir"]),
            folder,
            mode == "ui-native",
            microphone=mode == "pipeline-microphone",
        )
        readiness = preflight()
    except AudioEnvironmentError as error:
        readiness = {"runnable": False, "code": str(error)}
    except (RuntimeError, OSError):
        readiness = {"runnable": False, "code": "host_display_unavailable"}
    if not readiness["runnable"]:
        result = {
            "passed": False,
            "phase": "preflight",
            "preflight": readiness,
            "processes": [],
            "input_support_assessed": False,
        }
        write_json(folder / "acceptance.json", result)
        return result
    for name in ("tmp", "config", "data", "state", "cache", "runtime"):
        (folder / name).mkdir(mode=0o700)
    process = observe(
        command(manifest, output, mode), env, folder / "observer.log", 120
    )
    result_path = folder / "result.json"
    result = read_result(result_path)
    processes = [process, *result.get("processes", [])]
    audit_path = folder / "origins.json"
    audit = read_result(audit_path)
    flags = origins_valid(audit, manifest)
    if mode in ("default20", "cancel12"):
        rows = result.get("targets", [])
        expected = ["gtk"] if mode == "cancel12" else list(TARGETS)
        flags = (
            flags
            and result.get("restore_policy") == "production"
            and result.get("production_behavior_modified") is False
            and result.get("expected_source_root") is None
            and result.get("pacing_override_used") is False
            and [row.get("target") for row in rows] == expected
            and all(
                row.get("mapping_counts")
                == {
                    "mapping_writes": 13 if mode == "cancel12" else 136,
                    "restore_calls": 1,
                    "successful_restore_calls": 1,
                }
                for row in rows
            )
        )
    elif mode == "pipeline-microphone":
        flags = (
            flags
            and result.get("version") == "0.1.0a13"
            and result.get("runtime_kind") == "package"
            and result.get("runtime_modules_verified") == 10
            and result.get("pacing_override_seconds") is None
            and result.get("real_microphone") is True
            and result.get("real_desktop_input") is True
            and result.get("cloud_requests") == 0
            and result.get("user_credentials_read") is False
            and result.get("fixture_sse_profile") == "normal"
            and result.get("fixture_sse_delta_delay_seconds") == 0.35
            and result.get("fixture_final_codepoints") == 25
            and result.get("fixture_final_printable_codepoints") == 24
            and result.get("server_errors") == []
            and result.get("fixture_threads_closed") is True
        )
    else:
        flags = flags and result.get("native_wayland_ui") is True
    acceptance = {
        "mode": mode,
        "preflight": readiness,
        "runtime_scope": "host-audio" if mode == "pipeline-microphone" else "private",
        "runtime_directory": env["XDG_RUNTIME_DIR"],
        "controls_from": manifest.get("controls_from"),
        "artifact_sha256": ARTIFACT_SHA,
        "source_commit": PRODUCT_COMMIT,
        "runtime_kind": "package",
        "processes": processes,
        "profiles_and_logs_retained": True,
        "cloud_requests": 0,
        "user_credentials_read": False,
        "microphone_requested": mode == "pipeline-microphone",
        "native_wayland_input_validated": False,
        "passed": process["exit_code"] == 0
        and result.get("passed") is True
        and flags
        and not live_records(processes),
    }
    write_json(folder / "acceptance.json", acceptance)
    return acceptance


def empty_disposable_model(profile):
    settings = json.loads((profile / "config.json").read_text())
    provider = json.loads((profile / "providers/qwen.json").read_text())
    return settings["transcription_provider"] == "qwen" and provider["model"] == ""


def ui_helper(folder, appdir):
    from artifact_output_session_runtime_probe import audit_origins

    write_json(folder / "origins.json", audit_origins(appdir / "packages"))
    profile = folder / "config/inkecho"
    data = folder / "data/inkecho"
    if profile.exists() or data.exists():
        raise RuntimeError("fresh_disposable_ui_profile_required")
    pages = folder / "pages"
    pages.mkdir(exist_ok=False)
    base = [
        str(appdir / "AppRun"),
        "--config-dir",
        str(profile),
        "--data-dir",
        str(data),
    ]
    processes = []
    result = {
        "passed": False,
        "native_wayland_ui": False,
        "processes": processes,
        "ui_toggle_records_audio": False,
        "user_credentials_read": False,
        "cloud_requests": 0,
        "profiles_and_logs_retained": True,
    }
    log = (folder / "primary.log").open("x")
    primary = subprocess.Popen(
        [*base, "--screenshot-dir", str(pages)],
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    primary_record = {
        "pid": primary.pid,
        "start_ticks": process_start(primary.pid),
        "argv": [*base, "--screenshot-dir", str(pages)],
        "log": str(folder / "primary.log"),
        "running": True,
    }
    processes.append(primary_record)
    write_json(folder / "primary.identity.json", primary_record)
    phase = "screenshots"
    try:
        deadline = time.monotonic() + 60
        while not (pages / "page-09.png").exists():
            if primary.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError("ui_screenshot_observation_failed")
            time.sleep(0.1)
        dimensions = []
        for index in range(1, 10):
            content = (pages / f"page-{index:02}.png").read_bytes()
            if content[:8] != b"\x89PNG\r\n\x1a\n":
                raise RuntimeError("invalid_owned_screenshot")
            width, height = struct.unpack(">II", content[16:24])
            if width < 600 or height < 400:
                raise RuntimeError("unexpected_owned_screenshot_dimensions")
            dimensions.append({"width": width, "height": height})
        for action in ("show", "toggle", "cancel", "quit"):
            phase = "ipc_" + action
            if action == "toggle":
                # The actual default rejects before authorization or key lookup.
                if not empty_disposable_model(profile):
                    raise RuntimeError("empty_disposable_transcription_model_required")
                result["empty_model_verified_before_toggle"] = True
            record = observe(
                [*base, "--" + action],
                dict(os.environ),
                folder / f"ipc-{action}.log",
                30,
            )
            processes.append(record)
            if record["running"] or record["exit_code"] != 0:
                raise RuntimeError("ipc_observation_failed")
            if action != "quit" and primary.poll() is not None:
                raise RuntimeError("primary_exited_during_ipc")
        phase = "primary_cleanup"
        try:
            primary.wait(timeout=30)
        except subprocess.TimeoutExpired:
            raise RuntimeError("primary_cleanup_still_running") from None
        if primary.returncode != 0:
            raise RuntimeError("primary_exit_not_zero")
        phase = "damaged_profile"
        damaged = b'{"schema_version":'
        config = profile / "config.json"
        config.write_bytes(damaged)
        broken = observe(
            [*base, "--quit-after", "0.1"],
            dict(os.environ),
            folder / "damaged-profile.log",
            30,
        )
        processes.append(broken)
        if (
            broken["running"]
            or broken["exit_code"] != 1
            or config.read_bytes() != damaged
        ):
            raise RuntimeError("damaged_profile_check_failed")
        log.flush()
        actual_platform = any(
            line.strip() == '{"screenshots": 9, "platform": "wayland", "visible": true}'
            for line in (folder / "primary.log").read_text().splitlines()
        )
        result.update(
            passed=actual_platform,
            native_wayland_ui=actual_platform,
            pages=dimensions,
            ipc_show_toggle_cancel_quit=True,
            damaged_config_exit_1_preserved=True,
        )
    except Exception:
        result["failure_code"] = "ui_check_failed"
        result["failure_phase"] = phase
        raise  # Preserve the traceback in the owned observer log as well.
    finally:
        status = primary.poll()
        primary_record.update(exit_code=status, running=status is None)
        log.close()
        # Keep the entire profile and all PIDs; never terminate/kill a live app.
        write_json(folder / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "preview", "run", "ui-helper"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--appdir", type=Path)
    parser.add_argument("--controls-from", type=Path)
    parser.add_argument("--manifest-sha256")
    parser.add_argument("--mode", choices=MODES)
    args = parser.parse_args()
    output = args.output.resolve()
    if args.action == "ui-helper":
        if args.appdir is None:
            parser.error("ui-helper requires appdir")
        result = ui_helper(output, args.appdir.resolve(strict=True))
    elif args.action == "prepare":
        if args.appdir is None:
            parser.error("prepare requires appdir")
        result = prepare(
            output,
            args.appdir.resolve(strict=True),
            args.controls_from.resolve(strict=True) if args.controls_from else None,
        )
    else:
        if not args.manifest_sha256 or args.mode is None:
            parser.error("preview/run requires reviewed manifest hash and mode")
        manifest = load_manifest(output, args.manifest_sha256)
        if args.mode not in manifest["modes"]:
            parser.error("mode is absent from this reviewed plan")
        if args.action == "preview":
            result = {
                "argv": command(manifest, output, args.mode),
                "artifact_sha256": ARTIFACT_SHA,
                "source_commit": PRODUCT_COMMIT,
                "qt_platform": "wayland" if args.mode == "ui-native" else "xcb",
                "runtime_kind": "package",
                "starts_process": False,
                "microphone_requested": args.mode == "pipeline-microphone",
                "runtime_scope": "host-audio"
                if args.mode == "pipeline-microphone"
                else "private",
                "controls_from": manifest.get("controls_from"),
            }
        else:
            result = run_mode(output, manifest, args.mode)
    print(json.dumps(result, indent=2))
    if result.get("passed") is False:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
