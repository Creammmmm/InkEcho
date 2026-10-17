"""Owned desktop input timing only, using the unchanged actual a14 package."""

import argparse
import asyncio
import hashlib
import json
import math
import os
import statistics
import sys
import time
from contextlib import nullcontext
from pathlib import Path

DEPENDENCIES = (
    Path(__file__).resolve().parents[2]
    / "build/a14-acceptance-preparation/frozen-r2/scripts/validation"
)
sys.path.insert(0, str(DEPENDENCIES))
from artifact_scope import audit_package, selected_artifact  # noqa: E402
from native_acceptance import keymap_metadata, until  # noqa: E402
from native_guard import save, worker  # noqa: E402
from natural_owned_browser import NaturalOwnedBrowser, process_start  # noqa: E402
from x11_acceptance import desktop, observe, owned_focus  # noqa: E402

SAMPLE = (
    "这是一段中文输入速度测试，用来测量真实键盘发送字符的用时。"
    "今天我们同时检查中文、English words, numbers 12345, "
    "and punctuation. 中文结束。 Test 1."
)


def metrics(start, presses, first_callback, insert_return, returned, dom_exact):
    if (
        len(presses) < 2
        or not all(
            type(value) in (int, float) and math.isfinite(value)
            for value in [
                start,
                *presses,
                first_callback,
                insert_return,
                returned,
                dom_exact,
            ]
        )
        or not start <= presses[0] < presses[-1] <= insert_return <= returned
        or not presses[-1] <= dom_exact
        or abs(first_callback - presses[0]) > 0.005
    ):
        raise ValueError("invalid_dispatch_timing")
    intervals = [b - a for a, b in zip(presses, presses[1:], strict=False)]
    if any(value <= 0 for value in intervals):
        raise ValueError("invalid_dispatch_order")
    return {
        "start_to_first_press_ms": (presses[0] - start) * 1000,
        "first_to_last_press_ms": (presses[-1] - presses[0]) * 1000,
        "start_to_insert_return_ms": (insert_return - start) * 1000,
        "start_to_output_scope_return_ms": (returned - start) * 1000,
        "start_to_dom_exact_observed_ms": (dom_exact - start) * 1000,
        "first_press_to_dom_exact_observed_ms": (dom_exact - presses[0]) * 1000,
        "dispatch_throughput_chars_per_second": len(presses) / (returned - start),
        "steady_press_events_per_second": (len(presses) - 1)
        / (presses[-1] - presses[0]),
        "press_interval_ms": {
            "min": min(intervals) * 1000,
            "median": statistics.median(intervals) * 1000,
            "max": max(intervals) * 1000,
        },
        "successful_press_count": len(presses),
        "first_callback_delta_ms": (first_callback - presses[0]) * 1000,
    }


def worker_argv(args, directory):
    return [
        sys.executable,
        "-B",
        str(Path(__file__).resolve()),
        "--artifact",
        str(args.artifact),
        "--expected-sha",
        args.expected_sha,
        "--package-root",
        str(args.package_root),
        "--frozen-source-root",
        str(args.frozen_source_root),
        "--output",
        str(args.output),
        "--work-root",
        str(directory),
        "--backend",
        "native",
        "--worker",
        "--guard-state",
        str(directory / "guard.json"),
        "--guard-counts",
        str(directory / "counts.json"),
        "--owner-pid",
        str(os.getpid()),
    ]


