"""Controlled acknowledged-boundary hybrid routing, not transition throughput."""

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/validation"))
from artifact_scope import audit_package, selected_artifact  # noqa: E402
from host_mixed_wayland_probe import x11_evidence  # noqa: E402
from native_acceptance import keymap_metadata, until  # noqa: E402
from native_guard import save, worker  # noqa: E402
from natural_owned_browser import NaturalOwnedBrowser, process_start  # noqa: E402
from x11_acceptance import desktop, observe, owned_focus  # noqa: E402


def mismatch_metrics(received, expected):
    """Numeric-only readback diagnostics for the fixed public sample."""
    prefix = 0
    while (
        prefix < min(len(received), len(expected))
        and received[prefix] == expected[prefix]
    ):
        prefix += 1
    suffix = 0
    while (
        suffix < min(len(received), len(expected))
        and received[-1 - suffix] == expected[-1 - suffix]
    ):
        suffix += 1
    return {
        "common_prefix_length": prefix,
        "common_suffix_length": suffix,
        "length_mismatch": len(received) != len(expected),
        "length_delta": len(received) - len(expected),
    }


def audit_selected_package(args):
    """Only final package origins, full inventory, and its frozen source."""
    artifact = selected_artifact(args.artifact, args.expected_sha)
    audit = audit_package(
        args.package_root, args.frozen_source_root, args.expected_version
    )
    if (
        "inkecho.platform.hybrid_keyboard" not in audit["origins"]
        or len(audit["origins"]) != 19
        or audit["inventory"]["application_files_match_source"] != 44
    ):
        raise ValueError("final_hybrid_package_scope_required")
    return artifact, audit


SAMPLE = "中文éΩ\nAB，路由k混合测试 C，字符完成。"
SETUP_ERROR_CODES = frozenset(
    {
        "owned_browser_start_failed",
        "owned_browser_identity_changed",
        "owned_native_protocol_not_ready",
        "owned_x11_protocol_not_ready",
        "owned_target_not_ready",
        "owned_initial_text_not_empty",
        "old_field_prefix_not_exact",
        "controlled_prefix_not10",
    }
)


def fixed_setup_error(error):
    return (
        str(error)
        if isinstance(error, ValueError) and str(error) in SETUP_ERROR_CODES
        else None
    )


def exception_locations(error):
    result = []
    trace = error.__traceback__
    while trace is not None and len(result) < 8:
        result.append(
            {
                "file": Path(trace.tb_frame.f_code.co_filename).name,
                "line": trace.tb_lineno,
            }
        )
        trace = trace.tb_next
    return result


def setup_metadata(inputs, fixture, row):
    from inkecho.platform.keyboard import KeyboardError

    fixture.assert_owned()
    state = fixture.snapshot()
    record = {
        "phase": row["phase"],
        "at": time.monotonic(),
        "pid": fixture.process.pid,
        "start_ticks": fixture.started,
        "owner_identity_valid": True,
        "snapshot_present": state is not None,
        "document_focused": bool(state and state["document_focused"]),
        "field_focused": bool(state and state["field_focused"]),
        "snapshot_age_seconds": time.monotonic() - state["sampled_at"]
        if state
        else None,
    }
    try:
        driver = inputs.x11._driver
        with driver._checked():
            top = driver._property(driver.root, driver.active_atom)
            pid = driver._property(top, driver.pid_atom) if top else 0
        record.update(
            active_xid=top,
            active_pid=pid,
            active_pid_is_target=pid == fixture.process.pid,
        )
    except Exception as error:
        record["x11_metadata_error_type"] = type(error).__name__
        record["x11_metadata_error_code"] = (
            error.code if isinstance(error, KeyboardError) else None
        )
    row["setup_metadata"].append(record)


