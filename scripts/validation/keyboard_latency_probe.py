"""Measure the X11 keyboard backend only in newly created, owned test windows.

No user page, shell, clipboard or input-method API is used. Each press verifies
its current target PID, process start time, and the exact owned X window.
"""

import argparse
import asyncio
import ctypes
import json
import os
import platform
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager, nullcontext
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SAMPLE = "你好 InkEcho，世界！ café Ω 😀\n第二行。"
ROOT = Path(__file__).resolve().parents[2]


def start_time(pid):
    return (Path("/proc") / str(pid) / "stat").read_text().rsplit(")", 1)[1].split()[19]


def atomic_json(path, data):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data))
    temporary.replace(path)


def fixture_environment():
    """Launch system GTK/Chrome without inheriting a packaged Python runtime."""
    environment = dict(os.environ)
    for name in ("WAYLAND_DISPLAY", "PYTHONPATH", "PYTHONHOME", "LD_LIBRARY_PATH"):
        environment.pop(name, None)
    environment["GDK_BACKEND"] = "x11"
    return environment


class ProbeFailure(RuntimeError):
    """Controlled failure metadata with any completed target results retained."""

    def __init__(self, report):
        self.report = report
        super().__init__(json.dumps(report["failure"], sort_keys=True))


class TargetReadinessError(RuntimeError):
    def __init__(self, metadata):
        self.metadata = metadata
        super().__init__(json.dumps(metadata, sort_keys=True))


def fixture_stderr(output, target):
    if output is not None:
        path = output.with_name(f"{output.stem}-fixture-{target}.log")
        return path, path.open("xb")
    descriptor, name = tempfile.mkstemp(
        prefix=f"inkecho-fixture-{target}-", suffix=".log"
    )
    return Path(name), os.fdopen(descriptor, "wb")


def readiness_metadata(target, reason, process, output, windows, began):
    return {
        "target": target,
        "reason": reason,
        "process_alive": process.poll() is None,
        "readyfile_exists": output.exists(),
        "visible_window_count": len(windows),
        "elapsed_seconds": round(time.monotonic() - began, 3),
    }


def x_property_number(source, name):
    if source is None:
        return None
    match = re.search(
        rf"^{re.escape(name)}(?:\([^\n)]*\))?[ \t]*(?:=|:[ \t]*window id #)[ \t]*"
        r"(0x[0-9a-fA-F]+|[0-9]+)[ \t]*$",
        source,
        re.MULTILINE,
    )
    if match:
        value = int(match[1], 16 if match[1].startswith("0x") else 10)
        return value if 0 <= value <= 0xFFFFFFFF else None
    return None


