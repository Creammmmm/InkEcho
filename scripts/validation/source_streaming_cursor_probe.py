"""Exercise source StreamingOutput's lone first character and current cursor."""

import argparse
import asyncio
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from keyboard_latency_probe import (
    SAMPLE,
    fixture_environment,
    mapping_count_scope,
    start_time,
    verify_ubuntu24_vm_x11,
)
from source_pipeline_probe import audit_origins


async def run(args):
    import inkecho
    from inkecho.platform.keyboard import KeyboardInput
    from inkecho.streaming_output import StreamingOutput, TextDelta

    metadata = verify_ubuntu24_vm_x11()
    origins = audit_origins(
        args.source_root,
        args.dependency_root,
        json.loads(args.snapshot_manifest.read_text()),
    )
    report = {
        "passed": False,
        "version": inkecho.__version__,
        "runtime_kind": "source",
        "production_behavior_modified": False,
        "runtime_metadata": origins,
        "environment_metadata": metadata,
        "cloud_requests": 0,
        "user_credentials_read": False,
        "microphone_used": False,
    }
    inputs = KeyboardInput()
    clients = []
    events, routes, first = [], [], []
    counts = {"mapping_writes": 0, "restore_calls": 0, "successful_restore_calls": 0}
    switched = False
    switch_failed = False

    def command(*arguments):
        return subprocess.check_output(
            [args.xdotool, *arguments],
            env=fixture_environment(),
            text=True,
            timeout=3,
        ).strip()

    with tempfile.TemporaryDirectory(prefix="inkecho-a11-owned-switch-") as temporary:
        folder = Path(temporary)
        try:
            await inputs.connect()
            driver = inputs._driver
            original_map = driver._mapping()
            for index in range(2):
                output = folder / f"field-{index}.json"
                log = args.output.with_name(
                    f"{args.output.stem}-field-{index}.log"
                ).open("xb")
                process = subprocess.Popen(
                    [
                        "/usr/bin/python3",
                        str(Path(__file__).with_name("keyboard_latency_probe.py")),
                        "--fixture",
                        "gtk",
                        "--output",
                        str(output),
                    ],
                    env=fixture_environment(),
                    stdout=log,
                    stderr=subprocess.STDOUT,
                )
                identity = start_time(process.pid)
                client = {
                    "process": process,
                    "identity": identity,
                    "output": output,
                    "log": log,
                    "window": None,
                }
                clients.append(client)
                for _ in range(120):
                    if process.poll() is not None:
                        raise RuntimeError("owned_fixture_exited")
                    try:
                        windows = command(
                            "search", "--onlyvisible", "--pid", str(process.pid)
                        )
                    except subprocess.CalledProcessError:
                        windows = ""
                    if windows and output.exists():
                        client["window"] = int(windows.splitlines()[0])
                        break
                    await asyncio.sleep(0.05)
                if client["window"] is None:
                    raise RuntimeError("owned_fixture_not_ready")
            command("windowactivate", "--sync", str(clients[0]["window"]))
            await asyncio.sleep(0.35)
            original_send = inputs._send

            def switch():
                nonlocal switched, switch_failed
                try:
                    command("windowactivate", "--sync", str(clients[1]["window"]))
                    switched = True
                except Exception:
                    switch_failed = True

            def guard(window, code, pressed):
                if pressed:
                    active = driver._property(driver.root, driver.active_atom)
                    matched = None
                    for index, client in enumerate(clients):
                        process = client["process"]
                        if active != client["window"]:
                            continue
                        if (
                            process.poll() is not None
                            or start_time(process.pid) != client["identity"]
                            or driver._property(active, driver.pid_atom) != process.pid
                            or driver.focus() != window
                        ):
                            raise RuntimeError("owned_target_identity_changed")
                        matched = index
                    if matched is None:
                        raise RuntimeError("input_outside_owned_targets")
                original_send(window, code, pressed)
                events.append(pressed)
                if pressed:
                    routes.append(matched)
                    if len(routes) == 12:
                        asyncio.get_running_loop().call_soon(switch)

            inputs._send = guard
            text = SAMPLE * 2
            began = time.monotonic()
            first_event = asyncio.Event()

            def first_sent(sent_at):
                first.append(sent_at)
                first_event.set()

            async def send(chunk):
                return await inputs.insert(
                    chunk, lambda: not switch_failed, on_first_sent=first_sent
                )

            stream = StreamingOutput(send, lambda: not switch_failed)

            async def produce():
                await stream.append(TextDelta(0, text[:1]))
                await asyncio.wait_for(first_event.wait(), timeout=2)
                report["lone_first_character_sent_before_remaining_queued"] = True
                for offset, character in enumerate(text[1:], 1):
                    await stream.append(TextDelta(offset, character))
                await stream.finish(text)

            with mapping_count_scope(driver, counts):
                producer = asyncio.create_task(produce())
                consumer = asyncio.create_task(stream.run())
                try:
                    _, sent = await asyncio.gather(producer, consumer)
                finally:
                    for task in [producer, consumer]:
                        if not task.done():
                            task.cancel()
                    await asyncio.gather(producer, consumer, return_exceptions=True)
                    stream.close()
            elapsed = time.monotonic() - began
            await asyncio.sleep(0.2)
            received = [
                json.loads(client["output"].read_text())["text"] for client in clients
            ]
            report.update(
                {
                    "requested_codepoints": len(text),
                    "sent_codepoints": sent,
                    "received_codepoints": [len(value) for value in received],
                    "first_window_prefix_exact": received[0] == text[:12],
                    "second_window_suffix_exact": received[1] == text[12:],
                    "route_matches_focus_switch": routes
                    == [0] * 12 + [1] * (len(text) - 12),
                    "switch_completed": switched,
                    "switch_failed": switch_failed,
                    "balanced_events": events == [True, False] * len(text),
                    "map_restored": driver._mapping() == original_map,
                    "mapping_counts": counts,
                    "first_callback_count": len(first),
                    "first_sent_seconds": first[0] - began if first else None,
                    "elapsed_seconds": elapsed,
                }
            )
            report["passed"] = (
                inkecho.__version__ == "0.1.0a11"
                and sent == len(text)
                and all(
                    report[name]
                    for name in [
                        "first_window_prefix_exact",
                        "second_window_suffix_exact",
                        "route_matches_focus_switch",
                        "switch_completed",
                        "balanced_events",
                        "map_restored",
                    ]
                )
                and not switch_failed
                and len(first) >= 1
                and report.get("lone_first_character_sent_before_remaining_queued")
                is True
            )
        finally:
            try:
                await inputs.aclose()
            finally:
                for client in clients:
                    process = client["process"]
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                    client["log"].close()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--dependency-root", type=Path, required=True)
    parser.add_argument("--snapshot-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--xdotool", required=True)
    args = parser.parse_args()
    args.source_root = args.source_root.resolve(strict=True)
    args.dependency_root = args.dependency_root.resolve(strict=True)
    sys.path.insert(0, str(args.source_root))
    from PySide6.QtWidgets import QApplication

    from inkecho.runtime import ManagedQtEventLoop

    application = QApplication([])
    application.setQuitOnLastWindowClosed(False)
    if application.platformName() != "xcb":
        raise RuntimeError("actual_xorg_qt_platform_required")
    with ManagedQtEventLoop(application) as loop:
        report = loop.run_until_complete(run(args))
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
