"""Measure the X11 keyboard backend only in newly created, owned test windows.

No user page, shell, clipboard or input-method API is used. Each press verifies
its current target PID, process start time, and the exact owned X window.
"""

import argparse
import asyncio
import ctypes
import json
import os
import signal
import subprocess
import tempfile
import threading
import time
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
    def __init__(self, field, folder):
        self.field, self.folder, self.state = field, folder, None
        self.lock = threading.Lock()
        self.process = None

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
        env = dict(os.environ)
        for name in ("WAYLAND_DISPLAY", "PYTHONPATH", "PYTHONHOME", "LD_LIBRARY_PATH"):
            env.pop(name, None)
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
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
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
        "pacing_seconds": effective_pacing,
        "pacing_override_used": args.pacing is not None,
        "targets": [],
        "passed": False,
    }
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

    try:
        for target in args.targets:
            with tempfile.TemporaryDirectory(
                prefix="inkecho-keyboard-latency-"
            ) as temporary:
                folder = Path(temporary)
                output = folder / "text.json"
                browser = None
                process = None
                try:
                    if target.startswith("chrome-"):
                        browser = Browser(
                            target.removeprefix("chrome-"), folder
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
                            env=dict(os.environ, GDK_BACKEND="x11"),
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    identity = start_time(process.pid)
                    window = None
                    for _ in range(120):
                        if process.poll() is not None:
                            raise RuntimeError("Owned target exited")
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
                            pass
                        await asyncio.sleep(0.05)
                    if window is None:
                        raise RuntimeError("Owned target not ready")
                    focus(window)
                    await asyncio.sleep(0.35)
                    if int(command("getwindowpid", str(window))) != process.pid:
                        raise RuntimeError("Owned target PID mismatch")
                    events, first = [], []
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
                    count = await inputs.insert(
                        text, lambda: True, on_first_sent=first.append
                    )
                    elapsed = time.monotonic() - began
                    await asyncio.sleep(0.2)
                    received = (
                        browser.snapshot()
                        if browser
                        else json.loads(output.read_text())
                    )
                    actual = received["text"]
                    if target == "vte":
                        actual = actual.replace("\r", "\n")
                    exact = actual == text
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
                                    zip(text, actual, strict=False)
                                )
                                if pair[0] != pair[1]
                            ),
                            min(len(text), len(actual)) if not exact else None,
                        ),
                        "elapsed_seconds": round(elapsed, 4),
                        "seconds_per_codepoint": round(elapsed / len(text), 5),
                        "first_sent_seconds": round(first[0] - began, 5)
                        if first
                        else None,
                        "balanced_events": events == [True, False] * len(text),
                        "map_restored": driver._mapping() == original_map,
                    }
                    if target == "vte":
                        entry["raw_bytes_exact"] = (
                            bytes.fromhex(received["raw_hex"])
                            == text.replace("\n", "\r").encode()
                        )
                    report["targets"].append(entry)
                    inputs._send = original_send
                finally:
                    if browser:
                        browser.__exit__(None, None, None)
                    elif process is not None:
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
        report["passed"] = bool(report["targets"]) and all(
            row["exact"]
            and row["balanced_events"]
            and row["map_restored"]
            and row.get("raw_bytes_exact", True)
            for row in report["targets"]
        )
    finally:
        await inputs.aclose()
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
    parser.add_argument("--xdotool")
    parser.add_argument(
        "--environment",
        choices=("host-xwayland", "private-xvfb"),
        default="host-xwayland",
    )
    parser.add_argument("--pacing", nargs=3, type=float)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument(
        "--targets",
        nargs="+",
        choices=("chrome-textarea", "chrome-contenteditable", "gtk", "vte"),
        default=["chrome-textarea", "chrome-contenteditable", "gtk", "vte"],
    )
    args = parser.parse_args()
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
    report = asyncio.run(measure(args))
    encoded = json.dumps(report, sort_keys=True)
    if args.output:
        atomic_json(args.output, report)
    print(encoded)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