def readiness_scene(args, process, identity):
    """Read only fixed state from verified owned windows, before their cleanup."""
    deadline = time.monotonic() + 2

    def read(command):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        try:
            value = subprocess.check_output(
                command,
                text=True,
                stderr=subprocess.DEVNULL,
                env=fixture_environment(),
                timeout=min(0.4, remaining),
            )
            return value if len(value) <= 16384 else None
        except Exception:
            return None  # Read-only diagnostics never replace the primary error.

    root = read(
        ["/usr/bin/xprop", "-root", "_NET_CURRENT_DESKTOP", "_NET_ACTIVE_WINDOW"]
    )
    scene = {
        "current_desktop": x_property_number(root, "_NET_CURRENT_DESKTOP"),
        "active_window": x_property_number(root, "_NET_ACTIVE_WINDOW"),
        "locked_hint": None,
        "screensaver_active": None,
        "owned_windows": None,
    }
    session = getattr(args, "verified_session_id", None)
    if (
        args.environment == "ubuntu24-vm-x11"
        and isinstance(session, str)
        and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", session)
    ):
        locked = read(
            [
                "/usr/bin/loginctl",
                "show-session",
                session,
                "--property=LockedHint",
                "--value",
            ]
        )
        scene["locked_hint"] = (
            {"yes": True, "no": False}.get(locked.strip())
            if locked is not None
            else None
        )
        active = read(
            [
                "/usr/bin/gdbus",
                "call",
                "--session",
                "--dest",
                "org.gnome.ScreenSaver",
                "--object-path",
                "/org/gnome/ScreenSaver",
                "--method",
                "org.gnome.ScreenSaver.GetActive",
            ]
        )
        scene["screensaver_active"] = (
            {"(true,)": True, "(false,)": False}.get(active.strip())
            if active is not None
            else None
        )
    candidates = read(
        [args.xdotool, "search", "--limit", "8", "--pid", str(process.pid)]
    )
    if candidates is None:
        return scene
    scene["owned_windows"] = []
    states = {
        "_NET_WM_STATE_" + name
        for name in (
            "MODAL",
            "STICKY",
            "MAXIMIZED_VERT",
            "MAXIMIZED_HORZ",
            "SHADED",
            "SKIP_TASKBAR",
            "SKIP_PAGER",
            "HIDDEN",
            "FULLSCREEN",
            "ABOVE",
            "BELOW",
            "DEMANDS_ATTENTION",
            "FOCUSED",
        )
    }
    for candidate in candidates.splitlines()[:8]:
        if (
            not re.fullmatch(r"[0-9]{1,10}", candidate)
            or not 0 < int(candidate) <= 0xFFFFFFFF
        ):
            continue
        candidate = str(int(candidate))
        try:
            if process.poll() is not None or start_time(process.pid) != identity:
                break
        except Exception:
            break
        pid = read(["/usr/bin/xprop", "-id", candidate, "_NET_WM_PID"])
        if x_property_number(pid, "_NET_WM_PID") != process.pid:
            continue  # Never collect a foreign window's state or title.
        info = read(["/usr/bin/xwininfo", "-id", candidate, "-stats"])
        properties = read(
            [
                "/usr/bin/xprop",
                "-id",
                candidate,
                "WM_STATE",
                "_NET_WM_STATE",
                "_NET_WM_DESKTOP",
            ]
        )
        entry = {
            "window": int(candidate),
            "pid_matches": True,
            "map_state": None,
            "wm_state": None,
            "net_wm_state": None,
            "desktop": x_property_number(properties, "_NET_WM_DESKTOP"),
        }
        if info is not None:
            mapped = re.search(
                r"^\s*Map State:\s*(IsUnMapped|IsUnviewable|IsViewable)\s*$",
                info,
                re.MULTILINE,
            )
            entry["map_state"] = mapped[1] if mapped else None
        if properties is not None:
            wm = re.search(
                r"^\s*window state:\s*(Normal|Iconic|Withdrawn)\s*$",
                properties,
                re.MULTILINE,
            )
            entry["wm_state"] = wm[1] if wm else None
            net = re.search(
                r"^_NET_WM_STATE\(ATOM\)[ \t]*=[ \t]*([^\n]*)$",
                properties,
                re.MULTILINE,
            )
            if net:
                tokens = [token.strip() for token in net[1].split(",") if token.strip()]
                entry["net_wm_state"] = (
                    tokens
                    if len(tokens) <= 32 and all(token in states for token in tokens)
                    else None
                )
        scene["owned_windows"].append(entry)
    return scene


def probe_failure(
    report,
    target,
    phase,
    error,
    events,
    first,
    driver,
    original_map,
    log_path,
    mapping_counts=None,
):
    from inkecho.platform.keyboard import KeyboardError

    failure = {"target": target, "phase": phase, "reason": "target_failed"}
    if isinstance(error, TargetReadinessError):
        failure.update(error.metadata)
    if isinstance(error, KeyboardError) and error.code in KeyboardError.CODES:
        failure["keyboard_error_code"] = error.code
    failure.update(
        {
            "presses_sent": sum(events),
            "releases_sent": len(events) - sum(events),
            "first_callback_count": len(first),
            "map_restored": None,
            "fixture_stderr_log": str(log_path) if log_path is not None else None,
        }
    )
    try:
        failure["map_restored"] = driver._mapping() == original_map
    except Exception:
        pass  # Diagnostics cannot replace the primary failure.
    report["failure"] = failure
    if mapping_counts is not None:
        failure["mapping_counts"] = dict(mapping_counts)
    report["passed"] = False
    return ProbeFailure(report)


