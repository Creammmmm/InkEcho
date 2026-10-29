"""Exercise Session's X11 map wait in an owned Xorg fixture."""

import argparse
import asyncio
import hashlib
import importlib
import json
import sys
import time
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from artifact_scope import audit_package, selected_artifact
from natural_owned_browser import NaturalOwnedBrowser
from x11_acceptance import COUNTERS, SAMPLE, desktop, observe, owned_focus, until


def audit_source(source_root, manifest_path):
    """Bind the source-only experiment to a complete frozen module snapshot."""
    root = source_root.resolve(strict=True)
    manifest = json.loads(manifest_path.read_text())
    expected = manifest["files"]
    actual = {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (root / "inkecho").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and not path.is_symlink()
    }
    if actual != expected or any(
        path.is_symlink() for path in (root / "inkecho").rglob("*")
    ):
        raise ValueError("frozen_source_mismatch")
    sys.path.insert(0, str(root))
    origins = {}
    for name in ("inkecho.app", "inkecho.config", "inkecho.platform.keyboard"):
        module = importlib.import_module(name)
        origin = Path(module.__file__).resolve(strict=True)
        if not origin.is_relative_to(root / "inkecho"):
            raise ValueError("source_module_origin_mismatch")
        origins[name] = str(origin)
    return {
        "kind": "source-only",
        "origins": origins,
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }


@contextmanager
def measure_mapping_wait(inputs, timings):
    """Observe only successful writes and guarded presses, without changing timing."""
    driver = inputs._driver
    method_name = "prepare" if callable(getattr(driver, "prepare", None)) else "map"
    original, send = getattr(driver, method_name), inputs._send
    pending = None

    def measured_mapping(*args):
        nonlocal pending
        initial = driver.applied is None
        revision = driver._map_revision
        result = original(*args)
        if driver._map_revision != revision:
            pending = (time.monotonic(), initial)
        return result

    def measured_send(window, code, pressed):
        nonlocal pending
        send(window, code, pressed)
        if pressed and pending is not None:
            started, initial = pending
            timings.append(
                {
                    "initial": initial,
                    "milliseconds": (time.monotonic() - started) * 1000,
                }
            )
            pending = None

    setattr(driver, method_name, measured_mapping)
    inputs._send = measured_send
    try:
        yield
    finally:
        setattr(driver, method_name, original)
        inputs._send = send


