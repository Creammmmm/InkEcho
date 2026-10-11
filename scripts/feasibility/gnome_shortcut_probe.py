#!/usr/bin/env python3
"""Temporary GNOME binding test using standard keyboard portal consent.

Restores own keys and parent setting user/default distinction on exit. No text is
typed: only the three registered test shortcuts are synthesized. Run system Python
with PYTHONPATH=src so dbus-python and GObject introspection are available.
"""

import json
import shlex
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import dbus
import dbus.mainloop.glib
from gi.repository import Gio, GLib

from inkecho.platform.hotkeys import CUSTOM, MEDIA, OWN_PATH, GnomeShortcuts

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
parent = Gio.Settings.new(MEDIA)
own = Gio.Settings.new_with_path(CUSTOM, OWN_PATH)
original_parent = parent.get_user_value("custom-keybindings")
original_paths = parent.get_strv("custom-keybindings")
if OWN_PATH in original_paths:
    raise SystemExit("Refusing to replace an existing InkEcho binding during a probe.")
original_keys = {key: own.get_user_value(key) for key in ("name", "command", "binding")}
adapter = GnomeShortcuts()
bus = dbus.SessionBus()
portal = dbus.Interface(
    bus.get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop"),
    "org.freedesktop.portal.RemoteDesktop",
)
loop = GLib.MainLoop()
pending, results = {}, {}
session = None
folder = tempfile.TemporaryDirectory(prefix="inkecho-gnome-shortcut-")
marker = Path(folder.name) / "activated"
shortcuts = [("F13", [183]), ("F14", [184]), ("Ctrl+Alt+K", [29, 56, 37])]
current = 0


def options(**values):
    return dbus.Dictionary(values, signature="sv")


def request(method, callback, *arguments, **values):
    token = "inkecho_" + uuid.uuid4().hex
    sender = bus.get_unique_name()[1:].replace(".", "_")
    path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
    pending[path] = callback
    getattr(portal, method)(*arguments, options(handle_token=token, **values))


def response(code, result, path=None):
    callback = pending.pop(path, None)
    if code:
        results["portal_denied"] = int(code)
        results["portal_stage"] = callback.__name__ if callback else "unknown"
        loop.quit()
    elif callback:
        callback(result)


def prepare():
    if current == len(shortcuts):
        loop.quit()
        return False
    name, _ = shortcuts[current]
    marker.unlink(missing_ok=True)
    child = f"from pathlib import Path; Path({str(marker)!r}).write_text({name!r})"
    try:
        adapter.enable(name, [sys.executable, "-c", child])
    except Exception as error:
        results[name] = f"registration failed: {type(error).__name__}"
        loop.quit()
        return False
    GLib.timeout_add(1200, trigger)
    return False


def trigger():
    _, keys = shortcuts[current]
    try:
        for key in keys:
            portal.NotifyKeyboardKeycode(
                session, options(), dbus.Int32(key), dbus.UInt32(1)
            )
    finally:
        for key in reversed(keys):
            portal.NotifyKeyboardKeycode(
                session, options(), dbus.Int32(key), dbus.UInt32(0)
            )
    GLib.timeout_add(1500, check)
    return False


def check():
    global current
    name, _ = shortcuts[current]
    results[name] = marker.exists() and marker.read_text() == name
    current += 1
    GLib.idle_add(prepare)
    return False


def started(result):
    results["portal_keyboard_devices"] = int(result.get("devices", 0))
    GLib.idle_add(prepare)


def selected(_):
    request("Start", started, session, "")


def created(result):
    global session
    session = result["session_handle"]
    request(
        "SelectDevices",
        selected,
        session,
        types=dbus.UInt32(1),
        persist_mode=dbus.UInt32(0),
    )


bus.add_signal_receiver(
    response,
    signal_name="Response",
    dbus_interface="org.freedesktop.portal.Request",
    path_keyword="path",
)
settings_only = "--settings-only" in sys.argv
if not settings_only:
    request(
        "CreateSession", created, session_handle_token="inkecho_" + uuid.uuid4().hex
    )
    GLib.timeout_add_seconds(90, lambda: (loop.quit(), False)[1])
try:
    if settings_only:
        for name, _ in shortcuts:
            child = (
                f"from pathlib import Path; Path({str(marker)!r}).write_text({name!r})"
            )
            adapter.enable(name, [sys.executable, "-c", child])
            stored = adapter.settings.get(adapter.schema, "command")
            subprocess.run(shlex.split(stored), check=True, timeout=3)
            results[name] = marker.exists() and marker.read_text() == name
        results["mode"] = (
            "saved/readback and direct command launch; no shortcut activation"
        )
    else:
        loop.run()
finally:
    for path, interface in [(p, "Request") for p in pending] + (
        [(session, "Session")] if session else []
    ):
        try:
            dbus.Interface(
                bus.get_object("org.freedesktop.portal.Desktop", path),
                f"org.freedesktop.portal.{interface}",
            ).Close()
        except dbus.DBusException:
            pass
    adapter.disable()
    for key, value in original_keys.items():
        own.reset(key) if value is None else own.set_value(key, value)
    if parent.get_strv("custom-keybindings") == original_paths:
        if original_parent is None:
            parent.reset("custom-keybindings")
        else:
            parent.set_value("custom-keybindings", original_parent)
    Gio.Settings.sync()
    results["settings_restored"] = parent.get_user_value(
        "custom-keybindings"
    ) == original_parent and all(
        own.get_user_value(key) == value for key, value in original_keys.items()
    )
    results["physical_keyboard_tested"] = False
    print(json.dumps(results, indent=2))
    folder.cleanup()
raise SystemExit(
    0
    if all(results.get(name) is True for name, _ in shortcuts)
    and results["settings_restored"]
    else 1
)
