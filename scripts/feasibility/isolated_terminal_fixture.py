#!/usr/bin/env python3
"""Owned native VTE in the private compositor; raw PTY child never runs a shell."""

import argparse
import json
import os
import signal
import sys
import tempfile
import time
from pathlib import Path

from isolated_browser_fixture import parent_pid, private_environment, write_json
from private_xwayland_environment import private_xwayland_environment


def collect(output):
    import tty

    tty.setraw(0)
    data = b""
    while True:
        write_json(
            output, {"raw_hex": data.hex(), "text": data.decode("utf-8", "replace")}
        )
        part = os.read(0, 4096)
        if not part:
            return
        data += part
        if len(data) > 8192:
            raise RuntimeError("Owned fixed-sample byte limit exceeded")


def fixture(args, raw_output):
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    gi.require_version("Vte", "2.91")
    from gi.repository import Gdk, Gio, GLib, Gtk, Vte

    application = Gtk.Application(
        application_id="io.github.Creammmmm.InkEcho.IsolatedTerminalFixture",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )
    child_pid = None
    child_fd = None
    child_running = False
    error = None

    def activate(app):
        nonlocal error
        display = Gdk.Display.get_default()
        expected_display = (
            "GdkX11Display" if args.target == "vte-xwayland" else "GdkWaylandDisplay"
        )
        if display is None or display.__gtype__.name != expected_display:
            error = "Requested private GDK display required"
            app.quit()
            return
        window = Gtk.ApplicationWindow(application=app)
        window.set_title("InkEcho isolated raw terminal")
        window.set_default_size(640, 360)
        terminal = Vte.Terminal()

        def spawned(_terminal, pid, failure, _data):
            nonlocal child_pid, child_fd, child_running, error
            if failure is not None:
                error = "Owned PTY child failed to start"
                app.quit()
            else:
                child_pid, child_running = pid, True
                try:
                    child_fd = os.pidfd_open(pid)
                    if parent_pid(pid) != os.getpid():
                        os.close(child_fd)
                        child_fd = None
                        child_running = False
                        error = "Owned PTY child parent identity changed"
                        app.quit()
                except (ProcessLookupError, FileNotFoundError):
                    if child_fd is not None:
                        os.close(child_fd)
                        child_fd = None
                    child_running = False
                    error = "Owned PTY child exited before readiness"
                    app.quit()

        def exited(_terminal, _status):
            nonlocal child_running
            child_running = False

        terminal.connect("child-exited", exited)
        terminal.spawn_async(
            Vte.PtyFlags.DEFAULT,
            None,
            [
                "/usr/bin/python3",
                str(Path(__file__).resolve()),
                "--child",
                str(raw_output),
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
        window.add(terminal)
        window.show_all()
        terminal.grab_focus()
        window.present()

        def publish():
            raw = json.loads(raw_output.read_text()) if raw_output.exists() else None
            ready = raw is not None and child_running
            if raw is not None:
                # Preserve terminal protocol bytes: Return is usually CR, not LF.
                write_json(args.text_output, raw["text"])
            write_json(
                args.state_output,
                {
                    "active": bool(ready and window.is_active()),
                    "focused": bool(
                        ready and window.is_active() and terminal.has_focus()
                    ),
                    "target_pid": os.getpid(),
                    "target_parent_pid": os.getppid(),
                    "sampled_at": time.monotonic(),
                    "native_display": display.__gtype__.name,
                    "target_backend": args.target,
                    "xwayland_pid": args.xwayland_pid,
                    "raw_child_pid": child_pid,
                    "raw_child_ready": ready,
                    "raw_hex": raw["raw_hex"] if raw else "",
                    "shell_started": False,
                },
            )
            return True

        publish()
        GLib.timeout_add(30, publish)
        GLib.timeout_add(int(args.seconds * 1000), lambda: (app.quit(), False)[1])

    signal.signal(signal.SIGTERM, lambda *_: GLib.idle_add(application.quit))
    signal.signal(signal.SIGINT, lambda *_: GLib.idle_add(application.quit))
    application.connect("activate", activate)
    try:
        application.run([])
    finally:
        if child_fd is not None:
            try:
                signal.pidfd_send_signal(child_fd, signal.SIGTERM)
            except ProcessLookupError:
                pass
            finally:
                os.close(child_fd)
            # pidfd identifies the original process even if VTE already reaped it.
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                try:
                    found, _ = os.waitpid(child_pid, os.WNOHANG)
                except ChildProcessError:
                    break
                if found:
                    break
                time.sleep(0.02)
    if error:
        raise RuntimeError(error)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--child":
        collect(Path(sys.argv[2]))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target", choices=("vte-wayland", "vte-xwayland"), default="vte-wayland"
    )
    parser.add_argument("--compositor-pid", type=int)
    parser.add_argument("--text-output", type=Path, required=True)
    parser.add_argument("--state-output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=120)
    args = parser.parse_args()
    if not 0 < args.seconds <= 300:
        parser.error("seconds must be within (0, 300]")
    private_environment()
    args.xwayland_pid = None
    if args.target == "vte-xwayland":
        args.xwayland_pid = private_xwayland_environment(args.compositor_pid)["pid"]
    elif os.environ.get("GDK_BACKEND") != "wayland":
        raise RuntimeError("Explicit private Wayland GDK backend required")
    with tempfile.TemporaryDirectory(prefix="inkecho-isolated-raw-pty-") as folder:
        fixture(args, Path(folder) / "raw.json")


if __name__ == "__main__":
    main()