def verify_private_xvfb():
    """Prove the selected X socket belongs to this launcher's private server."""
    pid = int(os.environ.get("INKECHO_PRIVATE_XVFB", "0"))
    process = Path("/proc") / str(pid)
    expected = ROOT / "build/listening-test-tools/root/usr/bin/Xvfb"
    stat = (process / "stat").read_text().rsplit(")", 1)[1].split()
    if (
        process.joinpath("exe").resolve() != expected.resolve()
        or int(stat[1]) != os.getppid()
        or not os.environ.get("DISPLAY", "").startswith(":")
    ):
        raise RuntimeError("Private owned Xvfb process required")
    number = os.environ["DISPLAY"][1:].split(".")[0]
    if not number.isdigit():
        raise RuntimeError("Private Xvfb display number required")
    sockets = set()
    for path in (process / "fd").iterdir():
        try:
            target = os.readlink(path)
        except FileNotFoundError:
            continue
        if target.startswith("socket:["):
            sockets.add(target[8:-1])
    expected_path = f"/tmp/.X11-unix/X{number}"
    if not any(
        len(parts := line.split()) >= 8
        and parts[6] in sockets
        and parts[7].lstrip("@") == expected_path
        for line in Path("/proc/net/unix").read_text().splitlines()[1:]
    ):
        raise RuntimeError("Display socket is not owned by the private Xvfb")


def verify_ubuntu24_vm_x11():
    """Require guest OS/virtualization and a real, current-user X11 login."""
    release = {}
    with Path("/etc/os-release").open() as stream:
        source = stream.read(65537)
    if len(source) > 65536:
        raise RuntimeError("OS release metadata is too large")
    for line in source.splitlines():
        key, separator, value = line.partition("=")
        if separator and key in {"ID", "VERSION_ID", "PRETTY_NAME"}:
            fields = shlex.split(value, comments=True)
            if len(fields) != 1:
                raise RuntimeError("Invalid OS release metadata")
            release[key] = fields[0]
    if release.get("ID") != "ubuntu" or release.get("VERSION_ID") != "24.04":
        raise RuntimeError("Actual Ubuntu 24.04 guest required")
    if (
        os.environ.get("XDG_SESSION_TYPE") != "x11"
        or "WAYLAND_DISPLAY" in os.environ
        or not os.environ.get("DISPLAY")
    ):
        raise RuntimeError("Guest X11 environment without Wayland required")
    session = os.environ.get("XDG_SESSION_ID", "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", session):
        raise RuntimeError("Actual graphical logind session ID required")
    virtual = subprocess.check_output(
        ["/usr/bin/systemd-detect-virt", "--vm"], text=True, timeout=3
    ).strip()
    if virtual not in {"kvm", "qemu"}:
        raise RuntimeError("Actual KVM/QEMU guest required")
    properties = subprocess.check_output(
        [
            "/usr/bin/loginctl",
            "show-session",
            session,
            "--property=User",
            "--property=Type",
            "--property=Desktop",
        ],
        text=True,
        timeout=3,
    )
    login = dict(line.split("=", 1) for line in properties.splitlines() if "=" in line)
    if login.get("User") != str(os.getuid()) or login.get("Type") != "x11":
        raise RuntimeError("Current user's actual graphical X11 login required")
    return {
        "os_id": release["ID"],
        "os_version": release["VERSION_ID"],
        "os_pretty_name": release.get("PRETTY_NAME", ""),
        "kernel": platform.release(),
        "virtualization": virtual,
        "session_type": login["Type"],
        "session_desktop": login.get("Desktop", ""),
        "session_user_matches_process": True,
        "wayland_display_present": False,
    }


