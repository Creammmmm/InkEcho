"""Compare engine metadata, never surrounding text, in a private IBus."""

import os
import subprocess
import time

import gi

gi.require_version("IBus", "1.0")
from gi.repository import Gio, GLib, IBus  # noqa: E402

IBus.init()
bus = IBus.Bus.new()
assert bus.is_connected()
fake = bus.current_input_context()
assert fake
print("private engine set", bus.set_global_engine("xkb:us::eng"), flush=True)
real = bus.create_input_context("inkecho-engine-identity")
real.set_capabilities(IBus.Capabilite.FOCUS | IBus.Capabilite.PREEDIT_TEXT)
connection = bus.get_connection()


def engine_at(path):
    try:
        result = connection.call_sync(
            "org.freedesktop.IBus",
            path,
            "org.freedesktop.IBus.InputContext",
            "GetEngine",
            None,
            None,
            Gio.DBusCallFlags.NONE,
            4000,
            None,
        )
        desc = IBus.Serializable.deserialize_object(
            result.get_child_value(0).get_variant()
        )
        return ("engine", desc.get_name())
    except GLib.Error as error:
        return ("error", Gio.DBusError.get_remote_error(error), error.message)


print("fake current", engine_at(fake), flush=True)
real.focus_in()
time.sleep(0.3)
assert bus.current_input_context() == real.get_object_path()
owner_result = engine_at(real.get_object_path())
print("real current", owner_result, flush=True)
assert owner_result == ("engine", "xkb:us::eng")
foreign = subprocess.run(
    [
        "gdbus",
        "call",
        "--address",
        os.environ["IBUS_ADDRESS"],
        "--dest",
        "org.freedesktop.IBus",
        "--object-path",
        real.get_object_path(),
        "--method",
        "org.freedesktop.IBus.InputContext.GetEngine",
        "--timeout",
        "1",
    ],
    capture_output=True,
    text=True,
    timeout=4,
    check=False,
)
print(
    "foreign connection result", foreign.returncode, foreign.stderr.strip(), flush=True
)
assert foreign.returncode != 0
real.focus_out()
time.sleep(0.3)
assert bus.current_input_context() == fake
print("fake current again", engine_at(fake), flush=True)