async def run(args, report):
    from inkecho.app import Session
    from inkecho.config import ConfigStore
    from inkecho.platform.keyboard import KeyboardError, KeyboardInput

    scope = getattr(args, "scope", "ubuntu24-xorg")
    report["desktop"] = desktop(scope)
    args.work_root.mkdir(mode=0o700, exist_ok=False)
    store = ConfigStore(args.work_root / "private-config")
    store.initialize()
    store.save_settings(
        replace(
            store.load_settings(),
            x11_mapping_wait_ms=args.wait_ms,
            x11_feedback_timeout_ms=getattr(args, "feedback_timeout_ms", 40),
        )
    )
    session = Session(store=store)
    inputs = session.inputs
    keyboard = getattr(inputs, "keyboard", inputs)
    hybrid = scope == "ubuntu26-xwayland"
    if hybrid:
        from inkecho.platform.hybrid_keyboard import HybridKeyboardInput

        if type(keyboard) is not HybridKeyboardInput:
            raise ValueError("actual_wayland_hybrid_required")
        x11 = keyboard.x11
        sample = SAMPLE.replace("😀", "")
    else:
        if type(keyboard) is not KeyboardInput:
            raise ValueError("actual_xorg_keyboard_required")
        x11 = keyboard
        sample = SAMPLE
    counts = dict.fromkeys(COUNTERS, 0)
    report["counts"] = counts
    report["mapping_to_press"] = []
    report["saved_wait_ms"] = store.load_settings().x11_mapping_wait_ms
    report["saved_feedback_timeout_ms"] = store.load_settings().x11_feedback_timeout_ms
    fixtures, target, driver, before = [], None, None, None
    expected = []

    async def open_target(field):
        nonlocal target
        target = NaturalOwnedBrowser(
            args.work_root / f"browser-{len(fixtures)}", field=field, platform="x11"
        )
        fixtures.append(target)
        target.start(reviewed=True)
        await until(lambda: owned_focus(driver, target))

    def readback():
        return [
            item.snapshot()["text"] if item.snapshot() else None for item in fixtures
        ]

    try:
        await inputs.connect()
        prepare_task = getattr(inputs, "prepare_task", None)
        if callable(prepare_task):
            if await prepare_task("keyboard") != "keyboard":
                raise ValueError("keyboard_route_required")
        elif hybrid:
            await keyboard.authorize()
        driver = x11._driver
        before = driver._mapping()
        await open_target(
            "contenteditable" if args.mode == "contenteditable" else "textarea"
        )
        if hybrid:
            original_selection = keyboard._x_selected

            def owned_x_only():
                if not original_selection() or not owned_focus(driver, target):
                    raise KeyboardError("input_cancelled")
                return True

            keyboard._x_selected = owned_x_only
        with (
            observe(x11, lambda window: owned_focus(driver, target, window), counts),
            measure_mapping_wait(x11, report["mapping_to_press"]),
        ):
            try:
                output_started = time.monotonic()
                async with inputs.output_session():
                    if args.mode in {"currentcursor", "currentcursor-textareas"}:
                        count = await inputs.insert(sample[:5], lambda: True)
                        expected.append(sample[:5])
                        await until(lambda: readback() == expected)
                        await open_target(
                            "textarea"
                            if args.mode == "currentcursor-textareas"
                            else "contenteditable"
                        )
                        count += await inputs.insert(sample[5:], lambda: True)
                        expected.append(sample[5:])
                    else:
                        count = await inputs.insert(
                            sample,
                            lambda: args.mode != "cancel" or counts["press"] < 8,
                        )
                        expected.append(sample)
            except KeyboardError as error:
                if args.mode != "cancel" or error.code != "input_cancelled":
                    raise
                report["expected_error"] = error.code
                count = counts["press"]
                expected.append(sample[:8])
            report["output_elapsed_ms"] = (time.monotonic() - output_started) * 1000
            report["session_wait_ms"] = round(x11._output_mapping_wait * 1000)
            report["session_feedback_timeout_ms"] = round(
                x11._pacer.config.feedback_min * 1000
            )
            await until(lambda: readback() == expected)
            await asyncio.sleep(1.2)
            report["exact_readback_after_hold"] = readback() == expected
            report["confirmed_characters"] = count
        report["mapping_restored"] = driver._mapping() == before
    finally:
        session.timer.stop()
        await inputs.aclose()
        report["driver_closed"] = x11._driver is None and not inputs.connected
        report["target_snapshots"] = []
        for item in fixtures:
            state = item.snapshot()
            text = state.get("text") if state else None
            report["target_snapshots"].append(
                {
                    "length": len(text),
                    "sha256": hashlib.sha256(text.encode()).hexdigest(),
                }
                if isinstance(text, str)
                else None
            )
        report["expected_snapshots"] = [
            {"length": len(text), "sha256": hashlib.sha256(text.encode()).hexdigest()}
            for text in expected
        ]
        report["fixed_sample_differences"] = []
        for item, wanted in zip(fixtures, expected, strict=False):
            state = item.snapshot()
            actual = state.get("text") if state else None
            if not isinstance(actual, str):
                report["fixed_sample_differences"].append(None)
                continue
            report["fixed_sample_differences"].append(
                [
                    {
                        "index": index,
                        "expected": f"U+{ord(left):04X}",
                        "actual": f"U+{ord(right):04X}",
                    }
                    for index, (left, right) in enumerate(
                        zip(wanted, actual, strict=False)
                    )
                    if left != right
                ]
            )
        report["target_exits"] = [item.close() for item in reversed(fixtures)]
        report["fixture_errors"] = [code for item in fixtures for code in item.errors]
    wanted = 8 if args.mode == "cancel" else len(sample)
    report["passed"] = bool(
        report.get("saved_wait_ms") == args.wait_ms
        and report.get("session_wait_ms") == args.wait_ms
        and report.get("saved_feedback_timeout_ms")
        == getattr(args, "feedback_timeout_ms", 40)
        and report.get("session_feedback_timeout_ms")
        == getattr(args, "feedback_timeout_ms", 40)
        and report.get("exact_readback_after_hold")
        and report.get("mapping_restored")
        and report.get("driver_closed")
        and any(not item["initial"] for item in report["mapping_to_press"])
        and all(
            item["milliseconds"] >= (100 if item["initial"] else args.wait_ms) - 1
            for item in report["mapping_to_press"]
        )
        and counts["press"] == counts["release"] == wanted
        and report.get("confirmed_characters") == wanted
        and counts["guard_rejections"] == 0
        and report["target_exits"]
        and all(code == 0 for code in report["target_exits"])
        and not report["fixture_errors"]
        and (args.mode != "cancel" or report.get("expected_error") == "input_cancelled")
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    for (
        key
    ) in "artifact package-root frozen-source-root source-root source-manifest".split():
        parser.add_argument("--" + key, type=Path)
    for key in ("output", "work-root"):
        parser.add_argument("--" + key, type=Path, required=True)
    parser.add_argument("--expected-sha")
    parser.add_argument("--expected-version")
    parser.add_argument(
        "--scope",
        choices=("ubuntu24-xorg", "ubuntu26-xwayland"),
        default="ubuntu24-xorg",
    )
    parser.add_argument("--wait-ms", type=int, choices=range(20, 251), required=True)
    parser.add_argument(
        "--feedback-timeout-ms", type=int, choices=range(20, 251), default=40
    )
    parser.add_argument(
        "--mode",
        choices=(
            "normal",
            "cancel",
            "currentcursor",
            "currentcursor-textareas",
            "contenteditable",
        ),
        required=True,
    )
    parser.add_argument("--run-host", action="store_true")
    args = parser.parse_args()
    if not args.run_host or args.output.exists() or args.work_root.exists():
        parser.error("exclusive_paths_and_explicit_desktop_review_required")
    source_mode = args.source_root is not None or args.source_manifest is not None
    package_values = (
        args.artifact,
        args.package_root,
        args.frozen_source_root,
        args.expected_sha,
        args.expected_version,
    )
    if source_mode:
        if not args.source_root or not args.source_manifest or any(package_values):
            parser.error("source_mode_requires_only_source_root_and_manifest")
        artifact = None
        runtime = audit_source(args.source_root, args.source_manifest)
    else:
        if not all(package_values):
            parser.error("package_mode_requires_artifact_and_audit_options")
        artifact = selected_artifact(args.artifact, args.expected_sha)
        runtime = audit_package(
            args.package_root, args.frozen_source_root, args.expected_version
        )
    report = {
        "passed": False,
        "scope": args.scope,
        "mode": args.mode,
        "requested_wait_ms": args.wait_ms,
        "requested_feedback_timeout_ms": args.feedback_timeout_ms,
        "artifact": artifact,
        "runtime": runtime,
        "cloud_requests": 0,
        "microphone": False,
        "credential_store_reads": 0,
        "clipboard_used": False,
        "production_behavior_modified": False,
        "draw_or_presentation_confirmed": False,
    }
    from PySide6.QtWidgets import QApplication

    application = QApplication([])
    application.setQuitOnLastWindowClosed(False)
    try:
        asyncio.run(run(args, report))
    except Exception as error:
        report["failure_code"] = "x11_mapping_wait_probe_failed"
        report["failure_type"] = type(error).__name__
        if isinstance(getattr(error, "code", None), str):
            report["failure_detail_code"] = error.code
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps(report))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