def fixture(args):
    if args.fixture == "raw-child":
        import tty

        tty.setraw(0)
        data = b""
        while True:
            atomic_json(
                args.output,
                {"raw_hex": data.hex(), "text": data.decode("utf8", "replace")},
            )
            part = os.read(0, 4096)
            if not part:
                return
            data += part
            if len(data) > 32000:
                raise RuntimeError("Owned fixture byte cap exceeded")
    import gi

    gi.require_version("Gtk", "3.0")
    from gi.repository import GLib, Gtk

    child_pid = None
    child_fd = None
    window = Gtk.Window(title="InkEcho keyboard latency owned fixture")
    window.set_default_size(640, 360)
    window.connect("destroy", Gtk.main_quit)
    if args.fixture == "gtk":
        widget = Gtk.TextView()
        buffer = widget.get_buffer()

        def changed(*_):
            begin, end = buffer.get_bounds()
            atomic_json(args.output, {"text": buffer.get_text(begin, end, True)})

        buffer.connect("changed", changed)
        changed()
    else:
        gi.require_version("Vte", "2.91")
        from gi.repository import Vte

        widget = Vte.Terminal()

        def spawned(_widget, pid, error, _data):
            nonlocal child_pid, child_fd
            if error is not None:
                window.destroy()
            else:
                child_pid = pid
                child_fd = os.pidfd_open(pid)

        widget.spawn_async(
            Vte.PtyFlags.DEFAULT,
            None,
            [
                "/usr/bin/python3",
                str(Path(__file__).resolve()),
                "--fixture",
                "raw-child",
                "--output",
                str(args.output),
            ],
            None,
            GLib.SpawnFlags.DEFAULT,
            None,
            None,
            -1,
            None,
            spawned,
            None,
        )
    window.add(widget)
    window.show_all()
    widget.grab_focus()
    window.present()
    signal.signal(signal.SIGTERM, lambda *_: GLib.idle_add(window.destroy))
    try:
        Gtk.main()
    finally:
        if child_fd is not None:
            try:
                signal.pidfd_send_signal(child_fd, signal.SIGTERM)
            except ProcessLookupError:
                pass
            finally:
                os.close(child_fd)


class Browser:
    def __init__(self, field, folder, stderr=subprocess.DEVNULL):
        self.field, self.folder, self.state = field, folder, None
        self.lock = threading.Lock()
        self.process = None
        self.stderr = stderr

    def __enter__(self):
        target = (
            '<textarea id="target" autofocus rows="10" cols="65"></textarea>'
            if self.field == "textarea"
            else '<div id="target" contenteditable="true" autofocus '
            'style="min-height:300px"></div>'
        )
        page = (
            '<!doctype html><meta charset="utf-8">'
            "<title>InkEcho keyboard owned browser</title>"
            + target
            + '<script>const f=document.getElementById("target");let seq=0;'
            'function record(){fetch("/state",{method:"POST",body:JSON.stringify({'
            'sequence:++seq,text:(f.value??f.innerText).replace(/\\r/g,""),'
            "focused:document.hasFocus()&&document.activeElement===f})})}"
            'f.addEventListener("input",record);'
            'window.addEventListener("load",()=>{f.focus();record()});'
            'window.addEventListener("focus",()=>{f.focus();record()});'
            "setInterval(record,50);</script>"
        ).encode()
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(page)

            def do_POST(self):
                size = int(self.headers.get("Content-Length", 0))
                if self.path != "/state" or not 0 < size <= 32000:
                    self.send_error(400)
                    return
                state = json.loads(self.rfile.read(size))
                state["sampled_at"] = time.monotonic()
                with fixture.lock:
                    if (
                        fixture.state is None
                        or state["sequence"] > fixture.state["sequence"]
                    ):
                        fixture.state = state
                self.send_response(204)
                self.end_headers()

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.process = subprocess.Popen(
            [
                "google-chrome",
                "--ozone-platform=x11",
                "--class=InkEchoLatencyOwned",
                f"--user-data-dir={self.folder / 'profile'}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-networking",
                "--disable-component-update",
                "--disable-sync",
                "--password-store=basic",
                "--no-proxy-server",
                "--host-resolver-rules=MAP * ~NOTFOUND, "
                "EXCLUDE 127.0.0.1, EXCLUDE localhost",
                f"--app=http://127.0.0.1:{self.server.server_port}/",
            ],
            env=fixture_environment(),
            stdout=subprocess.DEVNULL,
            stderr=self.stderr,
        )
        return self

    def snapshot(self):
        with self.lock:
            return dict(self.state) if self.state is not None else None

    def __exit__(self, *_):
        if self.process is not None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()