async def one_run(args, index, cancel):
    from inkecho.platform.keyboard import KeyboardError, KeyboardInput
    from inkecho.platform.wayland_keyboard import WaylandKeyboardInput
    from inkecho.platform.wayland_worker import MutterSession

    native = args.backend == "native"
    directory = args.work_root / str(index)
    directory.mkdir(mode=0o700)
    guard_path, count_path = directory / "guard.json", directory / "counts.json"
    counts = dict.fromkeys(
        (
            "press release mapping_writes successful_restore_calls guard_rejections"
        ).split(),
        0,
    )
    row = {
        "index": index,
        "cancel_after": 8 if cancel else None,
        "passed": False,
        "backend": args.backend,
        "worker_owners": [],
    }
    fixture = NaturalOwnedBrowser(
        directory / "browser", platform="wayland" if native else "x11"
    )
    observer, inputs, monitor_task, exact_task = None, None, None, None
    presses, first_callback, workers = [], [], []
    backend_confirmed = False
    before = None

    def current_counts():
        return (
            json.loads(count_path.read_text())
            if native and count_path.exists()
            else counts
        )

    def allowed():
        if not fixture.process:
            return False
        fixture.assert_owned()
        state = fixture.snapshot()
        if native:
            valid = bool(
                backend_confirmed
                and state
                and state["document_focused"]
                and state["field_focused"]
                and 0 <= time.monotonic() - state["sampled_at"] <= 0.25
            )
            save(
                guard_path,
                {
                    "allowed": valid,
                    "backend_confirmed": backend_confirmed,
                    "owner_pid": os.getpid(),
                    "pid": fixture.process.pid,
                    "start_ticks": fixture.started,
                    "sampled_at": state["sampled_at"] if state else 0,
                },
            )
            return valid
        return owned_focus(inputs._driver, fixture)

    def active():
        measured = current_counts()
        return allowed() and (
            not cancel or measured.get("press_success", measured.get("press", 0)) < 8
        )

    async def monitor():
        while True:
            allowed()
            await asyncio.sleep(0.02)

    async def spawn(*_command, **options):
        command = worker_argv(args, directory)
        process = await asyncio.create_subprocess_exec(*command, **options)
        owner = {
            "pid": process.pid,
            "start_ticks": process_start(process.pid),
            "argv": command,
            "exit_code": None,
            "owner_observed_terminal": False,
        }
        workers.append((process, owner))
        row["worker_owners"].append(owner)
        save(directory / "live-owners.json", row)
        return process

    try:
        if native:
            observer = MutterSession()
            await observer.connect()
            await observer.authorize()
            before = await keymap_metadata(observer)
            inputs = WaylandKeyboardInput(spawn=spawn)
        else:
            inputs = KeyboardInput()
        await inputs.connect()
        if native:
            await inputs.authorize()
            request = inputs._request

            async def observed_request(operation, **options):
                started = time.monotonic()
                response = await request(operation, **options)
                if operation == "key":
                    stamp = response.get("sent_at")
                    if (
                        type(stamp) not in (int, float)
                        or not math.isfinite(stamp)
                        or not started <= stamp <= time.monotonic()
                    ):
                        raise ValueError("invalid_worker_dispatch_timestamp")
                    presses.append(stamp)
                return response

            inputs._request = observed_request
        else:
            before = inputs._driver._mapping()
        fixture.start(reviewed=True)
        if native:
            await until(
                lambda: all(
                    v is True
                    for k, v in fixture.native_evidence().items()
                    if k != "ozone_platform"
                ),
                "owned_native_backend_not_ready",
            )
            backend_confirmed = True
            row["native_evidence"] = fixture.native_evidence()
        await until(allowed, "owned_target_not_ready")
        if fixture.snapshot()["text"]:
            raise ValueError("owned_target_not_empty")
        monitor_task = asyncio.create_task(monitor())
        expected = SAMPLE[:8] if cancel else SAMPLE
        dom_exact = []

        async def watch_exact():
            await until(
                lambda: fixture.snapshot()["text"] == expected,
                "owned_readback_not_exact",
                seconds=40,
            )
            dom_exact.append(time.monotonic())

        exact_task = asyncio.create_task(watch_exact())
        timing_observation = (
            nullcontext()
            if native
            else observe(
                inputs,
                lambda window: owned_focus(inputs._driver, fixture, window),
                counts,
            )
        )
        with timing_observation:
            if not native:
                dispatch = inputs._send

                def timed_send(window, code, pressed):
                    value = dispatch(window, code, pressed)
                    if pressed:
                        presses.append(time.monotonic())
                    return value

                inputs._send = timed_send
            start = time.monotonic()
            try:
                if native:
                    await inputs.insert(
                        SAMPLE,
                        active,
                        deadline=start + 40,
                        on_first_sent=first_callback.append,
                    )
                    insert_return = time.monotonic()
                else:
                    async with inputs.output_session():
                        await inputs.insert(
                            SAMPLE,
                            active,
                            deadline=start + 40,
                            on_first_sent=first_callback.append,
                        )
                        insert_return = time.monotonic()
            except KeyboardError as error:
                if not cancel or error.code != "input_cancelled":
                    raise
                row["expected_error"] = error.code
                insert_return = time.monotonic()
            returned = time.monotonic()
            await exact_task
            row["timing"] = metrics(
                start, presses, first_callback[0], insert_return, returned, dom_exact[0]
            )
            await asyncio.sleep(0.5)
            measured = current_counts()
            row.update(
                exact_readback=fixture.snapshot()["text"] == expected,
                received_count=len(fixture.snapshot()["text"]),
                counts=measured,
                successful_press_timestamps=presses,
                no_tail_observation_seconds=0.5,
            )
            row["body_passed"] = (
                row["exact_readback"]
                and len(presses) == len(expected)
                and measured.get("press_success", measured.get("press"))
                == measured.get("release_success", measured.get("release"))
                == len(expected)
                and measured["guard_rejections"] == 0
                and (not cancel or row.get("expected_error") == "input_cancelled")
            )
        if not native:
            row["mapping_restored"] = inputs._driver._mapping() == before
    except Exception as error:
        row["safe_error_type"] = type(error).__name__
        row["safe_code"] = "input_benchmark_failed"
    finally:
        cleanup_started = time.monotonic()
        for task in [monitor_task, exact_task]:
            if task and not task.done():
                task.cancel()
        await asyncio.gather(
            *(task for task in [monitor_task, exact_task] if task),
            return_exceptions=True,
        )
        if inputs:
            await inputs.aclose()
        for process, owner in workers:
            owner.update(exit_code=await process.wait(), owner_observed_terminal=True)
        if observer:
            row["before"] = before
            row["after"] = await keymap_metadata(observer)
            row["mapping_restored"] = row["before"] == row["after"]
            await observer.close()
        if fixture.process:
            row["target_exit"] = fixture.close()
        row["fixture_errors"] = fixture.errors
        row["cleanup_ms"] = (time.monotonic() - cleanup_started) * 1000
        row["passed"] = bool(
            row.get("body_passed")
            and row.get("mapping_restored")
            and row.get("target_exit") == 0
            and not fixture.errors
            and all(owner["exit_code"] == 0 for _process, owner in workers)
        )
        save(directory / "result.json", row)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    for key in [
        "artifact",
        "package-root",
        "frozen-source-root",
        "output",
        "work-root",
    ]:
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--backend", choices=["native", "xwayland"], required=True)
    parser.add_argument("--run-reviewed", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--guard-state", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--guard-counts", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--owner-pid", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.worker and not args.run_reviewed:
        parser.error("explicit_review_required")
    audit = audit_package(args.package_root, args.frozen_source_root, "0.1.0a14")
    artifact = selected_artifact(args.artifact, args.expected_sha)
    if args.worker:
        if args.owner_pid != os.getppid() or not all(
            path and path.resolve().is_relative_to(args.work_root.resolve())
            for path in [args.guard_state, args.guard_counts]
        ):
            raise SystemExit(2)
        asyncio.run(worker(args.guard_state, args.guard_counts, args.owner_pid))
        return
    if args.output.exists() or args.work_root.exists():
        parser.error("new_evidence_paths_required")
    report = {
        "passed": False,
        "backend": args.backend,
        "artifact": artifact,
        "runtime": audit,
        "desktop": desktop("ubuntu26-xwayland"),
        "sample_codepoints": len(SAMPLE),
        "sample_sha256": hashlib.sha256(SAMPLE.encode()).hexdigest(),
        "rows": [],
        "cloud_requests": 0,
        "microphone": False,
        "keyring_access": False,
        "clipboard_used": False,
        "input_method_used": False,
        "production_algorithm_modified": False,
        "timing_clock": "time.monotonic",
        "dom_poll_seconds": 0.02,
        "fixture_state_interval_seconds": 0.05,
        "scope": (
            "one insert per task, backend baseline/best-case; "
            "not cloud pipeline or slow-SSE fragments; "
            "test-owned guard/counter overhead included; "
            "dispatch not glyph-visible time; setup excluded"
        ),
    }
    args.work_root.mkdir(mode=0o700)

    async def run():
        for index in range(4):
            row = await one_run(args, index, cancel=index == 3)
            report["rows"].append(row)
            save(args.output, report)
            print(
                json.dumps(
                    {
                        "index": index,
                        "backend": args.backend,
                        "passed": row["passed"],
                        "timing": row.get("timing"),
                    }
                ),
                flush=True,
            )
            if not row["passed"]:
                return
        report["passed"] = True
        report["normal_run_medians"] = {
            key: statistics.median(row["timing"][key] for row in report["rows"][:3])
            for key in [
                "start_to_first_press_ms",
                "first_to_last_press_ms",
                "start_to_output_scope_return_ms",
                "start_to_dom_exact_observed_ms",
                "dispatch_throughput_chars_per_second",
                "steady_press_events_per_second",
            ]
        }

    from PySide6.QtWidgets import QApplication

    from inkecho.runtime import ManagedQtEventLoop

    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    if app.platformName() != "wayland":
        raise ValueError("actual_host_wayland_qt_required")
    report["qt_platform"] = app.platformName()
    report["frontend_event_loop"] = "ManagedQtEventLoop (qasync)"
    try:
        with ManagedQtEventLoop(app) as loop:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run())
    finally:
        save(args.output, report)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            json.dumps(
                {
                    "safe_code": "benchmark_preflight_failed",
                    "safe_error_type": type(error).__name__,
                }
            )
        )
        raise SystemExit(2) from None
