#!/usr/bin/env python3
"""Two owned GTK editors on one private native/XWayland compositor; sends no keys."""

import argparse
import json
import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from isolated_browser_fixture import write_json
from private_xwayland_environment import private_xwayland_environment


def editor(args):
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, Gio, GLib, Gtk

    xlib = xdisplay = None
    if args.child == "xwayland" and not os.environ.get("INKECHO_MIXED_NO_X_DIAGNOSTIC"):
        import ctypes
        import ctypes.util

        gi.require_version("GdkX11", "3.0")
        from gi.repository import GdkX11

        xlib = ctypes.CDLL(ctypes.util.find_library("X11"))
        xlib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        xlib.XOpenDisplay.restype = ctypes.c_void_p
        xlib.XGetInputFocus.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
        ]
        xlib.XkbKeycodeToKeysym.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ubyte,
            ctypes.c_int,
            ctypes.c_int,
        ]
        xlib.XkbKeycodeToKeysym.restype = ctypes.c_ulong
        xlib.XQueryPointer.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_uint),
        ]
        xlib.XQueryTree.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_uint),
        ]
        xlib.XFree.argtypes = [ctypes.c_void_p]
        xlib.XCloseDisplay.argtypes = [ctypes.c_void_p]
        xdisplay = xlib.XOpenDisplay(os.fsencode(os.environ["DISPLAY"]))
        if not xdisplay:
            raise RuntimeError("Private X11 diagnostic connection unavailable")

    app = Gtk.Application(
        application_id=f"io.github.Creammmmm.InkEcho.MixedEditorFixture.{args.child}",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )
    error = None

    def activate(application):
        nonlocal error
        display = Gdk.Display.get_default()
        expected = "GdkWaylandDisplay" if args.child == "native" else "GdkX11Display"
        if display is None or display.__gtype__.name != expected:
            error = "Requested private editor backend unavailable"
            application.quit()
            return
        window = Gtk.ApplicationWindow(application=application)
        window.set_title(f"InkEcho private {args.child} editor")
        window.set_default_size(520, 300)
        widget = Gtk.TextView()
        buffer = widget.get_buffer()
        activation_serial = None
        received_keys = []
        received_buttons = []

        def button_pressed(_widget, event):
            received_buttons.append(
                {"button": event.button, "x": event.x, "y": event.y}
            )
            return False

        widget.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        widget.connect("button-press-event", button_pressed)

        def key_pressed(_widget, event):
            received_keys.append(
                {"keyval": event.keyval, "hardware_keycode": event.hardware_keycode}
            )
            return False

        widget.connect("key-press-event", key_pressed)

        def text_changed(*_):
            write_json(args.text_output, buffer.get_text(*buffer.get_bounds(), True))

        def state_changed():
            nonlocal activation_serial
            if args.activate_file and args.activate_file.exists():
                requested = json.loads(args.activate_file.read_text())
                if (
                    requested["target"] == args.child
                    and requested["serial"] != activation_serial
                ):
                    activation_serial = requested["serial"]
                    window.present()
                    widget.grab_focus()
            xstate = {}
            if xdisplay:
                focus = ctypes.c_ulong()
                revert = ctypes.c_int()
                xlib.XGetInputFocus(xdisplay, ctypes.byref(focus), ctypes.byref(revert))
                xid = GdkX11.X11Window.get_xid(window.get_window())
                ancestor = focus.value
                owned_focus = ancestor == xid
                for _ in range(20):
                    if owned_focus or ancestor in (0, 1):
                        break
                    root = ctypes.c_ulong()
                    parent = ctypes.c_ulong()
                    children = ctypes.c_void_p()
                    count = ctypes.c_uint()
                    valid = xlib.XQueryTree(
                        xdisplay,
                        ancestor,
                        ctypes.byref(root),
                        ctypes.byref(parent),
                        ctypes.byref(children),
                        ctypes.byref(count),
                    )
                    if children:
                        xlib.XFree(children)
                    if not valid or parent.value == ancestor:
                        break
                    ancestor = parent.value
                    owned_focus = ancestor == xid
                pointer_root, pointer_child = ctypes.c_ulong(), ctypes.c_ulong()
                root_x, root_y = ctypes.c_int(), ctypes.c_int()
                win_x, win_y, mask = ctypes.c_int(), ctypes.c_int(), ctypes.c_uint()
                xlib.XQueryPointer(
                    xdisplay,
                    xid,
                    ctypes.byref(pointer_root),
                    ctypes.byref(pointer_child),
                    ctypes.byref(root_x),
                    ctypes.byref(root_y),
                    ctypes.byref(win_x),
                    ctypes.byref(win_y),
                    ctypes.byref(mask),
                )
                xstate = {
                    "x_ae13_keysym": xlib.XkbKeycodeToKeysym(xdisplay, 132, 0, 0),
                    "pointer_root_xy": [root_x.value, root_y.value],
                    "pointer_window_xy": [win_x.value, win_y.value],
                    "x_input_focus": focus.value,
                    "x_focus_owned": owned_focus,
                    "x_window": GdkX11.X11Window.get_xid(window.get_window()),
                    "x_display": os.environ["DISPLAY"],
                    "window_origin": list(window.get_window().get_origin()),
                }
            write_json(
                args.state_output,
                {
                    "active": window.is_active(),
                    "focused": window.is_active() and widget.has_focus(),
                    "target_pid": os.getpid(),
                    "target_parent_pid": os.getppid(),
                    "sampled_at": time.monotonic(),
                    "display_backend": display.__gtype__.name,
                    "activation_serial": activation_serial,
                    "received_keys": received_keys,
                    "received_buttons": received_buttons,
                    **xstate,
                },
            )
            return True

        buffer.connect("changed", text_changed)
        text_changed()
        window.add(widget)
        window.show_all()
        widget.grab_focus()
        window.present()
        state_changed()
        GLib.timeout_add(30, state_changed)
        GLib.timeout_add(
            int(args.seconds * 1000), lambda: (application.quit(), False)[1]
        )

    signal.signal(signal.SIGTERM, lambda *_: GLib.idle_add(app.quit))
    app.connect("activate", activate)
    try:
        app.run([])
    finally:
        if xdisplay:
            xlib.XCloseDisplay(xdisplay)
    if error:
        raise RuntimeError(error)