@contextmanager
def restore_policy_scope(driver, policy, counts):
    """Test-only method scope, never a replacement insertion implementation."""
    candidate = policy == "end-of-insertion-candidate"
    original_restore, original_write = driver.restore, driver._write

    def write(values):
        result = original_write(values)
        counts["mapping_writes"] += 1
        return result

    def restore():
        if candidate:
            counts["deferred_restore_calls"] += 1
            return None
        counts["restore_calls"] += 1
        result = original_restore()
        counts["successful_restore_calls"] += 1
        return result

    driver.restore, driver._write = restore, write
    try:
        yield
    finally:
        # Restore the real method before synchronous mandatory ownership cleanup.
        driver.restore = original_restore
        try:
            if candidate:
                counts["restore_calls"] += 1
                original_restore()
                counts["successful_restore_calls"] += 1
        finally:
            driver._write = original_write


async def insert_sample(
    inputs,
    text,
    events,
    first,
    cancel_after=None,
    *,
    restore_policy=None,
    mapping_counts=None,
):
    """Cancel only after N successful presses; preserve backend cleanup."""
    from inkecho.platform.keyboard import KeyboardError

    def active():
        return cancel_after is None or sum(events) < cancel_after

    try:
        scope = (
            restore_policy_scope(inputs._driver, restore_policy, mapping_counts)
            if mapping_counts is not None
            else nullcontext()
        )
        with scope:
            count = await inputs.insert(text, active, on_first_sent=first.append)
    except (asyncio.CancelledError, KeyboardError) as error:
        if (
            cancel_after is None
            or sum(events) != cancel_after
            or (isinstance(error, KeyboardError) and error.code != "input_cancelled")
        ):
            raise
        return cancel_after, True
    return count, False


