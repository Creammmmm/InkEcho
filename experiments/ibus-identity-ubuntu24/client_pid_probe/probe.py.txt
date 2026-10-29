"""Probe process lookup on our own private IBus connection; no text is read."""

import os

import gi

gi.require_version("IBus", "1.0")
from gi.repository import Gio, GLib, IBus  # noqa: E402

IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected()
connection = bus.get_connection()
name = connection.get_unique_name()
assert name and name.startswith(":")


def call(method, parameter):
    return connection.call_sync(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        method,
        GLib.Variant("(s)", (parameter,)),
        None,
        Gio.DBusCallFlags.NONE,
        2000,
        None,
    ).unpack()


assert call("GetNameOwner", name) == (name,)
print("own unique name lookup passed", flush=True)
try:
    result = call("GetConnectionUnixProcessID", name)
except GLib.Error as error:
    remote = Gio.DBusError.get_remote_error(error)
    print("process lookup unavailable:", remote, flush=True)
    assert remote == "org.freedesktop.DBus.Error.UnknownMethod"
else:
    print("process lookup result:", result, flush=True)
    assert result == (os.getpid(),)
