"""Explicit new-package native BMP/cancel/reject/mixed acceptance; no cloud or mic."""

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from artifact_scope import audit_package, selected_artifact
from native_guard import save, worker
from natural_owned_browser import NaturalOwnedBrowser, process_start

SAMPLE = "你好 InkEcho，世界！ café Ω e\u0301\n第二行。"
MODES = ("textarea", "contenteditable", "cancel", "nonbmp", "mixed")


def counts(path):
    return (
        json.loads(path.read_text())
        if path.exists()
        else {"press_success": 0, "release_success": 0, "guard_rejections": 0}
    )


async def keymap_metadata(observer):
    state, data = await observer.snapshot(refresh=True)
    return {
        "map_sha256": hashlib.sha256(data).hexdigest(),
        **{key: state[key] for key in ["group", "depressed", "latched", "locked"]},
    }


async def until(predicate, code, seconds=10):
    end = time.monotonic() + seconds
    while not predicate():
        if time.monotonic() >= end:
            raise ValueError(code)
        await asyncio.sleep(0.02)


def common_argv(args):
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
        "--expected-version",
        args.expected_version,
        "--work-root",
        str(args.work_root),
        "--output",
        str(args.output),
        "--mode",
        args.mode,
    ]


async def run(args, report):
    from performance_host_a13 import preflight

    from inkecho.platform.keyboard import KeyboardError
    from inkecho.platform.wayland_keyboard import WaylandKeyboardInput
    from inkecho.platform.wayland_worker import MutterSession
    from inkecho.streaming_output import StreamingOutput, TextDelta

    observed = preflight()
    if not observed.get("runnable") or observed.get("session_type") != "wayland":
        raise ValueError("unlocked_actual_host_wayland_required")
    report["desktop_preflight"] = observed
    args.work_root.mkdir(mode=0o700, exist_ok=False)
    guard_path, count_path = (
        args.work_root / "guard.json",
        args.work_root / "counts.json",
    )
    fixtures, children = [], []
    focus = None
    transitioning = False
    stop_monitor = False
    confirmed_backends = {}
    cancel_at = 8 if args.mode == "cancel" else None
    observer, inputs = MutterSession(), None

    def publish():
        snapshot = focus.snapshot() if focus else None
        confirmed = bool(focus and confirmed_backends.get(focus.process.pid))
        if focus:
            focus.assert_owned()
        if focus and not confirmed:
            if focus.platform == "wayland":
                evidence = focus.native_evidence()
                confirmed = all(
                    v is True for k, v in evidence.items() if k != "ozone_platform"
                )
            else:
                # The same new, known Chrome process was launched on X11, with
                # explicit DISPLAY and no WAYLAND_DISPLAY. Reuse the reviewed
                # X server PID/class checks, not a command-line assumption.
                from host_mixed_wayland_probe import x11_evidence

                confirmed = x11_evidence(focus)["confirmed"]
            if confirmed:
                confirmed_backends[focus.process.pid] = True
        allowed = bool(
            not transitioning
            and snapshot
            and confirmed
            and snapshot["document_focused"]
            and snapshot["field_focused"]
            and 0 <= time.monotonic() - snapshot["sampled_at"] <= 0.25
        )
        save(
            guard_path,
            {
                "allowed": allowed,
                "backend_confirmed": confirmed,
                "owner_pid": os.getpid(),
                "pid": focus.process.pid if focus else 0,
                "start_ticks": focus.started if focus else None,
                "sampled_at": snapshot["sampled_at"] if snapshot else 0,
            },
        )
        return allowed

    def active():
        return publish() and (
            cancel_at is None or counts(count_path)["press_success"] < cancel_at
        )

    async def monitor():
        while not stop_monitor:
            publish()
            await asyncio.sleep(0.02)

    async def spawn(*_command, **options):
        command = [
            *common_argv(args),
            "--worker",
            "--guard-state",
            str(guard_path),
            "--guard-counts",
            str(count_path),
            "--owner-pid",
            str(os.getpid()),
        ]
        process = await asyncio.create_subprocess_exec(*command, **options)
        record = {
            "pid": process.pid,
            "start_ticks": process_start(process.pid),
            "argv": command,
            "exit_code": None,
            "owner_observed_terminal": False,
        }
        children.append((process, record))
        report["workers"] = [item for _process, item in children]
        save(args.output, report)
        return process

    def open_fixture(platform):
        item = NaturalOwnedBrowser(
            args.work_root / f"browser-{len(fixtures)}",
            field="textarea" if args.mode == "textarea" else "contenteditable",
            platform=platform,
        )
        item.start(reviewed=True)
        fixtures.append(item)
        return item

    task = None
    try:
        await observer.connect()
        await observer.authorize()
        report["before"] = await keymap_metadata(observer)
        inputs = WaylandKeyboardInput(spawn=spawn)
        await inputs.connect()
        await inputs.authorize()
        focus = open_fixture("wayland")
        await until(publish, "owned_native_focus_not_ready")
        if focus.snapshot()["text"]:
            raise ValueError("owned_initial_text_not_empty")
        report["native_evidence"] = focus.native_evidence()
        task = asyncio.create_task(monitor())
        first = []
        try:
            if args.mode == "mixed":

                async def send(text):
                    return await inputs.insert(
                        text,
                        active,
                        deadline=time.monotonic() + 45,
                        on_first_sent=first.append,
                    )

                output = StreamingOutput(send, lambda: True)
                consumer = asyncio.create_task(output.run())
                try:
                    await output.append(TextDelta(0, SAMPLE[:5]))
                    await until(
                        lambda: (
                            focus.snapshot()["text"] == SAMPLE[:5]
                            and output.sent_characters == 5
                        ),
                        "native_prefix_not_exact",
                    )
                    native = focus
                    transitioning = True
                    publish()
                    focus = open_fixture("x11")
                    transitioning = False
                    await until(publish, "owned_xwayland_focus_not_ready")
                    await output.append(TextDelta(5, SAMPLE[5:10]))
                    await until(
                        lambda: (
                            focus.snapshot()["text"] == SAMPLE[5:10]
                            and output.sent_characters == 10
                        ),
                        "xwayland_prefix_not_exact",
                    )
                    transitioning = True
                    publish()
                    focus.close()
                    focus = native
                    transitioning = False
                    await until(publish, "native_focus_not_restored")
                    await output.append(TextDelta(10, SAMPLE[10:]))
                    await output.finish(SAMPLE)
                    await consumer
                    await until(
                        lambda: native.snapshot()["text"] == SAMPLE[:5] + SAMPLE[10:],
                        "native_suffix_not_exact",
                    )
                    report["route_counts"] = [
                        len(native.snapshot()["text"]),
                        len(fixtures[1].snapshot()["text"]),
                    ]
                    report["three_segments_multiple_inserts_one_streaming_task"] = True
                finally:
                    output.close()
                    if not consumer.done():
                        consumer.cancel()
                    await asyncio.gather(consumer, return_exceptions=True)
            else:
                text = "😀" if args.mode == "nonbmp" else SAMPLE
                await inputs.insert(
                    text,
                    active,
                    deadline=time.monotonic() + 45,
                    on_first_sent=first.append,
                )
        except KeyboardError as error:
            if (args.mode == "cancel" and error.code == "input_cancelled") or (
                args.mode == "nonbmp" and error.code == "unsupported_text"
            ):
                report["expected_error"] = error.code
            else:
                raise
        await asyncio.sleep(0.5)
        measured = counts(count_path)
        if args.mode == "mixed":
            exact = report.get("route_counts") == [len(SAMPLE) - 5, 5]
        else:
            expected = (
                ""
                if args.mode == "nonbmp"
                else SAMPLE[:cancel_at]
                if cancel_at
                else SAMPLE
            )
            exact = focus.snapshot()["text"] == expected
            report["received_count"] = len(focus.snapshot()["text"])
        report.update(
            exact_readback=exact,
            counts=measured,
            first_callback_count=len(first),
            no_tail_observation_seconds=0.5,
        )
        expected_count = 0 if args.mode == "nonbmp" else cancel_at or len(SAMPLE)
        report["input_passed"] = bool(
            exact
            and measured["press_success"] == expected_count
            and measured["release_success"] == expected_count
            and not measured["guard_rejections"]
            and (
                args.mode != "nonbmp"
                or report.get("expected_error") == "unsupported_text"
            )
            and (
                args.mode != "cancel"
                or report.get("expected_error") == "input_cancelled"
            )
        )
    finally:
        stop_monitor = True
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if inputs:
            await inputs.aclose()
        for process, record in children:
            record.update(exit_code=await process.wait(), owner_observed_terminal=True)
        if "before" in report:
            report["after"] = await keymap_metadata(observer)
            report["mapping_and_modifiers_restored"] = (
                report["before"] == report["after"]
            )
        await observer.close()
        report["target_exits"] = [fixture.close() for fixture in reversed(fixtures)]
        report["fixture_errors"] = [
            code for fixture in fixtures for code in fixture.errors
        ]
        report["passed"] = bool(
            report.get("input_passed")
            and report.get("mapping_and_modifiers_restored")
            and all(code == 0 for code in report["target_exits"])
            and all(record["exit_code"] == 0 for _process, record in children)
            and not report["fixture_errors"]
        )


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
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--run-host", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--guard-state", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--guard-counts", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--owner-pid", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.worker and not args.run_host:
        parser.error("Explicit reviewed --run-host is required")
    artifact = selected_artifact(args.artifact, args.expected_sha)
    origins = audit_package(
        args.package_root, args.frozen_source_root, args.expected_version
    )
    if args.worker:
        if args.owner_pid != os.getppid() or not all(
            path and path.resolve().is_relative_to(args.work_root.resolve())
            for path in [args.guard_state, args.guard_counts]
        ):
            raise SystemExit(2) from None
        asyncio.run(worker(args.guard_state, args.guard_counts, args.owner_pid))
        return
    if args.output.exists() or args.work_root.exists():
        raise SystemExit(2) from None
    report = {
        "passed": False,
        "artifact": artifact,
        "runtime": origins,
        "mode": args.mode,
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
        report["failure_code"] = "native_acceptance_failed"
    finally:
        save(args.output, report)
        print(json.dumps(report))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(json.dumps({"status": "failed", "code": "acceptance_preflight_failed"}))
        raise SystemExit(2) from None
