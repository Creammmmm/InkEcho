"""Single-case owned Chrome benchmark through the real desktop keyboard factory.

Source mode uses explicitly approved source-manifest bytes with an audited package
interpreter/dependencies. Package mode imports only the audited package. Neither
mode proves general desktop compatibility. Preview performs no desktop operations;
--run-reviewed permits one fresh owned target and synthetic public text only.
"""

import argparse
import asyncio
import importlib
import json
import math
import os
import sys
import time
from contextlib import nullcontext
from pathlib import Path

from artifact_scope import MODULES, checksum, selected_artifact
from native_acceptance import keymap_metadata, until
from native_guard import save, worker
from natural_owned_browser import NaturalOwnedBrowser, debugger_endpoint, process_start
from x11_acceptance import observe, owned_focus

SAMPLE = (
    "这是一段中文输入速度测试，用来测量真实键盘发送字符的用时。"
    "今天我们同时检查中文、English words, numbers 12345, "
    "and punctuation. 中文结束。 Test 1."
)


def source_files(root: Path) -> dict:
    if any(path.is_symlink() for path in root.rglob("*")):
        raise ValueError("source_symlink_forbidden")
    return {
        "src/" + str(path.relative_to(root)): checksum(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def audit(args) -> dict:
    artifact = selected_artifact(args.artifact, args.artifact_sha)
    dependencies = args.package_root.resolve(strict=True)
    appdir = dependencies.parent
    if not Path(sys.executable).resolve().is_relative_to(appdir / "usr"):
        raise ValueError("audited_package_interpreter_required")
    inventory_path = appdir / "usr/share/doc/inkecho/inventory.json"
    inventory = json.loads(inventory_path.read_text())
    for name, pin in inventory["files"].items():
        path = (appdir / name).resolve(strict=True)
        if not path.is_relative_to(appdir) or checksum(path) != pin:
            raise ValueError("dependency_inventory_mismatch")
    for name, target in inventory["symlinks"].items():
        path = appdir / name
        if not path.is_symlink() or str(path.readlink()) != target:
            raise ValueError("dependency_symlink_mismatch")
        if not path.resolve(strict=True).is_relative_to(appdir):
            raise ValueError("dependency_symlink_escape")
    root, expected = dependencies, None
    if args.runtime == "source":
        if not args.source_root or not args.manifest or not args.manifest_sha:
            raise ValueError("approved_source_manifest_required")
        if checksum(args.manifest) != args.manifest_sha:
            raise ValueError("source_manifest_sha_mismatch")
        manifest = json.loads(args.manifest.read_text())
        root = args.source_root.resolve(strict=True)
        expected = source_files(root)
        if not expected or expected != manifest["source_files"]:
            raise ValueError("source_manifest_mismatch")
        pins = manifest.get(
            "approved_stage3_pins", manifest.get("approved_production_pins")
        )
        required = {
            "inkecho/platform/" + name + ".py"
            for name in (
                "keyboard",
                "hybrid_keyboard",
                "wayland_keyboard",
                "wayland_worker",
            )
        }
        if not isinstance(pins, dict) or set(pins) != required:
            raise ValueError("four_production_pins_required")
        if any(expected.get("src/" + name) != pin for name, pin in pins.items()):
            raise ValueError("production_pin_mismatch")
    elif args.source_root or args.manifest or args.manifest_sha:
        raise ValueError("package_mode_cannot_overlay_source")
    sys.path.insert(0, str(dependencies))
    sys.path.insert(0, str(root))
    modules = list(MODULES)
    if (root / "inkecho/platform/hybrid_keyboard.py").exists():
        modules.append("inkecho.platform.hybrid_keyboard")
    origins = {}
    for name in modules:
        path = Path(importlib.import_module(name).__file__).resolve(strict=True)
        package_dependency = expected is None or name == "websockets"
        selected = dependencies if package_dependency else root
        if not path.is_relative_to(selected):
            raise ValueError("module_origin_outside_selected_runtime")
        pin = checksum(path)
        declared = (
            inventory["files"].get(str(path.relative_to(appdir)))
            if package_dependency
            else expected.get("src/" + str(path.relative_to(root)))
        )
        if pin != declared:
            raise ValueError("module_origin_hash_mismatch")
        origins[name] = {"path": str(path), "sha256": pin}
    return {
        "runtime_kind": args.runtime,
        "artifact": artifact,
        "package_version": inventory["application"],
        "dependency_inventory_sha256": checksum(inventory_path),
        "source_root": str(root),
        "source_manifest_sha256": args.manifest_sha,
        "source_files_checked": len(expected) if expected is not None else None,
        "origins": origins,
        "not_a_new_package": args.runtime == "source",
    }


def measurement(start, first, returned, dom, count):
    if (
        type(count) is not int
        or count <= 0
        or any(
            type(v) not in (int, float) or not math.isfinite(v)
            for v in (start, first, returned, dom)
        )
        or not start <= first <= returned
        or returned <= start
        or dom < first
    ):
        raise ValueError("invalid_measurement")
    return {
        "start_to_first_sent_ms": (first - start) * 1000,
        "output_scope_ms": (returned - start) * 1000,
        "post_return_dom_exact_observed_ms": (dom - start) * 1000,
        "characters_per_second": count / (returned - start),
    }


def worker_argv(args, directory):
    command = [sys.executable, "-B", str(Path(__file__).resolve())]
    for field in (
        "runtime",
        "artifact",
        "artifact_sha",
        "package_root",
        "source_root",
        "manifest",
        "manifest_sha",
        "backend",
        "field",
        "output",
        "work_root",
    ):
        value = getattr(args, field)
        if value is not None:
            command += ["--" + field.replace("_", "-"), str(value)]
    command += [
        "--run-reviewed",
        "--worker",
        "--owner-pid",
        str(os.getpid()),
        "--guard-state",
        str(directory / "guard.json"),
        "--guard-counts",
        str(directory / "counts.json"),
    ]
    return command


async def close_owned_fixture(fixture, report, output):
    """Stop owned HTTP even if Chrome has not published its close endpoint yet.

    An absent endpoint is not permission to kill or abandon a live owned browser.
    After reporting pending cleanup, retain its original owner until normal close
    is possible or its original process becomes terminal.
    """

    def close_ready():
        if fixture.process.poll() is not None:
            return True
        fixture.assert_owned()
        try:
            debugger_endpoint(fixture.profile / "DevToolsActivePort", fixture.profile)
            return True
        except (OSError, ValueError):
            return False

    try:
        try:
            await until(close_ready, "owned_close_endpoint_not_ready")
        except ValueError:
            report["target_cleanup_pending"] = {
                "pid": fixture.process.pid,
                "start_ticks": fixture.started,
                "reason": "owned_close_endpoint_not_ready",
            }
            save(output, report)
    finally:
        # NaturalOwnedBrowser.close only stops HTTP after Browser.close succeeds.
        # This tool also owns the pre-ready failure path and must stop it there.
        server, thread = (
            getattr(fixture, "server", None),
            getattr(fixture, "thread", None),
        )
        errors = report.setdefault("cleanup_errors", [])
        for component, action in (
            ("http_shutdown", server.shutdown if server else None),
            ("http_close", server.server_close if server else None),
            ("http_join", (lambda: thread.join(timeout=3)) if thread else None),
        ):
            if action:
                try:
                    action()
                except (Exception, asyncio.CancelledError) as error:
                    errors.append(
                        {
                            "component": component,
                            "safe_error_type": type(error).__name__,
                        }
                    )
        if thread and thread.is_alive():
            errors.append(
                {"component": "http_join", "safe_error_type": "CleanupPending"}
            )
    while not close_ready():
        await asyncio.sleep(0.02)
    if fixture.process.poll() is None:
        return fixture.close()  # One normal close; it retains the original wait.
    code = fixture.process.wait()
    fixture.save_owner("terminal", code)
    stderr = getattr(fixture, "stderr_thread", None)
    if stderr:
        stderr.join(timeout=3)
        if stderr.is_alive():
            raise ValueError("owned_stderr_cleanup_pending")
    fixture.closed = True
    return code


async def direct_case(args, report):
    from inkecho.platform.keyboard import KeyboardError
    from inkecho.platform.wayland_keyboard import keyboard_for_desktop
    from inkecho.platform.wayland_worker import MutterSession

    directory = args.work_root
    native = args.backend == "native"
    fixture = NaturalOwnedBrowser(
        directory / "browser", field=args.field, platform="wayland" if native else "x11"
    )
    inputs = keyboard_for_desktop()
    native_inputs = (
        getattr(inputs, "native", inputs) if inputs.backend == "gnome-wayland" else None
    )
    x_inputs = getattr(inputs, "x11", None) if native_inputs else inputs
    counts = {
        name: 0
        for name in (
            "press",
            "release",
            "mapping_writes",
            "successful_restore_calls",
            "guard_rejections",
        )
    }
    observer = monitor_task = None
    workers, callbacks, presses = [], [], []
    expected = SAMPLE[:8] if args.cancel else SAMPLE
    guard_path, count_path = directory / "guard.json", directory / "counts.json"
    baseline_native = baseline_x = None
    ready = False

    def native_counts():
        return json.loads(count_path.read_text()) if count_path.exists() else {}

    def pressed():
        return counts["press"] + native_counts().get("press_success", 0)

    def guard():
        state = fixture.snapshot()
        valid = bool(
            ready
            and state
            and state["document_focused"]
            and state["field_focused"]
            and 0 <= time.monotonic() - state["sampled_at"] <= 0.25
        )
        if fixture.process:
            fixture.assert_owned()
        save(
            guard_path,
            {
                "allowed": valid and native,
                "backend_confirmed": native and ready,
                "owner_pid": os.getpid(),
                "pid": fixture.process.pid if fixture.process else 0,
                "start_ticks": fixture.started,
                "sampled_at": state["sampled_at"] if state else 0,
            },
        )
        return valid and (native or owned_focus(x_inputs._driver, fixture))

    async def monitor():
        while True:
            guard()
            await asyncio.sleep(0.02)

    async def spawn(*_command, **options):
        process = await asyncio.create_subprocess_exec(
            *worker_argv(args, directory), **options
        )
        workers.append(process)
        report["worker_owners"].append(
            {
                "pid": process.pid,
                "start_ticks": process_start(process.pid),
                "exit_code": None,
                "owner_observed_terminal": False,
            }
        )
        save(args.output, report)
        return process

    phase = "factory_prepare"
    try:
        if native and native_inputs is None:
            raise ValueError("native_factory_backend_unavailable")
        if native_inputs:
            native_inputs._spawn = spawn
            observer = MutterSession()
            await observer.connect()
            await observer.authorize()
        phase = "input_connect"
        await inputs.connect()
        phase = "input_authorize"
        await inputs.authorize()
        if native_inputs:
            request = native_inputs._request

            async def observed_request(operation, **options):
                response = await request(operation, **options)
                if operation == "key":
                    presses.append(response["sent_at"])
                return response

            native_inputs._request = observed_request
        phase = "target_start"
        fixture.start(reviewed=True)
        phase = "target_protocol_ready"
        if native:

            def native_ready():
                evidence = fixture.native_evidence()
                return evidence.get("ozone_platform") == "wayland" and all(
                    evidence.get(key) is True
                    for key in (
                        "display_unset_in_owned_process",
                        "wayland_surface_observed",
                        "xdg_toplevel_observed",
                    )
                )

            await until(native_ready, "owned_native_not_ready")
            report["field_protocol_evidence"] = fixture.native_evidence()
        else:
            from host_mixed_wayland_probe import x11_evidence

            def x_ready():
                fixture.assert_owned()
                report["field_protocol_evidence"] = x11_evidence(fixture)
                return report["field_protocol_evidence"].get("confirmed") is True

            await until(x_ready, "owned_x_backend_not_ready")
        phase = "target_field_ready"
        ready = True
        await until(guard, "owned_field_not_ready")
        if fixture.snapshot()["text"]:
            raise ValueError("owned_field_not_empty")
        phase = "formal_baseline"
        # Formal restoration baselines follow all connections and target setup.
        if observer:
            baseline_native = await keymap_metadata(observer)
        if x_inputs and x_inputs.connected:
            baseline_x = x_inputs._driver._mapping()
        monitor_task = asyncio.create_task(monitor())
        observed = (
            observe(
                x_inputs,
                lambda window: owned_focus(x_inputs._driver, fixture, window),
                counts,
            )
            if x_inputs and x_inputs.connected
            else nullcontext()
        )
        phase = "insert"
        start = time.monotonic()
        with observed:
            if x_inputs and x_inputs.connected:
                send = x_inputs._send

                def observed_send(window, code, pressed):
                    result = send(window, code, pressed)
                    if pressed:
                        presses.append(time.monotonic())
                    return result

                x_inputs._send = observed_send
            try:
                count = await inputs.insert(
                    SAMPLE,
                    lambda: not args.cancel or pressed() < 8,
                    deadline=start + 40,
                    on_first_sent=callbacks.append,
                )
                if args.cancel or count != len(SAMPLE):
                    raise ValueError("unexpected_dispatch_result")
            except KeyboardError as error:
                if not args.cancel or error.code != "input_cancelled" or pressed() != 8:
                    raise
                report["expected_error"] = error.code
        phase = "readback"
        returned = time.monotonic()
        await until(
            lambda: fixture.snapshot()["text"] == expected,
            "owned_readback_not_exact",
            seconds=40,
        )
        dom = time.monotonic()
        await asyncio.sleep(0.5)
        native_result = native_counts()
        releases = counts["release"] + native_result.get("release_success", 0)
        guards = counts["guard_rejections"] + native_result.get("guard_rejections", 0)
        report.update(
            exact_readback=fixture.snapshot()["text"] == expected,
            received_count=len(fixture.snapshot()["text"]),
            successful_presses=pressed(),
            successful_releases=releases,
            guard_rejections=guards,
            native_counts=native_result,
            x_counts=counts,
            timing=measurement(start, callbacks[0], returned, dom, len(expected)),
            no_tail_observation_seconds=0.5,
        )
        report["correct_route"] = (
            counts["press"] == 0
            if native
            else native_result.get("press_success", 0) == 0
        )
        report["successful_press_timestamps"] = presses
        if len(presses) >= 2:
            report["first_to_last_press_ms"] = (presses[-1] - presses[0]) * 1000
        if observer:
            report["scope_open_native_restored"] = (
                baseline_native == await keymap_metadata(observer)
            )
        if baseline_x is not None:
            report["scope_open_x_restored"] = x_inputs._driver._mapping() == baseline_x
        report["body_passed"] = (
            report["exact_readback"]
            and pressed() == releases == len(expected)
            and guards == 0
            and len(callbacks) == 1
            and report["correct_route"]
            and report.get("scope_open_native_restored", observer is None)
            and report.get("scope_open_x_restored", baseline_x is None)
        )
    except Exception as error:
        report["failed_phase"] = phase
        report["safe_setup_code"] = (
            "owned_protocol_not_ready"
            if phase == "target_protocol_ready"
            else "case_failed"
        )
        report["safe_error_type"] = type(error).__name__
        if isinstance(error, KeyboardError):
            report["safe_keyboard_code"] = error.code
    finally:
        errors = report["cleanup_errors"] = []

        def failed(component, error):
            errors.append(
                {"component": component, "safe_error_type": type(error).__name__}
            )

        if monitor_task:
            monitor_task.cancel()
            await asyncio.gather(monitor_task, return_exceptions=True)
        try:
            await inputs.aclose()
        except (Exception, asyncio.CancelledError) as error:
            failed("inputs", error)
        for process, owner in zip(workers, report["worker_owners"], strict=True):
            try:
                owner["exit_code"] = await process.wait()
                owner["owner_observed_terminal"] = True
            except (Exception, asyncio.CancelledError) as error:
                failed("worker_wait", error)
        if observer:
            try:
                report["native_mapping_restored"] = (
                    baseline_native is not None
                    and baseline_native == await keymap_metadata(observer)
                )
            except (Exception, asyncio.CancelledError) as error:
                failed("native_readback", error)
            try:
                await observer.close()
            except (Exception, asyncio.CancelledError) as error:
                failed("observer", error)
        if baseline_x is not None:
            driver = None
            try:
                from inkecho.platform.keyboard import _XDriver

                driver = _XDriver()
                report["x_mapping_restored"] = driver._mapping() == baseline_x
            except (Exception, asyncio.CancelledError) as error:
                failed("x_readback", error)
            finally:
                if driver is not None:
                    try:
                        driver.close()
                    except (Exception, asyncio.CancelledError) as error:
                        failed("x_observer", error)
        if fixture.process:
            try:
                report["target_exit"] = await close_owned_fixture(
                    fixture, report, args.output
                )
            except (Exception, asyncio.CancelledError) as error:
                failed("target", error)
        report["passed"] = bool(
            report.get("body_passed")
            and report.get("native_mapping_restored", observer is None)
            and report.get("x_mapping_restored", baseline_x is None)
            and report.get("target_exit") == 0
            and not fixture.errors
            and not errors
            and all(p.returncode == 0 for p in workers)
        )
        save(args.output, report)


def parser():
    result = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    result.add_argument("--runtime", choices=["source", "package"], required=True)
    for name in ("artifact", "package-root", "output", "work-root"):
        result.add_argument("--" + name, type=Path, required=True)
    result.add_argument("--artifact-sha", required=True)
    for name in ("source-root", "manifest"):
        result.add_argument("--" + name, type=Path)
    result.add_argument("--manifest-sha")
    result.add_argument("--backend", choices=["native", "xwayland"], required=True)
    result.add_argument(
        "--field", choices=["textarea", "contenteditable"], required=True
    )
    result.add_argument("--cancel", action="store_true")
    result.add_argument("--run-reviewed", action="store_true")
    result.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    result.add_argument("--owner-pid", type=int, help=argparse.SUPPRESS)
    result.add_argument("--guard-state", type=Path, help=argparse.SUPPRESS)
    result.add_argument("--guard-counts", type=Path, help=argparse.SUPPRESS)
    return result


def main():
    sys.dont_write_bytecode = True
    args = parser().parse_args()
    runtime = audit(args)
    if args.worker:
        if not args.run_reviewed:
            raise ValueError("worker_explicit_review_required")
        if args.owner_pid != os.getppid() or not all(
            path and path.resolve().is_relative_to(args.work_root.resolve())
            for path in (args.guard_state, args.guard_counts)
        ):
            raise ValueError("worker_owner_mismatch")
        asyncio.run(worker(args.guard_state, args.guard_counts, args.owner_pid))
        return
    if not args.run_reviewed:
        print(
            json.dumps(
                {
                    "preview_only": True,
                    "runtime": runtime,
                    "sample_codepoints": len(SAMPLE),
                    "argv": sys.argv,
                },
                indent=2,
            )
        )
        return
    if args.output.exists() or args.work_root.exists():
        raise ValueError("exclusive_new_evidence_paths_required")
    args.work_root.mkdir(mode=0o700)
    from PySide6.QtWidgets import QApplication

    from inkecho.runtime import ManagedQtEventLoop

    application = QApplication([])
    application.setQuitOnLastWindowClosed(False)
    if application.platformName() not in {"wayland", "xcb"}:
        raise ValueError("actual_graphical_qt_required")
    report = {
        "passed": False,
        "runtime": runtime,
        "backend": args.backend,
        "field": args.field,
        "cancel": args.cancel,
        "factory_selected": True,
        "argv": sys.argv,
        "parent_owner": {"pid": os.getpid(), "start_ticks": process_start(os.getpid())},
        "sample_codepoints": len(SAMPLE),
        "sample_sha256": checksum_text(SAMPLE),
        "worker_owners": [],
        "cloud_requests": 0,
        "microphone": False,
        "keyring_access": False,
        "clipboard_used": False,
        "input_method_used": False,
        "timing_scope": (
            "single insert, dispatch/DOM observation, owned guard overhead included"
        ),
        "unverified": "Xorg modifier state; other applications; microphone/cloud",
        "session": os.environ.get("XDG_SESSION_TYPE"),
        "desktop": os.environ.get("XDG_CURRENT_DESKTOP"),
    }
    try:
        with ManagedQtEventLoop(application) as loop:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(direct_case(args, report))
    finally:
        save(args.output, report)
    raise SystemExit(0 if report["passed"] else 1)


def checksum_text(text):
    import hashlib

    return hashlib.sha256(text.encode()).hexdigest()


if __name__ == "__main__":
    try:
        main()
    except (Exception, asyncio.CancelledError) as error:
        print(
            json.dumps(
                {
                    "safe_error_type": type(error).__name__,
                    "safe_code": "input_speed_probe_failed",
                }
            )
        )
        raise SystemExit(2) from None