async def measure(args):
    from inkecho.platform import keyboard

    inputs = keyboard.KeyboardInput()
    await inputs.connect()
    driver = inputs._driver
    original_map = driver._mapping()
    effective_pacing = args.pacing or [
        keyboard.MAP_SETTLE_SECONDS,
        keyboard.PRESS_SETTLE_SECONDS,
        keyboard.RELEASE_SETTLE_SECONDS,
    ]
    report = {
        "platform": args.environment,
        "event_loop": "qt" if args.qt_loop else "asyncio",
        "event_loop_class": type(asyncio.get_running_loop()).__name__,
        "pacing_seconds": effective_pacing,
        "pacing_override_used": args.pacing is not None,
        "targets": [],
        "passed": False,
        "restore_policy": args.restore_policy,
        "candidate_policy": args.restore_policy
        if args.restore_policy == "end-of-insertion-candidate"
        else None,
        "production_behavior_modified": args.restore_policy
        == "end-of-insertion-candidate",
    }
    if args.environment == "ubuntu24-vm-x11":
        report["environment_metadata"] = args.environment_metadata
        if args.qt_loop:
            from PySide6.QtCore import qVersion

            report["qt_version"] = qVersion()
    if args.cancel_after is not None:
        report["measurement"] = "partial_cancel"
        report["cancel_after"] = args.cancel_after
    (
        keyboard.MAP_SETTLE_SECONDS,
        keyboard.PRESS_SETTLE_SECONDS,
        keyboard.RELEASE_SETTLE_SECONDS,
    ) = effective_pacing

    def command(*parts):
        return subprocess.check_output(
            [args.xdotool, *parts], text=True, timeout=3
        ).strip()

    def focus(window):
        if args.environment == "private-xvfb":
            command("windowfocus", "--sync", str(window))
            # A private server has no WM. Publish its owned active-window property.
            method = driver.x11.XChangeProperty
            method.argtypes = [
                ctypes.c_void_p,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.POINTER(ctypes.c_ubyte),
                ctypes.c_int,
            ]
            value = ctypes.c_ulong(window)
            method(
                driver.display,
                driver.root,
                driver.active_atom,
                33,
                32,
                0,
                ctypes.cast(ctypes.byref(value), ctypes.POINTER(ctypes.c_ubyte)),
                1,
            )
            driver.x11.XSync(driver.display, 0)
        else:
            command("windowactivate", "--sync", str(window))

    target = None
    phase = "starting"
    events, first = [], []
    log_path = None
    mapping_counts = None
    try:
        for target in args.targets:
            with tempfile.TemporaryDirectory(
                prefix="inkecho-keyboard-latency-"
            ) as temporary:
                folder = Path(temporary)
                output = folder / "text.json"
                browser = None
                process = None
                stderr = None
                phase = "starting"
                events, first = [], []
                log_path = None
                mapping_counts = None
                try:
                    log_path, stderr = fixture_stderr(args.output, target)
                    if target.startswith("chrome-"):
                        browser = Browser(
                            target.removeprefix("chrome-"), folder, stderr
                        ).__enter__()
                        process = browser.process
                    else:
                        process = subprocess.Popen(
                            [
                                "/usr/bin/python3",
                                str(Path(__file__).resolve()),
                                "--fixture",
                                target,
                                "--output",
                                str(output),
                            ],
                            env=fixture_environment(),
                            stdout=subprocess.DEVNULL,
                            stderr=stderr,
                        )
                    identity = start_time(process.pid)
                    window = None
                    windows = []
                    waiting_since = time.monotonic()
                    for _ in range(120):
                        if process.poll() is not None:
                            raise TargetReadinessError(
                                readiness_metadata(
                                    target,
                                    "target_exited",
                                    process,
                                    output,
                                    windows,
                                    waiting_since,
                                )
                            )
                        try:
                            windows = command(
                                "search", "--onlyvisible", "--pid", str(process.pid)
                            ).splitlines()
                            ready = (
                                browser.snapshot() is not None
                                if browser
                                else output.exists()
                            )
                            if windows and ready:
                                window = int(windows[0])
                                break
                        except subprocess.CalledProcessError:
                            windows = []
                        await asyncio.sleep(0.05)
                    if window is None:
                        metadata = readiness_metadata(
                            target,
                            "target_not_ready",
                            process,
                            output,
                            windows,
                            waiting_since,
                        )
                        try:
                            metadata["scene"] = readiness_scene(args, process, identity)
                        except Exception:
                            metadata["scene"] = None
                        raise TargetReadinessError(metadata)
                    phase = "focusing"
                    focus(window)
                    await asyncio.sleep(0.35)
                    if int(command("getwindowpid", str(window))) != process.pid:
                        raise RuntimeError("Owned target PID mismatch")
                    original_send = inputs._send

                    def guard(
                        current,
                        code,
                        pressed,
                        process=process,
                        identity=identity,
                        window=window,
                        browser=browser,
                        original_send=original_send,
                        events=events,
                    ):
                        if pressed:
                            active = driver._property(driver.root, driver.active_atom)
                            if (
                                process.poll() is not None
                                or start_time(process.pid) != identity
                                or driver._property(active, driver.pid_atom)
                                != process.pid
                                or active != window
                                or driver.focus() != current
                            ):
                                raise RuntimeError(
                                    "Refusing input outside owned target"
                                )
                            if browser:
                                state = browser.snapshot()
                                if (
                                    not state
                                    or not state["focused"]
                                    or time.monotonic() - state["sampled_at"] > 0.25
                                ):
                                    raise RuntimeError("Owned browser field lost focus")
                        original_send(current, code, pressed)
                        events.append(pressed)

                    inputs._send = guard
                    text = SAMPLE * args.repeat
                    began = time.monotonic()
                    phase = "inserting"
                    mapping_counts = {
                        "mapping_writes": 0,
                        "restore_calls": 0,
                        "successful_restore_calls": 0,
                        "deferred_restore_calls": 0,
                    }
                    count, cancelled = await insert_sample(
                        inputs,
                        text,
                        events,
                        first,
                        args.cancel_after,
                        restore_policy=args.restore_policy,
                        mapping_counts=mapping_counts,
                    )
                    elapsed = time.monotonic() - began
                    phase = "readback"
                    await asyncio.sleep(0.2)
                    received = (
                        browser.snapshot()
                        if browser
                        else json.loads(output.read_text())
                    )
                    actual = received["text"]
                    if target == "vte":
                        actual = actual.replace("\r", "\n")
                    expected = (
                        text if args.cancel_after is None else text[: args.cancel_after]
                    )
                    exact = actual == expected
                    entry = {
                        "target": target,
                        "codepoints": len(text),
                        "count": count,
                        "received_codepoints": len(actual),
                        "exact": exact,
                        "first_mismatch_index": next(
                            (
                                index
                                for index, pair in enumerate(
                                    zip(expected, actual, strict=False)
                                )
                                if pair[0] != pair[1]
                            ),
                            min(len(expected), len(actual)) if not exact else None,
                        ),
                        "elapsed_seconds": round(elapsed, 4),
                        "seconds_per_codepoint": round(elapsed / len(text), 5)
                        if args.cancel_after is None
                        else None,
                        "first_sent_seconds": round(first[0] - began, 5)
                        if first
                        else None,
                        "balanced_events": events == [True, False] * len(expected),
                        "map_restored": driver._mapping() == original_map,
                        "mapping_counts": dict(mapping_counts),
                    }
                    if args.cancel_after is not None:
                        recorded_events = len(events)
                        await asyncio.sleep(0.5)
                        later = json.loads(output.read_text())["text"]
                        entry.update(
                            {
                                "cancelled": cancelled,
                                "expected_prefix": exact,
                                "no_late_tail": later == actual == expected
                                and len(events) == recorded_events,
                                "late_tail_wait_seconds": 0.5,
                            }
                        )
                        entry["map_restored"] = driver._mapping() == original_map
                    if target == "vte":
                        entry["raw_bytes_exact"] = (
                            bytes.fromhex(received["raw_hex"])
                            == text.replace("\n", "\r").encode()
                        )
                    report["targets"].append(entry)
                    inputs._send = original_send
                finally:
                    try:
                        if browser:
                            browser.__exit__(None, None, None)
                        elif process is not None:
                            process.terminate()
                            try:
                                process.wait(timeout=3)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait()
                    except Exception:
                        phase = "cleanup"
                        raise
                    finally:
                        if stderr is not None:
                            stderr.close()
        report["passed"] = bool(report["targets"]) and all(
            row["exact"]
            and row["balanced_events"]
            and row["map_restored"]
            and row.get("raw_bytes_exact", True)
            and row.get("cancelled", True)
            and row.get("expected_prefix", True)
            and row.get("no_late_tail", True)
            for row in report["targets"]
        )
    except Exception as error:
        raise probe_failure(
            report,
            target,
            phase,
            error,
            events,
            first,
            driver,
            original_map,
            log_path,
            mapping_counts,
        ) from error
    finally:
        try:
            await inputs.aclose()
        except Exception as error:
            raise probe_failure(
                report,
                target,
                "cleanup",
                error,
                events,
                first,
                driver,
                original_map,
                log_path,
                mapping_counts,
            ) from error
    return report