def coordinate(args, folder):
    native_environment = dict(os.environ)
    evidence = private_xwayland_environment(args.compositor_pid)
    xwayland_environment = dict(os.environ)
    native_environment["GDK_BACKEND"] = "wayland"
    children = {}
    try:
        for kind, environment in (
            ("native", native_environment),
            ("xwayland", xwayland_environment),
        ):
            children[kind] = subprocess.Popen(
                [
                    "/usr/bin/python3",
                    str(Path(__file__).resolve()),
                    "--child",
                    kind,
                    "--text-output",
                    str(folder / f"{kind}-text.json"),
                    "--state-output",
                    str(folder / f"{kind}-state.json"),
                    "--seconds",
                    str(args.seconds),
                    *(
                        ["--activate-file", str(args.activate_file)]
                        if args.activate_file
                        else []
                    ),
                ],
                env=environment,
            )
            deadline = time.monotonic() + 5
            while not (folder / f"{kind}-state.json").exists():
                if children[kind].poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Owned editor did not become ready")
                time.sleep(0.03)
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline:
            texts, states = {}, {}
            for kind, child in children.items():
                if child.poll() is not None:
                    raise RuntimeError("Owned editor exited")
                states[kind] = json.loads((folder / f"{kind}-state.json").read_text())
                texts[kind] = json.loads((folder / f"{kind}-text.json").read_text())
                if (
                    states[kind]["target_pid"] != child.pid
                    or states[kind]["target_parent_pid"] != os.getpid()
                ):
                    raise RuntimeError("Owned editor process identity mismatch")
            states["xwayland_pid"] = evidence["pid"]
            write_json(args.text_output, texts)
            write_json(args.state_output, states)
            time.sleep(0.03)
    finally:
        for child in children.values():
            if child.poll() is None:
                child.terminate()
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compositor-pid", type=int)
    parser.add_argument("--text-output", type=Path, required=True)
    parser.add_argument("--state-output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--activate-file", type=Path)
    parser.add_argument("--child", choices=("native", "xwayland"))
    args = parser.parse_args()
    if not 0 < args.seconds <= 300:
        parser.error("seconds must be within (0, 300]")
    if args.child:
        editor(args)
        return

    def terminate(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, terminate)
    try:
        with tempfile.TemporaryDirectory(prefix="inkecho-isolated-editors-") as folder:
            coordinate(args, Path(folder))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
