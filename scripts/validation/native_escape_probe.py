"""Production TaskEscape abort/disconnect with owned native target and ESC only."""

import argparse
import asyncio
import configparser
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def process_start(pid):
    return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]


def bootstrap(root, package):
    root = root.resolve(strict=True)
    if not (root / "inkecho" / "__init__.py").is_file():
        raise RuntimeError("Selected InkEcho runtime root required")
    sys.path.insert(0, str(root))
    if package:
        appdir = root.parent
        if root.name != "packages" or not Path(sys.executable).resolve().is_relative_to(
            appdir / "usr/bin"
        ):
            raise RuntimeError(
                "Package mode requires the selected AppDir's interpreter"
            )
    return root


def audit(root, package):
    values = {}
    for name, module in tuple(sys.modules.items()):
        filename = getattr(module, "__file__", None)
        if not filename:
            continue
        if name == "inkecho" or name.startswith("inkecho."):
            origin = Path(filename).resolve()
            if not origin.is_relative_to(root):
                raise RuntimeError("InkEcho import escaped selected runtime")
            values[name] = str(origin)
        elif package and name.split(".")[0] in {
            "PySide6",
            "shiboken6",
            "dbus_next",
            "qasync",
        }:
            if not Path(filename).resolve().is_relative_to(root):
                raise RuntimeError("Package dependency escaped selected runtime")
    return values


def target(root):
    from PySide6.QtCore import QSocketNotifier, Qt, QTimer
    from PySide6.QtWidgets import QApplication, QLineEdit

    app = QApplication([])
    counts = {"press": 0, "release": 0}
    shown_once = False

    class Target(QLineEdit):
        def keyPressEvent(self, event):
            if event.key() == Qt.Key.Key_Escape:
                counts["press"] += 1
            super().keyPressEvent(event)

        def keyReleaseEvent(self, event):
            if event.key() == Qt.Key.Key_Escape:
                counts["release"] += 1
            super().keyReleaseEvent(event)

    window = Target()
    window.setWindowTitle("InkEcho owned native Escape acceptance")
    window.setReadOnly(True)
    window.resize(400, 50)
    window.ensurePolished()
    window.grab().save(str(root / "ready.png"))

    def save():
        nonlocal shown_once
        request = root / "show-request"
        if not shown_once and request.exists():
            if (
                request.read_text().strip()
                == f"{os.getpid()}:{process_start(os.getpid())}"
            ):
                shown_once = True
                window.show()
                window.activateWindow()
                window.setFocus()
                QTimer.singleShot(
                    200, lambda: window.grab().save(str(root / "shown.png"))
                )
        value = {
            "pid": os.getpid(),
            "start": process_start(os.getpid()),
            "sampled": time.monotonic(),
            "platform": app.platformName(),
            "active": window.isActiveWindow(),
            "focused": window.hasFocus(),
            "display_unset": "DISPLAY" not in os.environ,
            "owned_first_show_once": shown_once,
            "visible": window.isVisible(),
            **counts,
        }
        temporary = root / "state.pending"
        temporary.write_text(json.dumps(value))
        temporary.replace(root / "state.json")

    timer = QTimer()
    timer.timeout.connect(save)
    timer.start(20)
    notifier = QSocketNotifier(sys.stdin.fileno(), QSocketNotifier.Type.Read)
    notifier.activated.connect(
        lambda *_: app.quit() if sys.stdin.readline() else app.quit()
    )
    QTimer.singleShot(120000, app.quit)
    result = app.exec()
    save()
    return result


