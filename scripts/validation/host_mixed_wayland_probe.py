#!/usr/bin/env python3
"""Reviewed opt-in host test: one transaction across owned native/XWayland Chrome.

Only a fixed BMP sample is sent. Natural new-window/close focus transitions are
paused at acknowledged character boundaries. No focus activation or bootstrap
keys are used. Unknown focus during a transition keeps presses disabled until
owned focus returns or the test times out. This is a validation harness, not a
product focus policy. Run only after coordinating exclusive desktop use.
"""

import argparse
import asyncio
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path

from native_wayland_keyboard_probe import SAMPLE, load_package, metadata

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feasibility"))
from isolated_browser_fixture import parent_pid, write_json  # noqa: E402
from owned_wayland_browser_fixture import OwnedWaylandBrowser  # noqa: E402


def process_start(pid):
    # comm may include spaces or parentheses; starttime is field 22.
    return (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[19]


def known_option_present(command_bytes, option):
    """Accept original argv or Chrome's single, space-separated process title."""
    tokens = command_bytes.split(b"\0")
    if option in tokens:
        return True
    if len([token for token in tokens if token]) != 1:
        return False
    # Chrome setproctitle flattens argv and clears its original env storage.
    # Match the entire known option, never a prefix or embedded substring.
    return (
        re.search(rb"(?<!\S)" + re.escape(option) + rb"(?!\S)", tokens[0]) is not None
    )


def x11_evidence(fixture):
    """Read window PID first; read class only for our owned browser's window."""
    pid = fixture.process.pid
    environment_bytes = (Path("/proc") / str(pid) / "environ").read_bytes()
    command_bytes = (Path("/proc") / str(pid) / "cmdline").read_bytes()
    environment = environment_bytes.split(b"\0")
    command = command_bytes.split(b"\0")
    display = os.fsencode("DISPLAY=" + os.environ["DISPLAY"])
    profile = os.fsencode(f"--user-data-dir={fixture.root / 'profile'}")
    result = {
        "ozone_platform": "x11",
        "display_set_in_owned_process": display in environment,
        "private_profile_in_owned_process": profile in command,
        "ozone_flag_in_owned_process": b"--ozone-platform=x11" in command,
        "x_window_pid_matches": False,
        "fresh_class_matches": False,
        "confirmed": False,
        "spawn_display_matches_x_server": bool(
            fixture.spawn_display and fixture.spawn_display == os.environ.get("DISPLAY")
        ),
        "private_profile_option_matches": known_option_present(command_bytes, profile),
        "ozone_option_matches": known_option_present(
            command_bytes, b"--ozone-platform=x11"
        ),
        # Only counts and known fixed-option comparisons, never host values.
        "proc_command_nul_count": command_bytes.count(b"\0"),
        "proc_environment_nul_count": environment_bytes.count(b"\0"),
        "known_ozone_bytes_present": b"--ozone-platform=x11" in command_bytes,
        "known_profile_bytes_present": profile in command_bytes,
        "known_display_bytes_present": display in environment_bytes,
        "proc_has_display_key": any(
            item.startswith(b"DISPLAY=") for item in environment
        ),
        "launch_ozone_option_matches": "--ozone-platform=x11" in fixture.process.args,
        "launch_private_profile_matches": os.fsdecode(profile) in fixture.process.args,
    }
    clients = subprocess.run(
        ["xprop", "-root", "_NET_CLIENT_LIST"],
        check=True,
        capture_output=True,
        text=True,
        timeout=2,
    ).stdout
    for window in re.findall(r"0x[0-9a-fA-F]+", clients):
        identity = subprocess.run(
            ["xprop", "-id", window, "_NET_WM_PID"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout
        match = re.search(r"_NET_WM_PID\(CARDINAL\) = (\d+)", identity)
        if not match or int(match[1]) != pid:
            continue
        properties = subprocess.run(
            ["xprop", "-id", window, "WM_CLASS"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout
        result.update(
            owned_x_window=window,
            x_window_pid_matches=True,
            fresh_class_matches=fixture.class_name in properties,
        )
        # The owned X window proves a connection to the same server used by
        # xprop. Chrome may clear the original environ memory with setproctitle;
        # its recorded spawn DISPLAY and window identity replace that stale view.
        result["confirmed"] = all(
            result[key] is True
            for key in (
                "spawn_display_matches_x_server",
                "private_profile_option_matches",
                "ozone_option_matches",
                "x_window_pid_matches",
                "fresh_class_matches",
            )
        )
        return result
    return result


def worker_guard(path, owner_parent):
    try:
        state = json.loads(path.read_text())
        pid = state["browser_pid"]
        return bool(
            state["allowed"] is True
            and state["backend_confirmed"] is True
            and state["browser_parent_pid"] == owner_parent
            and parent_pid(pid) == owner_parent
            and process_start(pid) == state["browser_start"]
            and state["phase"] in (0, 1, 2)
            and 0 <= time.monotonic() - state["sampled_at"] <= 0.25
        )
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return False


def owned_snapshots(fixtures):
    return [
        {
            "backend": fixture.platform,
            "process_running": fixture.process.poll() is None,
            "document_focused": bool(snapshot and snapshot["document_focused"]),
            "field_focused": bool(snapshot and snapshot["field_focused"]),
            "sample_age_ms": round((time.monotonic() - snapshot["sampled_at"]) * 1000)
            if snapshot
            else None,
            "received_codepoints": [ord(char) for char in snapshot["text"]]
            if snapshot
            else [],
        }
        for fixture in fixtures
        for snapshot in [fixture.snapshot()]
    ]


async def worker(args):
    from inkecho.platform.keyboard import KeyboardError
    from inkecho.platform.wayland_worker import MutterSession, main

    original = MutterSession.key
    original_set_map = MutterSession.set_map
    counts = {"press_attempts": 0, "release_attempts": 0, "focus_rejections": 0}

    async def guarded_key(self, code, pressed, *, newline=False):
        if pressed and not worker_guard(args.guard_state, args.owner_parent_pid):
            counts["focus_rejections"] += 1
            write_json(args.guard_counts, counts)
            raise KeyboardError("input_cancelled")
        counts["press_attempts" if pressed else "release_attempts"] += 1
        write_json(args.guard_counts, counts)
        result = await original(self, code, pressed, newline=newline)
        if not pressed and args.key_settle:
            await asyncio.sleep(args.key_settle)
        return result

    async def settled_map(self, data, group):
        result = await original_set_map(self, data, group)
        if args.map_settle:
            await asyncio.sleep(args.map_settle)
        return result

    MutterSession.key = guarded_key
    MutterSession.set_map = settled_map
    write_json(args.guard_counts, counts)
    await main()


async def run(args, report):
    from inkecho.platform.keyboard import KeyboardError
    from inkecho.platform.wayland_keyboard import WaylandKeyboardInput
    from inkecho.platform.wayland_worker import MutterSession

    observer = MutterSession()
    inputs = monitor = delivery = None
    phase = 0
    acknowledged = 0
    transitioning = True
    fixtures = []
    evidence = []
    starts = []
    focus_failed = False
    with (
        tempfile.TemporaryDirectory(prefix="inkecho-host-mixed-") as folder,
        ExitStack() as stack,
    ):
        root = Path(folder)
        xstack = stack.enter_context(ExitStack())
        guard_state, guard_counts = root / "guard.json", root / "counts.json"

        def add_fixture(platform):
            fixture_stack = xstack if platform == "x11" else stack
            fixture = fixture_stack.enter_context(
                OwnedWaylandBrowser(
                    args.field,
                    class_name="inkecho-mixed-" + secrets.token_hex(8),
                    platform=platform,
                )
            )
            if parent_pid(fixture.process.pid) != os.getpid():
                raise RuntimeError("Owned browser parent mismatch")
            fixtures.append(fixture)
            evidence.append(None)
            starts.append(process_start(fixture.process.pid))
            return fixture

        def publish_guard():
            index = 1 if phase == 1 else 0
            fixture = fixtures[index]
            snapshot = fixture.snapshot()
            owned = fixture.process.poll() is None
            if owned:
                owned = (
                    parent_pid(fixture.process.pid) == os.getpid()
                    and process_start(fixture.process.pid) == starts[index]
                )
            fresh = bool(
                snapshot
                and owned
                and 0 <= time.monotonic() - snapshot["sampled_at"] <= 0.25
            )
            focused = bool(
                fresh and snapshot["document_focused"] and snapshot["field_focused"]
            )
            allowed = bool(focused and evidence[index] and not transitioning)
            write_json(
                guard_state,
                {
                    "browser_pid": fixture.process.pid,
                    "browser_parent_pid": os.getpid(),
                    "browser_start": starts[index],
                    "phase": phase,
                    "backend_confirmed": bool(evidence[index]),
                    "sampled_at": snapshot["sampled_at"] if snapshot else 0,
                    "allowed": allowed,
                },
            )
            return focused and bool(evidence[index])

        async def wait_focus(index):
            deadline = time.monotonic() + 10
            stable_since = None
            while time.monotonic() < deadline:
                fixture = fixtures[index]
                if fixture.process.poll() is not None:
                    raise RuntimeError("Owned browser exited before focus")
                if evidence[index] is None:
                    if index == 0:
                        observed = fixture.native_evidence()
                        if all(
                            v is True
                            for k, v in observed.items()
                            if k != "ozone_platform"
                        ):
                            evidence[index] = observed
                    else:
                        observed = x11_evidence(fixture)
                        report["x_backend_diagnostics"] = observed
                        if observed["confirmed"]:
                            evidence[index] = observed
                # Test readiness only: do not start/resume body during a page
                # loading/autofocus blip. Presses remain disabled throughout.
                if publish_guard():
                    now = time.monotonic()
                    if stable_since is None:
                        stable_since = now
                    elif now - stable_since >= 0.25:
                        return
                else:
                    stable_since = None
                await asyncio.sleep(0.02)
            report["focus_wait_timeout_phase"] = phase
            report["owned_focus_at_timeout"] = owned_snapshots(fixtures)
            raise KeyboardError("input_cancelled")

        async def watch_focus():
            nonlocal focus_failed
            while True:
                try:
                    focused = publish_guard()
                except (OSError, RuntimeError):
                    focused = False
                if not focused and not transitioning:
                    focus_failed = True
                    if delivery is not None:
                        delivery.cancel()
                    return
                await asyncio.sleep(0.02)

        try:
            await observer.connect()
            await observer.authorize()
            report["before"] = await metadata(observer)

            async def spawn(*_command, **options):
                return await asyncio.create_subprocess_exec(
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--worker",
                    "--package-root",
                    str(args.package_root.resolve()),
                    "--guard-state",
                    str(guard_state),
                    "--guard-counts",
                    str(guard_counts),
                    "--key-settle",
                    str(args.key_settle),
                    "--map-settle",
                    str(args.map_settle),
                    "--owner-parent-pid",
                    str(os.getpid()),
                    **options,
                )

            inputs = WaylandKeyboardInput(spawn=spawn)
            await inputs.connect()
            await inputs.authorize()
            # Initialize transport before opening the test window so any session
            # setup focus change occurs before the owned focus is established.
            native = add_fixture("wayland")
            await wait_focus(0)
            if native.snapshot()["text"]:
                raise RuntimeError("Owned native field was not empty")
            original_request = inputs._request

            async def boundary_request(operation, **fields):
                nonlocal phase, transitioning, acknowledged
                response = await original_request(operation, **fields)
                if operation != "key":
                    return response
                acknowledged += 1
                # Let only the owned page report delivery; never inspect other apps.
                if acknowledged in (5, 10):
                    transitioning = True
                    publish_guard()
                    index = 0 if acknowledged == 5 else 1
                    expected = SAMPLE[:5] if index == 0 else SAMPLE[5:10]
                    end = time.monotonic() + 2
                    while fixtures[index].snapshot()["text"] != expected:
                        if time.monotonic() >= end:
                            raise KeyboardError("injection_failed")
                        await asyncio.sleep(0.02)
                    if acknowledged == 5:
                        xwayland = add_fixture("x11")
                        phase = 1
                        await wait_focus(1)
                        if xwayland.snapshot()["text"]:
                            raise RuntimeError("Owned X field was not empty")
                        report["native_to_x_switch"] = True
                    else:
                        report["x_received_exact"] = (
                            fixtures[1].snapshot()["text"] == SAMPLE[5:10]
                        )
                        # Closing only our direct child is the second natural switch.
                        xstack.close()
                        phase = 2
                        await wait_focus(0)
                        report["x_to_native_switch"] = True
                    transitioning = False
                    if not publish_guard():
                        raise KeyboardError("input_cancelled")
                return response

            inputs._request = boundary_request
            transitioning = False
            if not publish_guard():
                raise KeyboardError("input_cancelled")
            monitor = asyncio.create_task(watch_focus())
            delivery = asyncio.create_task(
                inputs.insert(
                    SAMPLE,
                    publish_guard,
                    deadline=time.monotonic() + 45,
                )
            )
            report["sent_codepoints"] = await delivery
            await asyncio.sleep(0.3)
            report["native_received_exact"] = (
                native.snapshot()["text"] == SAMPLE[:5] + SAMPLE[10:]
            )
        except asyncio.CancelledError:
            report["failure"] = "owned_focus_lost" if focus_failed else "cancelled"
        except KeyboardError as error:
            report["failure"] = error.code
        except (OSError, RuntimeError, subprocess.SubprocessError):
            report["failure"] = "owned_fixture_unavailable"
        finally:
            report["last_acknowledged_codepoints"] = acknowledged
            report["last_phase"] = phase
            report["owned_snapshots"] = owned_snapshots(fixtures)
            if monitor:
                monitor.cancel()
                await asyncio.gather(monitor, return_exceptions=True)
            if inputs:
                try:
                    await inputs.aclose()
                except KeyboardError as error:
                    report["cleanup_error"] = error.code
            if "before" in report:
                try:
                    report["after"] = await metadata(observer)
                    report["map_and_modifiers_restored"] = (
                        report["before"] == report["after"]
                    )
                except KeyboardError as error:
                    report["metadata_error"] = error.code
            await observer.close()
            if guard_counts.exists():
                report.update(json.loads(guard_counts.read_text()))
            report["backend_evidence"] = evidence
            report["focus_lost_during_emission"] = focus_failed
            report["passed"] = bool(
                all(
                    report.get(key) is True
                    for key in (
                        "native_received_exact",
                        "x_received_exact",
                        "native_to_x_switch",
                        "x_to_native_switch",
                        "map_and_modifiers_restored",
                    )
                )
                and report.get("sent_codepoints") == len(SAMPLE) == 26
                and report.get("press_attempts") == report.get("release_attempts") == 26
                and report.get("focus_rejections") == 0
                and not focus_failed
                and not any(
                    report.get(key)
                    for key in (
                        "failure",
                        "cleanup_error",
                        "metadata_error",
                    )
                )
            )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-host", action="store_true")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--field", choices=("textarea", "contenteditable"), default="textarea"
    )
    parser.add_argument("--map-settle", type=float, default=0)
    parser.add_argument("--key-settle", type=float, default=0)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--guard-state", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--guard-counts", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--owner-parent-pid", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 0 <= args.map_settle <= 0.1:
        parser.error("--map-settle must be between 0 and 0.1 seconds")
    if not 0 <= args.key_settle <= 0.1:
        parser.error("--key-settle must be between 0 and 0.1 seconds")
    if not args.worker and (not args.run_host or args.output is None):
        parser.error("Reviewed --run-host and --output are required")
    sources = load_package(args.package_root)
    if args.worker:
        if not args.guard_state or not args.guard_counts or not args.owner_parent_pid:
            parser.error("Internal worker guard arguments required")
        asyncio.run(worker(args))
        return
    report = {
        "passed": False,
        "package_root": str(args.package_root.resolve()),
        "production_modules": sources,
        "sample_codepoints": len(SAMPLE),
        "field": args.field,
        "single_insert_transaction": True,
        "test_only_map_settle_seconds": args.map_settle,
        "test_only_key_settle_seconds": args.key_settle,
        "diagnostic_only": args.map_settle != 0 or args.key_settle != 0,
        "cloud_requests": 0,
        "clipboard_used": False,
        "input_method_used": False,
        "focus_activation_used": False,
        "bootstrap_keys_used": False,
        "desktop_settings_changed": False,
        "fuse_parent_death_tested": False,
        "transition_policy": "presses_disabled_until_fresh_owned_focus_or_timeout",
        "owned_focus_ready_stability_seconds": 0.25,
    }
    try:
        asyncio.run(run(args, report))
    finally:
        report["default_acceptance_passed"] = (
            report["passed"] and args.map_settle == 0 and args.key_settle == 0
        )
        write_json(args.output, report)
        print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
