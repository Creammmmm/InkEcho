#!/usr/bin/env python3
"""Prepare or run only a local-TLS, fake-key comparison on the owned Noble Xorg VM.

Default --plan is read-only. --preview audits host staging only. This adapter
has no cloud or credential-store branch; desktop execution needs prior review.
"""

import argparse
import asyncio
import json
import os
import platform
import subprocess
import time
from pathlib import Path

import performance_live_comparison as core
from performance_memory_target import CHILD_SHA, RunHandle, digest, process_start

ROOT = Path(__file__).resolve().parents[2]
GUEST_ROOT = Path("/mnt/input/live-comparison-noble-r1")
GUEST_APPDIR = Path("/home/inkecho/inkecho-a13-runtime-r1/squashfs-root")
GUEST_ARTIFACT = Path("/mnt/input/a13-r1/InkEcho-0.1.0a13-x86_64.AppImage")
GUEST_HANDLE = Path("/mnt/output/live-comparison-noble-r1/handle.json")
XDOTOOL = Path("/usr/bin/xdotool")
NATIVE_HASHES = {
    "/usr/bin/xdotool": (
        "a21dba4297e197ef27035071f6a36061cc8604ac360df19792db99ad3fd9a5f5"
    ),
    "/usr/lib/x86_64-linux-gnu/libxdo.so.3": (
        "13b91b899cbbae9030a00405a50c203f66d9adc13796bc22508d3cfbf731a231"
    ),
}
DESKTOP = {
    "DISPLAY": ":0",
    "XAUTHORITY": "/run/user/1000/gdm/Xauthority",
    "DBUS_SESSION_BUS_ADDRESS": "unix:path=/run/user/1000/bus",
    "XDG_SESSION_TYPE": "x11",
    "XDG_SESSION_ID": "20",
    "XDG_CURRENT_DESKTOP": "ubuntu:GNOME",
}
GNOME_PID, GNOME_START = 26971, "95097"
SOURCES = (
    "scripts/validation/performance_noble_comparison.py",
    "scripts/validation/performance_live_comparison.py",
    "scripts/validation/performance_cloud_comparison.py",
    "scripts/validation/performance_memory_target.py",
    "scripts/validation/performance_comparison_fixture.py",
    "scripts/validation/performance_host_a13.py",
    "scripts/feasibility/owned_memory_text_fixture.py",
)
FAILURES = frozenset(
    {
        "noble_preflight_failed",
        "noble_native_mismatch",
        "noble_execution_path_mismatch",
        "noble_plan_required",
        "noble_plan_changed",
        "noble_producer_identity_failed",
        "noble_no_cloud_branch",
    }
)


def fail(code):
    raise ValueError(code)


def command_output(argv):
    """Read-only native queries; their arbitrary output never enters records."""
    clean = {"PATH": "/usr/bin:/bin", **DESKTOP}
    result = subprocess.run(
        argv, env=clean, capture_output=True, text=True, timeout=3, check=False
    )
    if result.returncode:
        fail("noble_preflight_failed")
    return result.stdout.strip()


def verify_controls(xdotool):
    if Path(xdotool) != XDOTOOL or any(
        digest(Path(path)) != checksum for path, checksum in NATIVE_HASHES.items()
    ):
        fail("noble_native_mismatch")
    child = ROOT / SOURCES[-1]
    if digest(child) != CHILD_SHA:
        fail("noble_native_mismatch")
    return {"files": NATIVE_HASHES.copy(), "child_sha256": CHILD_SHA}


