#!/usr/bin/env python3
"""Keyboard-only portal diagnostic for an explicitly selected disposable fixture.

Uses the standard permission dialog, requests no persistence or screen access,
and closes the granted session. Never use this as a production text backend:
focus validation and global key delivery are not atomic.
"""

import argparse
import json
import uuid

import dbus
import dbus.mainloop.glib
import gi

gi.require_version("Atspi", "2.0")
from gi.repository import Atspi, GLib  # noqa: E402
from wayland_probe import SAMPLE, targets  # noqa: E402

dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("kind", choices=("browser", "terminal", "editor"))
parser.add_argument(
    "--pid", required=True, type=int, help="Own test fixture process ID"
)
parser.add_argument(
    "--navigate", action="store_true", help="Cycle normal Alt+Escape to own fixture"
)
args = parser.parse_args()
bus = dbus.SessionBus()
portal = dbus.Interface(
    bus.get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop"),
    "org.freedesktop.portal.RemoteDesktop",
)
loop = GLib.MainLoop()
session = None
pending = {}
exit_code = 1


def options(**values):
    return dbus.Dictionary(values, signature="sv")


def finish(reason):
    print(json.dumps({"injected": False, "reason": reason}), flush=True)
    loop.quit()
    return False


def request(method, callback, *arguments, **values):
    token = "inkecho_" + uuid.uuid4().hex
    sender = bus.get_unique_name()[1:].replace(".", "_")
    path = f"/org/freedesktop/portal/desktop/request/{sender}/{token}"
    pending[path] = callback
    getattr(portal, method)(*arguments, options(handle_token=token, **values))


def response(code, result, path=None):
    callback = pending.pop(path, None)
    if not callback:
        return
    if code:
        print(json.dumps({"portal_result": int(code), "injected": False}), flush=True)
        loop.quit()
        return
    callback(result)


def active(node):
    node.clear_cache()
    if not node.get_state_set().contains(Atspi.StateType.FOCUSED):
        return False
    parent = node
    for _ in range(64):
        parent.clear_cache()
        if parent.get_state_set().contains(Atspi.StateType.ACTIVE):
            return True
        parent = parent.get_parent()
        if parent is None:
            break
    return False


def started(result):
    print(
        json.dumps({"portal_started": True, "devices": int(result.get("devices", 0))}),
        flush=True,
    )
    GLib.timeout_add(750, navigate if args.navigate else inject)


def navigate():
    attempts = 0

    def next_window():
        nonlocal attempts
        candidates = [
            n
            for n in targets(args.kind)
            if n.get_process_id() == args.pid and active(n)
        ]
        if candidates or attempts == 20:
            portal.NotifyKeyboardKeysym(
                session, options(), dbus.Int32(0xFFE9), dbus.UInt32(0)
            )
            GLib.timeout_add(500, inject)
            return False
        attempts += 1
        portal.NotifyKeyboardKeysym(
            session, options(), dbus.Int32(0xFFE9), dbus.UInt32(1)
        )
        for _ in range(attempts):
            portal.NotifyKeyboardKeysym(
                session, options(), dbus.Int32(0xFF1B), dbus.UInt32(1)
            )
            portal.NotifyKeyboardKeysym(
                session, options(), dbus.Int32(0xFF1B), dbus.UInt32(0)
            )
        portal.NotifyKeyboardKeysym(
            session, options(), dbus.Int32(0xFFE9), dbus.UInt32(0)
        )
        return True

    GLib.timeout_add(300, next_window)
    return False


def inject():
    candidates = [
        n for n in targets(args.kind) if n.get_process_id() == args.pid and active(n)
    ]
    if len(candidates) != 1:
        return finish("Own fixture not uniquely active and focused")
    node = candidates[0]
    sent = 0

    def step():
        nonlocal sent
        global exit_code
        try:
            if not active(node):
                return finish("Fixture lost focus; remaining text not sent")
            if sent == len(SAMPLE):
                received = Atspi.Text.get_text(node, 0, -1)
                exit_code = 0 if received == SAMPLE else 1
                print(
                    json.dumps(
                        {
                            "sent_characters": sent,
                            "exact_match": received == SAMPLE,
                            "received_fixture_text": received,
                            "production_safe": False,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
                loop.quit()
                return False
            character = SAMPLE[sent]
            keysym = 0xFF0D if character == "\n" else ord(character)
            if keysym > 255 and character != "\n":
                keysym |= 0x01000000
            try:
                portal.NotifyKeyboardKeysym(
                    session, options(), dbus.Int32(keysym), dbus.UInt32(1)
                )
            finally:
                portal.NotifyKeyboardKeysym(
                    session, options(), dbus.Int32(keysym), dbus.UInt32(0)
                )
            sent += 1
            return True
        except Exception as error:
            return finish(f"Fixture test failed: {type(error).__name__}")

    GLib.timeout_add(100, step)
    return False


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
request("CreateSession", created, session_handle_token="inkecho_" + uuid.uuid4().hex)
GLib.timeout_add_seconds(180, lambda: finish("Portal request timed out"))
try:
    loop.run()
finally:
    for path in pending:
        try:
            dbus.Interface(
                bus.get_object("org.freedesktop.portal.Desktop", path),
                "org.freedesktop.portal.Request",
            ).Close()
        except dbus.DBusException:
            pass
    if session:
        try:
            portal.NotifyKeyboardKeysym(
                session, options(), dbus.Int32(0xFFE9), dbus.UInt32(0)
            )
            dbus.Interface(
                bus.get_object("org.freedesktop.portal.Desktop", session),
                "org.freedesktop.portal.Session",
            ).Close()
        except dbus.DBusException:
            pass  # A closed request can already have closed its session.
raise SystemExit(exit_code)