def diagnosed_owned_focus(driver, fixture, row, window=None):
    """Preserve owned_focus's query order; record only a failed test guard."""
    from inkecho.platform.keyboard import KeyboardError

    gates = dict.fromkeys(
        (
            "owner_valid active_window_nonzero active_pid_matches_owned "
            "focus_matches_window spawn_display_matches platform_x11 "
            "state_present document_focused field_focused fresh"
        ).split(),
        None,
    )
    top = pid = focused = None
    state = None
    age = None

    def rejected(error=None):
        row["guard_failures"].append(
            {
                "at": time.monotonic(),
                "phase": row["phase"],
                "gates": gates,
                "active_xid": top,
                "active_pid": pid,
                "focus_xid": focused,
                "dispatch_xid": window,
                "owned_pid": fixture.process.pid if fixture.process else None,
                "snapshot_age_seconds": age,
                "error_type": type(error).__name__ if error else None,
                "error_code": error.code if isinstance(error, KeyboardError) else None,
            }
        )
        return False

    try:
        fixture.assert_owned()
        gates["owner_valid"] = True
        window = driver.focus() if window is None else window
        state = fixture.snapshot()
        with driver._checked():
            top = driver._property(driver.root, driver.active_atom)
            pid = driver._property(top, driver.pid_atom) if top else 0
        gates["active_window_nonzero"] = bool(top)
        if not gates["active_window_nonzero"]:
            return rejected()
        gates["active_pid_matches_owned"] = pid == fixture.process.pid
        if not gates["active_pid_matches_owned"]:
            return rejected()
        focused = driver.focus()
        gates["focus_matches_window"] = focused == window
        if not gates["focus_matches_window"]:
            return rejected()
        gates["spawn_display_matches"] = fixture.spawn_display == os.environ.get(
            "DISPLAY"
        )
        if not gates["spawn_display_matches"]:
            return rejected()
        gates["platform_x11"] = fixture.platform == "x11"
        if not gates["platform_x11"]:
            return rejected()
        gates["state_present"] = bool(state)
        if not gates["state_present"]:
            return rejected()
        gates["document_focused"] = bool(state["document_focused"])
        if not gates["document_focused"]:
            return rejected()
        gates["field_focused"] = bool(state["field_focused"])
        if not gates["field_focused"]:
            return rejected()
        age = time.monotonic() - state["sampled_at"]
        gates["fresh"] = 0 <= age <= 0.25
        return True if gates["fresh"] else rejected()
    except Exception as error:
        return rejected(error)