def preflight():
    """Require this already observed guest/session, never unlock or alter it."""
    fields = dict(
        line.split("=", 1)
        for line in Path("/etc/os-release").read_text().splitlines()
        if "=" in line
    )
    if (
        fields.get("ID", "").strip('"') != "ubuntu"
        or fields.get("VERSION_ID", "").strip('"') != "24.04"
        or platform.release() != "6.8.0-142-generic"
        or os.getuid() != 1000
        or process_start(GNOME_PID) != GNOME_START
        or Path(f"/proc/{GNOME_PID}/comm").read_text().strip() != "gnome-shell"
        or command_output(["/usr/bin/gnome-shell", "--version"]) != "GNOME Shell 46.0"
    ):
        fail("noble_preflight_failed")
    session = dict(
        line.split("=", 1)
        for line in command_output(
            [
                "/usr/bin/loginctl",
                "show-session",
                "20",
                "-p",
                "User",
                "-p",
                "Type",
                "-p",
                "LockedHint",
            ]
        ).splitlines()
        if "=" in line
    )
    if session != {"User": "1000", "Type": "x11", "LockedHint": "no"}:
        fail("noble_preflight_failed")
    if (
        command_output(
            [
                "/usr/bin/gdbus",
                "call",
                "--session",
                "--dest",
                "org.gnome.ScreenSaver",
                "--object-path",
                "/org/gnome/ScreenSaver",
                "--method",
                "org.gnome.ScreenSaver.GetActive",
            ]
        )
        != "(false,)"
    ):
        fail("noble_preflight_failed")
    return {
        "ubuntu_version": "24.04",
        "kernel": "6.8.0-142-generic",
        "gnome_version": "46.0",
        "gnome_pid": GNOME_PID,
        "gnome_start_ticks": GNOME_START,
        "uid": 1000,
        "session_id": "20",
        "session_type": "x11",
        "locked": False,
        "screensaver_active": False,
    }


def guest_command(*, worker=False, fingerprint=None):
    argv = [
        str(GUEST_APPDIR / "usr/bin/python3") if worker else "/usr/bin/python3",
        str(GUEST_ROOT / SOURCES[0]),
        "--package-root",
        str(GUEST_APPDIR / "packages"),
        "--appimage",
        str(GUEST_ARTIFACT),
    ]
    if fingerprint:
        argv += ["--offline-owned", "--accept-plan-sha", fingerprint]
    else:
        argv += ["--plan"]
    if worker:
        argv += ["--worker"]
    return argv


def make_plan(args):
    package = core.previous.verify_package(args.appimage, args.package_root)
    files = {name: digest(ROOT / name) for name in SOURCES}
    value = {
        "schema_version": 1,
        "kind": "noble_local_TLS_configuration_A_B",
        "source_snapshot": files,
        "package": package,
        "native_expected": NATIVE_HASHES.copy(),
        "desktop_environment": DESKTOP.copy(),
        "guest_paths": {
            "snapshot_root": str(GUEST_ROOT),
            "appdir": str(GUEST_APPDIR),
            "artifact": str(GUEST_ARTIFACT),
            "handle": str(GUEST_HANDLE),
        },
        "generated_recording_seconds": 0.2,
        "fixture_budget": {"per_arm_asr": 1, "per_arm_polishing": 1, "total": 4},
        "cloud_connections": 0,
        "credential_store_reads": 0,
        "user_configuration_reads": 0,
        "public_wave_reads": 0,
        "human_review_required_for_desktop": True,
        "live_cloud_route_ready": False,
    }
    if args.preview:
        value.update(
            kind="host_staging_preview_only",
            guest_preflight="not_run",
            native_verified_on_guest=False,
        )
    else:
        verify_paths(args)
        value.update(guest_preflight=preflight(), native_verified_on_guest=True)
        verify_controls(XDOTOOL)
    return {**value, "plan_sha256": core.previous.fingerprint(value)}


def verify_paths(args):
    if (
        Path(__file__).resolve() != GUEST_ROOT / SOURCES[0]
        or args.appimage.resolve() != GUEST_ARTIFACT
        or args.package_root.resolve() != GUEST_APPDIR / "packages"
    ):
        fail("noble_execution_path_mismatch")


def worker_environment(package_root, profile):
    # All writable user directories stay private. The explicit bus address and
    # Xauthority connect to session 20 without reusing its app IPC directories.
    return {
        **core.previous.worker_environment(package_root, profile),
        **DESKTOP,
        "QT_QPA_PLATFORM": "xcb",
        "QT_IM_MODULE": "compose",
    }


def attach_worker():
    handle = None
    for _attempt in range(100):
        candidate = RunHandle(GUEST_HANDLE)
        producer = candidate.record["producer"]
        if producer and producer["pid"] == os.getpid():
            handle = candidate
            break
        time.sleep(0.01)
    if handle is None or handle.record["producer"]["start_ticks"] != process_start(
        os.getpid()
    ):
        fail("noble_producer_identity_failed")
    return handle