async def run(args, app):
    sys.path.insert(0, str(args.source_root.resolve()))
    import inkecho
    import inkecho.platform.escape as escape_module
    import inkecho.platform.portal_escape as portal_module
    import inkecho.platform.wayland_worker as worker
    from inkecho.platform.wayland_worker import INTERFACE, ROOT, SERVICE

    report = {
        "scope": "production TaskEscape Portal abort; guarded native ESC-only sender",
        "forced_signals": [],
        "callbacks": [],
        "status": [],
        "origins": {},
        "runtime_mode": "package" if args.package_mode else "source",
        "version": inkecho.__version__,
        "desktop_entry": str(args.desktop_entry),
        "desktop_sha256": hashlib.sha256(args.desktop_entry.read_bytes()).hexdigest(),
        "interpreter": str(Path(sys.executable).resolve()),
    }
    for module in (escape_module, portal_module, worker):
        origin = Path(module.__file__).resolve()
        if not origin.is_relative_to(args.source_root.resolve()):
            raise RuntimeError("Selected production source escaped root")
        report["origins"][module.__name__] = {
            "path": str(origin),
            "sha256": hashlib.sha256(origin.read_bytes()).hexdigest(),
        }
    audit(args.source_root, args.package_mode)
    guard = None
    backend = None
    process = None
    remote = None
    try:

        def cancelled():
            report["callbacks"].append(
                {
                    "time": time.monotonic(),
                    "guard_active": guard.active,
                    "revision": guard.revision,
                    "backend_closed": backend.closed if backend is not None else None,
                }
            )

        guard = escape_module.TaskEscape(cancelled)
        guard.unavailable.connect(report["status"].append)
        guard.set_active(True)
        args.progress.write_text(
            json.dumps({**report, "phase": "portal-authorizing"}, indent=2)
        )
        deadline = time.monotonic() + 185
        while not (guard.portal and guard.portal.armed):
            if report["callbacks"] or report["status"] or time.monotonic() > deadline:
                raise RuntimeError("Production portal did not arm")
            await asyncio.sleep(0.02)
        if report["callbacks"] or not guard.active:
            raise RuntimeError("Task cancelled before owned target; no input allowed")
        backend = guard.portal
        report["trigger_description"] = backend.trigger_description
        report["session"] = backend.session
        report["portal_peer"] = backend.bus.unique_name
        remote = worker.MutterSession()
        await remote.connect()
        remote.path = (await remote._call(ROOT, SERVICE, "CreateSession")).body[0]
        await remote._call(remote.path, INTERFACE, "Start")
        report["sender_started_before_owned_window"] = True
        args.owned_root.mkdir(mode=0o700)
        environment = {
            **os.environ,
            "QT_QPA_PLATFORM": "wayland",
            "GDK_BACKEND": "wayland",
        }
        environment.pop("DISPLAY", None)
        process = subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-B",
                str(Path(__file__).resolve()),
                "--target",
                str(args.owned_root),
                "--selected-root",
                str(args.source_root),
                "--runtime-mode",
                "package" if args.package_mode else "source",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
        started = process_start(process.pid)
        state_path = args.owned_root / "state.json"

        async def state(phase="guard", require_focus=True):
            if process.poll() is not None or process_start(process.pid) != started:
                raise RuntimeError("Owned native target process changed")
            value = json.loads(state_path.read_text())
            checked = time.monotonic()
            observed = {
                **value,
                "checked_at": checked,
                "age": checked - value["sampled"],
                "phase": phase,
            }
            report["last_guard_state"] = observed
            report.setdefault("guard_samples", []).append(observed)
            if (
                value["pid"] != process.pid
                or value["start"] != started
                or value["platform"] != "wayland"
                or not value["display_unset"]
                or (require_focus and (not value["active"] or not value["focused"]))
                or not 0 <= time.monotonic() - value["sampled"] <= 0.25
            ):
                raise RuntimeError("Fresh exact owned native target focus required")
            return value

        deadline = time.monotonic() + 5
        while not state_path.exists() or not (args.owned_root / "ready.png").exists():
            if time.monotonic() > deadline:
                raise RuntimeError("Owned native ready/screenshot missing")
            await asyncio.sleep(0.02)
        report["target_pre_show"] = await state(
            "prepared-not-shown", require_focus=False
        )
        args.progress.write_text(
            json.dumps(
                {
                    **report,
                    "phase": "owned-pre-show-await-emit",
                    "preview_scope": "own widget before first show",
                },
                indent=2,
            )
        )
        deadline = time.monotonic() + 90
        while not args.emit_file.exists():
            if time.monotonic() > deadline:
                raise RuntimeError("No reviewed exact target emit file")
            await asyncio.sleep(0.05)
        if args.emit_file.read_text().strip() != f"{process.pid}:{started}":
            raise RuntimeError("Emit file mismatches owned native target")
        # Root-approved first show of this exact owned child, never reactivation
        # of an old or user window. Root reviewed its PID/start and own preview.
        with (args.owned_root / "show-request").open("x") as show_request:
            show_request.write(f"{process.pid}:{started}\n")
        report["fixture_owned_first_show"] = {
            "pid": process.pid,
            "start": started,
            "count": 1,
        }
        stable_since = None
        deadline = time.monotonic() + 3
        while True:
            observed = await state("approved-first-show", require_focus=False)
            if (
                observed.get("owned_first_show_once")
                and observed["active"]
                and observed["focused"]
            ):
                stable_since = stable_since or time.monotonic()
                if time.monotonic() - stable_since >= 0.25:
                    break
            else:
                stable_since = None
            if time.monotonic() > deadline:
                raise RuntimeError("Owned first show did not gain stable native focus")
            await asyncio.sleep(0.02)

        async def send_escape():
            await state("before-key-down")
            try:
                await remote.key(1, True)
                await asyncio.sleep(0.03)
            finally:
                await remote.key(1, False)
            await asyncio.sleep(0.25)

        report["before"] = await state("emit-after-prepared-mutter")
        await send_escape()
        report["after_active"] = await state("after-active-escape")
        if (
            len(report["callbacks"]) != 1
            or guard.active
            or not backend.closed
            or backend.bus is not None
            or report["after_active"]["press"] != 0
        ):
            raise RuntimeError("Production cancel/abort path failed")
        report["production_peer_disconnected"] = True
        await asyncio.sleep(0.15)
        baseline = await state("idle-before")
        await send_escape()
        report["after_idle"] = await state("after-idle-escape")
        if (
            report["after_idle"]["press"] != baseline["press"] + 1
            or report["after_idle"]["release"] != baseline["release"] + 1
            or len(report["callbacks"]) != 1
        ):
            raise RuntimeError("Idle Escape swallowed after production disconnect")
        report["idle_escape_delivered"] = True
        report["ok"] = True
    except Exception as error:
        report.update(ok=False, error=f"{type(error).__name__}: {error}")
    finally:
        if remote is not None:
            try:
                await remote.close()
                report["sender_closed"] = True
            except Exception as error:
                report.update(ok=False, sender_cleanup_error=str(error))
        if guard is not None:
            try:
                await guard.shutdown()
                report["guard_shutdown"] = True
            except Exception as error:
                report.update(ok=False, guard_cleanup_error=str(error))
        if process is not None:
            try:
                process.stdin.write("close\n")
                process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            try:
                stdout, stderr = await asyncio.to_thread(process.communicate, timeout=5)
                report["target_terminal"] = {
                    "exit": process.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "forced_signals": [],
                }
                if process.returncode != 0:
                    report["ok"] = False
            except subprocess.TimeoutExpired as error:
                report.update(
                    ok=False, target_cleanup_error=str(error), target_still_running=True
                )
        try:
            report["loaded_inkecho_origins"] = audit(
                args.source_root, args.package_mode
            )
        except Exception as error:
            report.update(ok=False, runtime_audit_error=str(error))
        with args.output.open("x") as output:
            json.dump(report, output, indent=2)
        print(json.dumps(report), flush=True)
    return 0 if report.get("ok") else 1


