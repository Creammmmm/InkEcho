"""Compare private bus identity metadata methods on this process only."""

import os
from pathlib import Path

import gi

gi.require_version("IBus", "1.0")
from gi.repository import Gio, GLib, IBus  # noqa: E402

assert os.environ["INKECHO_ISOLATED_BUS"] == "1"
assert os.environ["IBUS_ADDRESS"].startswith(f"unix:path={Path.home()}/")
IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected()
connection = bus.get_connection()
name = connection.get_unique_name()
assert name and name.startswith(":")


def call(method):
    return connection.call_sync(
        "org.freedesktop.DBus",
        "/org/freedesktop/DBus",
        "org.freedesktop.DBus",
        method,
        GLib.Variant("(s)", (name,)),
        None,
        Gio.DBusCallFlags.NONE,
        2000,
        None,
    ).unpack()


assert call("GetNameOwner") == (name,)
print("unique-name positive control: passed", flush=True)
for method in (
    "GetConnectionUnixProcessID",
    "GetConnectionUnixUser",
    "GetConnectionCredentials",
    "GetConnectionSELinuxSecurityContext",
):
    try:
        result = call(method)
    except GLib.Error as error:
        print(method, Gio.DBusError.get_remote_error(error), flush=True)
    else:
        print(method, result, flush=True)