async def run_pair(handle, reviewed, args):
    from performance_comparison_fixture import PCM, Fixture, audio_bytes

    desktop = {
        "handle": handle,
        "xdotool": XDOTOOL,
        "target_options": {
            "verifier": verify_controls,
            "child_path": ROOT / SOURCES[-1],
        },
    }

    def checkpoint(arm, _role, counts):
        handle.record["reserved_calls"] = counts
        handle.phase(f"{arm}_reserved")

    budget = core.Budget(checkpoint)
    rows = []
    for arm in ("A", "B"):
        if make_plan(args)["plan_sha256"] != reviewed["plan_sha256"]:
            fail("noble_plan_changed")
        folder = Path(os.environ["TMPDIR"]) / f"fixture-{arm}"
        folder.mkdir(mode=0o700)
        async with Fixture(folder) as fixture:
            row = core.safe_result(
                await core.run_arm(
                    arm,
                    budget,
                    audio_bytes(),
                    PCM,
                    core.Credentials(lambda: None),
                    local=fixture,
                    desktop=desktop,
                )
            )
            handle.record.setdefault("noble_arm_metadata", []).append(row)
            handle.phase("arm_acceptance")
            core.accept(row)
            if (
                fixture.errors
                or not fixture.polish_input_exact
                or bytes(fixture.audio) != PCM
                or fixture.calls
                != {
                    "http_asr": int(arm == "A"),
                    "wss_asr": int(arm == "B"),
                    "polishing": 1,
                }
            ):
                raise core.ProbeError("local_fixture_failed")
            if handle.timed_out:
                raise core.ProbeError("observation_timeout")
            rows.append(row)
    return {
        "evidence_kind": "package_Noble_Xorg_loopback_TLS_owned_GTK",
        "cloud_validated": False,
        "real_microphone": False,
        "public_wave_uploaded": False,
        "credential_store_reads": 0,
        "generated_recording_seconds": 0.2,
        "node_preflight": reviewed["guest_preflight"],
        "results": rows,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--appimage", type=Path, required=True)
    choice = parser.add_mutually_exclusive_group()
    choice.add_argument("--preview", action="store_true")
    choice.add_argument("--plan", action="store_true")
    choice.add_argument("--offline-owned", action="store_true")
    parser.add_argument("--accept-plan-sha")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    handle = None
    try:
        if args.worker:
            if not args.offline_owned:
                fail("noble_no_cloud_branch")
            handle = attach_worker()
        reviewed = make_plan(args)
        if not args.offline_owned:
            print(
                json.dumps(
                    {
                        **reviewed,
                        "guest_plan_argv": guest_command(),
                        "guest_execution_argv": guest_command(
                            fingerprint="ACTUAL_GUEST_REVIEWED_FINGERPRINT_REQUIRED"
                            if args.preview
                            else reviewed["plan_sha256"]
                        ),
                    },
                    indent=2,
                )
            )
            return 0
        if args.accept_plan_sha != reviewed["plan_sha256"]:
            fail("noble_plan_required")
        if not args.worker:
            profile = core.persistent_profile(GUEST_HANDLE)
            environment = worker_environment(args.package_root, profile)
            return core.previous.launch_owned_worker(
                guest_command(worker=True, fingerprint=reviewed["plan_sha256"]),
                environment,
                GUEST_HANDLE,
            )
        handle.record["noble_preflight"] = reviewed["guest_preflight"]
        handle.save()
        origins = core.audit_runtime(args.package_root)
        core.previous.verify_production_profiles()
        from PySide6.QtWidgets import QApplication

        from inkecho.runtime import ManagedQtEventLoop

        app = QApplication.instance() or QApplication([])
        app.setQuitOnLastWindowClosed(False)
        with ManagedQtEventLoop(app) as loop:
            asyncio.set_event_loop(loop)
            report = loop.run_until_complete(run_pair(handle, reviewed, args))
        report.update(runtime_origins=origins, plan_sha256=reviewed["plan_sha256"])
        print(json.dumps(report, indent=2, allow_nan=False))
        return 0
    except Exception as error:
        code = (
            error.args[0]
            if type(error) is ValueError and len(error.args) == 1
            else None
        )
        code = (
            code if type(code) is str and code in FAILURES else core.error_code(error)
        )
        if args.worker and handle:
            if "live_failure_code" not in handle.record:
                handle.record["live_failure_code"] = code
                handle.record["failed_phase"] = handle.record["phase"]
                handle.save()
        print(json.dumps({"status": "failed", "code": code}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