async def one_run(args, index, start_native, cancel):
    from inkecho.platform.hybrid_keyboard import HybridKeyboardInput
    from inkecho.platform.keyboard import KeyboardError
    from inkecho.platform.wayland_keyboard import keyboard_for_desktop
    from inkecho.platform.wayland_worker import MutterSession

    directory = args.work_root / str(index)
    directory.mkdir(mode=0o700)
    count_path, guard_path = directory / "counts.json", directory / "guard.json"
    total = 14 if cancel else len(SAMPLE)
    expected = [SAMPLE[:10], SAMPLE[10:total]]
    row = {
        "index": index,
        "passed": False,
        "start_backend": "native" if start_native else "x11",
        "cancel_after": 14 if cancel else None,
        "requests": [],
        "prefixes": [],
        "mapping_epochs": [],
        "targets": [],
        "worker_owners": [],
        "cleanup_errors": [],
        "guard_failures": [],
        "setup_metadata": [],
        "phase": "setup",
        "test_boundary": "native key ACK held"
        if start_native
        else "X prefix request capped at10",
    }
    fixtures, workers, callbacks = [], [], []
    current, native_epoch, x_epoch = None, False, False
    observer = inputs = monitor_task = None
    native_before = x_before = None
    counts = dict.fromkeys(
        (
            "press release mapping_writes successful_restore_calls guard_rejections"
        ).split(),
        0,
    )
    switched = False

    def measured():
        n = (
            json.loads(count_path.read_text())
            if count_path.exists()
            else dict.fromkeys(
                ("press_success", "release_success", "guard_rejections"), 0
            )
        )
        return {
            "native": n,
            "x11": dict(counts),
            "press_success": n["press_success"] + counts["press"],
            "release_success": n["release_success"] + counts["release"],
            "guard_rejections": n["guard_rejections"] + counts["guard_rejections"],
        }

    def active():
        return not cancel or measured()["press_success"] < 14

    def publish():
        if current is None:
            return False
        current.assert_owned()
        state = current.snapshot()
        fresh = bool(
            state
            and state["document_focused"]
            and state["field_focused"]
            and 0 <= time.monotonic() - state["sampled_at"] <= 0.25
        )
        save(
            guard_path,
            {
                "allowed": fresh and current.platform == "wayland",
                "backend_confirmed": current.platform == "wayland",
                "owner_pid": os.getpid(),
                "pid": current.process.pid,
                "start_ticks": current.started,
                "sampled_at": state["sampled_at"] if state else 0,
            },
        )
        return fresh

    async def monitor():
        while True:
            publish()
            await asyncio.sleep(0.02)

    async def open_target(native):
        nonlocal current
        item = NaturalOwnedBrowser(
            directory / f"browser{len(fixtures)}",
            platform="wayland" if native else "x11",
        )
        fixtures.append(item)
        row["phase"] = f"target{len(fixtures) - 1}_start"
        item.start(reviewed=True)
        row["phase"] = f"target{len(fixtures) - 1}_protocol"
        setup_metadata(inputs, item, row)
        if native:
            await until(
                lambda: all(
                    v is True
                    for k, v in item.native_evidence().items()
                    if k != "ozone_platform"
                ),
                "owned_native_protocol_not_ready",
            )
            proof = item.native_evidence()
        else:
            await until(
                lambda: x11_evidence(item)["confirmed"], "owned_x11_protocol_not_ready"
            )
            proof = x11_evidence(item)
        current = item
        row["phase"] = f"target{len(fixtures) - 1}_focus_ready"
        setup_metadata(inputs, item, row)
        await until(
            lambda: publish() and (native or owned_focus(inputs.x11._driver, item)),
            "owned_target_not_ready",
        )
        if item.snapshot()["text"]:
            raise ValueError("owned_initial_text_not_empty")
        row["phase"] = f"target{len(fixtures) - 1}_ready"
        setup_metadata(inputs, item, row)
        row["targets"].append(
            {
                "pid": item.process.pid,
                "start_ticks": item.started,
                "argv": item.argv,
                "protocol": proof,
            }
        )
        save(directory / "live-owners.json", row)

    async def boundary_switch():
        nonlocal switched
        row["phase"] = "test_boundary_pause"
        await until(
            lambda: fixtures[0].snapshot()["text"] == expected[0],
            "old_field_prefix_not_exact",
        )
        row["switch_started_at"] = time.monotonic()
        await open_target(not start_native)
        switched = True
        row["switch_ready_at"] = time.monotonic()
        row["phase"] = "output_after_boundary"

    async def spawn(*unused, **options):
        command = [sys.executable, "-B", str(Path(__file__).resolve())]
        for name in (
            "artifact",
            "expected_sha",
            "package_root",
            "frozen_source_root",
            "expected_version",
            "output",
        ):
            command.extend(["--" + name.replace("_", "-"), str(getattr(args, name))])
        command.extend(
            [
                "--work-root",
                str(directory),
                "--case",
                args.case,
                "--run-reviewed",
                "--worker",
                "--owner-pid",
                str(os.getpid()),
            ]
        )
        process = await asyncio.create_subprocess_exec(*command, **options)
        owner = {
            "pid": process.pid,
            "start_ticks": process_start(process.pid),
            "argv": command,
        }
        workers.append((process, owner))
        row["worker_owners"].append(owner)
        save(directory / "live-owners.json", row)
        return process

    try:
        row["phase"] = "metadata_observer_connect"
        observer = MutterSession()
        await observer.connect()
        row["phase"] = "metadata_observer_authorize"
        await observer.authorize()
        row["phase"] = "metadata_initial_snapshot"
        row["setup_initial_native"] = await keymap_metadata(observer)
        inputs = keyboard_for_desktop()
        if not isinstance(inputs, HybridKeyboardInput):
            raise ValueError("actual_factory_hybrid_required")
        row["factory_type"] = type(inputs).__name__
        row["factory_selected"] = True
        # Same test-only guarded Guardian seam on the actual factory backend.
        inputs.native._spawn = spawn
        row["phase"] = "hybrid_connect"
        await inputs.connect()
        row["phase"] = "hybrid_authorize"
        await inputs.authorize()
        x11, native = inputs.x11, inputs.native
        await open_target(start_native)
        row["phase"] = "ready_baseline"
        native_before = row["ready_native"] = await keymap_metadata(observer)
        x_before = x11._driver._mapping()
        row["ready_x11_map_sha256"] = hashlib.sha256(
            repr(x_before).encode()
        ).hexdigest()
        monitor_task = asyncio.create_task(monitor())
        request, mapping = native._request, x11._driver.map

        def epoch(operation):
            row["mapping_epochs"].append(
                {
                    "at": time.monotonic(),
                    "operation": operation,
                    "native": native_epoch,
                    "x11": x_epoch,
                }
            )

        async def observed_request(operation, **options):
            nonlocal native_epoch
            if operation == "begin" and x_epoch:
                raise ValueError("overlapping_mapping_epochs")
            trace = {"operation": operation, "started_at": time.monotonic()}
            row["requests"].append(trace)
            try:
                response = await request(operation, **options)
                trace["acknowledged"] = True
            except KeyboardError as error:
                trace.update(acknowledged=False, error_code=error.code)
                raise
            finally:
                trace["returned_at"] = time.monotonic()
            if operation == "begin":
                native_epoch = True
                epoch(operation)
            elif operation in {"finish", "cancel", "close"}:
                native_epoch = False
                epoch(operation)
            if (
                operation == "key"
                and start_native
                and not switched
                and measured()["native"]["press_success"] == 10
            ):
                # Only the test holds the real ACK. Production has already
                # completed this key and release; no new request is in flight.
                await boundary_switch()
            return response

        native._request = observed_request

        def observed_map(character):
            nonlocal x_epoch
            if native_epoch:
                raise ValueError("overlapping_mapping_epochs")
            result = mapping(character)
            x_epoch = character != "\n" or x_epoch
            epoch("x11_map")
            return result

        x11._driver.map = observed_map
        for label, backend in [("native", native), ("x11", x11)]:
            original = backend._insert_prefix

            async def prefix(
                text, *arguments, _original=original, _label=label, **options
            ):
                count = None
                capped = _label == "x11" and not start_native and not switched
                row["prefixes"].append(
                    {
                        "backend": _label,
                        "phase": "enter",
                        "at": time.monotonic(),
                        "test_request_cap10": capped,
                    }
                )
                try:
                    count = await _original(
                        text[:10] if capped else text, *arguments, **options
                    )
                    if capped:
                        if count != 10:
                            raise ValueError("controlled_prefix_not10")
                        await boundary_switch()
                    return count
                finally:
                    row["prefixes"].append(
                        {
                            "backend": _label,
                            "phase": "exit",
                            "at": time.monotonic(),
                            "confirmed_count": count,
                        }
                    )

            backend._insert_prefix = prefix
        with observe(
            x11,
            lambda window: (
                current is not None
                and diagnosed_owned_focus(x11._driver, current, row, window)
            ),
            counts,
        ):
            restore = x11._driver.restore

            def restored():
                nonlocal x_epoch
                result = restore()
                x_epoch = False
                epoch("x11_restore_returned")
                return result

            x11._driver.restore = restored
            row["phase"] = "output_before_boundary"
            try:
                count = await inputs.insert(
                    SAMPLE,
                    active,
                    deadline=time.monotonic() + 40,
                    on_first_sent=callbacks.append,
                )
                row["confirmed_insert_count"] = count
            except KeyboardError as error:
                row["output_error_code"] = error.code
                count_state = measured()
                if not (
                    cancel
                    and error.code == "input_cancelled"
                    and count_state["press_success"] == 14
                    and count_state["guard_rejections"] == 0
                ):
                    raise
            row["phase"] = "readback"
            await until(
                lambda: (
                    len(fixtures) == 2
                    and all(
                        item.snapshot()["text"] == wanted
                        for item, wanted in zip(fixtures, expected, strict=True)
                    )
                ),
                "owned_readback_not_exact",
            )
            await asyncio.sleep(0.5)
            row["no_tail_observation_seconds"] = 0.5
            row["scope_after_native"] = await keymap_metadata(observer)
            row["native_scope_mapping_restored"] = (
                native_before == row["scope_after_native"]
            )
            row["scope_metadata_taken_while_inputs_open"] = True
            row["output_epochs_closed"] = not native_epoch and not x_epoch
    except Exception as error:
        row.update(
            safe_error_type=type(error).__name__,
            error_code=error.code if isinstance(error, KeyboardError) else None,
            failed_phase=row["phase"],
            fixed_setup_error_code=fixed_setup_error(error),
            exception_locations=exception_locations(error),
        )
        if row["phase"].startswith("target") and fixtures and fixtures[-1].process:
            try:
                setup_metadata(inputs, fixtures[-1], row)
            except Exception as diagnostic_error:
                row["setup_failure_metadata_error_type"] = type(
                    diagnostic_error
                ).__name__
    finally:
        row["phase"] = "cleanup"
        if monitor_task:
            monitor_task.cancel()
            await asyncio.gather(monitor_task, return_exceptions=True)
        if inputs:
            try:
                row["after_x11_map_sha256"] = hashlib.sha256(
                    repr(inputs.x11._driver._mapping()).encode()
                ).hexdigest()
                row["x11_mapping_restored"] = (
                    x_before is not None and inputs.x11._driver._mapping() == x_before
                )
            except Exception as error:
                row["cleanup_errors"].append(
                    {"component": "x11_metadata", "error_type": type(error).__name__}
                )
            finally:
                try:
                    await inputs.aclose()
                except Exception as error:
                    row["cleanup_errors"].append(
                        {
                            "component": "hybrid_close",
                            "error_type": type(error).__name__,
                        }
                    )
        for process, owner in workers:
            owner.update(exit_code=await process.wait(), owner_observed_terminal=True)
        if observer:
            try:
                row["after_native"] = await keymap_metadata(observer)
                row["native_mapping_restored"] = (
                    native_before is not None and native_before == row["after_native"]
                )
            except Exception as error:
                row["cleanup_errors"].append(
                    {"component": "native_metadata", "error_type": type(error).__name__}
                )
            finally:
                try:
                    await observer.close()
                except Exception as error:
                    row["cleanup_errors"].append(
                        {
                            "component": "observer_close",
                            "error_type": type(error).__name__,
                        }
                    )
        row["readback"] = []
        for item, wanted in zip(fixtures, expected, strict=False):
            state = item.snapshot()
            text = state["text"] if state else ""
            row["readback"].append(
                {
                    "received_count": len(text),
                    "exact": state is not None and text == wanted,
                    **mismatch_metrics(text, wanted),
                }
            )
        for item in reversed(fixtures):
            if item.process:
                try:
                    code = item.close()
                    row.setdefault("target_exits", []).append(
                        {
                            "pid": item.process.pid,
                            "start_ticks": item.started,
                            "exit_code": code,
                        }
                    )
                except Exception as error:
                    row["cleanup_errors"].append(
                        {
                            "component": "browser_close",
                            "error_type": type(error).__name__,
                        }
                    )
        row["counts"] = measurement = measured()
        first_count = (
            measurement["native"]["press_success"]
            if start_native
            else measurement["x11"]["press"]
        )
        second_count = (
            measurement["x11"]["press"]
            if start_native
            else measurement["native"]["press_success"]
        )
        row["first_callback_count"] = len(callbacks)
        row["fixture_errors"] = [code for item in fixtures for code in item.errors]
        row["passed"] = bool(
            switched
            and len(row["readback"]) == 2
            and all(item["exact"] for item in row["readback"])
            and measurement["press_success"] == measurement["release_success"] == total
            and first_count == 10
            and second_count == total - 10
            and not measurement["guard_rejections"]
            and len(callbacks) == 1
            and row.get("output_epochs_closed")
            and row.get("x11_mapping_restored")
            and row.get("native_scope_mapping_restored")
            and row.get("scope_metadata_taken_while_inputs_open")
            and row.get("native_mapping_restored")
            and not row["cleanup_errors"]
            and not row["fixture_errors"]
            and len(row.get("target_exits", [])) == 2
            and all(item["exit_code"] == 0 for item in row["target_exits"])
            and all(owner["exit_code"] == 0 for owner in row["worker_owners"])
            and (
                (row.get("output_error_code") == "input_cancelled")
                if cancel
                else row.get("confirmed_insert_count") == total
            )
        )
        row["phase"] = "terminal"
        save(directory / "result.json", row)
    return row