def main():
    parser = argparse.ArgumentParser()
    selected = parser.add_mutually_exclusive_group(required=True)
    selected.add_argument("--source-root", type=Path)
    selected.add_argument("--package-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--progress", type=Path, required=True)
    parser.add_argument("--owned-root", type=Path, required=True)
    parser.add_argument("--emit-file", type=Path, required=True)
    parser.add_argument("--desktop-entry", type=Path)
    args = parser.parse_args()
    if any(
        p.exists()
        for p in (args.output, args.progress, args.owned_root, args.emit_file)
    ):
        parser.error("All owned output paths must be new")
    args.package_mode = args.package_root is not None
    args.source_root = bootstrap(
        args.package_root or args.source_root, args.package_mode
    )
    from inkecho.integration import APP_ID

    data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
    args.desktop_entry = (
        args.desktop_entry or data_home / "applications" / f"{APP_ID}.desktop"
    )
    if (
        args.desktop_entry.name != f"{APP_ID}.desktop"
        or args.desktop_entry.is_symlink()
        or not args.desktop_entry.is_file()
    ):
        raise RuntimeError("Existing legitimate own desktop entry required")
    entry = configparser.ConfigParser(interpolation=None, strict=True)
    entry.read_string(args.desktop_entry.read_text())
    if (
        entry["Desktop Entry"].get("Name") != "InkEcho"
        or entry["Desktop Entry"].get("Type") != "Application"
    ):
        raise RuntimeError("Own desktop identity does not match")
    os.environ.update(QT_QPA_PLATFORM="wayland", GDK_BACKEND="wayland")
    from PySide6.QtWidgets import QApplication

    from inkecho.runtime import ManagedQtEventLoop

    audit(args.source_root, args.package_mode)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    with ManagedQtEventLoop(app) as loop:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(run(args, app))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--target":
        child_parser = argparse.ArgumentParser()
        child_parser.add_argument("--target", type=Path, required=True)
        child_parser.add_argument("--selected-root", type=Path, required=True)
        child_parser.add_argument(
            "--runtime-mode", choices=("source", "package"), required=True
        )
        child_args = child_parser.parse_args()
        root = bootstrap(child_args.selected_root, child_args.runtime_mode == "package")
        __import__("PySide6.QtWidgets")
        audit(root, child_args.runtime_mode == "package")
        code = target(child_args.target)
        audit(root, child_args.runtime_mode == "package")
        raise SystemExit(code)
    raise SystemExit(main())
