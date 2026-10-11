#!/usr/bin/env python3
"""Check global X11 grabs on an isolated Xvfb display using synthetic keys."""

import argparse
import ctypes
import json
import time
import uuid

SHORTCUTS = {"F13": ("F13", 0), "F14": ("F14", 0), "Ctrl+Alt+K": ("k", 12)}


class KeyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("root", ctypes.c_ulong),
        ("subwindow", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("x_root", ctypes.c_int),
        ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("keycode", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]


class Event(ctypes.Union):
    _fields_ = [("key", KeyEvent), ("padding", ctypes.c_long * 24)]


def matching_shortcut(keycode: int, state: int, bindings: dict) -> str | None:
    for name, (code, modifiers) in bindings.items():
        if keycode == code and state & 0xFF == modifiers:
            return name
    return None


def probe(display_name: str, map_extended_keys: bool = False) -> dict:
    x11 = ctypes.CDLL("libX11.so.6")
    xtest = ctypes.CDLL("libXtst.so.6")
    pointer, integer, word = ctypes.c_void_p, ctypes.c_int, ctypes.c_ulong
    x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
    x11.XOpenDisplay.restype = pointer
    x11.XDefaultRootWindow.argtypes = [pointer]
    x11.XDefaultRootWindow.restype = word
    x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
    x11.XStringToKeysym.restype = word
    x11.XKeysymToKeycode.argtypes = [pointer, word]
    x11.XKeysymToKeycode.restype = ctypes.c_ubyte
    x11.XGrabKey.argtypes = [
        pointer,
        integer,
        ctypes.c_uint,
        word,
        integer,
        integer,
        integer,
    ]
    x11.XUngrabKey.argtypes = [pointer, integer, ctypes.c_uint, word]
    x11.XPending.argtypes = [pointer]
    x11.XNextEvent.argtypes = [pointer, ctypes.POINTER(Event)]
    x11.XSync.argtypes = [pointer, integer]
    x11.XCloseDisplay.argtypes = [pointer]
    x11.XDisplayKeycodes.argtypes = [
        pointer,
        ctypes.POINTER(integer),
        ctypes.POINTER(integer),
    ]
    x11.XGetKeyboardMapping.argtypes = [
        pointer,
        ctypes.c_ubyte,
        integer,
        ctypes.POINTER(integer),
    ]
    x11.XGetKeyboardMapping.restype = ctypes.POINTER(word)
    x11.XChangeKeyboardMapping.argtypes = [
        pointer,
        integer,
        integer,
        ctypes.POINTER(word),
        integer,
    ]
    x11.XFree.argtypes = [pointer]
    xtest.XTestFakeKeyEvent.argtypes = [pointer, ctypes.c_uint, integer, word]
    errors = []
    error_callback = ctypes.CFUNCTYPE(integer, pointer, pointer)
    error_handler = error_callback(lambda *_: errors.append("X11 grab error") or 0)
    x11.XSetErrorHandler.argtypes = [error_callback]
    x11.XSetErrorHandler.restype = error_callback
    previous_handler = x11.XSetErrorHandler(error_handler)
    display = x11.XOpenDisplay(display_name.encode())
    if not display:
        x11.XSetErrorHandler(previous_handler)

        raise RuntimeError("Cannot connect to the isolated X11 display.")
    root = x11.XDefaultRootWindow(display)

    def keycode(symbol: str) -> int:
        value = x11.XKeysymToKeycode(display, x11.XStringToKeysym(symbol.encode()))
        if not value:
            raise RuntimeError(f"No keycode for {symbol}; mapping was not modified.")
        return value

    bindings, received, original_maps = {}, [], []
    try:
        if map_extended_keys:
            low, high, width = integer(), integer(), integer()
            x11.XDisplayKeycodes(display, ctypes.byref(low), ctypes.byref(high))
            count = high.value - low.value + 1
            mapping = x11.XGetKeyboardMapping(
                display, low.value, count, ctypes.byref(width)
            )
            if not mapping:
                raise RuntimeError("Cannot read keyboard map.")
            try:
                empty = [
                    low.value + index
                    for index in range(count)
                    if not any(mapping[index * width.value : (index + 1) * width.value])
                ]
            finally:
                x11.XFree(mapping)
            for symbol in ("F13", "F14"):
                keysym = x11.XStringToKeysym(symbol.encode())
                if x11.XKeysymToKeycode(display, keysym):
                    continue
                if not empty:
                    raise RuntimeError("No unused keycode for the diagnostic mapping.")
                code = empty.pop()
                original_maps.append((code, width.value))
                values = (word * width.value)(keysym)
                x11.XChangeKeyboardMapping(display, code, width.value, values, 1)
                x11.XSync(display, 0)
        bindings = {
            name: (keycode(symbol), modifiers)
            for name, (symbol, modifiers) in SHORTCUTS.items()
        }
        for code, modifiers in bindings.values():
            x11.XGrabKey(display, code, modifiers, root, 0, 1, 1)
        x11.XSync(display, 0)
        if errors:
            raise RuntimeError("Global shortcut conflict or permission failure.")
        for code, modifiers in bindings.values():
            keys = [keycode("Control_L"), keycode("Alt_L")] if modifiers else []
            keys.append(code)
            for key in keys:
                xtest.XTestFakeKeyEvent(display, key, 1, 0)
            for key in reversed(keys):
                xtest.XTestFakeKeyEvent(display, key, 0, 0)
            x11.XSync(display, 0)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and len(received) < len(bindings):
            while x11.XPending(display):
                event = Event()
                x11.XNextEvent(display, ctypes.byref(event))
                if event.key.type == 2:
                    name = matching_shortcut(
                        event.key.keycode, event.key.state, bindings
                    )
                    if name:
                        received.append(name)
            time.sleep(0.01)
        return {
            "display": display_name,
            "trigger": "synthetic XTest, not physical keyboard",
            "temporary_extended_key_mapping": bool(original_maps),
            "received": received,
            "passed": received == list(SHORTCUTS),
        }
    finally:
        for code, modifiers in bindings.values():
            x11.XUngrabKey(display, code, modifiers, root)
        for code, width in original_maps:
            values = (word * width)()
            x11.XChangeKeyboardMapping(display, code, width, values, 1)
        x11.XSync(display, 0)
        x11.XCloseDisplay(display)
        x11.XSetErrorHandler(previous_handler)


def portal_probe(seconds: int, app_id: str) -> dict:
    """Request only this diagnostic's three shortcuts through normal portal UI."""
    import dbus
    import dbus.mainloop.glib
    from gi.repository import GLib

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    destination = "org.freedesktop.portal.Desktop"
    interface = "org.freedesktop.portal.GlobalShortcuts"
    dbus.Interface(
        bus.get_object(destination, "/org/freedesktop/portal/desktop"),
        "org.freedesktop.host.portal.Registry",
    ).Register(app_id, dbus.Dictionary({}, signature="sv"))
    portal = dbus.Interface(
        bus.get_object(destination, "/org/freedesktop/portal/desktop"), interface
    )
    loop = GLib.MainLoop()
    session, pending = None, {}
    result = {
        "environment": "native portal",
        "session_created": False,
        "bound": [],
        "activated": [],
        "timed_out": False,
    }

    def request(method, callback, *arguments, **options):
        token = "inkecho_" + uuid.uuid4().hex
        sender = bus.get_unique_name()[1:].replace(".", "_")
        path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
        pending[path] = callback
        try:
            getattr(portal, method)(
                *arguments,
                dbus.Dictionary(dict(handle_token=token, **options), signature="sv"),
            )
        except dbus.DBusException:
            pending.pop(path, None)
            raise

    def response(code, values, path=None):
        callback = pending.pop(path, None)
        if callback is None:
            return
        if code:
            result["request_error"] = int(code)
            loop.quit()
        else:
            callback(values)

    def bound(values):
        result["bound"] = [
            {"id": str(name), "trigger": str(options.get("trigger_description", ""))}
            for name, options in values.get("shortcuts", [])
        ]
        print(json.dumps({"registration": result["bound"]}), flush=True)

    def created(values):
        nonlocal session
        session = values["session_handle"]
        result["session_created"] = True
        shortcuts = dbus.Array(
            [
                (
                    name,
                    dbus.Dictionary(
                        {
                            "description": f"InkEcho diagnostic {name}",
                            "preferred_trigger": trigger,
                        },
                        signature="sv",
                    ),
                )
                for name, trigger in [
                    ("F13", "F13"),
                    ("F14", "F14"),
                    ("Ctrl+Alt+K", "CTRL+ALT+k"),
                ]
            ],
            signature="(sa{sv})",
        )
        request("BindShortcuts", bound, session, shortcuts, "")

    def activated(handle, name, _timestamp, _options):
        if str(handle) != str(session):
            return
        result["activated"].append(str(name))
        print(json.dumps({"activated": str(name)}), flush=True)
        if set(result["activated"]) == set(SHORTCUTS):
            loop.quit()

    bus.add_signal_receiver(
        response,
        signal_name="Response",
        dbus_interface="org.freedesktop.portal.Request",
        path_keyword="path",
    )
    bus.add_signal_receiver(
        activated, signal_name="Activated", dbus_interface=interface
    )

    def timed_out():
        result["timed_out"] = True
        loop.quit()
        return False

    try:
        request(
            "CreateSession", created, session_handle_token="inkecho_" + uuid.uuid4().hex
        )
        GLib.timeout_add_seconds(seconds, timed_out)
        loop.run()
    finally:
        for path in pending:
            try:
                dbus.Interface(
                    bus.get_object(destination, path), "org.freedesktop.portal.Request"
                ).Close()
            except dbus.DBusException as error:
                result["cleanup_error"] = error.get_dbus_name()
        if session:
            dbus.Interface(
                bus.get_object(destination, session), "org.freedesktop.portal.Session"
            ).Close()
    result["passed"] = set(result["activated"]) == set(SHORTCUTS)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--isolated-display")
    mode.add_argument("--native-portal", action="store_true")
    parser.add_argument("--listen-seconds", type=int, default=90)
    parser.add_argument("--app-id", default="io.github.Creammmmm.InkEcho.Probe")
    parser.add_argument(
        "--map-extended-keys",
        action="store_true",
        help="Temporarily map unused keycodes to F13/F14, then restore them",
    )
    args = parser.parse_args()
    if not 1 <= args.listen_seconds <= 120:
        parser.error("Listen time must be between 1 and 120 seconds.")
    if args.isolated_display in {":0", ":0.0", ":1", ":1.0"}:
        parser.error("Use a dedicated Xvfb display, not a normal desktop display.")
    result = (
        portal_probe(args.listen_seconds, args.app_id)
        if args.native_portal
        else probe(args.isolated_display, args.map_extended_keys)
    )
    print(json.dumps(result))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