def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    for name in (
        "artifact",
        "package-root",
        "frozen-source-root",
        "work-root",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--owner-pid", type=int, help=argparse.SUPPRESS)
    parser.add_argument(
        "--case",
        choices=[
            "native-to-x-normal",
            "x-to-native-normal",
            "native-to-x-cancel14",
            "x-to-native-cancel14",
        ],
        required=True,
    )
    parser.add_argument("--run-reviewed", action="store_true", required=True)
    args = parser.parse_args()
    artifact, audit = audit_selected_package(args)
    if args.worker:
        if args.owner_pid != os.getppid():
            raise ValueError("worker_parent_changed")
        asyncio.run(
            worker(
                args.work_root / "guard.json",
                args.work_root / "counts.json",
                args.owner_pid,
            )
        )
        return
    if args.work_root.exists() or args.output.exists():
        raise ValueError("exclusive_new_paths_required")
    args.work_root.mkdir(mode=0o700)
    report = {
        "passed": False,
        "runtime_kind": "package",
        "runtime": audit,
        "artifact": artifact,
        "desktop": desktop("ubuntu26-xwayland"),
        "sample_codepoints": len(SAMPLE),
        "sample_sha256": hashlib.sha256(SAMPLE.encode()).hexdigest(),
        "rows": [],
        "case": args.case,
        "hybrid_explicitly_constructed": False,
        "factory_used": True,
        "native_map_ack_count_observed": False,
        "production_insert_uses_formal_output_session": True,
        "no_cloud_mic_keyring_clipboard_or_ime": True,
        "scope": (
            "controlled actual ACK/request-prefix10 boundary switching; "
            "test pauses/newtargetready; not transition throughput/atomicity "
            "or real post-map switch proof"
        ),
    }
    from PySide6.QtWidgets import QApplication

    from inkecho.runtime import ManagedQtEventLoop

    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    if app.platformName() != "wayland":
        raise ValueError("actual_wayland_required")

    async def run():
        index, native, cancel = {
            "native-to-x-normal": (0, True, False),
            "x-to-native-normal": (1, False, False),
            "native-to-x-cancel14": (2, True, True),
            "x-to-native-cancel14": (3, False, True),
        }[args.case]
        row = await one_run(args, index, native, cancel)
        report["rows"].append(row)
        report["passed"] = row["passed"]
        save(args.output, report)
        print(json.dumps({"index": index, "passed": row["passed"]}), flush=True)

    with ManagedQtEventLoop(app) as loop:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(run())
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            json.dumps(
                {
                    "safe_code": "mixed_preflight_failed",
                    "safe_error_type": type(error).__name__,
                }
            )
        )
        raise SystemExit(2) from None
