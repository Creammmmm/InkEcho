#!/usr/bin/env python3
"""Opt-in native Chrome fixed-sample check using the selected production runtime.

No bootstrap keys, focus activation, clipboard, IME, user profile or cloud call.
The worker has an additional test-only fresh owned-focus guard before presses.
Extracted-runtime acceptance is not AppImage/FUSE parent-death acceptance.
"""

import argparse
import asyncio
import hashlib
import importlib
import json
import os
import secrets
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feasibility"))
from isolated_browser_fixture import parent_pid, write_json  # noqa: E402
from owned_wayland_browser_fixture import OwnedWaylandBrowser  # noqa: E402

SAMPLE = "你好 InkEcho，世界！ café Ω\n第二行。"


def successful_report(report):
    return bool(
        report.get("fixed_sample_exact")
        and report.get("map_and_modifiers_restored")
        and report.get("press_attempts") == len(SAMPLE)
        and report.get("release_attempts") == len(SAMPLE)
        and not report.get("focus_lost")
        and not report.get("cleanup_error")
        and not report.get("failure")
    )


def load_package(root):
    root = root.resolve(strict=True)
    if not (root / "inkecho" / "__init__.py").is_file():
        raise RuntimeError("Selected package root unavailable")
    sys.path.insert(0, str(root))
    evidence = {}
    for name in (
        "inkecho",
        "inkecho.platform.keyboard",
        "inkecho.platform.eis",
        "inkecho.platform.wayland_keymap",
        "inkecho.platform.wayland_worker",
        "inkecho.platform.wayland_keyboard",
    ):
        module = importlib.import_module(name)
        path = Path(module.__file__).resolve(strict=True)
        if not path.is_relative_to(root / "inkecho"):
            raise RuntimeError("Production module source mismatch")
        evidence[name] = {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    return evidence


def guard_allowed(path, pid, parent):
    try:
        state = json.loads(path.read_text())
        return (
            state["browser_pid"] == pid
            and state["browser_parent_pid"] == parent
            and parent_pid(pid) == parent
            and state["allowed"] is True
            and state["native_confirmed"] is True
            and 0 <= time.monotonic() - state["sampled_at"] <= 0.25
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


async def worker(args):
    from inkecho.platform.keyboard import KeyboardError
    from inkecho.platform.wayland_worker import MutterSession, main

    original = MutterSession.key
    counts = {"press_attempts": 0, "release_attempts": 0, "focus_rejections": 0}

    async def guarded_key(self, code, pressed, *, newline=False):
        if pressed and not guard_allowed(
            args.guard_state, args.owner_pid, args.owner_parent_pid
        ):
            counts["focus_rejections"] += 1
            write_json(args.guard_counts, counts)
            raise KeyboardError("input_cancelled")
        counts["press_attempts" if pressed else "release_attempts"] += 1
        write_json(args.guard_counts, counts)
        return await original(self, code, pressed, newline=newline)

    MutterSession.key = guarded_key
    write_json(args.guard_counts, counts)
    await main()


async def metadata(observer):
    state, data = await observer.snapshot(refresh=True)
    return {
        "map_sha256": hashlib.sha256(data).hexdigest(),
        **{key: state[key] for key in ("group", "depressed", "latched", "locked")},
    }


async def run(args, report):
    from inkecho.platform.keyboard import KeyboardError
    from inkecho.platform.wayland_keyboard import WaylandKeyboardInput
    from inkecho.platform.wayland_worker import MutterSession

    observer = MutterSession()  # Independent session; only metadata APIs are used.
    inputs = None
    monitor = None
    delivery = None
    guard_failed = False
    with tempfile.TemporaryDirectory(prefix="inkecho-host-keyboard-check-") as folder:
        root = Path(folder)
        guard_state, guard_counts = root / "guard.json", root / "counts.json"
        with OwnedWaylandBrowser(
            args.field, class_name="inkecho-owned-" + secrets.token_hex(6)
        ) as fixture:
            pid = fixture.process.pid
            if parent_pid(pid) != os.getpid():
                raise RuntimeError("Owned browser parent mismatch")
            report["browser_pid"] = pid
            native = None

            def publish_guard():
                nonlocal native
                snapshot = fixture.snapshot()
                if fixture.process.poll() is not None:
                    snapshot = None
                if native is None and snapshot is not None:
                    evidence = fixture.native_evidence()
                    if all(
                        v is True for k, v in evidence.items() if k != "ozone_platform"
                    ):
                        native = evidence
                allowed = bool(
                    native is not None
                    and snapshot is not None
                    and snapshot["document_focused"]
                    and snapshot["field_focused"]
                    and 0 <= time.monotonic() - snapshot["sampled_at"] <= 0.25
                )
                write_json(
                    guard_state,
                    {
                        "browser_pid": pid,
                        "browser_parent_pid": os.getpid(),
                        "sampled_at": snapshot["sampled_at"] if snapshot else 0,
                        "native_confirmed": native is not None,
                        "allowed": allowed,
                    },
                )
                return allowed

            focus_deadline = time.monotonic() + 10
            while not publish_guard():
                if time.monotonic() >= focus_deadline:
                    report["failure"] = "owned_focus_unavailable"
                    return
                await asyncio.sleep(0.02)
            if fixture.snapshot()["text"] != "":
                raise RuntimeError("Owned field was not empty")
            report["native_evidence"] = native
            report["owned_focus_before_input"] = True
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
                        "--owner-pid",
                        str(pid),
                        "--owner-parent-pid",
                        str(os.getpid()),
                        **options,
                    )

                inputs = WaylandKeyboardInput(spawn=spawn)
                if args.ack_settle:
                    original_request = inputs._request

                    async def settled_request(operation, **fields):
                        response = await original_request(operation, **fields)
                        if operation == "key":
                            await asyncio.sleep(args.ack_settle)
                        return response

                    inputs._request = settled_request
                await inputs.connect()
                await inputs.authorize()
                if not publish_guard():
                    report["failure"] = "owned_focus_lost_before_input"
                    return

                async def watch_focus():
                    nonlocal guard_failed
                    while True:
                        if not publish_guard():
                            guard_failed = True
                            if delivery is not None:
                                delivery.cancel()
                            return
                        await asyncio.sleep(0.02)

                deadline = time.monotonic() + 30
                monitor = asyncio.create_task(watch_focus())
                delivery = asyncio.create_task(
                    inputs.insert(SAMPLE, publish_guard, deadline=deadline)
                )
                report["sent_codepoints"] = await delivery
                await asyncio.sleep(0.3)
                result = fixture.snapshot()
                report["received_codepoints"] = len(result["text"])
                report["fixed_sample_exact"] = result["text"] == SAMPLE
                if not report["fixed_sample_exact"]:
                    report["owned_received_codepoints"] = [
                        ord(character) for character in result["text"]
                    ]
                report["focus_lost"] = guard_failed
            except asyncio.CancelledError:
                report["failure"] = "owned_focus_lost" if guard_failed else "cancelled"
            except KeyboardError as error:
                report["failure"] = error.code
            finally:
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
                report["passed"] = successful_report(report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--run-host", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ack-settle", type=float, default=0)
    parser.add_argument(
        "--field", choices=("textarea", "contenteditable"), default="textarea"
    )
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--guard-state", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--guard-counts", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--owner-pid", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--owner-parent-pid", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not 0 <= args.ack_settle <= 0.5:
        parser.error("--ack-settle must be between 0 and 0.5 seconds")
    if not args.worker and (not args.run_host or args.output is None):
        parser.error("Reviewed --run-host and --output are required")
    sources = load_package(args.package_root)
    if args.worker:
        asyncio.run(worker(args))
        return
    report = {
        "passed": False,
        "python": str(Path(sys.executable).resolve()),
        "package_root": str(args.package_root.resolve()),
        "production_modules": sources,
        "field": args.field,
        "sample_codepoints": len(SAMPLE),
        "test_only_ack_settle_seconds": args.ack_settle,
        "press_attempts": 0,
        "release_attempts": 0,
        "cloud_requests": 0,
        "clipboard_used": False,
        "input_method_used": False,
        "focus_activation_used": False,
        "fuse_parent_death_tested": False,
    }
    try:
        asyncio.run(run(args, report))
    finally:
        write_json(args.output, report)
        print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