def wayland_callback_probe(output):
    """Reuse the reviewed natural-focus owned-target guard, without pacing edits."""
    from types import SimpleNamespace

    from host_mixed_wayland_probe import load_package, run

    sources = load_package(ROOT / "src")
    from inkecho.platform.wayland_keyboard import WaylandKeyboardInput

    original = WaylandKeyboardInput.insert
    observed = []

    async def insert(self, text, can_continue, **kwargs):
        def first(sent_at):
            observed.append((sent_at, time.monotonic()))

        kwargs["on_first_sent"] = first
        return await original(self, text, can_continue, **kwargs)

    WaylandKeyboardInput.insert = insert
    args = SimpleNamespace(
        package_root=ROOT / "src", field="contenteditable", map_settle=0, key_settle=0
    )
    report = {"passed": False, "production_modules": sources}
    try:
        asyncio.run(run(args, report))
    finally:
        WaylandKeyboardInput.insert = original
        report["first_callback_count"] = len(observed)
        report["callback_after_press_seconds"] = (
            round(observed[0][1] - observed[0][0], 5) if observed else None
        )
        report["first_callback_valid"] = bool(
            len(observed) == 1 and 0 <= observed[0][1] - observed[0][0] <= 5
        )
        report["passed"] = report["passed"] and report["first_callback_valid"]
        atomic_json(output, report)
        print(json.dumps(report, sort_keys=True))
    if not report["passed"]:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture", choices=("gtk", "vte", "raw-child"), help=argparse.SUPPRESS
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--wayland-callback", action="store_true")
    parser.add_argument("--qt-loop", action="store_true")
    parser.add_argument("--xdotool")
    parser.add_argument(
        "--environment",
        choices=("host-xwayland", "private-xvfb", "ubuntu24-vm-x11"),
        default="host-xwayland",
    )
    parser.add_argument("--pacing", nargs=3, type=float)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument(
        "--restore-policy",
        choices=("per-character-production", "end-of-insertion-candidate"),
        default="per-character-production",
    )
    parser.add_argument("--cancel-after", type=int)
    parser.add_argument(
        "--targets",
        nargs="+",
        choices=("chrome-textarea", "chrome-contenteditable", "gtk", "vte"),
        default=["chrome-textarea", "chrome-contenteditable", "gtk", "vte"],
    )
    args = parser.parse_args()
    if args.restore_policy == "end-of-insertion-candidate" and (
        args.fixture or args.wayland_callback
    ):
        parser.error("restore candidate is only for the owned X11 measurement")
    if args.cancel_after is not None and (
        args.fixture
        or args.wayland_callback
        or args.targets != ["gtk"]
        or not 1 <= args.cancel_after < len(SAMPLE) * args.repeat
    ):
        parser.error(
            "cancel-after requires only GTK and a proper nonempty sample prefix"
        )
    if args.fixture:
        fixture(args)
        return
    if args.wayland_callback:
        if not args.output:
            parser.error("Wayland callback validation requires --output")
        wayland_callback_probe(args.output)
        return
    if (
        not args.xdotool
        or not 1 <= args.repeat <= 10
        or (
            args.pacing is not None
            and not all(0.001 <= value <= 0.04 for value in args.pacing)
        )
    ):
        parser.error("bounded pacing, repeat and xdotool are required")
    if (
        args.environment == "host-xwayland"
        and os.environ.get("XDG_SESSION_TYPE") != "wayland"
    ):
        parser.error("coordinated host Wayland session required")
    if args.environment == "private-xvfb":
        verify_private_xvfb()
    if args.environment == "ubuntu24-vm-x11":
        args.environment_metadata = verify_ubuntu24_vm_x11()
        args.verified_session_id = os.environ["XDG_SESSION_ID"]
    try:
        if args.qt_loop:
            from PySide6.QtWidgets import QApplication

            from inkecho.runtime import ManagedQtEventLoop

            application = QApplication([])
            application.setQuitOnLastWindowClosed(False)
            with ManagedQtEventLoop(application) as loop:
                report = loop.run_until_complete(measure(args))
        else:
            report = asyncio.run(measure(args))
    except ProbeFailure as error:
        report = error.report
        print(
            "Owned keyboard validation failed; see failure metadata.", file=sys.stderr
        )
    encoded = json.dumps(report, sort_keys=True)
    if args.output:
        atomic_json(args.output, report)
    print(encoded)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
