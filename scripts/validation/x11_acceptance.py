"""Reviewed, owned-Chrome X11 acceptance; no cloud, microphone or keyring."""

import argparse
import asyncio
import json
import os
import platform
import time
from contextlib import contextmanager
from pathlib import Path

from artifact_scope import audit_package, selected_artifact
from natural_owned_browser import NaturalOwnedBrowser

SAMPLE = "你好 InkEcho，世界！ café Ω e\u0301 😀\n第二行。"
MODES = ("textarea", "contenteditable", "cancel", "currentcursor")
COUNTERS = (
    "press release mapping_writes successful_restore_calls guard_rejections".split()
)


def owned_focus(driver, fixture, window=None):
    """Only a test guard: production focus may legitimately be a child XID."""
    try:
        fixture.assert_owned()
        window = driver.focus() if window is None else window
        state = fixture.snapshot()
        with driver._checked():
            top = driver._property(driver.root, driver.active_atom)
            pid = driver._property(top, driver.pid_atom) if top else 0
        return bool(
            top
            and pid == fixture.process.pid
            and driver.focus() == window
            and fixture.spawn_display == os.environ.get("DISPLAY")
            and fixture.platform == "x11"
            and state
            and state["document_focused"]
            and state["field_focused"]
            and 0 <= time.monotonic() - state["sampled_at"] <= 0.25
        )
    except Exception:
        return False


@contextmanager
def observe(inputs, allowed, counts):
    """Observe successful originals; a release is never subject to our guard."""
    from inkecho.platform.keyboard import KeyboardError

    driver = inputs._driver
    send, write, restore = inputs._send, driver._write, driver.restore

    def dispatch(window, code, pressed):
        if pressed and not allowed(window):
            counts["guard_rejections"] += 1
            raise KeyboardError("input_cancelled")
        send(window, code, pressed)
        counts["press" if pressed else "release"] += 1

    def mapping(values):
        result = write(values)
        counts["mapping_writes"] += 1
        return result

    def cleanup():
        result = restore()
        counts["successful_restore_calls"] += 1
        return result

    inputs._send, driver._write, driver.restore = dispatch, mapping, cleanup
    try:
        yield
    finally:
        inputs._send, driver._write, driver.restore = send, write, restore


async def until(predicate, seconds=10):
    end = time.monotonic() + seconds
    while not predicate():
        if time.monotonic() >= end:
            raise ValueError("owned_observation_timeout")
        await asyncio.sleep(0.02)


def desktop(scope):
    from performance_host_a13 import preflight

    if scope == "ubuntu24-xorg":
        import subprocess

        from keyboard_latency_probe import verify_ubuntu24_vm_x11

        result = verify_ubuntu24_vm_x11()
        clean = dict(os.environ)
        for key in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH", "QT_PLUGIN_PATH"):
            clean.pop(key, None)
        response = subprocess.check_output(
            "gdbus call --session --dest org.gnome.ScreenSaver --object-path "
            "/org/gnome/ScreenSaver --method org.gnome.ScreenSaver.GetActive".split(),
            env=clean,
            text=True,
            timeout=3,
        )
        if response.strip() != "(false,)":
            raise ValueError("unlocked_guest_required")
        return result
    release = platform.freedesktop_os_release()
    result = preflight()
    if (
        release.get("VERSION_ID") != "26.04"
        or release.get("ID") != "ubuntu"
        or os.environ.get("XDG_SESSION_TYPE") != "wayland"
        or not result.get("runnable")
        or not result.get("logind_graphical_session_verified")
    ):
        raise ValueError("unlocked_ubuntu26_wayland_required")
    return result


async def run(args, report):
    from inkecho.platform.keyboard import KeyboardError, KeyboardInput

    report["desktop"] = desktop(args.scope)
    args.work_root.mkdir(mode=0o700, exist_ok=False)
    inputs, fixtures, target = KeyboardInput(), [], None
    counts = dict.fromkeys(COUNTERS, 0)
    report["counts"] = counts
    driver = before = None
    expected = []

    async def open_target(field):
        nonlocal target
        target = NaturalOwnedBrowser(
            args.work_root / str(len(fixtures)), field=field, platform="x11"
        )
        fixtures.append(target)  # Preserve a Popen identity even if start fails.
        target.start(reviewed=True)
        await until(lambda: owned_focus(driver, target))

    def readback():
        return [
            item.snapshot()["text"] if item.snapshot() else None for item in fixtures
        ]

    try:
        await inputs.connect()
        driver = inputs._driver
        before = driver._mapping()
        await open_target(
            "contenteditable" if args.mode == "contenteditable" else "textarea"
        )
        with observe(
            inputs, lambda window: owned_focus(driver, target, window), counts
        ):
            try:
                async with inputs.output_session():
                    if args.mode == "currentcursor":
                        count = await inputs.insert(
                            SAMPLE[:5], can_continue=lambda: True
                        )
                        expected.append(SAMPLE[:5])
                        await until(lambda: readback() == expected)
                        await open_target("contenteditable")
                        count += await inputs.insert(
                            SAMPLE[5:], can_continue=lambda: True
                        )
                        expected.append(SAMPLE[5:])
                        report["acknowledged_split"] = [5, count - 5]
                    else:
                        count = await inputs.insert(
                            SAMPLE,
                            can_continue=lambda: (
                                args.mode != "cancel" or counts["press"] < 8
                            ),
                        )
                        expected.append(SAMPLE)
            except KeyboardError as error:
                if args.mode != "cancel" or error.code != "input_cancelled":
                    raise
                report["expected_error"] = error.code
                count = counts["press"]
                expected.append(SAMPLE[:8])
            await until(lambda: readback() == expected)
            await asyncio.sleep(0.5)
            report.update(
                exact_readback=readback() == expected, confirmed_characters=count
            )
        report["mapping_restored"] = driver._mapping() == before
    finally:
        await inputs.aclose()
        report["driver_closed"] = inputs._driver is None and not inputs.connected
        report["target_exits"] = [item.close() for item in reversed(fixtures)]
        report["fixture_errors"] = [code for item in fixtures for code in item.errors]
    wanted = 8 if args.mode == "cancel" else len(SAMPLE)
    report["passed"] = bool(
        report.get("exact_readback")
        and report.get("mapping_restored")
        and report["driver_closed"]
        and counts["press"] == counts["release"] == wanted
        and report["confirmed_characters"] == wanted
        and counts["guard_rejections"] == 0
        and report["target_exits"]
        and all(code == 0 for code in report["target_exits"])
        and not report["fixture_errors"]
        and (args.mode != "cancel" or report.get("expected_error") == "input_cancelled")
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    for key in "artifact package-root frozen-source-root output work-root".split():
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument(
        "--scope", choices=("ubuntu24-xorg", "ubuntu26-xwayland"), required=True
    )
    parser.add_argument("--run-host", action="store_true")
    args = parser.parse_args()
    if not args.run_host or args.output.exists() or args.work_root.exists():
        parser.error("exclusive_paths_and_explicit_desktop_review_required")
    report = {
        "passed": False,
        "mode": args.mode,
        "scope": args.scope,
        "artifact": selected_artifact(args.artifact, args.expected_sha),
        "runtime": audit_package(
            args.package_root, args.frozen_source_root, args.expected_version
        ),
        "cloud_requests": 0,
        "microphone": False,
        "credential_store_reads": 0,
        "clipboard_used": False,
        "input_method_used": False,
        "production_behavior_modified": False,
    }
    try:
        asyncio.run(run(args, report))
    except Exception:
        report["failure_code"] = "x11_acceptance_failed"
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
